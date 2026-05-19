# --- Archivo: twin/yerba_simulator.py ---
"""
Simulador realista del proceso de yerba mate (versión mejorada).

Mejoras sobre la versión Tkinter original:
- Considera temperatura y humedad ambiente reales (Open-Meteo) en zapecado,
  secado y cámaras de maduración.
- Zapecado: el setpoint varía dinámicamente con la velocidad de chips y la
  temperatura ambiente (cuando se corta la alimentación, el sistema se
  enfría hacia la temperatura ambiente real en lugar de un valor fijo).
- Secado: el "piso" de humedad se ajusta a la humedad ambiente.
- Cámaras: la pérdida térmica considera la diferencia con el ambiente.
- Historial circular en memoria para gráficos y exportación.
- Estado consultable como dict serializable (JSON-safe).
"""

import time
import random
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Any

DEFAULT_LIMITS = {
    "temp_min": 10,
    "temp_max": 120,
    "hum_min": 5,
    "hum_max": 95,
    "co2_min": 400,
    "co2_max": 8000,
    "tau_camera": 600,  # constante de tiempo de cámaras (s)
}

# Producción de CO2 por kg de yerba en maduración (ppm * s^-1 * kg^-1)
CO2_RATE = 0.03


# ---------------- Subsistemas ----------------
class Zapecado:
    """Etapa de zapecado (golpe térmico breve).

    Soporta:
    - `temperatura_obj`: SP manual (si es None usa SP dinámico vel.chips)
    - `tau`: constante de tiempo (s) - usuario puede acelerar/lentar respuesta
    - Fallas: `falla_quemador`, `falla_motor_tambor`
    """

    def __init__(self, config: Dict):
        self.temperatura = float(config.get("temperatura_inicial", 450))
        self.velocidad_tambor = float(config.get("velocidad_tambor", 15))
        self.velocidad_chip = float(config.get("velocidad_chip", 30))
        self.estado_alimentacion = True
        self.tau = float(config.get("tau", 90.0))  # respuesta térmica zapecado (s)
        # SP manual (None = SP dinámico calculado a partir de vel.chips)
        self.temperatura_obj: float | None = config.get("temperatura_objetivo")
        if self.temperatura_obj is not None:
            self.temperatura_obj = float(self.temperatura_obj)
        # Fallas
        self.falla_quemador = False     # quemador no calienta (target = ambient)
        self.falla_motor_tambor = False  # tambor parado (no avance, baja temp salida)

    def get_setpoint(self) -> float:
        if self.temperatura_obj is not None:
            return float(self.temperatura_obj)
        return max(350.0, min(600.0, 400.0 + min(self.velocidad_chip, 200) * 1.0))

    def update(self, dt: float, ambient_temp: float):
        if self.falla_quemador or not self.estado_alimentacion:
            target = ambient_temp
        else:
            target = self.get_setpoint()
        self.temperatura += (target - self.temperatura) / self.tau * dt
        self.temperatura += random.uniform(-0.4, 0.4)
        self.temperatura = max(ambient_temp - 5, min(620.0, self.temperatura))


class Secado:
    """Etapa de secado lento.

    Soporta:
    - `temperatura_obj`: SP de temperatura (default 95°C)
    - `humedad_obj`: SP de humedad objetivo final (default ~7%)
    - `tau_t`: constante de tiempo térmica (s)
    - Fallas: `falla_ventilador`, `falla_serpentin` (calefactor)
    """

    def __init__(self, config: Dict):
        self.temperatura = float(config.get("temperatura", 90))
        self.humedad = float(config.get("humedad", 30))
        self.velocidad_aire = float(config.get("velocidad_aire", 2.5))
        self.estado = True
        self.tau_t = float(config.get("tau_t", 120.0))  # respuesta térmica (s)
        self.temperatura_obj = float(config.get("temperatura_objetivo", 95.0))
        self.humedad_obj = float(config.get("humedad_objetivo", 7.0))
        self.falla_ventilador = False   # corta circulación de aire (h no baja)
        self.falla_serpentin = False    # calefactor no calienta

    def update(self, dt: float, ambient_temp: float, ambient_humidity: float):
        if self.falla_serpentin or not self.estado:
            target_t = ambient_temp
        else:
            target_t = self.temperatura_obj
        self.temperatura += (target_t - self.temperatura) / self.tau_t * dt
        self.temperatura += random.uniform(-0.2, 0.2)
        self.temperatura = max(ambient_temp - 5, min(120.0, self.temperatura))

        # Humedad: piso dinámico relacionado al ambiente y al SP del operador.
        piso = max(self.humedad_obj, ambient_humidity * 0.25)
        v_efectiva = 0.0 if self.falla_ventilador else max(self.velocidad_aire, 0.0)
        if self.estado and not self.falla_serpentin and self.humedad > piso:
            tasa = 0.0025 * (v_efectiva ** 0.5)
            self.humedad -= tasa * dt * (self.humedad - piso)
        elif not self.estado or self.falla_serpentin:
            # Se equilibra con el ambiente cuando está apagado o calefactor caído
            self.humedad += (ambient_humidity - self.humedad) / 600 * dt
        self.humedad += random.uniform(-0.05, 0.05)
        self.humedad = max(3.0, min(95.0, self.humedad))


class Canchado:
    """Etapa de canchado (molienda gruesa).

    Soporta:
    - `tamano_particula_obj`: SP de grosor de canchada (mm). Si es None usa
      SP dinámico = 10 - 0.07·rpm.
    - `tau_p`: respuesta del molino (s) - cuánto tarda en converger al SP.
    - Fallas: `falla_motor`, `rodamiento_caliente`.
    """

    def __init__(self, config: Dict):
        self.velocidad_molino = float(config.get("velocidad_molino", 60))
        self.estado = True
        self.tamano_particula = 10.0  # mm
        self.tamano_particula_obj: float | None = config.get("tamano_particula_objetivo")
        if self.tamano_particula_obj is not None:
            self.tamano_particula_obj = float(self.tamano_particula_obj)
        self.tau_p = float(config.get("tau_p", 5.0))
        self.falla_motor = False
        self.rodamiento_caliente = False  # eleva T rodamientos sin parar

    def get_setpoint(self) -> float:
        if self.tamano_particula_obj is not None:
            return float(self.tamano_particula_obj)
        return max(0.5, 10.0 - self.velocidad_molino * 0.07)

    def update(self, dt: float):
        if self.falla_motor or not self.estado:
            # Molino parado: la última carga queda igual
            self.tamano_particula += random.uniform(-0.02, 0.02)
        else:
            target = self.get_setpoint()
            self.tamano_particula += (target - self.tamano_particula) / self.tau_p * dt
            self.tamano_particula += random.uniform(-0.08, 0.08)
        self.tamano_particula = max(0.3, min(15.0, self.tamano_particula))


class CamaraMaduracion:
    """Cámara de maduración de yerba (estacionamiento controlado).

    Ahora con inyección de vapor: cuando está activa, fuerza T y H hacia los
    setpoints de vapor con una constante de tiempo más corta (acción rápida).
    El caudal de vapor (kg/h) escala qué tan rápido se llega al setpoint.
    """

    def __init__(self, camara_id: int, config: Dict, limits: Dict):
        self.id = camara_id
        self.nombre = config["nombre"]
        self.temperatura_obj = float(config["temperatura_objetivo"])
        self.humedad_obj = float(config["humedad_objetivo"])
        self.co2_obj = float(config["co2_objetivo"])

        self.temperatura = self.temperatura_obj + 3.0
        self.humedad = self.humedad_obj - 5.0
        self.co2 = 1800.0
        self.ventilador = True
        self.carga_kg = 0.0
        self.tiempo_maduracion = 0.0  # días

        # Inyección de vapor
        self.vapor_activo: bool = bool(config.get("vapor_activo", False))
        self.vapor_caudal_kgh: float = float(config.get("vapor_caudal_kgh", 0.0))   # 0-50 kg/h
        self.vapor_setpoint_temp: float = float(config.get("vapor_setpoint_temp", self.temperatura_obj))
        self.vapor_setpoint_hum: float = float(config.get("vapor_setpoint_hum", self.humedad_obj))
        self.vapor_kg_acum: float = 0.0  # vapor inyectado acumulado (para costos)

        # Fallas
        self.falla_ventilador = False    # no circula aire (CO2 sube, T no converge)
        self.fuga_vapor = False           # vapor "se escapa" - se inyecta sin efecto útil
        self.puerta_abierta = False       # techo/puerta abierta: pérdida hacia ambiente alta

        self.lim = limits
        self.tau = float(config.get("tau", limits.get("tau_camera", 600)))

    def update(self, dt: float, ambient_temp: float, ambient_humidity: float):
        # Maduración real solo si hay carga
        if self.carga_kg > 0:
            self.tiempo_maduracion += dt / 86400.0

        # Fallas que alteran el modo
        vent_efectivo = self.ventilador and not self.falla_ventilador
        vapor_efectivo = self.vapor_activo and self.vapor_caudal_kgh > 0 and not self.fuga_vapor

        # Tres modos: vapor activo / solo ventilador / pasivo
        if vapor_efectivo:
            # Vapor inyectado: tau más corto y proporcional al caudal
            speed = max(0.05, min(1.0, self.vapor_caudal_kgh / 50.0))
            tau_steam = self.tau * (0.1 + 0.2 * (1.0 - speed))  # 60-180s típicamente
            target_t = self.vapor_setpoint_temp
            target_h = self.vapor_setpoint_hum
            self.temperatura += (target_t - self.temperatura) / tau_steam * dt
            self.humedad += (target_h - self.humedad) / tau_steam * dt
            # Acumular consumo de vapor (kg). dt en segundos sim.
            self.vapor_kg_acum += self.vapor_caudal_kgh * dt / 3600.0
        elif vent_efectivo:
            # Solo ventilación: tau original hacia setpoint clásico
            target_t = self.temperatura_obj
            target_h = self.humedad_obj
            self.temperatura += (target_t - self.temperatura) / self.tau * dt
            self.humedad += (target_h - self.humedad) / self.tau * dt
        else:
            # Pasivo: 70% ambiente, 30% setpoint
            target_t = 0.7 * ambient_temp + 0.3 * self.temperatura_obj
            target_h = 0.7 * ambient_humidity + 0.3 * self.humedad_obj
            self.temperatura += (target_t - self.temperatura) / self.tau * dt
            self.humedad += (target_h - self.humedad) / self.tau * dt

        # Puerta/techo abierta: pérdida acelerada hacia ambiente
        if self.puerta_abierta:
            self.temperatura += (ambient_temp - self.temperatura) * 0.02 * dt
            self.humedad += (ambient_humidity - self.humedad) * 0.02 * dt

        # Fuga de vapor: si está activo el vapor con fuga, igual se consume pero
        # sólo aporta parcial al ambiente interno
        if self.vapor_activo and self.fuga_vapor:
            self.vapor_kg_acum += self.vapor_caudal_kgh * dt / 3600.0 * 0.6

        # Producción de CO2 por respiración de la yerba
        self.co2 += CO2_RATE * self.carga_kg * dt
        if vent_efectivo or vapor_efectivo:
            self.co2 -= (self.co2 - self.co2_obj) * 0.15 * dt
        else:
            # se acerca al CO2 ambiente (~420 ppm)
            self.co2 += (420.0 - self.co2) * 0.005 * dt

        self.temperatura += random.uniform(-0.04, 0.04)
        self.humedad += random.uniform(-0.04, 0.04)

        self.temperatura = max(self.lim["temp_min"], min(self.lim["temp_max"], self.temperatura))
        self.humedad = max(self.lim["hum_min"], min(self.lim["hum_max"], self.humedad))
        self.co2 = max(self.lim["co2_min"], min(self.lim["co2_max"], self.co2))


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

        # Historial circular para gráficos (≈30 min a 1 punto/s)
        self.history: deque = deque(maxlen=1800)

    # ---------- API ----------
    def set_weather(self, temp: float, humidity: float, meta: Dict[str, Any]):
        with self.lock:
            self.ambient_temp = float(temp)
            self.ambient_humidity = float(humidity)
            self.weather_meta.update(meta)

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
                     falla_quemador=None, falla_motor_tambor=None):
        with self.lock:
            z = self.zapecado
            if velocidad_tambor is not None:
                z.velocidad_tambor = float(velocidad_tambor)
            if velocidad_chip is not None:
                z.velocidad_chip = float(velocidad_chip)
            if estado_alimentacion is not None:
                z.estado_alimentacion = bool(estado_alimentacion)
            if temperatura_obj is not None:
                # None / 0 / cadena vacía => modo SP dinámico
                z.temperatura_obj = (None if temperatura_obj in ("", None) else float(temperatura_obj))
            if tau is not None:
                z.tau = max(5.0, float(tau))
            if falla_quemador is not None:
                z.falla_quemador = bool(falla_quemador)
            if falla_motor_tambor is not None:
                z.falla_motor_tambor = bool(falla_motor_tambor)

    def set_secado(self, *, velocidad_aire=None, estado=None,
                   temperatura_obj=None, humedad_obj=None, tau_t=None,
                   falla_ventilador=None, falla_serpentin=None):
        with self.lock:
            s = self.secado
            if velocidad_aire is not None:
                s.velocidad_aire = float(velocidad_aire)
            if estado is not None:
                s.estado = bool(estado)
            if temperatura_obj is not None:
                s.temperatura_obj = float(temperatura_obj)
            if humedad_obj is not None:
                s.humedad_obj = float(humedad_obj)
            if tau_t is not None:
                s.tau_t = max(5.0, float(tau_t))
            if falla_ventilador is not None:
                s.falla_ventilador = bool(falla_ventilador)
            if falla_serpentin is not None:
                s.falla_serpentin = bool(falla_serpentin)

    def set_canchado(self, *, velocidad_molino=None, estado=None,
                     tamano_particula_obj=None, tau_p=None,
                     falla_motor=None, rodamiento_caliente=None):
        with self.lock:
            c = self.canchado
            if velocidad_molino is not None:
                c.velocidad_molino = float(velocidad_molino)
            if estado is not None:
                c.estado = bool(estado)
            if tamano_particula_obj is not None:
                c.tamano_particula_obj = (None if tamano_particula_obj in ("", None) else float(tamano_particula_obj))
            if tau_p is not None:
                c.tau_p = max(0.5, float(tau_p))
            if falla_motor is not None:
                c.falla_motor = bool(falla_motor)
            if rodamiento_caliente is not None:
                c.rodamiento_caliente = bool(rodamiento_caliente)

    def set_camara(self, idx: int, *, carga_kg=None, ventilador=None,
                   temperatura_obj=None, humedad_obj=None, co2_obj=None,
                   vapor_activo=None, vapor_caudal_kgh=None,
                   vapor_setpoint_temp=None, vapor_setpoint_hum=None,
                   tau=None,
                   falla_ventilador=None, fuga_vapor=None, puerta_abierta=None):
        with self.lock:
            if idx < 0 or idx >= len(self.camaras):
                return
            cam = self.camaras[idx]
            if carga_kg is not None:
                cam.carga_kg = float(carga_kg)
            if ventilador is not None:
                cam.ventilador = bool(ventilador)
            if temperatura_obj is not None:
                cam.temperatura_obj = float(temperatura_obj)
            if humedad_obj is not None:
                cam.humedad_obj = float(humedad_obj)
            if co2_obj is not None:
                cam.co2_obj = float(co2_obj)
            if vapor_activo is not None:
                cam.vapor_activo = bool(vapor_activo)
            if vapor_caudal_kgh is not None:
                cam.vapor_caudal_kgh = max(0.0, min(200.0, float(vapor_caudal_kgh)))
            if vapor_setpoint_temp is not None:
                cam.vapor_setpoint_temp = float(vapor_setpoint_temp)
            if vapor_setpoint_hum is not None:
                cam.vapor_setpoint_hum = float(vapor_setpoint_hum)
            if tau is not None:
                cam.tau = max(10.0, float(tau))
            if falla_ventilador is not None:
                cam.falla_ventilador = bool(falla_ventilador)
            if fuga_vapor is not None:
                cam.fuga_vapor = bool(fuga_vapor)
            if puerta_abierta is not None:
                cam.puerta_abierta = bool(puerta_abierta)

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
            "zapecado": {
                "temperatura": round(z.temperatura, 2),
                "temperatura_obj": z.temperatura_obj,
                "temperatura_sp_efectivo": round(z.get_setpoint(), 1),
                "velocidad_tambor": z.velocidad_tambor,
                "velocidad_chip": z.velocidad_chip,
                "estado_alimentacion": z.estado_alimentacion,
                "tau": z.tau,
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
                "estado": s.estado,
                "tau_t": s.tau_t,
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
                "velocidad_molino": c.velocidad_molino,
                "tamano_particula": round(c.tamano_particula, 2),
                "tamano_particula_obj": c.tamano_particula_obj,
                "tamano_particula_sp_efectivo": round(c.get_setpoint(), 2),
                "estado": c.estado,
                "tau_p": c.tau_p,
                "faults": {
                    "falla_motor": c.falla_motor,
                    "rodamiento_caliente": c.rodamiento_caliente,
                },
                "sensors": {
                    "t_rodamientos": can_rod_t if not c.rodamiento_caliente else round(can_rod_t + 35, 1),
                    "vibrometro_x": can_vib_x if not c.rodamiento_caliente else round(can_vib_x + 4.0, 2),
                    "vibrometro_y": can_vib_y,                           # eje Y
                    "vibrometro_z": can_vib_z,                           # eje Z
                    "encoder_rpm": round(c.velocidad_molino, 0) if c.estado and not c.falla_motor else 0,
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
