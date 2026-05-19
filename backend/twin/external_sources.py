"""Fuentes externas: clientes Modbus / OPC UA / MQTT que alimentan el modo Gemelo/Shadow.

En modo `twin` el simulador deja de calcular; los valores vienen de estos clientes.
En modo `shadow` simulador y cliente externo corren en paralelo y se comparan.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =========================================================
# Mapeo por defecto de registros Modbus / topics MQTT / nodos OPC UA
# (coincide con el servidor que ya publica nuestro propio twin)
# =========================================================
DEFAULT_MODBUS_MAP = {
    # cada item: (unit_id, register_address, scale, target_path)
    # Holding registers (función 3). Scale: divisor del int leído.
    "zapecado.temperatura":    {"unit": 0, "addr": 0, "scale": 10.0},
    "secado.temperatura":      {"unit": 1, "addr": 0, "scale": 10.0},
    "secado.humedad":          {"unit": 1, "addr": 1, "scale": 10.0},
    "canchado.velocidad_molino": {"unit": 2, "addr": 0, "scale": 10.0},
    "canchado.tamano_particula": {"unit": 2, "addr": 1, "scale": 10.0},
    "cam0.temperatura":        {"unit": 3, "addr": 0, "scale": 10.0},
    "cam0.humedad":            {"unit": 3, "addr": 1, "scale": 10.0},
    "cam0.co2":                {"unit": 3, "addr": 2, "scale": 1.0},
    "cam1.temperatura":        {"unit": 4, "addr": 0, "scale": 10.0},
    "cam1.humedad":            {"unit": 4, "addr": 1, "scale": 10.0},
    "cam1.co2":                {"unit": 4, "addr": 2, "scale": 1.0},
    "cam2.temperatura":        {"unit": 5, "addr": 0, "scale": 10.0},
    "cam2.humedad":            {"unit": 5, "addr": 1, "scale": 10.0},
    "cam2.co2":                {"unit": 5, "addr": 2, "scale": 1.0},
    "cam3.temperatura":        {"unit": 6, "addr": 0, "scale": 10.0},
    "cam3.humedad":            {"unit": 6, "addr": 1, "scale": 10.0},
    "cam3.co2":                {"unit": 6, "addr": 2, "scale": 1.0},
}


# =========================================================
# Mirror: estado leído desde fuente externa
# =========================================================
class ExternalMirror:
    """Almacena el último valor leído por cada cliente externo y su timestamp."""

    def __init__(self):
        self.values: Dict[str, float] = {}
        self.sources: Dict[str, str] = {}     # tag -> 'modbus' | 'opcua' | 'mqtt'
        self.last_update: Dict[str, str] = {}
        self.errors: Dict[str, str] = {}      # source -> last error

    def set(self, tag: str, value: float, source: str):
        self.values[tag] = value
        self.sources[tag] = source
        self.last_update[tag] = datetime.now(timezone.utc).isoformat()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "values": dict(self.values),
            "sources": dict(self.sources),
            "last_update": dict(self.last_update),
            "errors": dict(self.errors),
        }


# =========================================================
# Modbus Client
# =========================================================
class ModbusClientPoller:
    """Polleo un servidor Modbus TCP externo y poblar el mirror."""

    def __init__(self, mirror: ExternalMirror, config: Dict[str, Any]):
        self.mirror = mirror
        self.host = config.get("host", "127.0.0.1")
        self.port = int(config.get("port", 5020))
        self.interval = float(config.get("interval", 2.0))
        self.mapping: Dict[str, Dict[str, Any]] = config.get("mapping") or DEFAULT_MODBUS_MAP
        self.enabled: bool = bool(config.get("enabled", False))
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._client = None

    async def _poll_once(self):
        try:
            from pymodbus.client import AsyncModbusTcpClient
        except ImportError:
            self.mirror.errors["modbus_client"] = "pymodbus AsyncModbusTcpClient no disponible"
            return
        try:
            if not self._client or not getattr(self._client, "connected", False):
                self._client = AsyncModbusTcpClient(self.host, port=self.port)
                ok = await self._client.connect()
                if not ok:
                    raise ConnectionError(f"No se pudo conectar a {self.host}:{self.port}")
            for tag, spec in self.mapping.items():
                try:
                    # pymodbus 3.7 API
                    res = await self._client.read_holding_registers(
                        address=spec["addr"], count=1, slave=spec["unit"]
                    )
                    if res.isError():
                        continue
                    raw = res.registers[0]
                    val = raw / float(spec.get("scale", 1.0))
                    self.mirror.set(tag, val, "modbus")
                except Exception as e:  # tag-level error, sigue con otros
                    logger.debug(f"modbus tag {tag} fail: {e}")
            self.mirror.errors.pop("modbus_client", None)
        except Exception as e:
            self.mirror.errors["modbus_client"] = str(e)
            try:
                if self._client:
                    await self._client.close()
            except Exception:
                pass
            self._client = None

    async def _loop(self):
        self.running = True
        while self.running:
            if self.enabled:
                await self._poll_once()
            await asyncio.sleep(self.interval)

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        loop = loop or asyncio.get_event_loop()
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass

    def reconfigure(self, **kwargs):
        if "host" in kwargs: self.host = kwargs["host"]
        if "port" in kwargs: self.port = int(kwargs["port"])
        if "interval" in kwargs: self.interval = float(kwargs["interval"])
        if "enabled" in kwargs: self.enabled = bool(kwargs["enabled"])
        if "mapping" in kwargs and kwargs["mapping"]:
            self.mapping = kwargs["mapping"]
        # Forzar reconexión
        self._client = None


# =========================================================
# OPC UA Client
# =========================================================
class OpcUaClientPoller:
    """Lee variables de un servidor OPC UA externo (nodos enumerados)."""

    def __init__(self, mirror: ExternalMirror, config: Dict[str, Any]):
        self.mirror = mirror
        self.endpoint = config.get("endpoint", "opc.tcp://127.0.0.1:4840/yerba/")
        self.interval = float(config.get("interval", 2.0))
        self.enabled = bool(config.get("enabled", False))
        self.namespace_idx = int(config.get("namespace_idx", 2))
        # Mapeo tag -> "Object.Variable" path desde Objects root
        self.mapping: Dict[str, str] = config.get("mapping") or {
            "zapecado.temperatura": "Zapecado.Temperatura",
            "secado.temperatura": "Secado.Temperatura",
            "secado.humedad": "Secado.Humedad",
            "canchado.velocidad_molino": "Canchado.VelocidadMolino",
            "cam0.temperatura": "Camara1.Temperatura",
            "cam0.humedad": "Camara1.Humedad",
            "cam0.co2": "Camara1.CO2",
        }
        self._task: Optional[asyncio.Task] = None
        self.running = False

    async def _poll_once(self):
        try:
            from asyncua import Client
        except ImportError:
            self.mirror.errors["opcua_client"] = "asyncua no disponible"
            return
        client = Client(url=self.endpoint, timeout=4)
        try:
            await client.connect()
            for tag, path in self.mapping.items():
                try:
                    obj, var = path.split(".")
                    node = client.nodes.objects.get_child([f"{self.namespace_idx}:{obj}", f"{self.namespace_idx}:{var}"])
                    value = await node.read_value()
                    if isinstance(value, (int, float)):
                        self.mirror.set(tag, float(value), "opcua")
                except Exception as e:
                    logger.debug(f"opcua tag {tag} fail: {e}")
            self.mirror.errors.pop("opcua_client", None)
        except Exception as e:
            self.mirror.errors["opcua_client"] = str(e)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def _loop(self):
        self.running = True
        while self.running:
            if self.enabled:
                await self._poll_once()
            await asyncio.sleep(self.interval)

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        loop = loop or asyncio.get_event_loop()
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass

    def reconfigure(self, **kwargs):
        for k in ("endpoint", "interval", "enabled", "mapping", "namespace_idx"):
            if k in kwargs and kwargs[k] is not None:
                setattr(self, k, kwargs[k])


# =========================================================
# MQTT Subscriber
# =========================================================
class MqttSubscriber:
    """Se suscribe a topics y parsea JSON {key: value} para alimentar el mirror."""

    def __init__(self, mirror: ExternalMirror, config: Dict[str, Any]):
        self.mirror = mirror
        self.broker = config.get("broker", "localhost")
        self.port = int(config.get("port", 1883))
        self.user = config.get("user", "")
        self.password = config.get("pass", "")
        self.topic_base = config.get("topic_base", "yerba_in")
        self.enabled = bool(config.get("enabled", False))
        self.mapping: Dict[str, str] = config.get("mapping") or {
            # subtopic -> tag
            "zapecado/temperatura": "zapecado.temperatura",
            "secado/temperatura": "secado.temperatura",
            "secado/humedad": "secado.humedad",
            "canchado/velocidad_molino": "canchado.velocidad_molino",
            "camara_1/temperatura": "cam0.temperatura",
            "camara_1/humedad": "cam0.humedad",
            "camara_1/co2": "cam0.co2",
        }
        self.client = None
        self._thread = None

    def _on_message(self, client, userdata, msg):
        try:
            subtopic = msg.topic[len(self.topic_base) + 1:] if msg.topic.startswith(self.topic_base + "/") else msg.topic
            payload = msg.payload.decode("utf-8", errors="ignore").strip()
            tag = self.mapping.get(subtopic)
            if not tag:
                return
            # acepta "12.3" o '{"value": 12.3}'
            try:
                val = float(payload)
            except ValueError:
                try:
                    obj = json.loads(payload)
                    val = float(obj.get("value") or obj.get("v") or list(obj.values())[0])
                except Exception:
                    return
            self.mirror.set(tag, val, "mqtt")
        except Exception as e:
            logger.debug(f"mqtt parse fail: {e}")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.mirror.errors.pop("mqtt_subscriber", None)
            for sub in self.mapping.keys():
                client.subscribe(f"{self.topic_base}/{sub}")
        else:
            self.mirror.errors["mqtt_subscriber"] = f"rc={rc}"

    def start(self):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.mirror.errors["mqtt_subscriber"] = "paho-mqtt no disponible"
            return
        if not self.enabled:
            return
        try:
            self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            if self.user:
                self.client.username_pw_set(self.user, self.password)
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.connect_async(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            self._thread = True
        except Exception as e:
            self.mirror.errors["mqtt_subscriber"] = str(e)

    def stop(self):
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
        except Exception:
            pass
        self.client = None

    def reconfigure(self, **kwargs):
        for k in ("broker", "port", "user", "password", "topic_base", "enabled", "mapping"):
            if k in kwargs and kwargs[k] is not None:
                setattr(self, k, kwargs[k])
        self.stop()
        time.sleep(0.2)
        self.start()


# =========================================================
# Drift calculation (sim vs external)
# =========================================================
def compute_drift(sim_state: Dict[str, Any], mirror: ExternalMirror) -> Dict[str, Dict[str, float]]:
    """Calcula desviación (sim - external) por tag medido."""
    out: Dict[str, Dict[str, float]] = {}
    def get_sim(path: str):
        # "cam0.temperatura" -> sim_state["camaras"][0]["temperatura"]
        try:
            if path.startswith("cam"):
                idx = int(path[3])
                field = path.split(".")[1]
                return float(sim_state["camaras"][idx][field])
            section, field = path.split(".")
            return float(sim_state[section][field])
        except Exception:
            return None

    for tag, ext_val in mirror.values.items():
        sim_val = get_sim(tag)
        if sim_val is None:
            continue
        out[tag] = {
            "sim": round(sim_val, 3),
            "ext": round(ext_val, 3),
            "delta": round(sim_val - ext_val, 3),
            "pct": round(abs(sim_val - ext_val) / max(abs(sim_val), 0.001) * 100, 2),
        }
    return out


# =========================================================
# Apply external values to simulator (modo twin)
# =========================================================
def push_external_to_simulator(mirror: ExternalMirror, simulator):
    """En modo 'twin', escribe los valores del mirror dentro del simulador."""
    v = mirror.values
    # Zapecado
    if "zapecado.temperatura" in v:
        simulator.zapecado.temperatura = float(v["zapecado.temperatura"])
    # Secado
    if "secado.temperatura" in v:
        simulator.secado.temperatura = float(v["secado.temperatura"])
    if "secado.humedad" in v:
        simulator.secado.humedad = float(v["secado.humedad"])
    # Canchado
    if "canchado.velocidad_molino" in v:
        simulator.canchado.velocidad_molino = float(v["canchado.velocidad_molino"])
    if "canchado.tamano_particula" in v:
        simulator.canchado.tamano_particula = float(v["canchado.tamano_particula"])
    # Cámaras
    for i in range(4):
        for field in ("temperatura", "humedad", "co2"):
            tag = f"cam{i}.{field}"
            if tag in v and i < len(simulator.camaras):
                setattr(simulator.camaras[i], field, float(v[tag]))
