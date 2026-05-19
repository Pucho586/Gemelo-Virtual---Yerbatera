"""Calibración del simulador a partir de un CSV histórico real.

Algoritmo simple por mínimos cuadrados sobre dinámicas de primer orden:
   y(t+dt) = y(t) + (target - y(t)) / tau * dt
Reorganizado:
   (y(t+dt) - y(t)) / dt = (target - y(t)) / tau

Resolvemos por regresión lineal: pendiente = 1/tau.
También computamos el ruido (stdev del residuo).
"""
import math
import statistics
from io import StringIO
from typing import Any, Dict, List, Optional

import pandas as pd


def _linear_fit_tau(values: List[float], target: float, dt: float) -> Optional[Dict[str, float]]:
    """Ajusta tau para dinámica de primer orden hacia un target."""
    n = len(values)
    if n < 5:
        return None
    xs, ys = [], []
    for i in range(1, n):
        x = target - values[i - 1]
        y = (values[i] - values[i - 1]) / dt
        if abs(x) < 1e-6:
            continue
        xs.append(x)
        ys.append(y)
    if len(xs) < 5:
        return None
    # y = (1/tau) * x  → least squares without intercept
    sum_xx = sum(x * x for x in xs)
    sum_xy = sum(xs[i] * ys[i] for i in range(len(xs)))
    if sum_xx < 1e-9:
        return None
    slope = sum_xy / sum_xx  # = 1/tau
    if slope <= 0:
        return None
    tau = 1.0 / slope
    # residual stdev
    residuals = [ys[i] - slope * xs[i] for i in range(len(xs))]
    try:
        noise = statistics.stdev(residuals) if len(residuals) > 1 else 0.0
    except statistics.StatisticsError:
        noise = 0.0
    return {"tau": round(tau, 2), "noise_std": round(noise, 4), "samples": len(xs)}


def calibrate_from_csv(csv_text: str, *, sample_interval_s: float = 5.0) -> Dict[str, Any]:
    """Lee CSV (debe tener columnas tipo zap_temperatura, sec_temperatura, sec_humedad...)
    y ajusta τ para zapecado y secado.

    Devuelve un dict con propuestas (no aplica - el usuario decide si guardar).
    """
    df = pd.read_csv(StringIO(csv_text))
    cols = {c.lower(): c for c in df.columns}
    result: Dict[str, Any] = {"rows": int(len(df)), "columns": list(df.columns)}

    # Zapecado: convergencia a ~450
    for cand in ("zap_temperatura", "zapecado_temperatura", "zap_t"):
        if cand in cols:
            vals = df[cols[cand]].dropna().astype(float).tolist()
            if vals:
                fit = _linear_fit_tau(vals, target=max(vals), dt=sample_interval_s)
                if fit:
                    result["zapecado"] = {**fit, "target_inferido": round(max(vals), 1)}
                break

    # Secado humedad: descenso a un piso
    for cand in ("sec_humedad", "secado_humedad", "sec_h"):
        if cand in cols:
            vals = df[cols[cand]].dropna().astype(float).tolist()
            if vals:
                target = min(vals)
                fit = _linear_fit_tau(vals, target=target, dt=sample_interval_s)
                if fit:
                    result["secado_humedad"] = {**fit, "piso_inferido": round(target, 1)}
                break

    # Cámara 1 temperatura
    for cand in ("cam1_temperatura", "cam_1_temperatura"):
        if cand in cols:
            vals = df[cols[cand]].dropna().astype(float).tolist()
            if vals:
                target = statistics.median(vals)
                fit = _linear_fit_tau(vals, target=target, dt=sample_interval_s)
                if fit:
                    result["camara1"] = {**fit, "setpoint_inferido": round(target, 1)}
                break

    return result


def apply_calibration_to_simulator(simulator, calibration: Dict[str, Any]):
    """Aplica los τ propuestos al simulador (mutación directa)."""
    z = calibration.get("zapecado")
    if z and "tau" in z:
        simulator.zapecado.tau = float(z["tau"])
    s = calibration.get("secado_humedad")
    if s and "tau" in s:
        # Aproximamos con tau_t (secado.tau_t controla la dinámica)
        simulator.secado.tau_t = float(s["tau"])
    c = calibration.get("camara1")
    if c and "tau" in c and simulator.camaras:
        for cam in simulator.camaras:
            cam.tau = float(c["tau"])
