"""Runtime: orquesta simulador + Modbus + MQTT + OPC UA + clima + persistencia."""
import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from .ai_service import AIService
from .mqtt_publisher import YerbaMqttPublisher
from .opcua_server import YerbaOpcUaServer
from .persistence import PersistenceService
from .weather import DEFAULT_LOCATION, WeatherService
from .yerba_modbus_server import YerbaModbusServer
from .yerba_simulator import YerbaProcessSimulator

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config_yerba.yaml"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    # Defaults
    cfg.setdefault("weather", {"latitude": DEFAULT_LOCATION["latitude"],
                               "longitude": DEFAULT_LOCATION["longitude"],
                               "city": DEFAULT_LOCATION["city"]})
    cfg.setdefault("persistence", {"enabled": True, "interval_seconds": 5})
    return cfg


def save_config(cfg: Dict[str, Any]):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)


class TwinRuntime:
    """Singleton-ish: arranca todos los componentes y mantiene su estado."""

    def __init__(self):
        self.config: Dict[str, Any] = load_config()
        self.simulator = YerbaProcessSimulator(self.config)
        self.ai = AIService()

        # Servicios industriales
        self.modbus: YerbaModbusServer | None = None
        self.mqtt: YerbaMqttPublisher | None = None
        self.opcua: YerbaOpcUaServer | None = None

        # Servicios asíncronos
        self.weather: WeatherService | None = None
        self.persistence: PersistenceService | None = None

        # Threads industriales
        self._sim_thread: threading.Thread | None = None
        self._modbus_thread: threading.Thread | None = None
        self._opcua_thread: threading.Thread | None = None

        # Estado de servicios
        self.service_status: Dict[str, Dict[str, Any]] = {
            "modbus": {"running": False, "error": None, "ip": None, "port": None},
            "mqtt": {"running": False, "error": None, "broker": None, "port": None},
            "opcua": {"running": False, "error": None, "endpoint": None},
            "weather": {"running": False, "error": None, "city": None},
            "persistence": {"running": False, "error": None, "interval": None},
        }

    # ---------- Bucle de simulación ----------
    def _sim_loop(self):
        while True:
            try:
                self.simulator.update()
            except Exception as e:
                logger.error(f"sim update error: {e}")
            time.sleep(max(0.05, 1.0 / max(self.simulator.aceleracion, 1.0)))

    def start_simulation(self):
        if self._sim_thread and self._sim_thread.is_alive():
            return
        self._sim_thread = threading.Thread(target=self._sim_loop, name="sim-loop", daemon=True)
        self._sim_thread.start()

    # ---------- Servidores industriales ----------
    def start_modbus(self):
        mb_cfg = self.config.get("modbus", {})
        try:
            self.modbus = YerbaModbusServer(self.simulator, mb_cfg)

            def runner():
                try:
                    self.modbus.start()
                except Exception as e:
                    logger.error(f"Modbus crashed: {e}")
                    self.service_status["modbus"]["running"] = False
                    self.service_status["modbus"]["error"] = str(e)

            self._modbus_thread = threading.Thread(target=runner, name="modbus-server", daemon=True)
            self._modbus_thread.start()
            self.service_status["modbus"] = {
                "running": True, "error": None,
                "ip": mb_cfg.get("ip", "127.0.0.1"),
                "port": mb_cfg.get("port", 5020),
            }
            logger.info(f"Modbus TCP server on {mb_cfg.get('ip','127.0.0.1')}:{mb_cfg.get('port',5020)}")
        except Exception as e:
            self.service_status["modbus"] = {"running": False, "error": str(e),
                                             "ip": mb_cfg.get("ip"), "port": mb_cfg.get("port")}
            logger.error(f"Modbus start failed: {e}")

    def start_mqtt(self):
        mqtt_cfg = self.config.get("mqtt", {})
        try:
            self.mqtt = YerbaMqttPublisher(self.simulator, mqtt_cfg)
            self.mqtt.start()
            self.service_status["mqtt"] = {
                "running": True, "error": None,
                "broker": mqtt_cfg.get("broker", "localhost"),
                "port": mqtt_cfg.get("port", 1883),
            }
            logger.info(f"MQTT publisher → {mqtt_cfg.get('broker')}:{mqtt_cfg.get('port')}")
        except Exception as e:
            self.service_status["mqtt"] = {"running": False, "error": str(e),
                                           "broker": mqtt_cfg.get("broker"), "port": mqtt_cfg.get("port")}
            logger.warning(f"MQTT start failed: {e}")

    def start_opcua(self):
        op_cfg = self.config.get("opcua", {})
        try:
            self.opcua = YerbaOpcUaServer(self.simulator, op_cfg)

            def runner():
                try:
                    self.opcua.start()
                    while True:
                        time.sleep(60)
                except Exception as e:
                    logger.error(f"OPC UA crashed: {e}")
                    self.service_status["opcua"]["running"] = False
                    self.service_status["opcua"]["error"] = str(e)

            self._opcua_thread = threading.Thread(target=runner, name="opcua-server", daemon=True)
            self._opcua_thread.start()
            endpoint = f"opc.tcp://{op_cfg.get('host', '0.0.0.0')}:{op_cfg.get('port', 4840)}{op_cfg.get('path', '/yerba/')}"
            self.service_status["opcua"] = {"running": True, "error": None, "endpoint": endpoint}
            logger.info(f"OPC UA server endpoint: {endpoint}")
        except Exception as e:
            self.service_status["opcua"] = {"running": False, "error": str(e), "endpoint": None}
            logger.error(f"OPC UA start failed: {e}")

    # ---------- Async services ----------
    async def start_async_services(self):
        # Weather
        try:
            self.weather = WeatherService(
                self.simulator,
                location=self.config.get("weather"),
                interval_seconds=int(self.config.get("weather", {}).get("interval_seconds", 600)),
            )
            await self.weather.refresh()
            self.weather.start()
            self.service_status["weather"] = {"running": True, "error": None,
                                              "city": self.weather.location.get("city")}
        except Exception as e:
            self.service_status["weather"] = {"running": False, "error": str(e), "city": None}
            logger.warning(f"Weather init failed: {e}")

        # Persistence
        try:
            p_cfg = self.config.get("persistence", {})
            self.persistence = PersistenceService(
                self.simulator, DATA_DIR,
                interval=int(p_cfg.get("interval_seconds", 5)),
                enabled=bool(p_cfg.get("enabled", True)),
            )
            self.persistence.start()
            self.service_status["persistence"] = {
                "running": True, "error": None,
                "interval": self.persistence.interval,
                "enabled": self.persistence.enabled,
            }
        except Exception as e:
            self.service_status["persistence"] = {"running": False, "error": str(e), "interval": None}
            logger.warning(f"Persistence init failed: {e}")

    # ---------- Vida ----------
    def start_all(self):
        self.start_simulation()
        self.start_modbus()
        self.start_mqtt()
        self.start_opcua()

    def update_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica cambios al config en memoria + YAML y al simulador."""
        # Merge superficial por sección
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(self.config.get(k), dict):
                self.config[k].update(v)
            else:
                self.config[k] = v

        # Aceleración
        if "simulacion" in patch and "aceleracion" in patch["simulacion"]:
            self.simulator.aceleracion = float(patch["simulacion"]["aceleracion"])

        # Persistencia
        if self.persistence and "persistence" in patch:
            pc = patch["persistence"]
            if "interval_seconds" in pc:
                self.persistence.interval = max(1, int(pc["interval_seconds"]))
            if "enabled" in pc:
                self.persistence.enabled = bool(pc["enabled"])
            self.service_status["persistence"]["interval"] = self.persistence.interval
            self.service_status["persistence"]["enabled"] = self.persistence.enabled

        save_config(self.config)
        return self.config


# Singleton global
runtime: TwinRuntime | None = None


def get_runtime() -> TwinRuntime:
    global runtime
    if runtime is None:
        runtime = TwinRuntime()
    return runtime
