# --- Archivo: core/opcua_server.py ---
from opcua import Server
import time
import threading

class YerbaOpcUaServer:
    def __init__(self, simulador, config):
        self.simulador = simulador

        self.host = config.get("host", "0.0.0.0")
        self.port = config.get("port", 4840)
        self.path = config.get("path", "/yerba/")
        self.nombre = config.get("nombre", "Yerba OPC UA Server")
        self.namespace = config.get("namespace", "YerbaProcess")
        self.interval = config.get("interval", 2000) / 1000.0  # convertir a segundos
        self.mode = config.get("mode", "None")
        self.policy = config.get("policy", "None")
        self.cert = config.get("cert", "")
        self.key = config.get("key", "")

        self.endpoint = f"opc.tcp://{self.host}:{self.port}{self.path}"
        self.server = Server()

    def configurar_nodos(self):
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name(self.nombre)

        ns = self.server.register_namespace(self.namespace)
        objects = self.server.get_objects_node()

        # Zapecado
        self.zapecado = objects.add_object(ns, "Zapecado")
        self.zap_temp = self.zapecado.add_variable(ns, "Temperatura", 0.0)
        self.zap_temp.set_writable()

        # Secado
        self.secado = objects.add_object(ns, "Secado")
        self.sec_temp = self.secado.add_variable(ns, "Temperatura", 0.0)
        self.sec_hum = self.secado.add_variable(ns, "Humedad", 0.0)
        self.sec_temp.set_writable()
        self.sec_hum.set_writable()

        # Canchado
        self.canchado = objects.add_object(ns, "Canchado")
        self.can_vel = self.canchado.add_variable(ns, "VelocidadMolino", 0.0)
        self.can_vel.set_writable()

        # Cámaras
        self.camaras = []
        for i, cam in enumerate(self.simulador.camaras):
            cam_node = objects.add_object(ns, f"Camara{i+1}")
            t = cam_node.add_variable(ns, "Temperatura", cam.temperatura)
            h = cam_node.add_variable(ns, "Humedad", cam.humedad)
            c = cam_node.add_variable(ns, "CO2", cam.co2)
            d = cam_node.add_variable(ns, "DiasMaduracion", cam.tiempo_maduracion)
            for var in (t, h, c, d):
                var.set_writable()
            self.camaras.append((t, h, c, d))

    def _update_loop(self):
        while True:
            self.zap_temp.set_value(self.simulador.zapecado.temperatura)
            self.sec_temp.set_value(self.simulador.secado.temperatura)
            self.sec_hum.set_value(self.simulador.secado.humedad)
            self.can_vel.set_value(self.simulador.canchado.velocidad_molino)

            for i, cam in enumerate(self.simulador.camaras):
                t, h, c, d = self.camaras[i]
                t.set_value(cam.temperatura)
                h.set_value(cam.humedad)
                c.set_value(cam.co2)
                d.set_value(cam.tiempo_maduracion)

            time.sleep(self.interval)

    def start(self):
        self.configurar_nodos()
        self.server.start()
        print(f"OPC UA server iniciado en {self.endpoint}")
        threading.Thread(target=self._update_loop, daemon=True).start()