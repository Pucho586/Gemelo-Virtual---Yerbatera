"""Runtime: orquesta simulador + Modbus + MQTT + OPC UA + clima + persistencia.

Multiusuario ("bancos"): el mismo backend puede correr N instancias aisladas
del gemelo (una por alumno/grupo). Cada banco tiene su propio simulador y sus
propios servidores industriales en puertos desplazados:

    Modbus TCP : 5020 + offset
    OPC UA     : 4840 + offset
    MQTT       : mismo broker, prefijo de topic  yerba/b<id>/...

El banco "default" (offset 0) conserva exactamente el comportamiento y los
puertos históricos (Modbus 5020, OPC 4840, MQTT yerba/). Ver WorkbenchManager.
"""
import asyncio
import contextvars
import copy
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    cfg.setdefault("ai", {"provider": "claude",
                          "claude_model": "claude-opus-4-8",
                          "gemini_model": "gemini-3-flash-preview"})
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
    """Un "banco de trabajo": simulador + servidores industriales aislados.

    Args:
        bank_id:   identificador del banco ("default" para el histórico).
        offset:    desplazamiento de puertos (0 = puertos históricos).
        name:      nombre visible del banco (ej. "Banco 3").
        student:   alumno/grupo asignado (opcional).
        persist:   si guarda config_yerba.yaml y corre persistencia a disco.
                   Solo el banco "default" persiste; el resto es en memoria para
                   no pisar los archivos compartidos.
    """

    def __init__(self, bank_id: str = "default", offset: int = 0,
                 name: Optional[str] = None, student: Optional[str] = None,
                 persist: bool = True):
        self.bank_id = bank_id
        self.offset = int(offset)
        self.name = name or ("Principal" if bank_id == "default" else f"Banco {bank_id}")
        self.student: Optional[str] = student
        self.persist = persist
        self.frozen: bool = False
        self.created_at = datetime.now(timezone.utc).isoformat()
        # Consigna del docente para este banco (ejercicio a resolver).
        self.consigna: Dict[str, Any] = {}

        base_cfg = load_config()
        # El banco default usa el config tal cual (y lo persiste). Los demás
        # trabajan sobre una copia en memoria con puertos desplazados.
        self.config: Dict[str, Any] = base_cfg if bank_id == "default" else copy.deepcopy(base_cfg)
        if self.offset:
            self._apply_port_offset()

        self.simulator = YerbaProcessSimulator(self.config)
        self.ai = AIService(config=self.config.get("ai"))

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

    # ---------- Config por banco ----------
    def _apply_port_offset(self):
        """Desplaza los puertos industriales según offset (bancos no-default)."""
        mb = self.config.setdefault("modbus", {})
        mb["port"] = int(mb.get("port", 5020)) + self.offset
        op = self.config.setdefault("opcua", {})
        op["port"] = int(op.get("port", 4840)) + self.offset
        mq = self.config.setdefault("mqtt", {})
        base_topic = mq.get("topic", "yerba")
        mq["topic"] = f"{base_topic}/b{self.bank_id}"
        # Bancos no-default no persisten a disco (evita pisar archivos globales).
        self.config.setdefault("persistence", {})["enabled"] = False

    def ports(self) -> Dict[str, Any]:
        mb = self.config.get("modbus", {})
        op = self.config.get("opcua", {})
        mq = self.config.get("mqtt", {})
        return {
            "modbus": mb.get("port", 5020),
            "opcua": op.get("port", 4840),
            "mqtt_prefix": mq.get("topic", "yerba"),
        }

    # ---------- Control de banco (docente) ----------
    def set_frozen(self, frozen: bool):
        self.frozen = bool(frozen)

    def reset(self):
        """Reinicia el simulador de este banco a su estado inicial.

        Reconstruye el simulador desde el config y re-apunta los servidores
        industriales al nuevo simulador (mantienen sus puertos/conexiones).
        """
        self.simulator = YerbaProcessSimulator(self.config)
        for srv in (self.modbus, self.mqtt, self.opcua):
            if srv is not None and hasattr(srv, "simulador"):
                srv.simulador = self.simulator
        if self.replay is not None:
            self.replay.simulator = self.simulator
        if self.whatif is not None:
            self.whatif.simulator = self.simulator
        if self.mass_flow is not None:
            self.mass_flow.simulator = self.simulator
        logger.info(f"[banco {self.bank_id}] simulador reiniciado")

    def set_consigna(self, consigna: Dict[str, Any]):
        self.consigna = consigna or {}

    def overview_snapshot(self) -> Dict[str, Any]:
        """Resumen liviano para el panel del docente (sin volcar todo el estado)."""
        s = self.simulator
        try:
            cams = getattr(s, "camaras", []) or []
            snap = {
                "zapecado_temp": round(getattr(s.zapecado, "temperatura", 0.0), 1),
                "zapecado_sp": s.zapecado.temperatura_obj,
                "zapecado_mode": getattr(s.zapecado, "control_mode", None),
                "secado_temp": round(getattr(s.secado, "temperatura", 0.0), 1),
                "secado_hum": round(getattr(s.secado, "humedad", 0.0), 1),
                "canchado_part": round(getattr(s.canchado, "tamano_particula", 0.0), 2),
                "camaras": len(cams),
                "mode": getattr(s, "mode", None),
                "aceleracion": getattr(s, "aceleracion", 1.0),
            }
        except Exception:
            snap = {}
        return {
            "id": self.bank_id,
            "name": self.name,
            "student": self.student,
            "created_at": self.created_at,
            "frozen": self.frozen,
            "offset": self.offset,
            "ports": self.ports(),
            "consigna": self.consigna,
            "services": {k: v.get("running") for k, v in self.service_status.items()},
            "snapshot": snap,
        }

    # ---------- Bucle de simulación ----------
    def _sim_loop(self):
        while True:
            try:
                if not self.frozen:
                    self.simulator.update()
            except Exception as e:
                logger.error(f"[banco {self.bank_id}] sim update error: {e}")
            time.sleep(max(0.05, 1.0 / max(self.simulator.aceleracion, 1.0)))

    def start_simulation(self):
        if self._sim_thread and self._sim_thread.is_alive():
            return
        self._sim_thread = threading.Thread(target=self._sim_loop, name="sim-loop", daemon=True)
        self._sim_thread.start()

    # ---------- Servidores industriales ----------
    def start_modbus(self):
        mb_cfg = self.config.get("modbus", {})
        if not mb_cfg.get("enabled", True):
            self.service_status["modbus"] = {"running": False, "error": None, "disabled": True,
                                             "ip": mb_cfg.get("ip"), "port": mb_cfg.get("port")}
            logger.info("Modbus TCP deshabilitado por configuración")
            return
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
        if not mqtt_cfg.get("enabled", True):
            self.service_status["mqtt"] = {"running": False, "error": None, "disabled": True,
                                           "broker": mqtt_cfg.get("broker"), "port": mqtt_cfg.get("port")}
            logger.info("MQTT deshabilitado por configuración")
            return
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
        if not op_cfg.get("enabled", True):
            self.service_status["opcua"] = {"running": False, "error": None, "disabled": True, "endpoint": None}
            logger.info("OPC UA deshabilitado por configuración")
            return
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

        if self.persist:
            save_config(self.config)
        return self.config


# ---------------------------------------------------------------------------
# Gestor de bancos (multiusuario)
# ---------------------------------------------------------------------------

# Banco activo para la request en curso (lo fija un middleware desde el header
# X-Bank-Id / query ?bank= / cookie). Los loops de fondo usan el default.
_current_bank: contextvars.ContextVar[str] = contextvars.ContextVar("bank", default="default")


class WorkbenchManager:
    """Mantiene N bancos aislados. El banco 'default' es el histórico."""

    def __init__(self):
        self.banks: Dict[str, TwinRuntime] = {}
        self._used_offsets: set[int] = set()
        self._seq: int = 0

    # ---- ciclo de vida ----
    def ensure_default(self) -> TwinRuntime:
        if "default" not in self.banks:
            bank = TwinRuntime(bank_id="default", offset=0, persist=True)
            self.banks["default"] = bank
            self._used_offsets.add(0)
        return self.banks["default"]

    def _alloc_offset(self) -> int:
        off = 1
        while off in self._used_offsets:
            off += 1
        self._used_offsets.add(off)
        return off

    def get(self, bank_id: Optional[str] = None) -> TwinRuntime:
        bid = bank_id or _current_bank.get()
        return self.banks.get(bid) or self.ensure_default()

    def exists(self, bank_id: str) -> bool:
        return bank_id in self.banks

    def list(self) -> List[TwinRuntime]:
        # default primero, resto por offset
        return sorted(self.banks.values(), key=lambda b: (b.bank_id != "default", b.offset))

    def create(self, name: Optional[str] = None, student: Optional[str] = None,
               bank_id: Optional[str] = None) -> TwinRuntime:
        self._seq += 1
        bid = bank_id or str(self._seq)
        if bid in self.banks:
            raise ValueError(f"El banco '{bid}' ya existe")
        offset = self._alloc_offset()
        bank = TwinRuntime(bank_id=bid, offset=offset, name=name, student=student, persist=False)
        # Arranca simulación + servidores industriales (puertos desplazados).
        bank.start_all()
        self.banks[bid] = bank
        logger.info(f"Banco creado id={bid} offset={offset} ports={bank.ports()}")
        return bank

    async def create_async(self, name: Optional[str] = None, student: Optional[str] = None,
                           bank_id: Optional[str] = None) -> TwinRuntime:
        bank = self.create(name=name, student=student, bank_id=bank_id)
        try:
            await bank.start_async_services()
        except Exception as e:
            logger.warning(f"Banco {bank.bank_id}: servicios async fallaron: {e}")
        return bank

    def delete(self, bank_id: str):
        if bank_id == "default":
            raise ValueError("No se puede eliminar el banco principal")
        bank = self.banks.pop(bank_id, None)
        if bank is None:
            raise KeyError(bank_id)
        self._used_offsets.discard(bank.offset)
        # Los servidores corren en threads daemon; detenerlos limpio es best-effort.
        for srv in (bank.modbus, bank.mqtt, bank.opcua):
            try:
                stop = getattr(srv, "stop", None)
                if callable(stop):
                    stop()
            except Exception:
                pass
        logger.info(f"Banco eliminado id={bank_id}")


# Instancia global del gestor
_manager: Optional[WorkbenchManager] = None


def get_manager() -> WorkbenchManager:
    global _manager
    if _manager is None:
        _manager = WorkbenchManager()
        _manager.ensure_default()
    return _manager


def set_current_bank(bank_id: Optional[str]) -> Any:
    """Fija el banco activo para el contexto actual. Devuelve el token para reset."""
    return _current_bank.set(bank_id or "default")


def reset_current_bank(token: Any):
    try:
        _current_bank.reset(token)
    except Exception:
        pass


def get_runtime() -> TwinRuntime:
    """Runtime del banco activo (o default). Compatible con el código existente."""
    return get_manager().get()
