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
    """Etapa de zapecado (golpe térmico breve)."""

    def __init__(self, config: Dict):
        self.temperatura = float(config.get("temperatura_inicial", 450))
        self.velocidad_tambor = float(config.get("velocidad_tambor", 15))
        self.velocidad_chip = float(config.get("velocidad_chip", 30))
        self.estado_alimentacion = True
        self.tau = 90.0  # respuesta térmica zapecado (s)

    def update(self, dt: float, ambient_temp: float):
        # Setpoint dinámico: base 400°C + aporte por carga de chips, max 600°C.
        # Sin alimentación, el horno se enfría hacia el ambiente real.
        if self.estado_alimentacion:
            target = 400.0 + min(self.velocidad_chip, 200) * 1.0  # 400-600°C
            target = max(350.0, min(600.0, target))
        else:
            target = ambient_temp
        self.temperatura += (target - self.temperatura) / self.tau * dt
        self.temperatura += random.uniform(-0.4, 0.4)
        self.temperatura = max(ambient_temp - 5, min(620.0, self.temperatura))


class Secado:
    """Etapa de secado lento."""

    def __init__(self, config: Dict):
        self.temperatura = float(config.get("temperatura", 90))
        self.humedad = float(config.get("humedad", 30))
        self.velocidad_aire = float(config.get("velocidad_aire", 2.5))
        self.estado = True
        self.tau_t = 120.0  # respuesta térmica (s)

    def update(self, dt: float, ambient_temp: float, ambient_humidity: float):
        # La cámara de secado tiende a su setpoint operativo si está activa,
        # y al ambiente si no.
        target_t = 95.0 if self.estado else ambient_temp
        self.temperatura += (target_t - self.temperatura) / self.tau_t * dt
        self.temperatura += random.uniform(-0.2, 0.2)
        self.temperatura = max(ambient_temp - 5, min(120.0, self.temperatura))

        # Humedad: piso dinámico relacionado al ambiente (no puede secar
        # por debajo de ~ambient/4). Velocidad de aire acelera el descenso.
        piso = max(5.0, ambient_humidity * 0.25)
        if self.estado and self.humedad > piso:
            tasa = 0.0025 * (max(self.velocidad_aire, 0.0) ** 0.5)
            self.humedad -= tasa * dt * (self.humedad - piso)
        elif not self.estado:
            # Se equilibra con el ambiente cuando está apagado
            self.humedad += (ambient_humidity - self.humedad) / 600 * dt
        self.humedad += random.uniform(-0.05, 0.05)
        self.humedad = max(3.0, min(95.0, self.humedad))


class Canchado:
    """Etapa de canchado (molienda gruesa)."""

    def __init__(self, config: Dict):
        self.velocidad_molino = float(config.get("velocidad_molino", 60))
        self.estado = True
        self.tamano_particula = 10.0  # mm

    def update(self, dt: float):
        if self.estado:
            target = max(0.5, 10.0 - self.velocidad_molino * 0.07)
            # respuesta rápida
            self.tamano_particula += (target - self.tamano_particula) / 5.0 * dt
            self.tamano_particula += random.uniform(-0.08, 0.08)
        else:
            # molino parado: la última carga queda igual
            self.tamano_particula += random.uniform(-0.02, 0.02)
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

        self.lim = limits
        self.tau = float(limits.get("tau_camera", 600))

    def update(self, dt: float, ambient_temp: float, ambient_humidity: float):
        # Maduración real solo si hay carga
        if self.carga_kg > 0:
            self.tiempo_maduracion += dt / 86400.0

        # Tres modos: vapor activo / solo ventilador / pasivo
        if self.vapor_activo and self.vapor_caudal_kgh > 0:
            # Vapor inyectado: tau más corto y proporcional al caudal (más kg/h → más rápido)
            # 50 kg/h = factor 1.0 (tau 60 s). 5 kg/h = factor 0.1 (tau 600 s).
            speed = max(0.05, min(1.0, self.vapor_caudal_kgh / 50.0))
            tau_steam = self.tau * (0.1 + 0.2 * (1.0 - speed))  # 60-180s típicamente
            target_t = self.vapor_setpoint_temp
            target_h = self.vapor_setpoint_hum
            self.temperatura += (target_t - self.temperatura) / tau_steam * dt
            self.humedad += (target_h - self.humedad) / tau_steam * dt
            # Acumular consumo de vapor (kg). dt en segundos sim.
            self.vapor_kg_acum += self.vapor_caudal_kgh * dt / 3600.0
        elif self.ventilador:
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

        # Producción de CO2 por respiración de la yerba
        self.co2 += CO2_RATE * self.carga_kg * dt
        if self.ventilador or (self.vapor_activo and self.vapor_caudal_kgh > 0):
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

    def set_zapecado(self, *, velocidad_tambor=None, velocidad_chip=None, estado_alimentacion=None):
        with self.lock:
            z = self.zapecado
            if velocidad_tambor is not None:
                z.velocidad_tambor = float(velocidad_tambor)
            if velocidad_chip is not None:
                z.velocidad_chip = float(velocidad_chip)
            if estado_alimentacion is not None:
                z.estado_alimentacion = bool(estado_alimentacion)

    def set_secado(self, *, velocidad_aire=None, estado=None):
        with self.lock:
            s = self.secado
            if velocidad_aire is not None:
                s.velocidad_aire = float(velocidad_aire)
            if estado is not None:
                s.estado = bool(estado)

    def set_canchado(self, *, velocidad_molino=None, estado=None):
        with self.lock:
            c = self.canchado
            if velocidad_molino is not None:
                c.velocidad_molino = float(velocidad_molino)
            if estado is not None:
                c.estado = bool(estado)

    def set_camara(self, idx: int, *, carga_kg=None, ventilador=None,
                   temperatura_obj=None, humedad_obj=None, co2_obj=None,
                   vapor_activo=None, vapor_caudal_kgh=None,
                   vapor_setpoint_temp=None, vapor_setpoint_hum=None):
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
                "velocidad_tambor": z.velocidad_tambor,
                "velocidad_chip": z.velocidad_chip,
                "estado_alimentacion": z.estado_alimentacion,
            },
            "secado": {
                "temperatura": round(s.temperatura, 2),
                "humedad": round(s.humedad, 2),
                "velocidad_aire": s.velocidad_aire,
                "estado": s.estado,
            },
            "canchado": {
                "velocidad_molino": c.velocidad_molino,
                "tamano_particula": round(c.tamano_particula, 2),
                "estado": c.estado,
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
                }
                for cam in self.camaras
            ],
        }
