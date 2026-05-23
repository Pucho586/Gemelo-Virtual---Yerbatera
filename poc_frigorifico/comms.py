class CommsManager:
    def __init__(self):
        self.modbus_status = "Desconectado"
        self.opcua_status = "Desconectado"
        self.mqtt_status = "Desconectado"

        self.config = {
            "modbus_host": "192.168.1.100",
            "modbus_port": 502,
            "opcua_endpoint": "opc.tcp://192.168.1.101:4840",
            "mqtt_broker": "mqtt://broker.hivemq.com"
        }

    def connect_all(self):
        self.modbus_status = "Conectado (Leyendo PLC-1)"
        self.opcua_status = "Conectado (Servidor Activo)"
        self.mqtt_status = "Conectado (Suscrito a frigorifico/telemetry)"

    def disconnect_all(self):
        self.modbus_status = "Desconectado"
        self.opcua_status = "Desconectado"
        self.mqtt_status = "Desconectado"

    def update_config(self, new_config: dict):
        self.config.update(new_config)

    def get_status(self):
        return {
            "modbus": {"status": self.modbus_status, "config": self.config["modbus_host"]},
            "opcua": {"status": self.opcua_status, "config": self.config["opcua_endpoint"]},
            "mqtt": {"status": self.mqtt_status, "config": self.config["mqtt_broker"]}
        }

    def send_command(self, protocol: str, command: dict) -> bool:
        """Simula el envío de un comando industrial a la planta real."""
        # En la vida real, aquí usaríamos pymodbus o asyncua para escribir en el PLC.
        status = getattr(self, f"{protocol.lower()}_status", "Desconectado")
        if not status.startswith("Conectado"):
            return False
        return True
