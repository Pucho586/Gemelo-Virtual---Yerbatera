"""Iteración 11 — Tests de BIDIRECCIONALIDAD (MQTT, Modbus, OPC UA) + Docs + Weather.

Pre-requisitos:
- Backend corriendo en REACT_APP_BACKEND_URL
- MQTT broker en localhost:1883 (mosquitto). Si no está, los tests MQTT se skipean.
- Modbus TCP en 0.0.0.0:5020, OPC UA en opc.tcp://0.0.0.0:4840/yerba/

Latencias:
- MQTT: ~100-500ms
- Modbus: ~200ms (intervalo polling _apply_external_writes)
- OPC UA: ~2-3s
"""
import json
import os
import socket
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session", autouse=True)
def _auth_session():
    """Login admin y aplicar Authorization header global via session, además parchear requests.post/get default."""
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=10)
    r.raise_for_status()
    tok = r.json()["access_token"]
    hdrs = {"Authorization": f"Bearer {tok}"}
    orig_post = requests.post
    orig_get = requests.get
    def _post(url, **kw):
        kw.setdefault("headers", {}).update(hdrs)
        return orig_post(url, **kw)
    def _get(url, **kw):
        kw.setdefault("headers", {}).update(hdrs)
        return orig_get(url, **kw)
    requests.post = _post
    requests.get = _get
    yield
    requests.post = orig_post
    requests.get = orig_get


def _state():
    r = requests.get(f"{API}/state", timeout=10)
    r.raise_for_status()
    return r.json()


def _reset_defaults():
    """Limpiar fallas y manipuladas a un estado conocido."""
    requests.post(f"{API}/zapecado", json={
        "velocidad_chip": 30, "velocidad_tambor": 15,
        "falla_quemador": False, "falla_motor_tambor": False
    }, timeout=5)
    requests.post(f"{API}/secado", json={
        "posicion_calefactor": 0, "velocidad_aire": 50,
        "falla_ventilador": False, "falla_serpentin": False,
        "pid_t": {"enabled": False, "reset": True},
        "pid_h": {"enabled": False, "reset": True}
    }, timeout=5)
    requests.post(f"{API}/camaras/0", json={
        "vapor_activo": False, "vapor_caudal_kgh": 0,
        "falla_ventilador": False, "fuga_vapor": False, "puerta_abierta": False
    }, timeout=5)


# ============================ MQTT BIDIRECCIONAL ============================

def _mqtt_broker_available():
    try:
        s = socket.create_connection(("localhost", 1883), timeout=1.5)
        s.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def mqtt_client():
    if not _mqtt_broker_available():
        pytest.skip("MQTT broker no disponible en localhost:1883")
    import paho.mqtt.client as mqtt
    c = mqtt.Client(client_id="iter11_test", callback_api_version=mqtt.CallbackAPIVersion.VERSION2) \
        if hasattr(mqtt, "CallbackAPIVersion") else mqtt.Client(client_id="iter11_test")
    c.connect("localhost", 1883, keepalive=30)
    c.loop_start()
    time.sleep(0.3)
    yield c
    c.loop_stop()
    c.disconnect()


class TestMqttBidirectional:
    def test_zapecado_cmd(self, mqtt_client):
        _reset_defaults()
        mqtt_client.publish("yerba/cmd/zapecado",
                            json.dumps({"velocidad_chip": 80, "falla_quemador": True}), qos=0)
        time.sleep(1.0)
        st = _state()["zapecado"]
        assert st["velocidad_chip"] == 80, f"velocidad_chip={st['velocidad_chip']}"
        assert st["faults"]["falla_quemador"] is True

    def test_secado_cmd_with_pid(self, mqtt_client):
        _reset_defaults()
        # Nota: el simulador override pid_t.sp ← temperatura_obj cuando PID está enabled,
        # por lo que para mantener sp=98 hay que enviar también temperatura_obj=98.
        mqtt_client.publish("yerba/cmd/secado",
                            json.dumps({"posicion_calefactor": 75,
                                        "temperatura_obj": 98,
                                        "pid_t": {"enabled": True, "sp": 98}}), qos=0)
        # Tomar snapshot rápido antes que el PID iguale posicion_calefactor a su salida
        time.sleep(0.3)
        st = _state()["secado"]
        # pid_t.enabled & sp deben persistir
        assert st["pid_t"]["enabled"] is True
        assert st["pid_t"]["sp"] == 98
        # posicion_calefactor: PID activo lo gobierna; aceptamos 75 inicial o salida del PID (>0)
        assert st["posicion_calefactor"] > 0, f"pos_cal={st['posicion_calefactor']}"

    def test_camara_cmd(self, mqtt_client):
        _reset_defaults()
        mqtt_client.publish("yerba/cmd/camara/0",
                            json.dumps({"vapor_activo": True, "vapor_caudal_kgh": 30,
                                        "temperatura_obj": 40}), qos=0)
        time.sleep(1.0)
        cam0 = _state()["camaras"][0]
        assert cam0["vapor_activo"] is True
        assert cam0["vapor_caudal_kgh"] == 30
        assert cam0["temperatura_obj"] == 40

    def test_raw_value_shortcut(self, mqtt_client):
        _reset_defaults()
        mqtt_client.publish("yerba/cmd/zapecado/velocidad_chip", "45", qos=0)
        time.sleep(1.0)
        st = _state()["zapecado"]
        assert st["velocidad_chip"] == 45, f"got {st['velocidad_chip']}"

    def test_weather_cmd(self, mqtt_client):
        mqtt_client.publish("yerba/cmd/weather",
                            json.dumps({"temperature": 18, "humidity": 80}), qos=0)
        time.sleep(1.0)
        amb = _state()["ambient"]
        assert abs(amb["temp"] - 18) < 0.5
        assert amb["source"] == "mqtt-cmd"


# ============================ MODBUS BIDIRECCIONAL ============================

@pytest.fixture(scope="module")
def modbus_client():
    try:
        from pymodbus.client import ModbusTcpClient
    except Exception:
        pytest.skip("pymodbus no instalado")
    c = ModbusTcpClient("127.0.0.1", port=5020, timeout=3)
    if not c.connect():
        pytest.skip("Modbus server no responde en :5020")
    yield c
    c.close()


class TestModbusBidirectional:
    def test_zapecado_register_and_coil(self, modbus_client):
        _reset_defaults()
        # Restaurar temperatura sp
        requests.post(f"{API}/weather/manual", json={"temperature": 18, "humidity": 75}, timeout=5)
        # reg5 escala /10 → 4800 → 480
        r1 = modbus_client.write_register(address=5, value=4800, slave=0)
        assert not r1.isError(), f"write_register err: {r1}"
        # coil0 → falla_quemador
        r2 = modbus_client.write_coil(address=0, value=True, slave=0)
        assert not r2.isError()
        time.sleep(1.5)
        st = _state()["zapecado"]
        assert st["temperatura_obj"] == 480, f"got {st['temperatura_obj']}"
        assert st["faults"]["falla_quemador"] is True
        # cleanup
        modbus_client.write_coil(address=0, value=False, slave=0)

    def test_secado_registers_and_coil(self, modbus_client):
        _reset_defaults()
        # reg4 secado → temperatura_obj /10
        r1 = modbus_client.write_register(address=4, value=950, slave=1)
        assert not r1.isError()
        r2 = modbus_client.write_register(address=7, value=700, slave=1)
        assert not r2.isError()
        r3 = modbus_client.write_coil(address=0, value=True, slave=1)
        assert not r3.isError()
        time.sleep(1.5)
        st = _state()["secado"]
        assert st["temperatura_obj"] == 95
        assert abs(st["posicion_calefactor"] - 70) < 0.5
        assert st["faults"]["falla_ventilador"] is True
        modbus_client.write_coil(address=0, value=False, slave=1)

    def test_camara_registers(self, modbus_client):
        _reset_defaults()
        # slave=3 → cam 0
        r1 = modbus_client.write_register(address=3, value=380, slave=3)
        assert not r1.isError()
        r2 = modbus_client.write_register(address=10, value=250, slave=3)
        assert not r2.isError()
        time.sleep(1.5)
        cam = _state()["camaras"][0]
        assert cam["temperatura_obj"] == 38, f"got {cam['temperatura_obj']}"
        assert abs(cam["vapor_caudal_kgh"] - 25) < 0.5


# ============================ OPC UA BIDIRECCIONAL ============================

@pytest.fixture(scope="module")
def opcua_client():
    try:
        from opcua import Client
    except Exception:
        pytest.skip("opcua no instalado")
    cli = Client("opc.tcp://127.0.0.1:4840/yerba/", timeout=5)
    try:
        cli.connect()
    except Exception as e:
        pytest.skip(f"OPC UA no responde: {e}")
    yield cli
    try:
        cli.disconnect()
    except Exception:
        pass


class TestOpcuaBidirectional:
    def test_zapecado_temperatura_objetivo(self, opcua_client):
        _reset_defaults()
        node = opcua_client.get_objects_node().get_child(
            ["2:Zapecado", "2:TemperaturaObjetivo"]
        )
        node.set_value(500.0)
        time.sleep(4.0)
        st = _state()["zapecado"]
        assert st["temperatura_obj"] == 500.0, f"got {st['temperatura_obj']}"

    def test_camara1_falla_ventilador(self, opcua_client):
        _reset_defaults()
        node = opcua_client.get_objects_node().get_child(
            ["2:Camara1", "2:FallaVentilador"]
        )
        node.set_value(True)
        time.sleep(4.0)
        cam = _state()["camaras"][0]
        assert cam["faults"]["falla_ventilador"] is True
        node.set_value(False)


# ============================ DOCS ============================

class TestDocs:
    def test_list_3_files(self):
        r = requests.get(f"{API}/docs", timeout=5)
        assert r.status_code == 200
        files = r.json()
        names = {f["name"] for f in files}
        assert "manual_operaciones.md" in names
        assert "manual_tecnico.md" in names
        assert "instructivo_nodered.md" in names

    def test_instructivo_content(self):
        r = requests.get(f"{API}/docs/instructivo_nodered.md", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "instructivo_nodered.md"
        assert "content" in data
        assert len(data["content"]) > 10_000, f"content size={len(data['content'])}"


# ============================ WEATHER ============================

class TestWeather:
    def test_ambient_source_valid(self):
        amb = _state()["ambient"]
        assert amb.get("source") in ("open-meteo", "fallback-seasonal", "manual", "mqtt-cmd"), \
            f"source inválido: {amb.get('source')}"

    def test_forecast_count_in_range_when_present(self):
        sim = _state()["sim"]
        fc = sim.get("forecast_count")
        if fc and fc > 0:
            assert 24 <= fc <= 96, f"forecast_count={fc} fuera de 24..96"


# ============================ REGRESSION ============================

class TestRegression:
    def test_pid_secado_t_converges(self):
        _reset_defaults()
        requests.post(f"{API}/weather/manual", json={"temperature": 18, "humidity": 75}, timeout=5)
        requests.post(f"{API}/secado", json={
            "pid_t": {"enabled": True, "sp": 95, "kp": 4.0, "ki": 0.15, "reset": True}
        }, timeout=5)
        time.sleep(32)
        st = _state()["secado"]
        T = st["temperatura"]
        assert 93 <= T <= 97, f"T={T} no converge a 95±2 (con 30s y accel=60)"
        # cleanup
        requests.post(f"{API}/secado", json={"pid_t": {"enabled": False}}, timeout=5)
