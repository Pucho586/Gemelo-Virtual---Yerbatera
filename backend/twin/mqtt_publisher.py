# --- Archivo: twin/mqtt_publisher.py ---
"""Publica el estado completo del simulador en MQTT.

Topics (todos JSON):
- yerba/zapecado, yerba/secado, yerba/canchado, yerba/camara_{N}
  → PV, manipuladas, SP, PIDs, fallas
- yerba/ambient → T y HR ambiente + ciudad + source (open-meteo/manual)
- yerba/sim → reloj simulado, aceleración, throughput
- yerba/forecast → próximas 24h del pronóstico (cuando hay)
"""
import json
import time
import threading
import paho.mqtt.client as mqtt


class YerbaMqttPublisher:
    def __init__(self, simulador, config):
        self.simulador = simulador
        self.broker = config.get('broker', 'localhost')
        self.port = config.get('port', 1883)
        self.topic_base = config.get('topic', 'yerba')
        self.username = config.get('user', '')
        self.password = config.get('pass', '')
        self.interval = config.get('interval', 5)
        self.keepalive = config.get('keepalive', 60)
        self.client = mqtt.Client()
        if self.username:
            self.client.username_pw_set(self.username, self.password)

    def start(self):
        try:
            self.client.connect(self.broker, self.port, keepalive=self.keepalive)
            threading.Thread(target=self._publish_loop, daemon=True).start()
            print("MQTT Publisher conectado a:", self.broker)
        except Exception as e:
            print("Error al conectar al broker MQTT:", e)

    def _publish_loop(self):
        while True:
            try:
                self._publicar_zapecado()
                self._publicar_secado()
                self._publicar_canchado()
                self._publicar_camaras()
                self._publicar_ambient()
                self._publicar_sim()
                self._publicar_forecast()
            except Exception as e:
                print("Error publicando MQTT:", e)
            time.sleep(self.interval)

    def _pub(self, topic, payload):
        self.client.publish(f"{self.topic_base}/{topic}", json.dumps(payload))

    def _publicar_zapecado(self):
        z = self.simulador.zapecado
        self._pub("zapecado", {
            "pv_temperatura": round(z.temperatura, 2),
            "sp_temperatura": z.temperatura_obj,
            "manipuladas": {
                "velocidad_chip": z.velocidad_chip,
                "velocidad_tambor": z.velocidad_tambor,
                "estado_alimentacion": z.estado_alimentacion,
                "vel_chip_real": z.vel_chip_real(),
                "vel_tambor_real": z.vel_tambor_real(),
            },
            "pid": z.pid.to_dict(),
            "faults": {
                "falla_quemador": z.falla_quemador,
                "falla_motor_tambor": z.falla_motor_tambor,
            },
        })

    def _publicar_secado(self):
        s = self.simulador.secado
        self._pub("secado", {
            "pv_temperatura": round(s.temperatura, 2),
            "pv_humedad": round(s.humedad, 2),
            "sp_temperatura": s.temperatura_obj,
            "sp_humedad": s.humedad_obj,
            "manipuladas": {
                "posicion_calefactor": round(s.posicion_calefactor, 2),
                "velocidad_aire": s.velocidad_aire,
                "estado": s.estado,
                "pos_cal_real": s.pos_cal_real(),
                "vel_aire_real": s.vel_aire_real(),
            },
            "pid_t": s.pid_t.to_dict(),
            "pid_h": s.pid_h.to_dict(),
            "faults": {
                "falla_ventilador": s.falla_ventilador,
                "falla_serpentin": s.falla_serpentin,
            },
        })

    def _publicar_canchado(self):
        c = self.simulador.canchado
        self._pub("canchado", {
            "pv_tamano_particula": round(c.tamano_particula, 3),
            "sp_tamano_particula": c.tamano_particula_obj,
            "manipuladas": {
                "velocidad_molino": c.velocidad_molino,
                "estado": c.estado,
                "vel_molino_real": c.vel_molino_real(),
            },
            "pid": c.pid.to_dict(),
            "faults": {
                "falla_motor": c.falla_motor,
                "rodamiento_caliente": c.rodamiento_caliente,
            },
        })

    def _publicar_camaras(self):
        for i, cam in enumerate(self.simulador.camaras):
            self._pub(f"camara_{i+1}", {
                "pv_temperatura": round(cam.temperatura, 2),
                "pv_humedad": round(cam.humedad, 2),
                "pv_co2": round(cam.co2, 0),
                "sp_temperatura": cam.temperatura_obj,
                "sp_humedad": cam.humedad_obj,
                "sp_co2": cam.co2_obj,
                "manipuladas": {
                    "ventilador": cam.ventilador,
                    "vent_pos": cam.vent_pos,
                    "vapor_activo": cam.vapor_activo,
                    "vapor_caudal_kgh": cam.vapor_caudal_kgh,
                    "ventilador_real_pct": cam.vent_real() * 100,
                    "vapor_real_kgh": cam.vapor_real_kgh(),
                },
                "pid_t": cam.pid_t.to_dict(),
                "carga_kg": cam.carga_kg,
                "dias_maduracion": round(cam.tiempo_maduracion, 3),
                "vapor_kg_acum": round(cam.vapor_kg_acum, 2),
                "faults": {
                    "falla_ventilador": cam.falla_ventilador,
                    "fuga_vapor": cam.fuga_vapor,
                    "puerta_abierta": cam.puerta_abierta,
                },
            })

    def _publicar_ambient(self):
        self._pub("ambient", {
            "temperatura": round(self.simulador.ambient_temp, 2),
            "humedad": round(self.simulador.ambient_humidity, 2),
            **(self.simulador.weather_meta or {}),
        })

    def _publicar_sim(self):
        self._pub("sim", {
            "aceleracion": self.simulador.aceleracion,
            "throughput_kgh": self.simulador.throughput_kgh,
            "mode": self.simulador.mode,
            "sim_clock": self.simulador.get_sim_clock().isoformat(),
        })

    def _publicar_forecast(self):
        """Publica las próximas 24 horas del forecast (si hay)."""
        fc = getattr(self.simulador, "forecast_hourly", []) or []
        if not fc:
            return
        # tomar máximo 24 puntos
        sample = [{"time": pt[0].isoformat(), "temp": round(pt[1], 2), "hum": round(pt[2], 2)}
                  for pt in fc[:24]]
        self._pub("forecast", {"hourly_next_24h": sample})
