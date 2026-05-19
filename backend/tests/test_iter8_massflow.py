"""Iteration 8: Mass-flow tracking + Snapshot→Whatif + rodamientos rename tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
STAGES_ORDER = ["recepcion", "zapecado", "secado", "canchado", "estacionamiento"]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def operario_token():
    r = requests.post(f"{API}/auth/login", json={"username": "operario", "password": "operario"}, timeout=15)
    assert r.status_code == 200
    return r.json()["access_token"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def reset_state(admin_token):
    """Reset mass-flow state before every test."""
    requests.post(f"{API}/massflow/reset", headers=H(admin_token), timeout=15)
    yield


# ============ MASSFLOW: GET ============
class TestMassFlowGet:
    def test_initial_snapshot_shape(self):
        r = requests.get(f"{API}/massflow", timeout=15)
        assert r.status_code == 200
        data = r.json()
        for k in ("stages", "merma_pct", "order", "log_recent"):
            assert k in data, f"missing key {k}"
        assert data["order"] == STAGES_ORDER

    def test_default_mermas(self):
        data = requests.get(f"{API}/massflow", timeout=15).json()
        m = data["merma_pct"]
        assert m["recepcion"] == 0.0
        assert m["zapecado"] == 0.35
        assert m["secado"] == 0.22
        assert m["canchado"] == 0.04
        assert m["estacionamiento"] == 0.005

    def test_initial_stages_zero(self):
        data = requests.get(f"{API}/massflow", timeout=15).json()
        for s in STAGES_ORDER:
            assert data["stages"][s]["kg_actual"] == 0


# ============ MASSFLOW: CARGA ============
class TestCarga:
    def test_carga_defaults(self, admin_token):
        r = requests.post(f"{API}/massflow/carga", json={"kg": 1000}, headers=H(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["kg_actual"] == 1000
        assert body["kg_acum_in"] == 1000
        assert body["H_in"] == 55.0
        assert body["T_in"] is not None  # ambient

    def test_carga_explicit_T_H(self, admin_token):
        requests.post(f"{API}/massflow/carga", json={"kg": 500, "T": 18, "H": 52},
                      headers=H(admin_token), timeout=15)
        snap = requests.get(f"{API}/massflow", timeout=15).json()
        r = snap["stages"]["recepcion"]
        assert r["kg_actual"] == 500
        assert r["T_in"] == 18.0
        assert r["H_in"] == 52.0

    def test_carga_weighted_avg(self, admin_token):
        # First load 500 kg @ T=20, H=50
        requests.post(f"{API}/massflow/carga", json={"kg": 500, "T": 20, "H": 50},
                      headers=H(admin_token), timeout=15)
        # Second load 500 kg @ T=30, H=60 → average should be 25, 55
        requests.post(f"{API}/massflow/carga", json={"kg": 500, "T": 30, "H": 60},
                      headers=H(admin_token), timeout=15)
        r = requests.get(f"{API}/massflow", timeout=15).json()["stages"]["recepcion"]
        assert r["kg_actual"] == 1000
        assert abs(r["T_in"] - 25.0) < 0.1
        assert abs(r["H_in"] - 55.0) < 0.1

    def test_carga_invalid_kg(self, admin_token):
        r = requests.post(f"{API}/massflow/carga", json={"kg": 0}, headers=H(admin_token), timeout=15)
        assert r.status_code == 400


# ============ MASSFLOW: TRANSFERIR ============
class TestTransferir:
    def test_recepcion_to_zapecado_no_merma(self, admin_token):
        requests.post(f"{API}/massflow/carga", json={"kg": 1000}, headers=H(admin_token), timeout=15)
        r = requests.post(f"{API}/massflow/transferir", json={"de": "recepcion", "a": "zapecado"},
                          headers=H(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        ev = r.json()
        assert ev["kg_in"] == 1000
        assert ev["kg_out"] == 1000  # recepcion merma = 0
        snap = requests.get(f"{API}/massflow", timeout=15).json()["stages"]
        assert snap["recepcion"]["kg_actual"] == 0
        assert snap["zapecado"]["kg_actual"] == 1000
        assert snap["zapecado"]["H_in"] == 55.0  # inherits from recepcion output

    def test_zapecado_to_secado_with_merma(self, admin_token):
        # Load + transfer to zapecado first
        requests.post(f"{API}/massflow/carga", json={"kg": 1000}, headers=H(admin_token), timeout=15)
        requests.post(f"{API}/massflow/transferir", json={"de": "recepcion", "a": "zapecado"},
                      headers=H(admin_token), timeout=15)
        # Now to secado, expect 35% merma
        r = requests.post(f"{API}/massflow/transferir", json={"de": "zapecado", "a": "secado"},
                          headers=H(admin_token), timeout=15)
        assert r.status_code == 200
        ev = r.json()
        assert abs(ev["kg_out"] - 650.0) < 0.1  # 1000 * 0.65
        assert abs(ev["merma_kg"] - 350.0) < 0.1
        assert ev["merma_pct"] == 0.35
        snap = requests.get(f"{API}/massflow", timeout=15).json()["stages"]
        assert abs(snap["secado"]["kg_actual"] - 650.0) < 0.1
        assert snap["secado"]["T_in"] is not None

    def test_non_sequential_transfer_400(self, admin_token):
        requests.post(f"{API}/massflow/carga", json={"kg": 1000}, headers=H(admin_token), timeout=15)
        r = requests.post(f"{API}/massflow/transferir", json={"de": "recepcion", "a": "secado"},
                          headers=H(admin_token), timeout=15)
        assert r.status_code == 400

    def test_partial_transfer_keeps_remainder(self, admin_token):
        requests.post(f"{API}/massflow/carga", json={"kg": 1000}, headers=H(admin_token), timeout=15)
        r = requests.post(f"{API}/massflow/transferir",
                          json={"de": "recepcion", "a": "zapecado", "kg": 400},
                          headers=H(admin_token), timeout=15)
        assert r.status_code == 200
        snap = requests.get(f"{API}/massflow", timeout=15).json()["stages"]
        assert snap["recepcion"]["kg_actual"] == 600
        assert snap["zapecado"]["kg_actual"] == 400  # recepcion merma = 0

    def test_transfer_empty_stage_400(self, admin_token):
        r = requests.post(f"{API}/massflow/transferir", json={"de": "recepcion", "a": "zapecado"},
                          headers=H(admin_token), timeout=15)
        assert r.status_code == 400


# ============ MASSFLOW: MERMA + RESET (admin only) ============
class TestAdminOps:
    def test_set_merma_persists(self, admin_token):
        r = requests.post(f"{API}/massflow/merma", json={"stage": "zapecado", "pct": 0.30},
                          headers=H(admin_token), timeout=15)
        assert r.status_code == 200
        snap = r.json()
        assert snap["merma_pct"]["zapecado"] == 0.30
        # verify via GET
        g = requests.get(f"{API}/massflow", timeout=15).json()
        assert g["merma_pct"]["zapecado"] == 0.30
        # restore default
        requests.post(f"{API}/massflow/merma", json={"stage": "zapecado", "pct": 0.35},
                      headers=H(admin_token), timeout=15)

    def test_merma_operario_403(self, operario_token):
        r = requests.post(f"{API}/massflow/merma", json={"stage": "zapecado", "pct": 0.30},
                          headers=H(operario_token), timeout=15)
        assert r.status_code == 403

    def test_merma_no_auth_401(self):
        r = requests.post(f"{API}/massflow/merma", json={"stage": "zapecado", "pct": 0.30}, timeout=15)
        assert r.status_code in (401, 403)

    def test_reset_admin_ok(self, admin_token):
        requests.post(f"{API}/massflow/carga", json={"kg": 500}, headers=H(admin_token), timeout=15)
        r = requests.post(f"{API}/massflow/reset", headers=H(admin_token), timeout=15)
        assert r.status_code == 200
        snap = r.json()
        for s in STAGES_ORDER:
            assert snap["stages"][s]["kg_actual"] == 0

    def test_reset_operario_403(self, operario_token):
        r = requests.post(f"{API}/massflow/reset", headers=H(operario_token), timeout=15)
        assert r.status_code == 403


# ============ WHATIF SNAPSHOT ============
class TestWhatIfSnapshot:
    @classmethod
    def teardown_class(cls):
        try:
            r = requests.post(f"{API}/auth/login",
                              json={"username": "admin", "password": "admin"}, timeout=10)
            t = r.json()["access_token"]
            requests.post(f"{API}/whatif/reset", headers={"Authorization": f"Bearer {t}"}, timeout=10)
        except Exception:
            pass

    def test_snapshot_creates_scenario(self, admin_token):
        requests.post(f"{API}/whatif/reset", headers=H(admin_token), timeout=15)
        body = {"name": "Snap1", "extra_overrides": {"secado": {"velocidad_aire": 0.7}}}
        r = requests.post(f"{API}/whatif/snapshot", json=body, headers=H(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        sc = r.json()
        assert sc["name"] == "Snap1"
        # Verify it exists in /whatif list
        lst = requests.get(f"{API}/whatif", timeout=15).json()
        assert any(s["name"] == "Snap1" for s in lst)
        # cleanup
        requests.post(f"{API}/whatif/reset", headers=H(admin_token), timeout=15)

    def test_snapshot_operario_403(self, operario_token):
        r = requests.post(f"{API}/whatif/snapshot",
                          json={"name": "X", "extra_overrides": {}},
                          headers=H(operario_token), timeout=15)
        assert r.status_code == 403

    def test_snapshot_no_auth(self):
        r = requests.post(f"{API}/whatif/snapshot",
                          json={"name": "X", "extra_overrides": {}}, timeout=15)
        assert r.status_code in (401, 403)


# ============ REGRESSION: rodamientos rename ============
class TestRodamientosRename:
    def test_maintenance_uses_rodamientos(self):
        r = requests.get(f"{API}/maintenance", timeout=15)
        assert r.status_code == 200
        items = r.json().get("items", [])
        actions = [it.get("accion") for it in items]
        assert "rodamientos" in actions, f"'rodamientos' not in actions: {actions}"
        assert "rulemanes" not in actions, f"'rulemanes' should be removed from actions"


# ============ REGRESSION: prior endpoints still work ============
class TestRegression:
    def test_energy(self):
        assert requests.get(f"{API}/energy", timeout=15).status_code == 200

    def test_oee(self):
        assert requests.get(f"{API}/oee", timeout=15).status_code == 200

    def test_alarms(self):
        assert requests.get(f"{API}/alarms/active", timeout=15).status_code == 200

    def test_state(self):
        assert requests.get(f"{API}/state", timeout=15).status_code == 200
