"""Tests for iteración v2.1 - auth, mode, throughput, recipes, batches."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-code-mentor-11.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(username: str, password: str):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=15)
    return r


@pytest.fixture(scope="session")
def admin_token():
    r = _login("admin", "admin")
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["user"]["role"] == "admin"
    assert "access_token" in body
    return body["access_token"]


@pytest.fixture(scope="session")
def operator_token():
    r = _login("operario", "operario")
    assert r.status_code == 200, f"Operator login failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["user"]["role"] == "operator"
    return body["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --------- AUTH ---------
class TestAuth:
    def test_login_admin(self):
        r = _login("admin", "admin")
        assert r.status_code == 200
        b = r.json()
        assert b["user"]["role"] == "admin"
        assert b["user"]["username"] == "admin"
        assert isinstance(b["access_token"], str) and len(b["access_token"]) > 20

    def test_login_operator(self):
        r = _login("operario", "operario")
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "operator"

    def test_login_invalid(self):
        r = _login("admin", "wrong")
        assert r.status_code == 401
        r2 = _login("doesnotexist", "x")
        assert r2.status_code == 401

    def test_me(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["username"] == "admin"
        assert d["role"] == "admin"
        assert "password_hash" not in d
        assert "_id" not in d

    def test_me_no_token(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_change_password_wrong_current(self, operator_token):
        r = requests.post(
            f"{API}/auth/change-password",
            json={"current_password": "wrong", "new_password": "newpw"},
            headers=_h(operator_token), timeout=10,
        )
        assert r.status_code == 401

    def test_change_password_correct_then_revert(self, operator_token):
        # cambiar a temporal
        r = requests.post(
            f"{API}/auth/change-password",
            json={"current_password": "operario", "new_password": "operario2"},
            headers=_h(operator_token), timeout=10,
        )
        assert r.status_code == 200
        # login con nueva
        assert _login("operario", "operario2").status_code == 200
        # revertir vía recover (sabemos código)
        rec = requests.post(
            f"{API}/auth/recover",
            json={"username": "operario", "recovery_code": "yerbatera-recovery-2026", "new_password": "operario"},
            timeout=10,
        )
        assert rec.status_code == 200
        assert _login("operario", "operario").status_code == 200

    def test_recover_invalid_code(self):
        r = requests.post(
            f"{API}/auth/recover",
            json={"username": "admin", "recovery_code": "wrong", "new_password": "x"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_list_users_admin(self, admin_token):
        r = requests.get(f"{API}/auth/users", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        users = r.json()
        names = {u["username"] for u in users}
        assert "admin" in names and "operario" in names
        for u in users:
            assert "password_hash" not in u

    def test_list_users_operator_forbidden(self, operator_token):
        r = requests.get(f"{API}/auth/users", headers=_h(operator_token), timeout=10)
        assert r.status_code == 403


# --------- MODE / THROUGHPUT ---------
class TestMode:
    def test_get_mode(self):
        r = requests.get(f"{API}/mode", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "mode" in d and "throughput_kgh" in d
        assert d["mode"] in ("simulator", "twin")

    def test_set_mode_admin(self, admin_token):
        r = requests.post(f"{API}/mode", json={"mode": "twin"}, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        assert requests.get(f"{API}/mode", timeout=10).json()["mode"] == "twin"
        # revert
        r2 = requests.post(f"{API}/mode", json={"mode": "simulator"}, headers=_h(admin_token), timeout=10)
        assert r2.status_code == 200

    def test_set_mode_operator_forbidden(self, operator_token):
        r = requests.post(f"{API}/mode", json={"mode": "twin"}, headers=_h(operator_token), timeout=10)
        assert r.status_code == 403

    def test_throughput_admin(self, admin_token):
        r = requests.post(f"{API}/throughput", json={"kgh": 1234.5}, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        assert abs(r.json()["throughput_kgh"] - 1234.5) < 1e-3
        assert abs(requests.get(f"{API}/mode", timeout=10).json()["throughput_kgh"] - 1234.5) < 1e-3

    def test_throughput_operator_forbidden(self, operator_token):
        r = requests.post(f"{API}/throughput", json={"kgh": 500}, headers=_h(operator_token), timeout=10)
        assert r.status_code == 403

    def test_twin_mode_freezes_simulator(self, admin_token):
        # set twin
        assert requests.post(f"{API}/mode", json={"mode": "twin"}, headers=_h(admin_token), timeout=10).status_code == 200
        s1 = requests.get(f"{API}/state", timeout=10).json()
        time.sleep(3)
        s2 = requests.get(f"{API}/state", timeout=10).json()
        # in twin mode, zapecado.humedad_salida should not change automatically
        z1 = s1["zapecado"].get("humedad_salida")
        z2 = s2["zapecado"].get("humedad_salida")
        # revert
        requests.post(f"{API}/mode", json={"mode": "simulator"}, headers=_h(admin_token), timeout=10)
        # tolerant: should be equal or very close (no auto-evolution)
        if z1 is not None and z2 is not None:
            assert abs(z1 - z2) < 1e-6, f"Twin mode should freeze sim, but {z1} -> {z2}"


# --------- STATE shape ---------
class TestStateNew:
    def test_state_has_new_fields(self):
        d = requests.get(f"{API}/state", timeout=10).json()
        assert "mode" in d
        assert "throughput_kgh" in d
        assert "flujo" in d
        flujo = d["flujo"]
        assert "zap_out_humedad" in flujo
        assert "sec_out_humedad" in flujo


# --------- RECIPES ---------
class TestRecipes:
    def test_list_defaults(self):
        r = requests.get(f"{API}/recipes", timeout=10)
        assert r.status_code == 200
        names = {x["id"] for x in r.json()}
        for rid in ("suave", "fuerte", "barbacua", "organica"):
            assert rid in names, f"Falta receta default {rid}"

    def test_apply_recipe_suave(self, operator_token):
        r = requests.post(f"{API}/recipes/suave/apply", headers=_h(operator_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["applied"] is True
        assert d["recipe"]["id"] == "suave"

    def test_apply_recipe_404(self, operator_token):
        r = requests.post(f"{API}/recipes/no-existe/apply", headers=_h(operator_token), timeout=10)
        assert r.status_code == 404

    def test_create_recipe_admin(self, admin_token):
        payload = {"id": "test-custom-xyz", "nombre": "TEST_custom", "descripcion": "t",
                   "zapecado": {"velocidad_chip": 70}, "secado": {"velocidad_aire": 4}}
        r = requests.post(f"{API}/recipes", json=payload, headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        assert r.json()["id"] == "test-custom-xyz"
        # appears in list
        ids = {x["id"] for x in requests.get(f"{API}/recipes", timeout=10).json()}
        assert "test-custom-xyz" in ids

    def test_create_recipe_operator_forbidden(self, operator_token):
        r = requests.post(f"{API}/recipes", json={"nombre": "x"}, headers=_h(operator_token), timeout=10)
        assert r.status_code == 403

    def test_delete_recipe_admin(self, admin_token):
        r = requests.delete(f"{API}/recipes/test-custom-xyz", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        assert r.json()["deleted"] == 1

    def test_delete_recipe_operator_forbidden(self, operator_token):
        r = requests.delete(f"{API}/recipes/suave", headers=_h(operator_token), timeout=10)
        assert r.status_code == 403


# --------- BATCHES ---------
class TestBatches:
    @pytest.fixture(autouse=True, scope="class")
    def _cleanup(self, admin_token):
        # If a batch is active at start, cancel it
        r = requests.get(f"{API}/batches/active", headers=_h(admin_token), timeout=10)
        if r.status_code == 200 and r.json():
            bid = r.json()["id"]
            requests.post(f"{API}/batches/{bid}/cancel", headers=_h(admin_token), timeout=10)
        yield
        r = requests.get(f"{API}/batches/active", headers=_h(admin_token), timeout=10)
        if r.status_code == 200 and r.json():
            bid = r.json()["id"]
            requests.post(f"{API}/batches/{bid}/cancel", headers=_h(admin_token), timeout=10)

    def test_list_batches_requires_auth(self):
        r = requests.get(f"{API}/batches", timeout=10)
        assert r.status_code == 401

    def test_active_when_none(self, admin_token):
        r = requests.get(f"{API}/batches/active", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        # null permitido
        assert r.json() is None or isinstance(r.json(), dict)

    def test_create_and_close_batch(self, operator_token):
        payload = {"kg_entrada": 1000, "receta_id": "suave", "observaciones": "TEST_batch"}
        r = requests.post(f"{API}/batches", json=payload, headers=_h(operator_token), timeout=10)
        assert r.status_code == 200, f"create batch: {r.status_code} {r.text}"
        batch = r.json()
        assert batch["kg_entrada"] == 1000
        assert "id" in batch
        bid = batch["id"]

        # 409 si intento otro
        r2 = requests.post(f"{API}/batches", json=payload, headers=_h(operator_token), timeout=10)
        assert r2.status_code == 409

        # active
        ra = requests.get(f"{API}/batches/active", headers=_h(operator_token), timeout=10)
        assert ra.status_code == 200
        assert ra.json()["id"] == bid

        # close with kg_salida -> merma 10%
        rc = requests.post(f"{API}/batches/{bid}/close", json={"kg_salida": 900},
                           headers=_h(operator_token), timeout=10)
        assert rc.status_code == 200
        closed = rc.json()
        assert "merma_pct" in closed
        assert abs(closed["merma_pct"] - 10.0) < 0.5

        # list includes it
        rl = requests.get(f"{API}/batches", headers=_h(operator_token), timeout=10)
        assert rl.status_code == 200
        ids = [b["id"] for b in rl.json()]
        assert bid in ids


# --------- SERVICES still up ---------
class TestServicesUp:
    def test_services_status(self):
        r = requests.get(f"{API}/services/status", timeout=10)
        assert r.status_code == 200
        d = r.json()
        for s in ("modbus", "opcua", "weather"):
            assert s in d
            assert "running" in d[s]
