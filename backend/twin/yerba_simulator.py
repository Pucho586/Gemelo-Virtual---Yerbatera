# --- Archivo: twin/yerba_simulator.py ---
"""
Simulador realista del proceso de yerba mate (modelo físico puro v2).

Filosofía: el simulador es PROCESO PURO basado en balances de masa/energía.
Los SP son objetivos del operador (sólo display + opcional PID). El operador
mueve VARIABLES MANIPULADAS (combustible, vel.aire, posición calefactor,
caudal de vapor, rpm) y el sistema responde según la física.

Cada etapa expone un PID interno (off por default) que, si se activa, ajusta
automáticamente la manipulada para llegar al SP. Esto permite al usuario
practicar sintonía (Kp/Ki/Kd).

Vía Modbus/OPC UA/MQTT, un PLC externo puede leer los valores y escribir las
manipuladas (sin necesidad del PID interno) — modo "shadow"/"twin".
"""

import time
import random
import threading
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple

from .pid import PID

DEFAULT_LIMITS = {
    "temp_min": 10,
    "temp_max": 120,
    "hum_min": 5,
    "hum_max": 95,
    "co2_min": 400,
    "co2_max": 8000,
}

# Constantes físicas (simplificadas)
PCI_CHIP_KWH_KG = 5.0      # kW térmicos por kg/h de chips quemándose (PCI ~18 MJ/kg × η 0.5 / 3600)
CP_AIRE = 1.0              # kJ/(kg·°C)
CP_YERBA = 1.8             # kJ/(kg·°C)
LAMBDA_VAP = 2260.0        # kJ/kg (calor latente de vaporización a 100°C)
H_VAPOR_KJ_KG = 2680.0     # entalpía del vapor saturado ~150°C

# Producción de CO2 por kg de yerba en maduración (ppm * s^-1 * kg^-1)
CO2_RATE = 0.03


# ---------------- Subsistemas ----------------
class Zapecado:
    """Horno rotatorio de chips de madera.

    Variables manipuladas (operador o PLC ajusta):
    - `velocidad_chip` (kg/h)  → combustible
    - `velocidad_tambor` (rpm) → extracción de gases + carga de yerba
    - `estado_alimentacion` (bool) → permiso quemador

    SP `temperatura_obj` es referencia/objetivo. PID interno opcional ajusta
    `velocidad_chip` para llegar al SP si está activado.

    Balance térmico:
      C · dT/dt = P_chips − P_pared − P_aire − P_yerba
        P_chips  = vel_chip × PCI × η_combustión
        P_pared  = U_pared · (T − T_amb)
        P_aire   = k_aire · vel_tambor · (T − T_amb)
        P_yerba  = k_yerba · vel_tambor · (T − T_amb)
    """

    # Parámetros físicos (kJ/°C, kW/°C, etc.)
    C_HORNO = 30.0             # capacidad térmica del horno (kJ/°C)
    U_PARED = 0.05             # pérdida pasiva (kW/°C)
    K_AIRE  = 0.003            # extracción aire por rpm (kW/(°C·rpm))
    K_YERBA = 0.015            # calefacción yerba por rpm (kW/(°C·rpm))

    def __init__(self, config: Dict):
        self.temperatura = float(config.get("temperatura_inicial", 250))  # arranca tibio
        # Variables manipuladas
        self.velocidad_tambor = float(config.get("velocidad_tambor", 15))
        self.velocidad_chip = float(config.get("velocidad_chip", 30))
        self.estado_alimentacion = True
        # SP (objetivo / referencia)
        self.temperatura_obj: float | None = config.get("temperatura_objetivo")
        if self.temperatura_obj is not None:
            self.temperatura_obj = float(self.temperatura_obj)
        # Fallas
        self.falla_quemador = False
        self.falla_motor_tambor = False
        # tau (compat, no usado en modelo físico nuevo)
        self.tau = float(config.get("tau", 90.0))
        # PID interno (manipula velocidad_chip para llegar al SP)
        self.pid = PID(kp=0.15, ki=0.005, kd=0.0,
                       out_min=0.0, out_max=200.0,
                       direct_action=True)
        if self.temperatura_obj is not None:
            self.pid.sp = float(self.temperatura_obj)

    def get_setpoint(self) -> float:
        """Compatibilidad: devuelve el SP nominal o un SP "esperado físico"
        cuando no hay SP manual (sólo para display)."""
        if self.temperatura_obj is not None:
            return float(self.temperatura_obj)
        return 420.0  # SP por defecto si el operador no fijó

    def vel_tambor_real(self) -> float:
        if not self.estado_alimentacion or self.falla_motor_tambor:
            return 0.0
        return float(self.velocidad_tambor)

    def vel_chip_real(self) -> float:
        if not self.estado_alimentacion or self.falla_quemador:
            return 0.0
        # Ahogo: con tambor muy bajo, combustión incompleta
        if self.vel_tambor_real() < 5:
            return float(self.velocidad_chip) * 0.1
        return float(self.velocidad_chip)

    def update(self, dt: float, ambient_temp: float):
        # PID opcional: ajusta velocidad_chip
        if self.pid.enabled:
            self.pid.sp = float(self.temperatura_obj) if self.temperatura_obj is not None else 420.0
            out = self.pid.step(self.temperatura, dt)
            if out is not None:
                self.velocidad_chip = max(0.0, min(200.0, out))
        # Balance térmico
        T = self.temperatura
        dT = T - ambient_temp
        P_in = self.vel_chip_real() * PCI_CHIP_KWH_KG   # kW
        P_pared = self.U_PARED * dT
        P_aire  = self.K_AIRE  * self.vel_tambor_real() * dT
        P_yerba = self.K_YERBA * self.vel_tambor_real() * dT
        P_net = P_in - P_pared - P_aire - P_yerba       # kW = kJ/s
        # dT/dt = P_net (kJ/s) / C (kJ/°C) = °C/s
        self.temperatura += P_net / self.C_HORNO * dt
        self.temperatura += random.uniform(-0.3, 0.3)   # ruido sensor
        self.temperatura = max(ambient_temp - 2, min(750.0, self.temperatura))


class Secado:
    """Secador de cinta con calefactor (serpentín) y ventilador.

    Manipuladas (operador o PLC):
    - `posicion_calefactor` (0-100%) — potencia del serpentín
    - `velocidad_aire` (m/s)          — ventilador (convección + arrastre HR)
    - `estado` (bool)

    SP `temperatura_obj` y `humedad_obj` son referencias del operador.
    2 PIDs opcionales: T→calefactor, HR→vel_aire.

    Balance térmico:
      C·dT/dt = P_cal − P_pared − P_aire − P_evap
    Balance humedad yerba:
      dHR_y/dt = -k·vel_aire·max(0, HR_y − HR_eq)
    """

    C_ZONA   = 25.0
    P_MAX_CAL = 50.0  # potencia máx calefactor (kW)
    U_PARED  = 0.05
    K_AIRE   = 0.15   # extracción aire (kW/(°C·m/s))
    K_EVAP   = 0.0008

    def __init__(self, config: Dict):
        self.temperatura = float(config.get("temperatura", 40))
        self.humedad = float(config.get("humedad", 30))
        self.velocidad_aire = float(config.get("velocidad_aire", 2.5))
        self.posicion_calefactor = float(config.get("posicion_calefactor", 0.0))
        self.estado = True
        self.temperatura_obj = float(config.get("temperatura_objetivo", 95.0))
        self.humedad_obj = float(config.get("humedad_objetivo", 7.0))
        self.falla_ventilador = False
        self.falla_serpentin = False
        # tau (compat)
        self.tau_t = float(config.get("tau_t", 120.0))
        self.pid_t = PID(kp=4.0, ki=0.15, kd=0.0, out_min=0.0, out_max=100.0, direct_action=True)
        self.pid_t.sp = self.temperatura_obj
        self.pid_h = PID(kp=0.3, ki=0.02, kd=0.0, out_min=0.5, out_max=12.0, direct_action=False)
        self.pid_h.sp = self.humedad_obj

    def vel_aire_real(self) -> float:
        if not self.estado or self.falla_ventilador:
            return 0.0
        return max(0.0, float(self.velocidad_aire))

    def pos_cal_real(self) -> float:
        if not self.estado or self.falla_serpentin:
            return 0.0
        return max(0.0, min(100.0, float(self.posicion_calefactor)))

    def update(self, dt: float, ambient_temp: float, ambient_humidity: float):
        if self.pid_t.enabled:
            self.pid_t.sp = self.temperatura_obj
            out = self.pid_t.step(self.temperatura, dt)
            if out is not None:
                self.posicion_calefactor = max(0.0, min(100.0, out))
        if self.pid_h.enabled:
            self.pid_h.sp = self.humedad_obj
            out = self.pid_h.step(self.humedad, dt)
            if out is not None:
                self.velocidad_aire = max(0.0, min(15.0, out))

        T = self.temperatura
        v_aire = self.vel_aire_real()
        dT = T - ambient_temp
        P_cal = (self.pos_cal_real() / 100.0) * self.P_MAX_CAL
        P_pared = self.U_PARED * max(0.0, dT)
        P_aire  = self.K_AIRE * v_aire * dT
        HR_eq = max(2.0, ambient_humidity * 0.15 + (T - ambient_temp) * 0.05)
        evap_rate = self.K_EVAP * v_aire * max(0.0, self.humedad - HR_eq)
        m_dot_water = 0.001 * evap_rate * 100
        P_evap = m_dot_water * LAMBDA_VAP
        P_net = P_cal - P_pared - P_aire - P_evap
        self.temperatura += P_net / self.C_ZONA * dt
        self.temperatura += random.uniform(-0.15, 0.15)
        self.temperatura = max(ambient_temp - 2, min(140.0, self.temperatura))

        self.humedad -= evap_rate * dt
        if v_aire < 0.1 or self.pos_cal_real() < 1:
            self.humedad += (ambient_humidity - self.humedad) / 600 * dt
        self.humedad += random.uniform(-0.03, 0.03)
        self.humedad = max(2.0, min(95.0, self.humedad))


class Canchado:
    """Molino canchador. La rpm es manipulada directa.

    Sin PID interno: la partícula es función directa de la rpm con dinámica ~5s.
    Si el usuario quiere un PID que ajuste rpm para llegar a un SP grosor, se
    activa `pid.enabled = True` (poco habitual en planta real).
    """

    def __init__(self, config: Dict):
        self.velocidad_molino = float(config.get("velocidad_molino", 60))
        self.estado = True
        self.tamano_particula = 10.0
        self.tamano_particula_obj: float | None = config.get("tamano_particula_objetivo")
        if self.tamano_particula_obj is not None:
            self.tamano_particula_obj = float(self.tamano_particula_obj)
        self.tau_p = float(config.get("tau_p", 5.0))
        self.falla_motor = False
        self.rodamiento_caliente = False
        # PID opcional: SP grosor → ajusta rpm (acción inversa: más rpm = menos grosor)
        self.pid = PID(kp=-10.0, ki=-0.5, kd=0.0, out_min=0.0, out_max=130.0, direct_action=True)

    def get_setpoint(self) -> float:
        if self.tamano_particula_obj is not None:
            return float(self.tamano_particula_obj)
        rpm_real = self.vel_molino_real()
        if rpm_real <= 0:
            return self.tamano_particula
        return max(0.5, 10.0 - rpm_real * 0.07)

    def vel_molino_real(self) -> float:
        if self.falla_motor or not self.estado:
            return 0.0
        return float(self.velocidad_molino)

    def update(self, dt: float):
        if self.pid.enabled and self.tamano_particula_obj is not None:
            self.pid.sp = float(self.tamano_particula_obj)
            out = self.pid.step(self.tamano_particula, dt)
            if out is not None:
                self.velocidad_molino = max(0.0, min(130.0, out))
        if self.falla_motor or not self.estado:
            self.tamano_particula += random.uniform(-0.01, 0.01)
        else:
            target = self.get_setpoint()
            self.tamano_particula += (target - self.tamano_particula) / self.tau_p * dt
            self.tamano_particula += random.uniform(-0.06, 0.06)
        self.tamano_particula = max(0.3, min(15.0, self.tamano_particula))


class CamaraMaduracion:
    """Cámara de maduración con balance térmico real.

    Manipuladas (operador o PLC):
    - `vapor_caudal_kgh` (0-200) — caudal de inyección de vapor
    - `vapor_activo` (bool)       — válvula de paso de vapor
    - `ventilador` (bool/0-100%)  — extracción/recirculación de aire

    SP `temperatura_obj`, `humedad_obj`, `co2_obj` son referencias.
    Un PID opcional ajusta `vapor_caudal_kgh` para llegar al SP T (mantiene
    humedad alta cuando se ajusta a un SP cálido y húmedo).

    Balance térmico (C·dT/dt = P_vapor − P_pared − P_extrac):
      P_vapor  = m_vapor_dot · h_vapor_efectivo  (energía del vapor)
      P_pared  = U · A · (T − T_amb)
      P_extrac = k_aire · vent · (T − T_amb)
    """

    C_CAMARA = 200.0       # kJ/°C (cámara grande con carga térmica)
    U_PARED  = 0.20        # kW/°C (pérdida pasiva paredes)
    K_AIRE   = 0.05        # kW/(°C·vent_frac) (ventilador en fracción 0..1)
    K_VAPOR_T = 0.0006     # °C/kg_vapor de aporte térmico directo
    K_VAPOR_H = 0.08       # %HR/kg_vapor de aporte húmedo

    def __init__(self, camara_id: int, config: Dict, limits: Dict):
        self.id = camara_id
        self.nombre = config["nombre"]
        self.temperatura_obj = float(config["temperatura_objetivo"])
        self.humedad_obj = float(config["humedad_objetivo"])
        self.co2_obj = float(config["co2_objetivo"])

        self.temperatura = self.temperatura_obj + 3.0
        self.humedad = self.humedad_obj - 5.0
        self.co2 = 1800.0
        # Manipuladas
        self.ventilador = True       # ON/OFF
        self.vent_pos = 100.0        # 0-100% (apertura de damper)
        self.carga_kg = 0.0
        self.tiempo_maduracion = 0.0

        self.vapor_activo: bool = bool(config.get("vapor_activo", False))
        self.vapor_caudal_kgh: float = float(config.get("vapor_caudal_kgh", 0.0))
        self.vapor_setpoint_temp: float = float(config.get("vapor_setpoint_temp", self.temperatura_obj))
        self.vapor_setpoint_hum: float = float(config.get("vapor_setpoint_hum", self.humedad_obj))
        self.vapor_kg_acum: float = 0.0

        self.falla_ventilador = False
        self.fuga_vapor = False
        self.puerta_abierta = False

        self.lim = limits
        # tau (compat)
        self.tau = float(config.get("tau", limits.get("tau_camera", 600)))
        # PID opcional: SP T → manipula vapor_caudal_kgh
        self.pid_t = PID(kp=8.0, ki=0.1, kd=0.0, out_min=0.0, out_max=200.0, direct_action=True)
        self.pid_t.sp = self.temperatura_obj

    def vent_real(self) -> float:
        """Fracción efectiva de ventilación (0..1)."""
        if not self.ventilador or self.falla_ventilador:
            return 0.0
        return max(0.0, min(1.0, self.vent_pos / 100.0))

    def vapor_real_kgh(self) -> float:
        """Caudal de vapor efectivo (0 si válvula cerrada o fuga)."""
        if not self.vapor_activo:
            return 0.0
        if self.fuga_vapor:
            return float(self.vapor_caudal_kgh) * 0.3  # 70% se pierde por fuga
        return float(self.vapor_caudal_kgh)

    def update(self, dt: float, ambient_temp: float, ambient_humidity: float):
        if self.carga_kg > 0:
            self.tiempo_maduracion += dt / 86400.0

        if self.pid_t.enabled:
            self.pid_t.sp = self.temperatura_obj
            out = self.pid_t.step(self.temperatura, dt)
            if out is not None:
                self.vapor_caudal_kgh = max(0.0, min(200.0, out))
                if out > 0.5:
                    self.vapor_activo = True

        # Balance térmico
        T = self.temperatura
        dT = T - ambient_temp
        m_vap_dot = self.vapor_real_kgh() / 3600.0    # kg/s
        P_vapor = m_vap_dot * H_VAPOR_KJ_KG           # kW de aporte térmico
        # Si SP_vapor < T actual, el vapor también condensa enfriando (modelo simplificado: aporte neto = (Tvapor−T))
        if self.vapor_real_kgh() > 0 and T > self.vapor_setpoint_temp:
            P_vapor *= 0.3  # el vapor pierde efectividad si la cámara ya está más caliente que el SP de inyección
        P_pared = self.U_PARED * max(0.0, dT)
        P_extrac = self.K_AIRE * self.vent_real() * dT
        # Puerta abierta: pérdida masiva
        if self.puerta_abierta:
            P_extrac += 5.0 * dT  # equivalente a un ventilador enorme

        P_net = P_vapor - P_pared - P_extrac
        self.temperatura += P_net / self.C_CAMARA * dt
        self.temperatura += random.uniform(-0.05, 0.05)
        self.temperatura = max(ambient_temp - 2, min(80.0, self.temperatura))

        # Balance humedad: vapor aporta, ventilador y paredes pierden
        vapor_kg_acum_dt = self.vapor_real_kgh() * dt / 3600.0
        self.humedad += self.K_VAPOR_H * vapor_kg_acum_dt
        # Pérdida pasiva a ambiente (paredes)
        self.humedad += (ambient_humidity - self.humedad) * 0.0005 * dt
        # Ventilador remueve humedad si está abierto
        self.humedad -= self.vent_real() * (self.humedad - ambient_humidity) * 0.002 * dt
        if self.puerta_abierta:
            self.humedad += (ambient_humidity - self.humedad) * 0.02 * dt
        self.humedad += random.uniform(-0.04, 0.04)
        self.humedad = max(2.0, min(98.0, self.humedad))

        # Acumular kg de vapor consumido (para costos)
        self.vapor_kg_acum += self.vapor_caudal_kgh * dt / 3600.0 if self.vapor_activo else 0.0

        # CO2 por respiración yerba + extracción
        self.co2 += CO2_RATE * self.carga_kg * dt
        self.co2 -= self.vent_real() * (self.co2 - 420.0) * 0.005 * dt
        if self.puerta_abierta:
            self.co2 += (420.0 - self.co2) * 0.02 * dt
        self.co2 = max(380.0, min(8000.0, self.co2))



# ---------------- Simulador principal ----------------
class YerbaProcessSimulator:
    def __init__(self, config: Dict):
        self.lock = threading.Lock()
        self.config = config

        limits_cfg = config.get("limits", {})
        self.limits = {**DEFAULT_LIMITS, **limits_cfg}

        self.zapecado = Zapecado(config["zapecado"])
        self.secado = Secado(config["secado"])
        self.canchado = Canchado(config["canchado"])
        self.camaras = [
            CamaraMaduracion(i, c, self.limits) for i, c in enumerate(config["camaras"])
        ]

        self.aceleracion = float(config.get("simulacion", {}).get("aceleracion", 60.0))
        self.last_update = time.time()

        # Modo de operación: 'simulator' (simula matemáticamente) o 'twin' (valores
        # vienen de fuente externa: API, Modbus client externo, MQTT subscribe).
        self.mode = config.get("simulacion", {}).get("mode", "simulator")

        # Throughput / flujo de masa entre etapas (kg/h)
        self.throughput_kgh = float(config.get("simulacion", {}).get("throughput_kgh", 800.0))

        # Estado de flujo: humedad de salida real de cada etapa
        self.flujo = {
            "zap_out_humedad": 35.0,   # entra hoja verde ~50%, sale ~30-40%
            "sec_out_humedad": 8.0,    # sale del secado ~7-10%
            "can_out_kgh": self.throughput_kgh * 0.96,  # 4% merma típica en canchado
        }

        # Clima inicial (será actualizado por WeatherService)
        self.ambient_temp = 24.0  # °C (default Posadas)
        self.ambient_humidity = 70.0  # %
        self.weather_meta: Dict[str, Any] = {
            "latitude": -27.3667,
            "longitude": -55.8967,
            "city": "Posadas, Misiones, Argentina",
            "updated_at": None,
        }
        # Reloj simulado (avanza con factor aceleración respecto al real)
        self.sim_clock_start_real = time.time()
        self.sim_clock_start_sim = datetime.now(timezone.utc)
        self.forecast_hourly: List[Tuple[datetime, float, float]] = []

        # Historial circular para gráficos (≈30 min a 1 punto/s)
        self.history: deque = deque(maxlen=1800)

    # ---------- API ----------
    def set_weather(self, temp: float, humidity: float, meta: Dict[str, Any]):
        with self.lock:
            self.ambient_temp = float(temp)
            self.ambient_humidity = float(humidity)
            self.weather_meta.update(meta)

    def set_forecast(self, forecast):
        """Recibe lista de (datetime UTC, T, HR) ordenada. Para uso con aceleración."""
        with self.lock:
            self.forecast_hourly = list(forecast) if forecast else []

    def reset_sim_clock(self):
        with self.lock:
            self.sim_clock_start_real = time.time()
            self.sim_clock_start_sim = datetime.now(timezone.utc)

    def get_sim_clock(self) -> datetime:
        elapsed_real = time.time() - self.sim_clock_start_real
        elapsed_sim = elapsed_real * self.aceleracion
        return self.sim_clock_start_sim + timedelta(seconds=elapsed_sim)

    def _ambient_for_sim_time(self) -> Tuple[float, float]:
        if not self.forecast_hourly or self.aceleracion <= 1.0:
            return (self.ambient_temp, self.ambient_humidity)
        sim_t = self.get_sim_clock()
        import bisect as _b
        times = [pt[0] for pt in self.forecast_hourly]
        idx = _b.bisect_left(times, sim_t)
        if idx <= 0:
            return (self.forecast_hourly[0][1], self.forecast_hourly[0][2])
        if idx >= len(times):
            return (self.forecast_hourly[-1][1], self.forecast_hourly[-1][2])
        t0, T0, H0 = self.forecast_hourly[idx-1]
        t1, T1, H1 = self.forecast_hourly[idx]
        span = (t1 - t0).total_seconds() or 1
        f = max(0.0, min(1.0, (sim_t - t0).total_seconds() / span))
        return (T0 + (T1 - T0) * f, H0 + (H1 - H0) * f)

    def set_mode(self, mode: str):
        if mode not in ("simulator", "twin", "shadow", "replay"):
            raise ValueError("mode debe ser 'simulator', 'twin', 'shadow' o 'replay'")
        with self.lock:
            self.mode = mode

    def set_throughput(self, kgh: float):
        with self.lock:
            self.throughput_kgh = float(kgh)

    def set_zapecado(self, *, velocidad_tambor=None, velocidad_chip=None, estado_alimentacion=None,
                     temperatura_obj=None, tau=None,
                     falla_quemador=None, falla_motor_tambor=None,
                     pid=None):
        with self.lock:
            z = self.zapecado
            if velocidad_tambor is not None:
                z.velocidad_tambor = float(velocidad_tambor)
            if velocidad_chip is not None:
                z.velocidad_chip = float(velocidad_chip)
            if estado_alimentacion is not None:
                z.estado_alimentacion = bool(estado_alimentacion)
            if temperatura_obj is not None:
                z.temperatura_obj = (None if temperatura_obj in ("", None) else float(temperatura_obj))
                if z.temperatura_obj is not None:
                    z.pid.sp = z.temperatura_obj
            if tau is not None:
                z.tau = max(5.0, float(tau))
            if falla_quemador is not None:
                z.falla_quemador = bool(falla_quemador)
            if falla_motor_tambor is not None:
                z.falla_motor_tambor = bool(falla_motor_tambor)
            if pid is not None and isinstance(pid, dict):
                z.pid.update_params(**pid)

    def set_secado(self, *, velocidad_aire=None, posicion_calefactor=None, estado=None,
                   temperatura_obj=None, humedad_obj=None, tau_t=None,
                   falla_ventilador=None, falla_serpentin=None,
                   pid_t=None, pid_h=None):
        with self.lock:
            s = self.secado
            if velocidad_aire is not None:
                s.velocidad_aire = float(velocidad_aire)
            if posicion_calefactor is not None:
                s.posicion_calefactor = max(0.0, min(100.0, float(posicion_calefactor)))
            if estado is not None:
                s.estado = bool(estado)
            if temperatura_obj is not None:
                s.temperatura_obj = float(temperatura_obj)
                s.pid_t.sp = s.temperatura_obj
            if humedad_obj is not None:
                s.humedad_obj = float(humedad_obj)
                s.pid_h.sp = s.humedad_obj
            if tau_t is not None:
                s.tau_t = max(5.0, float(tau_t))
            if falla_ventilador is not None:
                s.falla_ventilador = bool(falla_ventilador)
            if falla_serpentin is not None:
                s.falla_serpentin = bool(falla_serpentin)
            if pid_t is not None and isinstance(pid_t, dict):
                s.pid_t.update_params(**pid_t)
            if pid_h is not None and isinstance(pid_h, dict):
                s.pid_h.update_params(**pid_h)

    def set_canchado(self, *, velocidad_molino=None, estado=None,
                     tamano_particula_obj=None, tau_p=None,
                     falla_motor=None, rodamiento_caliente=None,
                     pid=None):
        with self.lock:
            c = self.canchado
            if velocidad_molino is not None:
                c.velocidad_molino = float(velocidad_molino)
            if estado is not None:
                c.estado = bool(estado)
            if tamano_particula_obj is not None:
                c.tamano_particula_obj = (None if tamano_particula_obj in ("", None) else float(tamano_particula_obj))
                if c.tamano_particula_obj is not None:
                    c.pid.sp = c.tamano_particula_obj
            if tau_p is not None:
                c.tau_p = max(0.5, float(tau_p))
            if falla_motor is not None:
                c.falla_motor = bool(falla_motor)
            if rodamiento_caliente is not None:
                c.rodamiento_caliente = bool(rodamiento_caliente)
            if pid is not None and isinstance(pid, dict):
                c.pid.update_params(**pid)

    def set_camara(self, idx: int, *, carga_kg=None, ventilador=None, vent_pos=None,
                   temperatura_obj=None, humedad_obj=None, co2_obj=None,
                   vapor_activo=None, vapor_caudal_kgh=None,
                   vapor_setpoint_temp=None, vapor_setpoint_hum=None,
                   tau=None,
                   falla_ventilador=None, fuga_vapor=None, puerta_abierta=None,
                   pid_t=None):
        with self.lock:
            if idx < 0 or idx >= len(self.camaras):
                return
            cam = self.camaras[idx]
            if carga_kg is not None: cam.carga_kg = float(carga_kg)
            if ventilador is not None: cam.ventilador = bool(ventilador)
            if vent_pos is not None: cam.vent_pos = max(0.0, min(100.0, float(vent_pos)))
            if temperatura_obj is not None:
                cam.temperatura_obj = float(temperatura_obj)
                cam.pid_t.sp = cam.temperatura_obj
            if humedad_obj is not None: cam.humedad_obj = float(humedad_obj)
            if co2_obj is not None: cam.co2_obj = float(co2_obj)
            if vapor_activo is not None: cam.vapor_activo = bool(vapor_activo)
            if vapor_caudal_kgh is not None:
                cam.vapor_caudal_kgh = max(0.0, min(200.0, float(vapor_caudal_kgh)))
            if vapor_setpoint_temp is not None: cam.vapor_setpoint_temp = float(vapor_setpoint_temp)
            if vapor_setpoint_hum is not None: cam.vapor_setpoint_hum = float(vapor_setpoint_hum)
            if tau is not None: cam.tau = max(10.0, float(tau))
            if falla_ventilador is not None: cam.falla_ventilador = bool(falla_ventilador)
            if fuga_vapor is not None: cam.fuga_vapor = bool(fuga_vapor)
            if puerta_abierta is not None: cam.puerta_abierta = bool(puerta_abierta)
            if pid_t is not None and isinstance(pid_t, dict):
                cam.pid_t.update_params(**pid_t)

    MAX_CAMARAS = 12

    def add_camara(self, config: Dict | None = None) -> int:
        """Agrega una cámara nueva al final. Devuelve el nuevo id."""
        with self.lock:
            if len(self.camaras) >= self.MAX_CAMARAS:
                return -1
            i = len(self.camaras)
            cfg = config or {
                "nombre": f"Camara {i+1}",
                "temperatura_objetivo": 35.0,
                "humedad_objetivo": 75.0,
                "co2_objetivo": 3000.0,
            }
            cam = CamaraMaduracion(i, cfg, self.limits)
            self.camaras.append(cam)
            return i

    def remove_camara(self, idx: int) -> bool:
        with self.lock:
            if idx < 0 or idx >= len(self.camaras) or len(self.camaras) <= 1:
                return False
            self.camaras.pop(idx)
            # Reindexar
            for k, cam in enumerate(self.camaras):
                cam.id = k
            return True

    def set_camaras_count(self, n: int) -> int:
        """Ajusta el total a n (1..MAX_CAMARAS) agregando o removiendo desde el final."""
        with self.lock:
            n = max(1, min(self.MAX_CAMARAS, int(n)))
            while len(self.camaras) < n:
                i = len(self.camaras)
                self.camaras.append(CamaraMaduracion(i, {
                    "nombre": f"Camara {i+1}",
                    "temperatura_objetivo": 35.0,
                    "humedad_objetivo": 75.0,
                    "co2_objetivo": 3000.0,
                }, self.limits))
            while len(self.camaras) > n:
                self.camaras.pop()
            for k, cam in enumerate(self.camaras):
                cam.id = k
            return len(self.camaras)

    def update(self):
        now = time.time()
        dt_real = now - self.last_update
        self.last_update = now
        dt = dt_real * self.aceleracion

        # Si hay forecast y aceleración > 1, usar pronóstico para ambient
        amb_t, amb_h = self._ambient_for_sim_time()
        if self.aceleracion > 1.0 and self.forecast_hourly:
            self.ambient_temp = amb_t
            self.ambient_humidity = amb_h

        with self.lock:
            if self.mode in ("simulator", "shadow"):
                self.zapecado.update(dt, self.ambient_temp)
                self.secado.update(dt, self.ambient_temp, self.ambient_humidity)
                self.canchado.update(dt)
                for cam in self.camaras:
                    cam.update(dt, self.ambient_temp, self.ambient_humidity)

                # Flujo de masa: el zapecado quita humedad de la hoja (50% → 30-40%).
                # La salida del zapecado entra al secado, que termina de bajar a ~7-10%.
                # Mayor temperatura de zapecado y mayor velocidad de chips → más humedad evaporada.
                zap_eff = max(0.0, min(1.0, (self.zapecado.temperatura - 350) / 200.0))
                self.flujo["zap_out_humedad"] = 50.0 - 18.0 * zap_eff
                # La humedad inicial del secado tiende a la salida del zapecado
                # (modelo lento, integrado en el secado real más arriba). Acoplamos un
                # leve pull para que se vea la dependencia:
                self.secado.humedad += (self.flujo["zap_out_humedad"] - self.secado.humedad) * 0.001 * dt
                self.flujo["sec_out_humedad"] = self.secado.humedad
                self.flujo["can_out_kgh"] = self.throughput_kgh * 0.96
            else:
                # Modo Gemelo: no recalcula; solo aplica ruido pequeño y respeta clamps.
                # Los valores son escritos por API/Modbus/MQTT externos.
                pass

            snapshot = self._snapshot_locked()
            self.history.append(snapshot)
        return snapshot

    def get_state(self) -> Dict[str, Any]:
        with self.lock:
            return self._snapshot_locked()

    def get_history(self, n: int = 600):
        with self.lock:
            data = list(self.history)
        return data[-n:]

    def _snapshot_locked(self) -> Dict[str, Any]:
        z = self.zapecado
        s = self.secado
        c = self.canchado
        amb = self.ambient_temp
        # Vibrómetro: base + ruido + spike si rodamientos cerca del umbral
        # (no tenemos runtime hours acá - sólo base + ruido pseudo)
        zap_vib = round(2.5 + random.uniform(-0.3, 0.3) + (0.5 if z.estado_alimentacion else 0.0), 2)
        can_vib_x = round(1.8 + random.uniform(-0.2, 0.2) + (0.4 if c.estado else 0.0), 2)
        can_vib_y = round(1.6 + random.uniform(-0.2, 0.2) + (0.3 if c.estado else 0.0), 2)
        can_vib_z = round(0.9 + random.uniform(-0.1, 0.1), 2)
        # T rodamientos canchado: ambiente + delta por carga térmica del molino
        can_rod_t = round(amb + 22 + (c.velocidad_molino - 1500) * 0.008 +
                          random.uniform(-1.5, 1.5), 1) if c.estado else round(amb + 5, 1)
        # T salida yerba en zapecado: típicamente 1/3 de la T de gases (110-130°C)
        zap_t_yerba = round(amb + (z.temperatura - amb) * 0.32 + random.uniform(-2, 2), 1)
        # H salida zapecado (capacitivo / NIR): la del flujo
        zap_h_out_nir = round(self.flujo.get("zap_out_humedad", 25.0) + random.uniform(-0.8, 0.8), 2)
        # H NIR opcional en canchado (debe coincidir con secado)
        can_h_nir = round(s.humedad + random.uniform(-0.3, 0.3), 2)
        # Higrómetro bulbo húmedo: aire de extracción del secadero (T_húmedo)
        # Para aire saliendo del secadero: HR aire ~ 60-80% (saturado por evaporación)
        sec_t_aire_out = round(s.temperatura - 25 + random.uniform(-2, 2), 1)
        sec_hr_aire_extr = round(min(90, 60 + (z.temperatura - 200) * 0.08), 1)
        # T aire entrada secadero (setpoint cerca, con variación pequeña)
        sec_t_aire_in = round(s.temperatura + 8 + random.uniform(-1.5, 1.5), 1)

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode,
            "throughput_kgh": self.throughput_kgh,
            "flujo": {k: round(v, 3) for k, v in self.flujo.items()},
            "ambient": {
                "temp": round(self.ambient_temp, 2),
                "humidity": round(self.ambient_humidity, 2),
                **self.weather_meta,
            },
            "sim": {
                "aceleracion": self.aceleracion,
                "throughput_kgh": self.throughput_kgh,
                "mode": self.mode,
                "sim_clock": self.get_sim_clock().isoformat(),
                "forecast_count": len(self.forecast_hourly),
                "forecast_preview": [
                    {"time": pt[0].isoformat(), "temp": round(pt[1], 2), "hum": round(pt[2], 2)}
                    for pt in self.forecast_hourly[:24]
                ],
            },
            "zapecado": {
                "temperatura": round(z.temperatura, 2),
                "temperatura_obj": z.temperatura_obj,
                "temperatura_sp_efectivo": round(z.get_setpoint(), 1),
                "velocidad_tambor": z.velocidad_tambor,            # SP del operador
                "velocidad_tambor_real": round(z.vel_tambor_real(), 1),  # rpm efectiva
                "velocidad_chip": z.velocidad_chip,
                "estado_alimentacion": z.estado_alimentacion,
                "tau": z.tau,
                "pid": z.pid.to_dict(),
                "faults": {
                    "falla_quemador": z.falla_quemador,
                    "falla_motor_tambor": z.falla_motor_tambor,
                },
                "sensors": {
                    "t_gases_entrada": round(z.temperatura, 1),         # Termocupla K - tambor
                    "t_yerba_salida": zap_t_yerba,                       # Termocupla K - salida
                    "h_salida_nir": zap_h_out_nir,                       # Sensor capacitivo / NIR
                    "vibrometro": zap_vib,                               # eje del tambor (mm/s RMS)
                },
            },
            "secado": {
                "temperatura": round(s.temperatura, 2),
                "temperatura_obj": s.temperatura_obj,
                "humedad": round(s.humedad, 2),
                "humedad_obj": s.humedad_obj,
                "velocidad_aire": s.velocidad_aire,
                "posicion_calefactor": round(s.posicion_calefactor, 1),
                "posicion_calefactor_real": round(s.pos_cal_real(), 1),
                "velocidad_aire_real": round(s.vel_aire_real(), 2),
                "estado": s.estado,
                "tau_t": s.tau_t,
                "pid_t": s.pid_t.to_dict(),
                "pid_h": s.pid_h.to_dict(),
                "faults": {
                    "falla_ventilador": s.falla_ventilador,
                    "falla_serpentin": s.falla_serpentin,
                },
                "sensors": {
                    "t_aire_entrada": sec_t_aire_in,                     # PT100 / Termocupla K
                    "t_aire_salida": sec_t_aire_out,                     # PT100
                    "t_zona": round(s.temperatura, 1),                   # PT100 zona cintas
                    "h_final_nir": round(s.humedad, 2),                  # Higrómetro NIR
                    "h_bulbo_humedo": sec_hr_aire_extr,                  # bulbo húmedo extracción
                },
            },
            "canchado": {
                "velocidad_molino": c.velocidad_molino,                # SP del operador
                "velocidad_molino_real": round(c.vel_molino_real(), 1), # rpm efectiva
                "tamano_particula": round(c.tamano_particula, 2),
                "tamano_particula_obj": c.tamano_particula_obj,
                "tamano_particula_sp_efectivo": round(c.get_setpoint(), 2),
                "estado": c.estado,
                "tau_p": c.tau_p,
                "pid": c.pid.to_dict(),
                "faults": {
                    "falla_motor": c.falla_motor,
                    "rodamiento_caliente": c.rodamiento_caliente,
                },
                "sensors": {
                    "t_rodamientos": can_rod_t if not c.rodamiento_caliente else round(can_rod_t + 35, 1),
                    "vibrometro_x": can_vib_x if not c.rodamiento_caliente else round(can_vib_x + 4.0, 2),
                    "vibrometro_y": can_vib_y,                           # eje Y
                    "vibrometro_z": can_vib_z,                           # eje Z
                    "encoder_rpm": round(c.vel_molino_real(), 0),        # encoder rotor
                    "h_nir_salida": can_h_nir,                           # NIR opcional
                },
            },
            "camaras": [
                {
                    "id": cam.id,
                    "nombre": cam.nombre,
                    "temperatura": round(cam.temperatura, 2),
                    "humedad": round(cam.humedad, 2),
                    "co2": round(cam.co2, 1),
                    "carga_kg": cam.carga_kg,
                    "tiempo_maduracion": round(cam.tiempo_maduracion, 3),
                    "ventilador": cam.ventilador,
                    "vent_pos": round(cam.vent_pos, 1),
                    "ventilador_real": round(cam.vent_real() * 100, 1),
                    "vapor_real_kgh": round(cam.vapor_real_kgh(), 2),
                    "pid_t": cam.pid_t.to_dict(),
                    "temperatura_obj": cam.temperatura_obj,
                    "humedad_obj": cam.humedad_obj,
                    "co2_obj": cam.co2_obj,
                    "vapor_activo": cam.vapor_activo,
                    "vapor_caudal_kgh": cam.vapor_caudal_kgh,
                    "vapor_setpoint_temp": cam.vapor_setpoint_temp,
                    "vapor_setpoint_hum": cam.vapor_setpoint_hum,
                    "vapor_kg_acum": round(cam.vapor_kg_acum, 3),
                    "tau": cam.tau,
                    "faults": {
                        "falla_ventilador": cam.falla_ventilador,
                        "fuga_vapor": cam.fuga_vapor,
                        "puerta_abierta": cam.puerta_abierta,
                    },
                    "sensors": {
                        # PT100 doble: pared y centro de la pila
                        "pt100_pared": round(cam.temperatura + random.uniform(-0.4, 0.4), 2),
                        "pt100_centro_pila": round(
                            cam.temperatura + (0.5 + cam.carga_kg / 5000) + random.uniform(-0.3, 0.3), 2),
                        # Humedad relativa capacitivo
                        "hr_capacitivo": round(cam.humedad + random.uniform(-0.5, 0.5), 2),
                        # CO2 NDIR
                        "co2_ndir": round(cam.co2 + random.uniform(-8, 8), 0),
                        # Termoresistencia línea de vapor (si hay inyección)
                        "t_linea_vapor": (
                            round(120 + cam.vapor_caudal_kgh * 0.15 + random.uniform(-2, 2), 1)
                            if cam.vapor_activo and cam.vapor_caudal_kgh > 0 else 0.0
                        ),
                        # Caudalímetro vapor másico (kg/h)
                        "caudal_vapor": (
                            round(cam.vapor_caudal_kgh + random.uniform(-0.4, 0.4), 2)
                            if cam.vapor_activo else 0.0
                        ),
                    },
                }
                for cam in self.camaras
            ],
        }
