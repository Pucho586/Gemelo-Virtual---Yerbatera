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
        self.zap_temp_obj = self.zapecado.add_variable(ns, "TemperaturaObjetivo", 0.0)
        self.zap_tau = self.zapecado.add_variable(ns, "Tau", 90.0)
        self.zap_falla_quemador = self.zapecado.add_variable(ns, "FallaQuemador", False)
        self.zap_falla_motor = self.zapecado.add_variable(ns, "FallaMotorTambor", False)
        for v in (self.zap_temp, self.zap_temp_obj, self.zap_tau, self.zap_falla_quemador, self.zap_falla_motor):
            v.set_writable()

        # Secado
        self.secado = objects.add_object(ns, "Secado")
        self.sec_temp = self.secado.add_variable(ns, "Temperatura", 0.0)
        self.sec_hum = self.secado.add_variable(ns, "Humedad", 0.0)
        self.sec_temp_obj = self.secado.add_variable(ns, "TemperaturaObjetivo", 95.0)
        self.sec_hum_obj = self.secado.add_variable(ns, "HumedadObjetivo", 7.0)
        self.sec_tau_t = self.secado.add_variable(ns, "TauTermico", 120.0)
        self.sec_falla_vent = self.secado.add_variable(ns, "FallaVentilador", False)
        self.sec_falla_serp = self.secado.add_variable(ns, "FallaSerpentin", False)
        for v in (self.sec_temp, self.sec_hum, self.sec_temp_obj, self.sec_hum_obj,
                  self.sec_tau_t, self.sec_falla_vent, self.sec_falla_serp):
            v.set_writable()

        # Canchado
        self.canchado = objects.add_object(ns, "Canchado")
        self.can_vel = self.canchado.add_variable(ns, "VelocidadMolino", 0.0)
        self.can_part = self.canchado.add_variable(ns, "TamanoParticula", 0.0)
        self.can_part_obj = self.canchado.add_variable(ns, "TamanoParticulaObjetivo", 0.0)
        self.can_tau_p = self.canchado.add_variable(ns, "TauMolino", 5.0)
        self.can_falla_motor = self.canchado.add_variable(ns, "FallaMotor", False)
        self.can_rod_caliente = self.canchado.add_variable(ns, "RodamientoCaliente", False)
        for v in (self.can_vel, self.can_part, self.can_part_obj, self.can_tau_p,
                  self.can_falla_motor, self.can_rod_caliente):
            v.set_writable()

        # Globales
        self.globales = objects.add_object(ns, "Simulacion")
        self.glb_acel = self.globales.add_variable(ns, "Aceleracion", 60.0)
        self.glb_throughput = self.globales.add_variable(ns, "ThroughputKgh", 800.0)
        self.glb_modo = self.globales.add_variable(ns, "Modo", "simulator")
        for v in (self.glb_acel, self.glb_throughput, self.glb_modo):
            v.set_writable()

        # Cámaras (pre-allocate 12 slots). Solo las primeras N tendrán datos reales.
        self.camaras = []
        self.MAX_CAMARAS = 12
        for i in range(self.MAX_CAMARAS):
            cam_node = objects.add_object(ns, f"Camara{i+1}")
            t = cam_node.add_variable(ns, "Temperatura", 0.0)
            h = cam_node.add_variable(ns, "Humedad", 0.0)
            c = cam_node.add_variable(ns, "CO2", 0.0)
            d = cam_node.add_variable(ns, "DiasMaduracion", 0.0)
            tobj = cam_node.add_variable(ns, "TemperaturaObjetivo", 35.0)
            hobj = cam_node.add_variable(ns, "HumedadObjetivo", 75.0)
            va = cam_node.add_variable(ns, "VaporActivo", False)
            vc = cam_node.add_variable(ns, "VaporCaudalKgh", 0.0)
            vst = cam_node.add_variable(ns, "VaporSetpointTemp", 0.0)
            vsh = cam_node.add_variable(ns, "VaporSetpointHum", 0.0)
            vka = cam_node.add_variable(ns, "VaporKgAcum", 0.0)
            tau = cam_node.add_variable(ns, "Tau", 600.0)
            fv = cam_node.add_variable(ns, "FallaVentilador", False)
            fg = cam_node.add_variable(ns, "FugaVapor", False)
            pa = cam_node.add_variable(ns, "PuertaAbierta", False)
            act = cam_node.add_variable(ns, "Activa", False)
            for var in (t, h, c, d, tobj, hobj, va, vc, vst, vsh, vka, tau, fv, fg, pa, act):
                var.set_writable()
            self.camaras.append((t, h, c, d, tobj, hobj, va, vc, vst, vsh, vka, tau, fv, fg, pa, act))

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
                z = self.simulador.zapecado
                s = self.simulador.secado
                c = self.simulador.canchado
                self.zap_temp.set_value(float(z.temperatura))
                self.zap_temp_obj.set_value(float(z.temperatura_obj if z.temperatura_obj is not None else 0.0))
                self.zap_tau.set_value(float(z.tau))
                self.zap_falla_quemador.set_value(bool(z.falla_quemador))
                self.zap_falla_motor.set_value(bool(z.falla_motor_tambor))
                self.sec_temp.set_value(float(s.temperatura))
                self.sec_hum.set_value(float(s.humedad))
                self.sec_temp_obj.set_value(float(s.temperatura_obj))
                self.sec_hum_obj.set_value(float(s.humedad_obj))
                self.sec_tau_t.set_value(float(s.tau_t))
                self.sec_falla_vent.set_value(bool(s.falla_ventilador))
                self.sec_falla_serp.set_value(bool(s.falla_serpentin))
                self.can_vel.set_value(float(c.velocidad_molino))
                self.can_part.set_value(float(c.tamano_particula))
                self.can_part_obj.set_value(float(c.tamano_particula_obj if c.tamano_particula_obj is not None else 0.0))
                self.can_tau_p.set_value(float(c.tau_p))
                self.can_falla_motor.set_value(bool(c.falla_motor))
                self.can_rod_caliente.set_value(bool(c.rodamiento_caliente))
                self.glb_acel.set_value(float(self.simulador.aceleracion))
                self.glb_throughput.set_value(float(self.simulador.throughput_kgh))
                self.glb_modo.set_value(str(self.simulador.mode))

                n_real = len(self.simulador.camaras)
                for i, nodes in enumerate(self.camaras):
                    (t, h, co, d, tobj, hobj, va, vc, vst, vsh, vka, tau, fv, fg, pa, act) = nodes
                    if i < n_real:
                        cam = self.simulador.camaras[i]
                        t.set_value(float(cam.temperatura))
                        h.set_value(float(cam.humedad))
                        co.set_value(float(cam.co2))
                        d.set_value(float(cam.tiempo_maduracion))
                        tobj.set_value(float(cam.temperatura_obj))
                        hobj.set_value(float(cam.humedad_obj))
                        va.set_value(bool(cam.vapor_activo))
                        vc.set_value(float(cam.vapor_caudal_kgh))
                        vst.set_value(float(cam.vapor_setpoint_temp))
                        vsh.set_value(float(cam.vapor_setpoint_hum))
                        vka.set_value(float(cam.vapor_kg_acum))
                        tau.set_value(float(cam.tau))
                        fv.set_value(bool(cam.falla_ventilador))
                        fg.set_value(bool(cam.fuga_vapor))
                        pa.set_value(bool(cam.puerta_abierta))
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
