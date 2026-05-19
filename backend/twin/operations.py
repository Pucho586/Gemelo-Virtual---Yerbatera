"""Cálculo de OEE + mantenimiento predictivo + costos energéticos.

OEE (Overall Equipment Effectiveness):
   D = tiempo operativo / tiempo planificado
   R = producción real / producción nominal
   Q = kg buenos / kg totales
   OEE = D * R * Q

Mantenimiento predictivo: horas de marcha por componente, umbrales y predicción.
Energía: kWh + m³ gas estimado + costo $.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -------------- Defaults --------------
DEFAULT_PRICES = {
    "kwh_ars": 120.0,
    "kg_chips_ars": 95.0,           # Chips de madera (combustible para zapecado)
    "kg_yerba_venta_ars": 3500.0,
}

# Configuración de turnos (cantidad y duración) para calcular tiempo planificado
DEFAULT_SHIFTS = {
    "shifts_per_day": 3,
    "hours_per_shift": 8.0,
}

# Potencia nominal estimada de cada componente (kW)
COMPONENT_POWER_KW = {
    "tambor_zapecado": 18.0,
    "secador": 35.0,
    "molino_canchado": 22.0,
    "ventilador_cam0": 1.5,
    "ventilador_cam1": 1.5,
    "ventilador_cam2": 1.5,
    "ventilador_cam3": 1.5,
}

# Umbrales de mantenimiento (horas de marcha)
DEFAULT_MAINT_THRESHOLDS = {
    "tambor_zapecado": {"lubricacion": 500, "rulemanes": 2000, "overhaul": 4000},
    "secador":         {"lubricacion": 500, "rulemanes": 2000, "overhaul": 4000},
    "molino_canchado": {"lubricacion": 400, "rulemanes": 1500, "overhaul": 3000},
    "ventilador_cam0": {"lubricacion": 800, "rulemanes": 4000, "overhaul": 8000},
    "ventilador_cam1": {"lubricacion": 800, "rulemanes": 4000, "overhaul": 8000},
    "ventilador_cam2": {"lubricacion": 800, "rulemanes": 4000, "overhaul": 8000},
    "ventilador_cam3": {"lubricacion": 800, "rulemanes": 4000, "overhaul": 8000},
}


class OperationsService:
    """Mantiene contadores de horas, energía y permite calcular OEE/costos."""

    def __init__(self, db):
        self.db = db
        # Estado en memoria (se persiste cada N segundos)
        self.runtime_hours: Dict[str, float] = {k: 0.0 for k in COMPONENT_POWER_KW}
        self.kwh_accum: Dict[str, float] = {k: 0.0 for k in COMPONENT_POWER_KW}
        self.chips_kg_accum: float = 0.0  # Chips de madera consumidos (kg)
        self.kg_produced: float = 0.0
        self.kg_input: float = 0.0
        self.last_tick: float = 0.0
        self.prices: Dict[str, float] = dict(DEFAULT_PRICES)
        self.thresholds: Dict[str, Dict[str, float]] = {k: dict(v) for k, v in DEFAULT_MAINT_THRESHOLDS.items()}
        self.maint_acks: Dict[str, Dict[str, str]] = {}
        # Configuración de turnos
        self.shifts_per_day: int = DEFAULT_SHIFTS["shifts_per_day"]
        self.hours_per_shift: float = DEFAULT_SHIFTS["hours_per_shift"]

    async def ensure_indexes(self):
        await self.db.ops_state.create_index("id", unique=True)
        await self.db.maint_log.create_index([("ts", -1)])

    @property
    def planned_hours_per_day(self) -> float:
        return float(self.shifts_per_day) * float(self.hours_per_shift)

    async def load(self):
        doc = await self.db.ops_state.find_one({"id": "singleton"}, {"_id": 0})
        if doc:
            self.runtime_hours.update(doc.get("runtime_hours", {}))
            self.kwh_accum.update(doc.get("kwh_accum", {}))
            # Compat retro: gas_m3_accum → chips_kg_accum
            self.chips_kg_accum = float(doc.get("chips_kg_accum", doc.get("gas_m3_accum", 0.0)))
            self.kg_produced = float(doc.get("kg_produced", 0.0))
            self.kg_input = float(doc.get("kg_input", 0.0))
            # Migrar precios viejos
            old_prices = doc.get("prices", {}) or {}
            self.prices = {**DEFAULT_PRICES, **{k: v for k, v in old_prices.items() if k in DEFAULT_PRICES}}
            if "m3_gas_ars" in old_prices and "kg_chips_ars" not in old_prices:
                # Si venía precio gas, lo mapeamos como chips (orden de magnitud distinto, queda default)
                pass
            self.thresholds = doc.get("thresholds", self.thresholds)
            self.maint_acks = doc.get("maint_acks", {})
            self.shifts_per_day = int(doc.get("shifts_per_day", DEFAULT_SHIFTS["shifts_per_day"]))
            self.hours_per_shift = float(doc.get("hours_per_shift", DEFAULT_SHIFTS["hours_per_shift"]))

    async def save(self):
        await self.db.ops_state.replace_one(
            {"id": "singleton"},
            {
                "id": "singleton",
                "runtime_hours": self.runtime_hours,
                "kwh_accum": self.kwh_accum,
                "chips_kg_accum": self.chips_kg_accum,
                "kg_produced": self.kg_produced,
                "kg_input": self.kg_input,
                "prices": self.prices,
                "thresholds": self.thresholds,
                "maint_acks": self.maint_acks,
                "shifts_per_day": self.shifts_per_day,
                "hours_per_shift": self.hours_per_shift,
                "updated_at": now_iso(),
            },
            upsert=True,
        )

    # -------- Tick: acumula horas + kWh + chips de madera según estado del simulador --------
    def tick(self, state: Dict[str, Any], dt_sim_seconds: float):
        """Acumula contadores. dt_sim_seconds = segundos simulados transcurridos."""
        dt_h = dt_sim_seconds / 3600.0
        if dt_h <= 0:
            return
        z = state.get("zapecado", {})
        s = state.get("secado", {})
        c = state.get("canchado", {})
        if z.get("estado_alimentacion"):
            self.runtime_hours["tambor_zapecado"] += dt_h
            self.kwh_accum["tambor_zapecado"] += COMPONENT_POWER_KW["tambor_zapecado"] * dt_h
            # Chips de madera (combustible): proporcional al delta temp respecto ambiente.
            # Estimación: 1.8 kg/h por cada 100°C arriba del ambiente (poder calorífico ~17 MJ/kg).
            amb = state.get("ambient", {}).get("temp", 25)
            t = z.get("temperatura", 0)
            chips_rate = max(0.0, (t - amb) / 100.0 * 1.8)
            self.chips_kg_accum += chips_rate * dt_h
        if s.get("estado"):
            self.runtime_hours["secador"] += dt_h
            self.kwh_accum["secador"] += COMPONENT_POWER_KW["secador"] * dt_h
        if c.get("estado"):
            self.runtime_hours["molino_canchado"] += dt_h
            self.kwh_accum["molino_canchado"] += COMPONENT_POWER_KW["molino_canchado"] * dt_h
        for cam in state.get("camaras", []):
            key = f"ventilador_cam{cam.get('id')}"
            if cam.get("ventilador") and key in self.runtime_hours:
                self.runtime_hours[key] += dt_h
                self.kwh_accum[key] += COMPONENT_POWER_KW[key] * dt_h

    # -------- Producción --------
    def record_batch_close(self, kg_input: float, kg_output: float):
        self.kg_input += float(kg_input or 0)
        self.kg_produced += float(kg_output or 0)

    # -------- KPIs --------
    def total_kwh(self) -> float:
        return sum(self.kwh_accum.values())

    def energy_cost_ars(self) -> float:
        return self.total_kwh() * self.prices["kwh_ars"] + self.gas_m3_accum * self.prices["m3_gas_ars"]

    def revenue_ars(self) -> float:
        return self.kg_produced * self.prices["kg_yerba_venta_ars"]

    def cost_per_kg_ars(self) -> float:
        if self.kg_produced <= 0:
            return 0.0
        return self.energy_cost_ars() / self.kg_produced

    def margin_per_kg_ars(self) -> float:
        return self.prices["kg_yerba_venta_ars"] - self.cost_per_kg_ars()

    # -------- OEE --------
    def oee(self, window_hours: float = 24.0, throughput_kgh: float = 800.0) -> Dict[str, float]:
        """OEE para una ventana móvil reciente."""
        # Disponibilidad: usamos secador como referencia (es el cuello de botella habitual)
        op_h = min(self.runtime_hours["secador"], window_hours)
        availability = op_h / window_hours if window_hours > 0 else 0.0
        # Rendimiento: producción real vs nominal en esa ventana
        nominal = throughput_kgh * op_h
        # kg_produced acumulado, pero para ventana móvil lo escalamos por tiempo proporcional
        # Aproximación simple: tomar el último 'window' del producido por la fracción de horas operativas
        produced_window = self.kg_produced * (op_h / max(self.runtime_hours["secador"], 0.01))
        performance = produced_window / nominal if nominal > 0 else 0.0
        # Calidad: kg buenos / kg totales (input - merma)
        if self.kg_input > 0:
            quality = self.kg_produced / self.kg_input
        else:
            quality = 1.0
        oee = max(0.0, min(1.0, availability)) * max(0.0, min(1.0, performance)) * max(0.0, min(1.0, quality))
        return {
            "availability": round(min(1.0, availability), 4),
            "performance": round(min(1.0, performance), 4),
            "quality": round(min(1.0, quality), 4),
            "oee": round(oee, 4),
            "operativas_h": round(op_h, 2),
            "produccion_kg": round(self.kg_produced, 1),
        }

    # -------- Mantenimiento --------
    def maintenance_status(self) -> Dict[str, Any]:
        out: List[Dict[str, Any]] = []
        for comp, hours in self.runtime_hours.items():
            comp_thresholds = self.thresholds.get(comp, {})
            comp_acks = self.maint_acks.get(comp, {})
            for action, thr in comp_thresholds.items():
                last_ack = comp_acks.get(action)
                hours_since = hours
                if last_ack:
                    # No tracking exact hours at ack time → asumimos 0 desde ack (simplificación útil)
                    # Mejora futura: guardar hours_at_ack
                    last_hours = self.maint_acks.get(comp, {}).get(f"{action}_hours", 0)
                    hours_since = max(0, hours - float(last_hours or 0))
                pct = hours_since / thr if thr > 0 else 0
                horas_restantes = max(0.0, thr - hours_since)
                status = "ok"
                if pct >= 1.0: status = "due"
                elif pct >= 0.8: status = "warning"
                out.append({
                    "componente": comp,
                    "accion": action,
                    "horas_marcha": round(hours_since, 1),
                    "umbral_h": thr,
                    "horas_restantes": round(horas_restantes, 1),
                    "pct": round(pct * 100, 1),
                    "status": status,
                    "last_ack": last_ack,
                    "potencia_kw": COMPONENT_POWER_KW.get(comp),
                })
        return {"items": out, "total_runtime": dict(self.runtime_hours)}

    def ack_maintenance(self, component: str, action: str, username: str):
        self.maint_acks.setdefault(component, {})
        ts = now_iso()
        self.maint_acks[component][action] = ts
        self.maint_acks[component][f"{action}_hours"] = self.runtime_hours.get(component, 0.0)
        # log
        return {
            "component": component, "action": action, "ack_at": ts,
            "ack_by": username, "hours_at_ack": self.runtime_hours.get(component, 0.0),
        }

    # -------- Reset (para tests / nueva temporada) --------
    def reset(self, what: str = "all"):
        if what in ("all", "runtime"):
            for k in self.runtime_hours: self.runtime_hours[k] = 0.0
        if what in ("all", "energy"):
            for k in self.kwh_accum: self.kwh_accum[k] = 0.0
            self.chips_kg_accum = 0.0
        if what in ("all", "production"):
            self.kg_produced = 0.0
            self.kg_input = 0.0

    def update_prices(self, prices: Dict[str, float]):
        for k in ("kwh_ars", "kg_chips_ars", "kg_yerba_venta_ars"):
            if k in prices and prices[k] is not None:
                self.prices[k] = float(prices[k])

    def update_shifts(self, shifts_per_day: Optional[int] = None, hours_per_shift: Optional[float] = None):
        if shifts_per_day is not None:
            self.shifts_per_day = max(1, int(shifts_per_day))
        if hours_per_shift is not None:
            self.hours_per_shift = max(0.5, min(24.0, float(hours_per_shift)))

    def update_thresholds(self, thresholds: Dict[str, Dict[str, float]]):
        """Actualiza umbrales de mantenimiento. Estructura:
           {"tambor_zapecado": {"lubricacion": 500, "rulemanes": 2000, ...}, ...}"""
        for comp, actions in (thresholds or {}).items():
            if comp not in self.thresholds:
                self.thresholds[comp] = {}
            for action, hours in actions.items():
                if hours is not None:
                    self.thresholds[comp][action] = float(hours)
