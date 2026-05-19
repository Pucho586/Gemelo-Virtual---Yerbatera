"""Runtime: orquesta simulador + Modbus + MQTT + OPC UA + clima + persistencia."""
import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from .ai_service import AIService
from .external_sources import (
    ExternalMirror, ModbusClientPoller, MqttSubscriber, OpcUaClientPoller,
    compute_drift, push_external_to_simulator,
)
from .mqtt_publisher import YerbaMqttPublisher
from .opcua_server import YerbaOpcUaServer
from .persistence import PersistenceService
from .mass_flow import MassFlowService
from .replay_service import ReplayService
from .weather import DEFAULT_LOCATION, WeatherService
from .whatif_service import WhatIfService
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
    cfg.setdefault("external", {
        "modbus_client": {"enabled": False, "host": "127.0.0.1", "port": 5020, "interval": 2.0},
        "opcua_client": {"enabled": False, "endpoint": "opc.tcp://127.0.0.1:4840/yerba/", "interval": 2.0, "namespace_idx": 2},
        "mqtt_subscriber": {"enabled": False, "broker": "localhost", "port": 1883, "topic_base": "yerba_in"},
    })
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
        self.replay: ReplayService | None = None
        self.whatif: WhatIfService | None = None
        self.mass_flow: MassFlowService | None = None

        # Fuentes externas (modo twin/shadow)
        self.mirror = ExternalMirror()
        self.modbus_client: ModbusClientPoller | None = None
        self.opcua_client: OpcUaClientPoller | None = None
        self.mqtt_subscriber: MqttSubscriber | None = None
        self._external_loop_task: asyncio.Task | None = None
        self.last_drift: Dict[str, Any] = {}

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
            "modbus_client": {"running": False, "error": None, "host": None, "port": None},
            "opcua_client": {"running": False, "error": None, "endpoint": None},
            "mqtt_subscriber": {"running": False, "error": None, "broker": None},
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

        # External sources
        await self._start_external_sources()

    async def _start_external_sources(self):
        ext_cfg = self.config.get("external", {})
        # Modbus client
        mb_cfg = ext_cfg.get("modbus_client", {})
        self.modbus_client = ModbusClientPoller(self.mirror, mb_cfg)
        self.modbus_client.start()
        self.service_status["modbus_client"] = {
            "running": mb_cfg.get("enabled", False), "error": None,
            "host": mb_cfg.get("host"), "port": mb_cfg.get("port"),
        }
        # OPC UA client
        op_cfg = ext_cfg.get("opcua_client", {})
        self.opcua_client = OpcUaClientPoller(self.mirror, op_cfg)
        self.opcua_client.start()
        self.service_status["opcua_client"] = {
            "running": op_cfg.get("enabled", False), "error": None,
            "endpoint": op_cfg.get("endpoint"),
        }
        # MQTT subscriber
        ms_cfg = ext_cfg.get("mqtt_subscriber", {})
        self.mqtt_subscriber = MqttSubscriber(self.mirror, ms_cfg)
        self.mqtt_subscriber.start()
        self.service_status["mqtt_subscriber"] = {
            "running": ms_cfg.get("enabled", False), "error": None,
            "broker": ms_cfg.get("broker"),
        }
        # Loop de aplicación / drift
        self._external_loop_task = asyncio.get_event_loop().create_task(self._external_apply_loop())

    async def _external_apply_loop(self):
        """En modo twin: empuja mirror al simulador. En modo shadow: solo calcula drift."""
        while True:
            try:
                mode = self.simulator.mode
                if mode == "twin" and self.mirror.values:
                    push_external_to_simulator(self.mirror, self.simulator)
                if mode in ("twin", "shadow") and self.mirror.values:
                    state = self.simulator.get_state()
                    self.last_drift = compute_drift(state, self.mirror)
                else:
                    self.last_drift = {}
            except Exception as e:
                logger.debug(f"external apply loop: {e}")
            await asyncio.sleep(1.0)

    def reconfigure_external(self, section: str, **kwargs):
        """Reconfigura una fuente externa en caliente."""
        if section == "modbus_client" and self.modbus_client:
            self.modbus_client.reconfigure(**kwargs)
            self.service_status["modbus_client"].update({
                "running": self.modbus_client.enabled,
                "host": self.modbus_client.host,
                "port": self.modbus_client.port,
            })
        elif section == "opcua_client" and self.opcua_client:
            self.opcua_client.reconfigure(**kwargs)
            self.service_status["opcua_client"].update({
                "running": self.opcua_client.enabled,
                "endpoint": self.opcua_client.endpoint,
            })
        elif section == "mqtt_subscriber" and self.mqtt_subscriber:
            self.mqtt_subscriber.reconfigure(**kwargs)
            self.service_status["mqtt_subscriber"].update({
                "running": self.mqtt_subscriber.enabled,
                "broker": self.mqtt_subscriber.broker,
            })
        # Persistir en config
        self.update_config({"external": {section: kwargs}})

    # ---------- Vida ----------
    def start_all(self):
        self.start_simulation()
        self.start_modbus()
        self.start_mqtt()
        self.start_opcua()
        # Replay service (no arranca solo, queda listo)
        self.replay = ReplayService(self.simulator, DATA_DIR)
        # What-if service (orquesta escenarios paralelos)
        self.whatif = WhatIfService(self.simulator, self)
        # Mass-flow service (trazabilidad de masa entre etapas)
        self.mass_flow = MassFlowService(self.simulator)

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
