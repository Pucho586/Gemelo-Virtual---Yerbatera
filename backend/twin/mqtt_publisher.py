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
import logging
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class YerbaMqttPublisher:
    """Publica el estado del simulador + se suscribe a comandos externos.

    Topics de comando (bidireccional):
      yerba/cmd/zapecado     payload: {velocidad_chip:50, temperatura_obj:480, pid:{enabled:true,kp:0.2}}
      yerba/cmd/secado       payload: {posicion_calefactor:75, pid_t:{enabled:true,sp:95}}
      yerba/cmd/canchado     payload: {velocidad_molino:80, falla_motor:true}
      yerba/cmd/camara/0     payload: {vapor_caudal_kgh:30, vapor_activo:true}
      yerba/cmd/weather      payload: {temperature:18,humidity:75}  (override manual)
      yerba/cmd/sim          payload: {aceleracion:3600, throughput_kgh:1200}

    Cualquier campo del Patch correspondiente es aceptado. Útil para Node-RED.
    """

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
        self.client.on_message = self._on_message
        if self.username:
            self.client.username_pw_set(self.username, self.password)

    def start(self):
        try:
            self.client.connect(self.broker, self.port, keepalive=self.keepalive)
            # Suscribirse a topics de comando (bidireccional)
            cmd_topic = f"{self.topic_base}/cmd/#"
            self.client.subscribe(cmd_topic, qos=0)
            self.client.loop_start()
            threading.Thread(target=self._publish_loop, daemon=True).start()
            logger.info(f"MQTT conectado a {self.broker}:{self.port} · publica '{self.topic_base}/*' · escucha '{cmd_topic}'")
        except Exception as e:
            logger.error(f"Error al conectar al broker MQTT: {e}")

    # ---- BIDIRECCIONAL: handler de comandos entrantes ----
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8") or "{}")
        except Exception:
            try:
                # permitir número crudo: yerba/cmd/zapecado/velocidad_chip "50"
                payload_raw = msg.payload.decode("utf-8").strip()
                payload = float(payload_raw) if payload_raw and payload_raw[0] in "0123456789-." else payload_raw
            except Exception:
                logger.warning(f"MQTT payload no parseable: topic={msg.topic} payload={msg.payload!r}")
                return

        parts = msg.topic.split("/")
        # Espera: yerba/cmd/<destino>[/<idx_o_campo>][/<campo>]
        if len(parts) < 3 or parts[1] != "cmd":
            return
        dest = parts[2]
        sub = parts[3] if len(parts) > 3 else None
        field = parts[4] if len(parts) > 4 else None

        # Si payload es un valor crudo + campo en topic, armar dict
        if field and not isinstance(payload, dict):
            payload = {field: payload}
        elif sub and not isinstance(payload, dict) and dest in ("zapecado", "secado", "canchado", "weather", "sim"):
            payload = {sub: payload}

        if not isinstance(payload, dict):
            logger.warning(f"MQTT cmd ignored, payload no es dict: {msg.topic} → {payload}")
            return

        try:
            if dest == "zapecado":
                self.simulador.set_zapecado(**payload)
            elif dest == "secado":
                self.simulador.set_secado(**payload)
            elif dest == "canchado":
                self.simulador.set_canchado(**payload)
            elif dest == "camara":
                # yerba/cmd/camara/<idx> payload={field:value}
                idx = int(sub) if sub is not None and sub.isdigit() else None
                if idx is not None:
                    self.simulador.set_camara(idx, **payload)
            elif dest == "weather":
                t = payload.get("temperature")
                h = payload.get("humidity")
                if t is not None and h is not None:
                    from datetime import datetime, timezone
                    self.simulador.set_weather(float(t), float(h), {
                        "city": self.simulador.weather_meta.get("city", "MQTT"),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "source": "mqtt-cmd",
                    })
            elif dest == "sim":
                if "aceleracion" in payload:
                    self.simulador.aceleracion = float(payload["aceleracion"])
                if "throughput_kgh" in payload:
                    self.simulador.throughput_kgh = float(payload["throughput_kgh"])
                if "mode" in payload:
                    self.simulador.mode = str(payload["mode"])
            logger.info(f"MQTT cmd OK: {msg.topic} → {payload}")
        except Exception as e:
            logger.error(f"MQTT cmd error {msg.topic}: {e}")

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
                logger.error(f"Error publicando MQTT: {e}")
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
