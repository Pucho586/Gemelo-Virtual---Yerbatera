"""Tests for FASE 2 - Industria 4.0: external sources, drift, calibration, audit."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def operator_token():
    r = requests.post(f"{API}/auth/login", json={"username": "operario", "password": "operario"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- external/status ----------
class TestExternalStatus:
    def test_status_shape(self, admin_token):
        r = requests.get(f"{API}/external/status", headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("mirror", "drift", "modbus_client", "opcua_client", "mqtt_subscriber", "config"):
            assert key in body, f"Falta {key} en /external/status"
        assert isinstance(body["mirror"], dict)
        assert "values" in body["mirror"] and "errors" in body["mirror"]


# ---------- Modbus client closed-loop ----------
class TestModbusClient:
    def test_operator_forbidden(self, operator_token):
        r = requests.post(f"{API}/external/modbus_client",
                          json={"enabled": True, "host": "127.0.0.1", "port": 5020, "interval": 2.0},
                          headers=hdr(operator_token), timeout=10)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_admin_enable_and_mirror_populates(self, admin_token):
        r = requests.post(f"{API}/external/modbus_client",
                          json={"enabled": True, "host": "127.0.0.1", "port": 5020, "interval": 2.0},
                          headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body["status"]["running"] is True

        # Esperar a que polleo se complete (interval=2s + connect time)
        time.sleep(6)
        r2 = requests.get(f"{API}/external/status", headers=hdr(admin_token), timeout=10)
        assert r2.status_code == 200
        data = r2.json()
        values = data["mirror"]["values"]
        errors = data["mirror"]["errors"]
        assert "modbus_client" not in errors or not errors.get("modbus_client"), \
            f"modbus_client error: {errors.get('modbus_client')}"
        assert len(values) >= 15, f"Esperado >=15 tags en mirror, got {len(values)}: {list(values.keys())}"
        # Verificar tags clave
        assert "zapecado.temperatura" in values
        assert "secado.temperatura" in values


# ---------- Modo + drift ----------
class TestModeAndDrift:
    def test_set_mode_shadow(self, admin_token):
        r = requests.post(f"{API}/mode", json={"mode": "shadow"},
                          headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200
        assert r.json()["mode"] == "shadow"

    def test_drift_populated_in_shadow(self, admin_token):
        # Necesita Modbus cliente ya activo (test anterior). Esperar a que loop apply corra.
        time.sleep(3)
        r = requests.get(f"{API}/drift", headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200
        drift = r.json()
        assert isinstance(drift, dict)
        assert len(drift) > 0, f"drift vacío en modo shadow: {drift}"
        # Sample one tag
        sample_tag = next(iter(drift))
        sample = drift[sample_tag]
        for k in ("sim", "ext", "delta", "pct"):
            assert k in sample, f"falta {k} en drift[{sample_tag}]: {sample}"

    def test_set_mode_twin(self, admin_token):
        r = requests.post(f"{API}/mode", json={"mode": "twin"},
                          headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200
        assert r.json()["mode"] == "twin"
        # Tras un par de segundos, sim values deberían acercarse a mirror values
        time.sleep(3)
        st = requests.get(f"{API}/external/status", headers=hdr(admin_token), timeout=10).json()
        sim_state = requests.get(f"{API}/state", timeout=10).json()
        ext_v = st["mirror"]["values"].get("zapecado.temperatura")
        sim_v = sim_state.get("zapecado", {}).get("temperatura")
        if ext_v is not None and sim_v is not None:
            assert abs(float(sim_v) - float(ext_v)) < 5, \
                f"twin no sincroniza zapecado.temp: sim={sim_v}, ext={ext_v}"

    def test_back_to_simulator(self, admin_token):
        r = requests.post(f"{API}/mode", json={"mode": "simulator"},
                          headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200


# ---------- OPC UA y MQTT clients endpoints ----------
class TestOtherClients:
    def test_opcua_client_endpoint(self, admin_token):
        r = requests.post(f"{API}/external/opcua_client",
                          json={"enabled": True, "endpoint": "opc.tcp://127.0.0.1:4840/yerba/", "interval": 2.0},
                          headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_mqtt_subscriber_endpoint(self, admin_token):
        r = requests.post(f"{API}/external/mqtt_subscriber",
                          json={"enabled": True, "broker": "localhost", "port": 1883, "topic_base": "yerba_in"},
                          headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # status.running flag debe estar
        assert "running" in r.json()["status"]


# ---------- Calibración CSV ----------
class TestCalibration:
    CSV = (
        "ts,zap_temperatura,sec_temperatura,sec_humedad,cam1_temperatura\n"
        "2026-01-01,440,90,30,35\n"
        "2026-01-02,445,92,28,35.2\n"
        "2026-01-03,448,93,25,35.5\n"
        "2026-01-04,449,94,22,35.6\n"
        "2026-01-05,449.5,94.5,20,35.7\n"
        "2026-01-06,450,95,18,35.8\n"
    )

    def test_analyze(self, admin_token):
        r = requests.post(f"{API}/calibration/analyze",
                          json={"csv": self.CSV},
                          headers=hdr(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # Debe tener al menos los 3 grupos mencionados
        assert isinstance(body, dict)
        # Buscar campos tau anidados
        s = str(body)
        assert "tau" in s, f"Esperado campo tau en respuesta calibration/analyze: {body}"
        TestCalibration._last_result = body

    def test_apply(self, admin_token):
        result = getattr(TestCalibration, "_last_result", None)
        assert result is not None, "Run analyze primero"
        r = requests.post(f"{API}/calibration/apply",
                          json={"calibration": result},
                          headers=hdr(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_analyze_forbidden_operator(self, operator_token):
        r = requests.post(f"{API}/calibration/analyze",
                          json={"csv": self.CSV},
                          headers=hdr(operator_token), timeout=10)
        assert r.status_code == 403


# ---------- Audit log ----------
class TestAudit:
    def test_admin_sees_all(self, admin_token):
        r = requests.get(f"{API}/audit", headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200
        events = r.json()
        assert isinstance(events, list)
        assert len(events) > 0, "audit vacío - debería tener set_mode, configure_external, calibration_apply"
        actions = {e.get("action") for e in events}
        # Al menos uno de los esperados
        assert any(a in actions for a in ("set_mode", "calibration_apply")
                   or any(a and a.startswith("configure_external") for a in actions for _ in [0])), \
            f"acciones encontradas: {actions}"

    def test_operator_sees_only_own(self, operator_token, admin_token):
        # Primero, generar un evento como operario (login ya queda registrado? No, login no se audita)
        # El operario puede no tener eventos, pero el endpoint debe filtrar por su username.
        r = requests.get(f"{API}/audit", headers=hdr(operator_token), timeout=10)
        assert r.status_code == 200
        events = r.json()
        assert isinstance(events, list)
        for e in events:
            assert e.get("username") == "operario", f"operario ve evento ajeno: {e}"


# ---------- Regresión básica ----------
class TestRegression:
    def test_state(self):
        r = requests.get(f"{API}/state", timeout=10)
        assert r.status_code == 200
        s = r.json()
        assert "zapecado" in s and "secado" in s

    def test_services_status(self):
        r = requests.get(f"{API}/services/status", timeout=10)
        assert r.status_code == 200
        assert "modbus" in r.json()

    def test_recipes(self):
        r = requests.get(f"{API}/recipes", timeout=10)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_batches_list(self, admin_token):
        r = requests.get(f"{API}/batches", headers=hdr(admin_token), timeout=10)
        assert r.status_code == 200
