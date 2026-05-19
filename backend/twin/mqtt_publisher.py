# --- Archivo: core/mqtt_publisher.py ---
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
            except Exception as e:
                print("Error publicando MQTT:", e)
            time.sleep(self.interval)

    def _publicar_zapecado(self):
        z = self.simulador.zapecado
        payload = json.dumps({
            "temperatura": round(z.temperatura, 1),
            "velocidad_tambor": z.velocidad_tambor,
            "velocidad_chip": z.velocidad_chip,
            "estado_alimentacion": z.estado_alimentacion
        })
        self.client.publish(f"{self.topic_base}/zapecado", payload)

    def _publicar_secado(self):
        s = self.simulador.secado
        payload = json.dumps({
            "temperatura": round(s.temperatura, 1),
            "humedad": round(s.humedad, 1),
            "velocidad_aire": s.velocidad_aire,
            "estado": s.estado
        })
        self.client.publish(f"{self.topic_base}/secado", payload)

    def _publicar_canchado(self):
        c = self.simulador.canchado
        payload = json.dumps({
            "velocidad_molino": c.velocidad_molino,
            "tamano_particula": round(c.tamano_particula, 1),
            "estado": c.estado
        })
        self.client.publish(f"{self.topic_base}/canchado", payload)

    def _publicar_camaras(self):
        for i, cam in enumerate(self.simulador.camaras):
            payload = json.dumps({
                "temperatura": round(cam.temperatura, 1),
                "humedad": round(cam.humedad, 1),
                "co2": cam.co2,
                "carga": cam.carga_kg,
                "dias": round(cam.tiempo_maduracion, 2),
                "ventilador": cam.ventilador
            })
            topic = f"{self.topic_base}/camara_{i+1}"
            self.client.publish(topic, payload)