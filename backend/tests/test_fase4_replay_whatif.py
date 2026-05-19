"""Tests for FASE 4: chambers count, steam injection, replay mode, what-if scenarios."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-code-mentor-11.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=15)
    assert r.status_code == 200, f"admin login failed {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def operario_token():
    r = requests.post(f"{API}/auth/login", json={"username": "operario", "password": "operario"}, timeout=15)
    assert r.status_code == 200
    return r.json()["access_token"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Cámaras: steam fields ----------
class TestCamaras:
    def test_state_has_new_camera_fields(self):
        r = requests.get(f"{API}/state", timeout=15)
        assert r.status_code == 200
        camaras = r.json().get("camaras", [])
        assert len(camaras) >= 1
        c0 = camaras[0]
        for key in ("vapor_activo", "vapor_caudal_kgh", "vapor_setpoint_temp", "vapor_setpoint_hum", "vapor_kg_acum"):
            assert key in c0, f"missing {key} in camara0"

    def test_patch_camara_steam(self, admin_token):
        body = {"vapor_activo": True, "vapor_caudal_kgh": 30, "vapor_setpoint_temp": 42, "vapor_setpoint_hum": 85}
        r = requests.post(f"{API}/camaras/0", json=body, headers=H(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        r2 = requests.get(f"{API}/state", timeout=15)
        c0 = r2.json()["camaras"][0]
        assert c0["vapor_activo"] is True
        assert c0["vapor_caudal_kgh"] == 30
        assert c0["vapor_setpoint_temp"] == 42
        assert c0["vapor_setpoint_hum"] == 85

    def test_camaras_count_admin_only(self, operario_token):
        # operario => 403
        r = requests.post(f"{API}/camaras/count", json={"count": 5}, headers=H(operario_token), timeout=15)
        assert r.status_code == 403
        # missing auth => 401
        r2 = requests.post(f"{API}/camaras/count", json={"count": 5}, timeout=15)
        assert r2.status_code in (401, 403)

    def test_camaras_count_grow_shrink_persist(self, admin_token):
        # Grow to 6
        r = requests.post(f"{API}/camaras/count", json={"count": 6}, headers=H(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["count"] == 6
        assert data["max"] == 12
        assert len(data["camaras"]) == 6
        # State reflects
        s = requests.get(f"{API}/state", timeout=15).json()
        assert len(s["camaras"]) == 6
        # Shrink to 3
        r2 = requests.post(f"{API}/camaras/count", json={"count": 3}, headers=H(admin_token), timeout=15)
        assert r2.json()["count"] == 3
        # Persistence: set to 4 -> read /state -> should be 4
        r3 = requests.post(f"{API}/camaras/count", json={"count": 4}, headers=H(admin_token), timeout=15)
        assert r3.json()["count"] == 4
        s2 = requests.get(f"{API}/state", timeout=15).json()
        assert len(s2["camaras"]) == 4


# ---------- Replay ----------
class TestReplay:
    def test_replay_files_lists_csvs(self):
        r = requests.get(f"{API}/replay/files", timeout=15)
        assert r.status_code == 200
        files = r.json()
        assert isinstance(files, list)
        assert len(files) >= 1
        assert all("name" in f and f["name"].endswith(".csv") for f in files)

    def test_replay_admin_only(self, operario_token):
        r = requests.post(f"{API}/replay/start", json={"file": "x.csv"}, headers=H(operario_token), timeout=15)
        assert r.status_code == 403
        r2 = requests.post(f"{API}/replay/start", json={"file": "x.csv"}, timeout=15)
        assert r2.status_code in (401, 403)

    def test_replay_full_lifecycle(self, admin_token):
        files = requests.get(f"{API}/replay/files", timeout=15).json()
        assert files, "no replay files available"
        fname = files[0]["name"]
        # Start
        r = requests.post(f"{API}/replay/start", json={"file": fname, "speed": 10},
                          headers=H(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["active"] is True
        # Mode should be replay
        m = requests.get(f"{API}/mode", timeout=15).json()
        assert m["mode"] == "replay"
        # Pause
        rp = requests.post(f"{API}/replay/pause", json={"paused": True}, headers=H(admin_token), timeout=15)
        assert rp.status_code == 200
        assert rp.json()["paused"] is True
        # Resume
        rr = requests.post(f"{API}/replay/pause", json={"paused": False}, headers=H(admin_token), timeout=15)
        assert rr.json()["paused"] is False
        # Seek
        rs = requests.post(f"{API}/replay/seek", json={"row": 50}, headers=H(admin_token), timeout=15)
        assert rs.status_code == 200
        assert rs.json()["cursor"] == 50 or rs.json()["cursor"] >= 50  # may auto-advance
        # Speed
        rsp = requests.post(f"{API}/replay/speed", json={"speed": 60}, headers=H(admin_token), timeout=15)
        assert rsp.status_code == 200
        assert rsp.json()["speed"] == 60
        # Status
        stt = requests.get(f"{API}/replay/status", timeout=15).json()
        assert stt["active"] is True
        assert stt["file"] == fname
        # Stop
        rst = requests.post(f"{API}/replay/stop", headers=H(admin_token), timeout=15)
        assert rst.status_code == 200
        m2 = requests.get(f"{API}/mode", timeout=15).json()
        assert m2["mode"] == "simulator"


# ---------- What-if ----------
class TestWhatIf:
    @classmethod
    def teardown_class(cls):
        # cleanup: reset whatif
        try:
            r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=10)
            t = r.json()["access_token"]
            requests.post(f"{API}/whatif/reset", headers={"Authorization": f"Bearer {t}"}, timeout=10)
        except Exception:
            pass

    def test_whatif_admin_only_create(self, operario_token):
        r = requests.post(f"{API}/whatif", json={"name": "X", "overrides": {}}, headers=H(operario_token), timeout=15)
        assert r.status_code == 403
        r2 = requests.post(f"{API}/whatif", json={"name": "X", "overrides": {}}, timeout=15)
        assert r2.status_code in (401, 403)

    def test_whatif_create_and_kpis(self, admin_token):
        # Reset to clean state
        requests.post(f"{API}/whatif/reset", headers=H(admin_token), timeout=15)
        body = {"name": "Test", "overrides": {"zapecado.velocidad_chip": 20}}
        r = requests.post(f"{API}/whatif", json=body, headers=H(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        sc = r.json()
        assert "id" in sc
        assert sc["name"] == "Test"
        assert "kpis" in sc
        # Wait for KPIs to populate
        time.sleep(3.5)
        lst = requests.get(f"{API}/whatif", timeout=15).json()
        assert len(lst) == 1
        kpis = lst[0]["kpis"]
        assert kpis["TempZapecado"] > 0
        assert kpis["TempSecado"] > 0
        # kWhAcum may be 0 if equipment inactive; check it's a number
        assert isinstance(kpis["kWhAcum"], (int, float))

    def test_whatif_max_3_scenarios(self, admin_token):
        requests.post(f"{API}/whatif/reset", headers=H(admin_token), timeout=15)
        for i in range(3):
            r = requests.post(f"{API}/whatif", json={"name": f"s{i}", "overrides": {}},
                              headers=H(admin_token), timeout=15)
            assert r.status_code == 200
        r4 = requests.post(f"{API}/whatif", json={"name": "s4", "overrides": {}},
                           headers=H(admin_token), timeout=15)
        assert r4.status_code == 400
        assert "Máximo 3" in r4.json().get("detail", "") or "3 escenarios" in r4.json().get("detail", "")

    def test_whatif_delete(self, admin_token):
        requests.post(f"{API}/whatif/reset", headers=H(admin_token), timeout=15)
        r = requests.post(f"{API}/whatif", json={"name": "todel", "overrides": {}},
                          headers=H(admin_token), timeout=15)
        sid = r.json()["id"]
        rd = requests.delete(f"{API}/whatif/{sid}", headers=H(admin_token), timeout=15)
        assert rd.status_code == 200
        lst = requests.get(f"{API}/whatif", timeout=15).json()
        assert all(s["id"] != sid for s in lst)

    def test_whatif_reset(self, admin_token):
        requests.post(f"{API}/whatif", json={"name": "r1", "overrides": {}}, headers=H(admin_token), timeout=15)
        rr = requests.post(f"{API}/whatif/reset", headers=H(admin_token), timeout=15)
        assert rr.status_code == 200
        lst = requests.get(f"{API}/whatif", timeout=15).json()
        assert lst == []


# ---------- Regression ----------
class TestRegression:
    def test_energy_endpoint_still_works(self):
        r = requests.get(f"{API}/energy", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "chips_kg" in data
        assert "prices" in data
        assert "kwh_by_component" in data

    def test_oee_endpoint(self):
        r = requests.get(f"{API}/oee", timeout=15)
        assert r.status_code == 200

    def test_recipes_endpoint(self):
        r = requests.get(f"{API}/recipes", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_alarms_active(self):
        r = requests.get(f"{API}/alarms/active", timeout=15)
        assert r.status_code == 200
