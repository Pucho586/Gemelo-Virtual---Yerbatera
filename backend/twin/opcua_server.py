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

        # What-if scenario nodes (rellenado por WhatIfService al registrar escenarios)
        self.whatif_nodes = {}  # scenario_id -> dict of variable nodes
        self._ns = None

    def configurar_nodos(self):
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name(self.nombre)

        ns = self.server.register_namespace(self.namespace)
        self._ns = ns
        objects = self.server.get_objects_node()
        self._objects = objects

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

        # Cámaras (pre-allocate 12 slots). Solo las primeras N tendrán datos reales.
        self.camaras = []
        self.MAX_CAMARAS = 12
        for i in range(self.MAX_CAMARAS):
            cam_node = objects.add_object(ns, f"Camara{i+1}")
            t = cam_node.add_variable(ns, "Temperatura", 0.0)
            h = cam_node.add_variable(ns, "Humedad", 0.0)
            c = cam_node.add_variable(ns, "CO2", 0.0)
            d = cam_node.add_variable(ns, "DiasMaduracion", 0.0)
            va = cam_node.add_variable(ns, "VaporActivo", False)
            vc = cam_node.add_variable(ns, "VaporCaudalKgh", 0.0)
            vst = cam_node.add_variable(ns, "VaporSetpointTemp", 0.0)
            vsh = cam_node.add_variable(ns, "VaporSetpointHum", 0.0)
            vka = cam_node.add_variable(ns, "VaporKgAcum", 0.0)
            act = cam_node.add_variable(ns, "Activa", False)
            for var in (t, h, c, d, va, vc, vst, vsh, vka, act):
                var.set_writable()
            self.camaras.append((t, h, c, d, va, vc, vst, vsh, vka, act))

        # What-if root object (los escenarios cuelgan acá)
        self.whatif_root = objects.add_object(ns, "WhatIf")

    def register_whatif_scenario(self, scenario_id: str):
        """Crea nodos OPC UA para un escenario what-if. Idempotente."""
        if scenario_id in self.whatif_nodes or self._ns is None:
            return
        ns = self._ns
        sc = self.whatif_root.add_object(ns, scenario_id)
        nodes = {
            "OEE": sc.add_variable(ns, "OEE", 0.0),
            "CostoPorKg": sc.add_variable(ns, "CostoPorKg", 0.0),
            "kWhAcum": sc.add_variable(ns, "kWhAcum", 0.0),
            "ChipsKgAcum": sc.add_variable(ns, "ChipsKgAcum", 0.0),
            "TempZapecado": sc.add_variable(ns, "TempZapecado", 0.0),
            "TempSecado": sc.add_variable(ns, "TempSecado", 0.0),
            "HumFinal": sc.add_variable(ns, "HumFinal", 0.0),
            "ProduccionKg": sc.add_variable(ns, "ProduccionKg", 0.0),
        }
        for v in nodes.values():
            v.set_writable()
        self.whatif_nodes[scenario_id] = nodes

    def update_whatif_scenario(self, scenario_id: str, kpis: dict):
        """Actualiza valores de un escenario."""
        nodes = self.whatif_nodes.get(scenario_id)
        if not nodes:
            return
        for k, node in nodes.items():
            v = kpis.get(k)
            if v is not None:
                try:
                    node.set_value(float(v))
                except Exception:
                    pass

    def _update_loop(self):
        while True:
            try:
                self.zap_temp.set_value(self.simulador.zapecado.temperatura)
                self.sec_temp.set_value(self.simulador.secado.temperatura)
                self.sec_hum.set_value(self.simulador.secado.humedad)
                self.can_vel.set_value(self.simulador.canchado.velocidad_molino)

                n_real = len(self.simulador.camaras)
                for i, (t, h, c, d, va, vc, vst, vsh, vka, act) in enumerate(self.camaras):
                    if i < n_real:
                        cam = self.simulador.camaras[i]
                        t.set_value(float(cam.temperatura))
                        h.set_value(float(cam.humedad))
                        c.set_value(float(cam.co2))
                        d.set_value(float(cam.tiempo_maduracion))
                        va.set_value(bool(cam.vapor_activo))
                        vc.set_value(float(cam.vapor_caudal_kgh))
                        vst.set_value(float(cam.vapor_setpoint_temp))
                        vsh.set_value(float(cam.vapor_setpoint_hum))
                        vka.set_value(float(cam.vapor_kg_acum))
                        act.set_value(True)
                    else:
                        act.set_value(False)
            except Exception:
                pass

            time.sleep(self.interval)

    def start(self):
        self.configurar_nodos()
        self.server.start()
        print(f"OPC UA server iniciado en {self.endpoint}")
        threading.Thread(target=self._update_loop, daemon=True).start()
