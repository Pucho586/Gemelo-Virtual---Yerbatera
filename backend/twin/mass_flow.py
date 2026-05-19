"""MassFlowService: trazabilidad real del lote a través de las etapas.

Modelo del proceso (fuente: literatura yerbatera, INYM, normativas Mercosur):

  COSECHA ─► RECEPCIÓN/PESAJE ─► ZAPECADO ─► SECADO ─► CANCHADO ─► ESTACIONAMIENTO ─► MOLIENDA FINA ─► EMPAQUE
              (50-55% hum)        (3-5 s)    (3-8 h)   (molienda    (6-24 meses        (separa hojas    (paquetes
                                  T 300-550° T 80-120° gruesa)      o cámara con       y palitos)       500g-1kg)
                                  H_out 25%  H_out 4-7%             vapor 30-90 días)

Este servicio gestiona el flujo de masa entre las 4 etapas que el simulador opera:
RECEPCION → ZAPECADO → SECADO → CANCHADO → ESTACIONAMIENTO (cámaras).

Cada etapa mantiene:
  - kg_actual:    masa de yerba en proceso ahora mismo en la etapa
  - T_in / H_in:  estado de entrada (heredado de etapa anterior al transferir)
  - T_out / H_out:estado de salida (calculado por el simulador físico de la etapa)
  - merma_pct:    merma típica de la etapa (referencial)
  - kg_acum_in / kg_acum_out: contadores históricos del día

Operaciones:
  - cargar_hoja_verde(kg, T, H):    agrega a recepción
  - transferir(de_etapa, a_etapa, kg=None):  pasa kg (o todo) a siguiente etapa
                                              calcula merma según la etapa de origen
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Mermas referenciales (% de pérdida típica por etapa, fuente: literatura yerbatera)
DEFAULT_MERMA = {
    "recepcion": 0.0,        # sólo pesaje, sin pérdida
    "zapecado": 0.35,        # 50% hum → 25% hum (evaporación)
    "secado": 0.22,          # 25% → 6% (evaporación)
    "canchado": 0.04,        # polvo y partículas finas que se pierden
    "estacionamiento": 0.005,  # mínima, sólo respiración yerba
}

# Tiempo mínimo de procesamiento real (segundos) antes de poder transferir.
# Ajustados para uso en simulador (aceleración x60 típica): valores rápidos pero realistas.
# Si la planta opera en modo real (sin aceleración), estos tiempos son chicos a propósito
# para que el operario tenga feedback visual claro; subir según necesidad desde admin.
DEFAULT_MIN_TIME_S = {
    "recepcion": 0,           # transferencia inmediata posible
    "zapecado": 8,            # ~3-5s reales × aceleración 60 muy rápido; damos 8s ojo
    "secado": 60,             # 3-8h reales son muchos minutos en acelerado; 60s mínimo
    "canchado": 10,           # molienda rápida
    "estacionamiento": 0,     # cargado a cámara, ya está
}

STAGES_ORDER = ["recepcion", "zapecado", "secado", "canchado", "estacionamiento"]


class StageMass:
    """Estado de masa para una etapa."""

    def __init__(self, name: str):
        self.name = name
        self.kg_actual: float = 0.0          # masa actualmente en proceso
        self.kg_acum_in: float = 0.0         # acumulado entrante (histórico)
        self.kg_acum_out: float = 0.0        # acumulado saliente
        self.merma_kg_acum: float = 0.0      # acumulado de merma
        self.T_in: Optional[float] = None    # T del último ingreso
        self.H_in: Optional[float] = None    # H del último ingreso
        self.ts_last_in: Optional[str] = None
        self.ts_last_out: Optional[str] = None
        self.ts_processing_started: Optional[float] = None  # epoch sec when current batch started

    def processing_seconds(self) -> float:
        if self.ts_processing_started is None or self.kg_actual <= 0:
            return 0.0
        import time as _t
        return max(0.0, _t.time() - self.ts_processing_started)

    def to_dict(self, min_time_s: float = 0.0) -> Dict[str, Any]:
        proc_s = self.processing_seconds()
        return {
            "name": self.name,
            "kg_actual": round(self.kg_actual, 2),
            "kg_acum_in": round(self.kg_acum_in, 2),
            "kg_acum_out": round(self.kg_acum_out, 2),
            "merma_kg_acum": round(self.merma_kg_acum, 2),
            "T_in": round(self.T_in, 2) if self.T_in is not None else None,
            "H_in": round(self.H_in, 2) if self.H_in is not None else None,
            "ts_last_in": self.ts_last_in,
            "ts_last_out": self.ts_last_out,
            "processing_seconds": round(proc_s, 1),
            "min_time_s": float(min_time_s),
            "ready": self.kg_actual <= 0 or proc_s >= min_time_s,
            "progress_pct": min(100.0, (proc_s / min_time_s * 100.0)) if min_time_s > 0 else 100.0,
        }


class MassFlowService:
    """Trazabilidad de masa entre las etapas del simulador."""

    def __init__(self, simulator):
        self.simulator = simulator
        self.lock = threading.Lock()
        self.stages: Dict[str, StageMass] = {n: StageMass(n) for n in STAGES_ORDER}
        self.merma_pct: Dict[str, float] = dict(DEFAULT_MERMA)
        self.min_time_s: Dict[str, float] = dict(DEFAULT_MIN_TIME_S)
        self.log: List[Dict[str, Any]] = []   # eventos de carga / transferencia (últimos 200)

    # ---------- Carga inicial ----------
    def cargar_hoja_verde(self, kg: float, T: Optional[float] = None, H: Optional[float] = None,
                          user: str = "sistema") -> Dict[str, Any]:
        """Agrega hoja verde fresca a Recepción.

        T y H opcionales: si no se pasan, se toman del clima ambiente (más realista)."""
        if kg <= 0:
            raise ValueError("kg debe ser > 0")
        import time as _t
        with self.lock:
            r = self.stages["recepcion"]
            if T is None:
                T = self.simulator.ambient_temp
            if H is None:
                # Hoja recién cosechada: humedad típica 50-55%
                H = 55.0
            # Si ya había masa, hacer promedio ponderado de T y H
            if r.kg_actual > 0 and r.T_in is not None and r.H_in is not None:
                w_new = kg / (r.kg_actual + kg)
                r.T_in = r.T_in * (1 - w_new) + T * w_new
                r.H_in = r.H_in * (1 - w_new) + H * w_new
            else:
                r.T_in = float(T)
                r.H_in = float(H)
            r.kg_actual += float(kg)
            r.kg_acum_in += float(kg)
            r.ts_last_in = now_iso()
            if r.ts_processing_started is None:
                r.ts_processing_started = _t.time()
            ev = {"ts": r.ts_last_in, "action": "carga_hoja_verde", "kg": kg,
                  "T": T, "H": H, "user": user}
            self._log_event(ev)
            return r.to_dict(self.min_time_s.get("recepcion", 0))

    # ---------- Transferencia entre etapas ----------
    def transferir(self, de: str, a: str, kg: Optional[float] = None,
                   user: str = "sistema", force: bool = False) -> Dict[str, Any]:
        """Mueve kg de una etapa a la siguiente.

        Reglas:
          - kg=None ⇒ transfiere todo lo que está en `de`.
          - Aplica merma de la etapa de origen (kg salida = kg entrada × (1 - merma)).
          - El estado T_out/H_out del simulador en la etapa `de` se pasa como T_in/H_in de `a`.
          - Sólo se permite transferir a la etapa siguiente en el orden de proceso.
          - Si la etapa de origen no terminó su tiempo mínimo de procesamiento, devuelve 400
            (salvo que force=True, sólo permitido para admin desde UI).
        """
        if de not in self.stages or a not in self.stages:
            raise ValueError(f"Etapa inválida: {de}/{a}")
        if STAGES_ORDER.index(a) != STAGES_ORDER.index(de) + 1:
            raise ValueError(f"Solo se permite avanzar al siguiente paso (de '{de}' a '{a}' no es válido)")
        import time as _t
        with self.lock:
            src = self.stages[de]
            dst = self.stages[a]
            if src.kg_actual <= 0:
                raise ValueError(f"No hay masa en '{de}' para transferir")
            # Validar readiness
            min_t = self.min_time_s.get(de, 0)
            proc_s = src.processing_seconds()
            if not force and min_t > 0 and proc_s < min_t:
                falta = min_t - proc_s
                raise ValueError(f"'{de}' aún procesando ({proc_s:.0f}s/{min_t:.0f}s). Falta {falta:.0f}s. Esperá o forzá con force=true.")
            kg_transferir = min(float(kg) if kg is not None else src.kg_actual, src.kg_actual)
            merma_pct = self.merma_pct.get(de, 0.0)
            kg_out = kg_transferir * (1.0 - merma_pct)
            merma_kg = kg_transferir - kg_out

            # Leer T/H de salida desde el simulador (puntos físicos reales)
            T_out, H_out = self._read_stage_output(de)

            # Actualizar src
            src.kg_actual -= kg_transferir
            src.kg_acum_out += kg_out
            src.merma_kg_acum += merma_kg
            src.ts_last_out = now_iso()
            if src.kg_actual <= 0.01:
                src.kg_actual = 0
                src.ts_processing_started = None  # liberada

            # Actualizar dst: T_in y H_in heredados del src (promediado si ya había masa)
            if dst.kg_actual > 0 and dst.T_in is not None and dst.H_in is not None:
                w_new = kg_out / (dst.kg_actual + kg_out)
                dst.T_in = dst.T_in * (1 - w_new) + T_out * w_new
                dst.H_in = dst.H_in * (1 - w_new) + H_out * w_new
            else:
                dst.T_in = T_out
                dst.H_in = H_out
            dst.kg_actual += kg_out
            dst.kg_acum_in += kg_out
            dst.ts_last_in = now_iso()
            # Inicia procesamiento si no estaba
            if dst.ts_processing_started is None:
                dst.ts_processing_started = _t.time()

            # Si la transferencia es a estacionamiento, repartir entre cámaras (round-robin)
            if a == "estacionamiento" and len(self.simulator.camaras) > 0:
                self._distribuir_a_camaras(kg_out)

            ev = {"ts": dst.ts_last_in, "action": "transferir",
                  "de": de, "a": a,
                  "kg_in": round(kg_transferir, 2),
                  "kg_out": round(kg_out, 2),
                  "merma_kg": round(merma_kg, 2),
                  "merma_pct": merma_pct,
                  "T_out": round(T_out, 2),
                  "H_out": round(H_out, 2),
                  "user": user,
                  "forced": force and min_t > 0 and proc_s < min_t}
            self._log_event(ev)
            return ev

    def _distribuir_a_camaras(self, kg_total: float):
        """Reparte kg entre las cámaras existentes (round-robin a la cámara con menor carga)."""
        cams = self.simulator.camaras
        if not cams:
            return
        # Elegir la cámara con menos carga (load balancing)
        target = min(cams, key=lambda c: c.carga_kg)
        target.carga_kg += kg_total

    def _read_stage_output(self, stage: str) -> tuple:
        """Lee T y H actuales del simulador en el punto de salida de la etapa."""
        sim = self.simulator
        if stage == "recepcion":
            # Recepción: ambiente. T y H del clima.
            return (sim.ambient_temp, 55.0)  # hoja verde mantiene su humedad alta
        elif stage == "zapecado":
            # Termopar de salida del tambor zapecador + humedad estimada por evaporación
            return (sim.zapecado.temperatura, sim.flujo.get("zap_out_humedad", 25.0))
        elif stage == "secado":
            # Higrómetro NIR a la salida del secadero + termopar de yerba a la salida
            return (sim.secado.temperatura, sim.secado.humedad)
        elif stage == "canchado":
            # No hay cambio térmico significativo en canchado; T y H heredan del secado
            return (sim.secado.temperatura - 5.0, sim.secado.humedad)
        return (sim.ambient_temp, 50.0)

    # ---------- Snapshot ----------
    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "stages": {n: s.to_dict(self.min_time_s.get(n, 0)) for n, s in self.stages.items()},
                "merma_pct": dict(self.merma_pct),
                "min_time_s": dict(self.min_time_s),
                "order": list(STAGES_ORDER),
                "log_recent": self.log[-50:],
            }

    def set_merma(self, stage: str, pct: float):
        if stage not in self.merma_pct:
            raise ValueError(f"Etapa inválida: {stage}")
        if pct < 0 or pct > 0.95:
            raise ValueError("pct debe estar entre 0 y 0.95")
        with self.lock:
            self.merma_pct[stage] = float(pct)

    def set_min_time(self, stage: str, seconds: float):
        if stage not in self.min_time_s:
            raise ValueError(f"Etapa inválida: {stage}")
        if seconds < 0 or seconds > 3600:
            raise ValueError("seconds debe estar entre 0 y 3600")
        with self.lock:
            self.min_time_s[stage] = float(seconds)

    def reset(self):
        with self.lock:
            for s in self.stages.values():
                s.kg_actual = 0
                s.kg_acum_in = 0
                s.kg_acum_out = 0
                s.merma_kg_acum = 0
                s.T_in = None
                s.H_in = None
                s.ts_last_in = None
                s.ts_last_out = None
                s.ts_processing_started = None
            self.log.clear()

    def _log_event(self, ev: Dict[str, Any]):
        self.log.append(ev)
        if len(self.log) > 200:
            self.log = self.log[-200:]
