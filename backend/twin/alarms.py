"""Sistema de Alarmas ISA-18.2.

Estados:
- 'unacked_active': condición activa, no reconocida
- 'acked_active': condición activa, reconocida
- 'unacked_rtn': retornada a normal sin haber sido reconocida (pendiente ACK)
- 'normal' (no se persiste como evento corriente, solo en historial)

Prioridades: 'urgent' (1), 'high' (2), 'medium' (3), 'low' (4)
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

PRIORITY_LEVELS = {"urgent": 1, "high": 2, "medium": 3, "low": 4}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Reglas predefinidas (configurables por admin)
DEFAULT_RULES: List[Dict[str, Any]] = [
    {"id": "zap_temp_critical", "name": "Zapecado sobre 580°C", "tag": "zapecado.temperatura",
     "op": ">", "threshold": 580, "priority": "urgent",
     "description": "Temperatura crítica de zapecado. Riesgo de quema de yerba."},
    {"id": "zap_temp_high", "name": "Zapecado sobre 540°C", "tag": "zapecado.temperatura",
     "op": ">", "threshold": 540, "priority": "high",
     "description": "Temperatura alta. Revisar velocidad de chips y tambor."},
    {"id": "sec_hum_high", "name": "Humedad de secado >35%", "tag": "secado.humedad",
     "op": ">", "threshold": 35, "priority": "medium",
     "description": "Secado ineficiente. Aumentar velocidad de aire."},
    {"id": "sec_hum_low", "name": "Yerba sobre-secada <6%", "tag": "secado.humedad",
     "op": "<", "threshold": 6, "priority": "high",
     "description": "Sobre-secado. Bajar temperatura o tiempo."},
    {"id": "cam_co2_critical", "name": "Cámara con CO₂ >5500 ppm", "tag_any_cam": "co2",
     "op": ">", "threshold": 5500, "priority": "urgent",
     "description": "CO₂ crítico. Encender ventilador inmediatamente."},
    {"id": "cam_co2_high", "name": "Cámara con CO₂ >4200 ppm", "tag_any_cam": "co2",
     "op": ">", "threshold": 4200, "priority": "medium",
     "description": "CO₂ elevado. Verificar ventilación."},
    {"id": "can_part_small", "name": "Partícula muy fina <1mm", "tag": "canchado.tamano_particula",
     "op": "<", "threshold": 1.0, "priority": "low",
     "description": "Granulometría fuera de spec. Bajar rpm del molino."},
]


def _eval_op(value: float, op: str, thr: float) -> bool:
    if op == ">":  return value > thr
    if op == "<":  return value < thr
    if op == ">=": return value >= thr
    if op == "<=": return value <= thr
    if op == "==": return abs(value - thr) < 0.001
    return False


class AlarmEngine:
    """Evalúa reglas contra el estado del simulador y mantiene alarmas activas."""

    def __init__(self, db):
        self.db = db
        self.rules: List[Dict[str, Any]] = list(DEFAULT_RULES)
        # En memoria: rule_id → alarma activa actualmente
        self.active: Dict[str, Dict[str, Any]] = {}

    async def ensure_indexes(self):
        await self.db.alarms.create_index([("ts", -1)])
        await self.db.alarms.create_index("status")
        await self.db.alarms.create_index("rule_id")
        await self.db.alarm_rules.create_index("id", unique=True)

    async def load_rules(self):
        custom = await self.db.alarm_rules.find({}, {"_id": 0}).to_list(length=200)
        # Reemplaza defaults solo si hay custom del mismo id
        by_id = {r["id"]: r for r in DEFAULT_RULES}
        for r in custom:
            by_id[r["id"]] = r
        self.rules = list(by_id.values())

    # ---------- Eval ----------
    def _extract_value(self, state: Dict[str, Any], rule: Dict[str, Any]):
        """Devuelve (value, label) o (None, None)."""
        if "tag" in rule:
            try:
                section, field = rule["tag"].split(".")
                return float(state[section][field]), rule["tag"]
            except Exception:
                return None, None
        if "tag_any_cam" in rule:
            # devuelve la peor cámara (mayor valor para >, menor para <)
            field = rule["tag_any_cam"]
            worst_val, worst_label = None, None
            for cam in state.get("camaras", []):
                v = cam.get(field)
                if v is None:
                    continue
                if worst_val is None or (rule["op"] in (">", ">=") and v > worst_val) or (rule["op"] in ("<", "<=") and v < worst_val):
                    worst_val = float(v)
                    worst_label = f"cam{cam.get('id')}.{field}"
            return worst_val, worst_label
        return None, None

    async def evaluate(self, state: Dict[str, Any]):
        """Corre todas las reglas. Crea/cierra alarmas. Devuelve la lista activa."""
        for rule in self.rules:
            if rule.get("enabled") is False:
                continue
            value, label = self._extract_value(state, rule)
            if value is None:
                continue
            triggered = _eval_op(value, rule["op"], rule["threshold"])
            active = self.active.get(rule["id"])

            if triggered:
                if not active:
                    # nueva alarma
                    alarm = {
                        "id": str(uuid.uuid4()),
                        "rule_id": rule["id"],
                        "name": rule["name"],
                        "tag": label,
                        "priority": rule["priority"],
                        "value_at_trigger": round(value, 3),
                        "threshold": rule["threshold"],
                        "op": rule["op"],
                        "description": rule.get("description", ""),
                        "status": "unacked_active",
                        "ts": now_iso(),
                        "acked_at": None,
                        "acked_by": None,
                        "cleared_at": None,
                    }
                    await self.db.alarms.insert_one(dict(alarm))
                    alarm.pop("_id", None)
                    self.active[rule["id"]] = alarm
                else:
                    # Actualizar último value para info
                    active["last_value"] = round(value, 3)
            else:
                # condición ya no se cumple
                if active:
                    if active["status"] == "unacked_active":
                        # No fue reconocida; queda pendiente RTN-unacked
                        await self.db.alarms.update_one(
                            {"id": active["id"]},
                            {"$set": {"status": "unacked_rtn", "cleared_at": now_iso(),
                                      "last_value": round(value, 3)}}
                        )
                        active["status"] = "unacked_rtn"
                        active["cleared_at"] = now_iso()
                        # se mantiene en active hasta ACK
                    elif active["status"] == "acked_active":
                        # ya fue reconocida y ahora retornó a normal → cerrar
                        await self.db.alarms.update_one(
                            {"id": active["id"]},
                            {"$set": {"status": "cleared", "cleared_at": now_iso(),
                                      "last_value": round(value, 3)}}
                        )
                        self.active.pop(rule["id"], None)
        return list(self.active.values())

    async def ack(self, alarm_id: str, username: str) -> Optional[Dict[str, Any]]:
        alarm = await self.db.alarms.find_one({"id": alarm_id}, {"_id": 0})
        if not alarm:
            return None
        ts = now_iso()
        new_status = "acked_active" if alarm["status"] == "unacked_active" else "cleared"
        await self.db.alarms.update_one(
            {"id": alarm_id},
            {"$set": {"status": new_status, "acked_at": ts, "acked_by": username}}
        )
        if new_status == "cleared":
            # estaba en unacked_rtn → ahora se va de la lista activa
            for k, v in list(self.active.items()):
                if v["id"] == alarm_id:
                    self.active.pop(k, None)
        else:
            # actualizar in-memory
            for v in self.active.values():
                if v["id"] == alarm_id:
                    v["status"] = new_status
                    v["acked_at"] = ts
                    v["acked_by"] = username
        return await self.db.alarms.find_one({"id": alarm_id}, {"_id": 0})

    async def history(self, limit: int = 200, priority: Optional[str] = None,
                      status: Optional[str] = None) -> List[Dict[str, Any]]:
        q: Dict[str, Any] = {}
        if priority: q["priority"] = priority
        if status: q["status"] = status
        cursor = self.db.alarms.find(q, {"_id": 0}).sort("ts", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def upsert_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        if not rule.get("id"):
            rule["id"] = f"r-{uuid.uuid4().hex[:8]}"
        await self.db.alarm_rules.replace_one({"id": rule["id"]}, rule, upsert=True)
        await self.load_rules()
        return rule

    async def delete_rule(self, rule_id: str):
        await self.db.alarm_rules.delete_one({"id": rule_id})
        await self.load_rules()
