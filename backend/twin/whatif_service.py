"""What-if service: corre escenarios paralelos al simulador baseline.

Cada escenario es una instancia liviana de YerbaProcessSimulator con un override
de parámetros (setpoints, modificadores, etc). Avanza en su propio thread.

Expone sus KPIs en:
  - Estado JSON (vía API)
  - Modbus TCP: unit IDs 20, 21, 22 (escenarios 1, 2, 3) - registros holding
  - OPC UA: /Plant/WhatIf/Scenario{N}/{KPI}
  - MQTT: yerba/whatif/{scenario_id}/{kpi}
"""
from __future__ import annotations

import copy
import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from .yerba_simulator import YerbaProcessSimulator

logger = logging.getLogger(__name__)

MAX_SCENARIOS = 3


class WhatIfScenario:
    """Una variante del simulador corriendo en paralelo."""

    def __init__(self, scenario_id: str, name: str, overrides: Dict[str, Any], base_config: Dict[str, Any]):
        self.id = scenario_id
        self.name = name
        self.overrides = overrides or {}
        # Clonar config base y aplicar overrides
        cfg = copy.deepcopy(base_config)
        self._apply_overrides(cfg, overrides)
        self.simulator = YerbaProcessSimulator(cfg)
        self.created_at = time.time()
        self.kpis: Dict[str, float] = {}
        self.lock = threading.Lock()
        # Contadores para KPIs simples
        self.kwh_acum: float = 0.0
        self.chips_kg_acum: float = 0.0
        self.kg_produced: float = 0.0
        self.runtime_h: float = 0.0
        self._last_tick = time.time()

    def _apply_overrides(self, cfg: Dict[str, Any], overrides: Dict[str, Any]):
        """Aplica overrides genéricos. Ejemplos:
           {"secado.temperatura_setpoint": 105, "throughput_kgh": 600,
            "zapecado.velocidad_chip": 25}"""
        for key, val in overrides.items():
            if "." in key:
                section, field = key.split(".", 1)
                cfg.setdefault(section, {})[field] = val
            else:
                cfg[key] = val

    def step(self, ambient_temp: float, ambient_humidity: float):
        """Avanza un tick del escenario. Llamado desde el bucle del WhatIfService."""
        # Sincronizar clima con el baseline
        self.simulator.set_weather(ambient_temp, ambient_humidity, {})
        self.simulator.update()
        # Acumular KPIs
        now = time.time()
        dt_real = now - self._last_tick
        self._last_tick = now
        dt_sim = dt_real * self.simulator.aceleracion
        dt_h = dt_sim / 3600.0
        # kWh estimado simple: si zapecado activo + secado activo
        kw_total = 0.0
        if self.simulator.zapecado.estado_alimentacion:
            kw_total += 18.0  # tambor zapecado
            # chips
            amb = self.simulator.ambient_temp
            t = self.simulator.zapecado.temperatura
            chips_rate = max(0.0, (t - amb) / 100.0 * 1.8)
            with self.lock:
                self.chips_kg_acum += chips_rate * dt_h
        if self.simulator.secado.estado:
            kw_total += 35.0
            with self.lock:
                self.runtime_h += dt_h
        if self.simulator.canchado.estado:
            kw_total += 22.0
        for cam in self.simulator.camaras:
            if cam.ventilador:
                kw_total += 1.5
        with self.lock:
            self.kwh_acum += kw_total * dt_h
            # Producción estimada: throughput * runtime con calidad por humedad final
            quality = 1.0 - max(0.0, (self.simulator.secado.humedad - 7.0) / 10.0)
            self.kg_produced += self.simulator.throughput_kgh * dt_h * 0.96 * max(0.5, min(1.0, quality))

    def compute_kpis(self, prices: Dict[str, float], window_h: float = 24.0) -> Dict[str, Any]:
        """Calcula KPIs comparables vs baseline."""
        with self.lock:
            s = self.simulator.get_state()
            availability = min(1.0, self.runtime_h / max(window_h, 0.01))
            nominal = self.simulator.throughput_kgh * self.runtime_h
            performance = (self.kg_produced / nominal) if nominal > 0 else 0.0
            quality = 1.0 - max(0.0, (s["secado"]["humedad"] - 7.0) / 10.0)
            quality = max(0.0, min(1.0, quality))
            oee = max(0.0, min(1.0, availability)) * max(0.0, min(1.0, performance)) * quality
            energy_cost = self.kwh_acum * prices.get("kwh_ars", 120.0) + self.chips_kg_acum * prices.get("kg_chips_ars", 95.0)
            cost_per_kg = energy_cost / self.kg_produced if self.kg_produced > 0 else 0.0
            self.kpis = {
                "OEE": round(oee * 100, 2),               # %
                "CostoPorKg": round(cost_per_kg, 2),
                "kWhAcum": round(self.kwh_acum, 2),
                "ChipsKgAcum": round(self.chips_kg_acum, 2),
                "TempZapecado": round(s["zapecado"]["temperatura"], 2),
                "TempSecado": round(s["secado"]["temperatura"], 2),
                "HumFinal": round(s["secado"]["humedad"], 2),
                "ProduccionKg": round(self.kg_produced, 1),
            }
            return self.kpis

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "overrides": self.overrides,
            "created_at": self.created_at,
            "kpis": self.kpis,
            "state": self.simulator.get_state(),
        }


class WhatIfService:
    """Orquesta hasta MAX_SCENARIOS escenarios paralelos."""

    def __init__(self, baseline_sim, runtime):
        self.baseline = baseline_sim
        self.runtime = runtime
        self.scenarios: Dict[str, WhatIfScenario] = {}
        self.lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

    def create(self, name: str, overrides: Dict[str, Any]) -> WhatIfScenario:
        with self.lock:
            if len(self.scenarios) >= MAX_SCENARIOS:
                raise ValueError(f"Máximo {MAX_SCENARIOS} escenarios paralelos")
            # Asignar ID estable scenario1/scenario2/scenario3
            used_ids = {s.id for s in self.scenarios.values()}
            sid = None
            for n in range(1, MAX_SCENARIOS + 1):
                cand = f"scenario{n}"
                if cand not in used_ids:
                    sid = cand
                    break
            if sid is None:
                sid = f"scenario_{uuid.uuid4().hex[:6]}"
            sc = WhatIfScenario(sid, name, overrides, self.baseline.config)
            self.scenarios[sid] = sc
            # Registrar nodos OPC UA
            try:
                if self.runtime.opcua:
                    self.runtime.opcua.register_whatif_scenario(sid)
            except Exception as e:
                logger.warning(f"OPC UA register whatif: {e}")
            # Asegurar el loop
            self._ensure_loop()
            return sc

    def delete(self, scenario_id: str) -> bool:
        with self.lock:
            return self.scenarios.pop(scenario_id, None) is not None

    def update_overrides(self, scenario_id: str, overrides: Dict[str, Any]) -> Optional[WhatIfScenario]:
        with self.lock:
            sc = self.scenarios.get(scenario_id)
            if not sc:
                return None
            # Recrear el simulator con nuevos overrides (más simple que parchear in-place)
            cfg = copy.deepcopy(self.baseline.config)
            sc._apply_overrides(cfg, overrides)
            sc.overrides = overrides
            sc.simulator = YerbaProcessSimulator(cfg)
            sc.kwh_acum = 0.0
            sc.chips_kg_acum = 0.0
            sc.kg_produced = 0.0
            sc.runtime_h = 0.0
            return sc

    def list(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [sc.to_dict() for sc in self.scenarios.values()]

    def reset_all(self):
        with self.lock:
            self.scenarios.clear()

    def _ensure_loop(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="whatif-loop", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop_evt.is_set():
            try:
                with self.lock:
                    items = list(self.scenarios.items())
                if not items:
                    time.sleep(0.5)
                    continue
                amb_t = self.baseline.ambient_temp
                amb_h = self.baseline.ambient_humidity
                prices = {"kwh_ars": 120.0, "kg_chips_ars": 95.0}
                # Tomar precios reales del ops_service si está disponible
                try:
                    from .. import server  # noqa
                except Exception:
                    pass
                # Hot path: tick + KPIs + publicar
                for sid, sc in items:
                    sc.step(amb_t, amb_h)
                    kpis = sc.compute_kpis(prices)
                    # OPC UA
                    try:
                        if self.runtime.opcua:
                            self.runtime.opcua.update_whatif_scenario(sid, kpis)
                    except Exception:
                        pass
                    # Modbus: unit IDs 20,21,22 → escenario 1,2,3 (offset por orden de creación)
                    try:
                        if self.runtime.modbus:
                            order = list(self.scenarios.keys()).index(sid)
                            unit = 20 + order
                            if unit in self.runtime.modbus.context.slaves() if hasattr(self.runtime.modbus.context, 'slaves') else True:
                                self.runtime.modbus.context[unit].setValues(3, 0, [
                                    int(kpis["OEE"] * 10),
                                    int(kpis["CostoPorKg"] * 10),
                                    int(kpis["kWhAcum"] * 10),
                                    int(kpis["ChipsKgAcum"] * 10),
                                    int(kpis["TempZapecado"] * 10),
                                    int(kpis["TempSecado"] * 10),
                                    int(kpis["HumFinal"] * 10),
                                    int(kpis["ProduccionKg"]),
                                ])
                    except Exception:
                        pass
                    # MQTT
                    try:
                        if self.runtime.mqtt and getattr(self.runtime.mqtt, "client", None):
                            for k, v in kpis.items():
                                topic = f"yerba/whatif/{sid}/{k}"
                                self.runtime.mqtt.client.publish(topic, str(v), qos=0, retain=False)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"whatif loop: {e}")
            time.sleep(1.0)
