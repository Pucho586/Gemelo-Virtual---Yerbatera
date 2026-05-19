"""End-to-end pytest for Yerba Mate digital twin API."""
import os
import time
import json
import asyncio
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-code-mentor-11.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def client():
    """Session with admin bearer token for endpoints that require auth.

    Public endpoints (GET /state, /history, /services/status, /weather, etc.)
    work without auth but adding the header is harmless.
    """
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # admin login (seeded admin/admin)
    try:
        r = s.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=10)
        if r.status_code == 200:
            tok = r.json().get("access_token") or r.json().get("token")
            if tok:
                s.headers.update({"Authorization": f"Bearer {tok}"})
    except Exception:
        pass
    return s


# ---------- Core state ----------
class TestState:
    def test_root(self, client):
        r = client.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_state_structure(self, client):
        r = client.get(f"{API}/state")
        assert r.status_code == 200
        data = r.json()
        for k in ["ambient", "zapecado", "secado", "canchado", "camaras"]:
            assert k in data, f"Missing key {k} in state"
        assert isinstance(data["camaras"], list)
        assert len(data["camaras"]) == 4, f"Expected 4 camaras, got {len(data['camaras'])}"

    def test_services_status(self, client):
        r = client.get(f"{API}/services/status")
        assert r.status_code == 200
        data = r.json()
        for svc in ["modbus", "mqtt", "opcua", "weather", "persistence"]:
            assert svc in data, f"Missing service {svc}"
            assert "running" in data[svc], f"Missing running flag in {svc}"

    def test_history(self, client):
        # give simulator some time to accumulate history
        time.sleep(5)
        r = client.get(f"{API}/history?n=50")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)


# ---------- Controls ----------
class TestControls:
    def test_zapecado_patch(self, client):
        payload = {"velocidad_chip": 80, "velocidad_tambor": 25, "estado_alimentacion": True}
        r = client.post(f"{API}/zapecado", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert abs(data.get("velocidad_chip", 0) - 80) < 1e-3
        assert abs(data.get("velocidad_tambor", 0) - 25) < 1e-3
        assert data.get("estado_alimentacion") is True
        # verify persisted in /state
        st = client.get(f"{API}/state").json()["zapecado"]
        assert abs(st.get("velocidad_chip", 0) - 80) < 1e-3

    def test_secado_patch(self, client):
        payload = {"velocidad_aire": 5.0, "estado": True}
        r = client.post(f"{API}/secado", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert abs(data.get("velocidad_aire", 0) - 5.0) < 1e-3
        assert data.get("estado") is True

    def test_canchado_patch(self, client):
        payload = {"velocidad_molino": 90, "estado": True}
        r = client.post(f"{API}/canchado", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert abs(data.get("velocidad_molino", 0) - 90) < 1e-3

    def test_camara_patch(self, client):
        payload = {"carga_kg": 200, "ventilador": True, "temperatura_obj": 36}
        r = client.post(f"{API}/camaras/0", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert abs(data.get("carga_kg", 0) - 200) < 1e-3
        assert data.get("ventilador") is True
        assert abs(data.get("temperatura_obj", 0) - 36) < 1e-3

    def test_camara_invalid_idx(self, client):
        r = client.post(f"{API}/camaras/9", json={"carga_kg": 100})
        assert r.status_code == 404


# ---------- Config ----------
class TestConfig:
    def test_get_config(self, client):
        r = client.get(f"{API}/config")
        assert r.status_code == 200
        data = r.json()
        for k in ["modbus", "mqtt", "opcua", "simulacion", "persistence", "weather", "camaras"]:
            assert k in data, f"Missing config key {k}"

    def test_patch_config(self, client):
        payload = {"simulacion": {"aceleracion": 30}, "persistence": {"interval_seconds": 10, "enabled": True}}
        r = client.post(f"{API}/config", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data.get("saved") is True
        cfg = data.get("config", {})
        assert cfg.get("simulacion", {}).get("aceleracion") == 30
        assert cfg.get("persistence", {}).get("interval_seconds") == 10


# ---------- Weather ----------
class TestWeather:
    def test_weather_get(self, client):
        # Allow weather to fetch on startup
        r = client.get(f"{API}/weather")
        assert r.status_code == 200
        data = r.json()
        if data.get("available"):
            assert "location" in data
            assert "current" in data

    def test_weather_search(self, client):
        r = client.get(f"{API}/weather/search", params={"q": "Oberá"})
        assert r.status_code == 200
        results = r.json()
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_weather_set_location(self, client):
        payload = {"latitude": -31.4, "longitude": -64.2, "city": "Córdoba"}
        r = client.post(f"{API}/weather/location", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        loc = data.get("location", {})
        assert loc.get("city", "").startswith("Córdoba") or loc.get("city") == "Córdoba"


# ---------- AI ----------
class TestAI:
    def test_ai_chat(self, client):
        r = client.post(f"{API}/ai/chat", json={"message": "Diagnóstico rápido", "include_state": True}, timeout=60)
        assert r.status_code == 200, f"Chat failed: {r.text[:300]}"
        data = r.json()
        assert "reply" in data
        assert isinstance(data["reply"], str)
        assert len(data["reply"].strip()) > 0, "AI reply empty"
        assert "session_id" in data

    def test_ai_anomalies(self, client):
        r = client.get(f"{API}/ai/anomalies", timeout=60)
        assert r.status_code == 200
        data = r.json()
        assert "anomalies" in data
        assert "diagnosis" in data

    def test_ai_forecast(self, client):
        r = client.get(f"{API}/ai/forecast", params={"horizon": 20})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)


# ---------- Persistence ----------
class TestPersistence:
    def test_data_files(self, client):
        r = client.get(f"{API}/data/files")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_data_excel(self, client):
        r = client.get(f"{API}/data/excel")
        # 404 acceptable if no files yet; 200 if file generated
        assert r.status_code in (200, 404), f"unexpected {r.status_code}"
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            assert "spreadsheetml" in ct or "octet-stream" in ct


# ---------- WebSocket ----------
class TestWebSocket:
    def test_ws_stream(self):
        try:
            from websockets.sync.client import connect
        except ImportError:
            pytest.skip("websockets lib not available")
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws"
        with connect(ws_url, open_timeout=10) as ws:
            msg = ws.recv(timeout=5)
            data = json.loads(msg)
            assert "ambient" in data
            assert "camaras" in data
