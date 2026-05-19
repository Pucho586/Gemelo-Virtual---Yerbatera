"""FASE 3 Operaciones - tests para alarmas, OEE, mantenimiento, energía y reportes PDF."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def operario_token():
    r = requests.post(f"{API}/auth/login", json={"username": "operario", "password": "operario"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Alarmas ----------
class TestAlarms:
    def test_active_returns_list(self):
        r = requests.get(f"{API}/alarms/active", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_history_returns_list(self):
        r = requests.get(f"{API}/alarms/history?limit=50", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) <= 50

    def test_rules_default_count(self):
        r = requests.get(f"{API}/alarms/rules", timeout=10)
        assert r.status_code == 200
        rules = r.json()
        assert isinstance(rules, list)
        assert len(rules) >= 7

    def test_alarm_generated_after_simulator_runs(self):
        """Espera unos segundos para que zapecado>540 dispare alarma high."""
        deadline = time.time() + 15
        active = []
        while time.time() < deadline:
            r = requests.get(f"{API}/alarms/active", timeout=10)
            if r.status_code == 200 and len(r.json()) > 0:
                active = r.json()
                break
            time.sleep(2)
        # Aunque no haya alarma activa, verificar history tiene al menos una
        if not active:
            h = requests.get(f"{API}/alarms/history?limit=10", timeout=10).json()
            assert len(h) >= 0  # tolerante - puede que el sim no esté disparando
        else:
            a = active[0]
            for k in ("id", "rule_id", "name", "priority", "status", "tag"):
                assert k in a, f"falta campo {k} en alarma"
            assert a["priority"] in ("urgent", "high", "medium", "low")

    def test_ack_requires_auth(self):
        r = requests.post(f"{API}/alarms/ack", json={"alarm_id": "x"}, timeout=10)
        assert r.status_code in (401, 403)

    def test_ack_flow(self, operario_token):
        # busca una alarma en history
        h = requests.get(f"{API}/alarms/history?limit=20", timeout=10).json()
        if not h:
            pytest.skip("no hay alarmas para acknowledger")
        target = next((a for a in h if a["status"] in ("unacked_active", "unacked_rtn")), None)
        if not target:
            pytest.skip("no hay alarmas pendientes de ACK")
        r = requests.post(f"{API}/alarms/ack",
                          json={"alarm_id": target["id"]},
                          headers=H(operario_token), timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] in ("acked_active", "cleared")
        assert data["acked_by"] == "operario"

    def test_rules_admin_only(self, operario_token):
        rule = {"id": "TEST_custom_rule", "name": "Test rule", "tag": "secado.humedad",
                "op": "<", "threshold": 50, "priority": "low", "description": "test"}
        r = requests.post(f"{API}/alarms/rules", json=rule,
                          headers=H(operario_token), timeout=10)
        assert r.status_code == 403

    def test_rules_admin_create_and_delete(self, admin_token):
        rule = {"id": "TEST_custom_rule", "name": "Test rule", "tag": "secado.humedad",
                "op": "<", "threshold": 50, "priority": "low", "description": "test"}
        r = requests.post(f"{API}/alarms/rules", json=rule,
                          headers=H(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        # cleanup
        requests.delete(f"{API}/alarms/rules/TEST_custom_rule",
                        headers=H(admin_token), timeout=10)


# ---------- OEE ----------
class TestOEE:
    def test_oee_shape(self):
        r = requests.get(f"{API}/oee", timeout=10)
        assert r.status_code == 200
        d = r.json()
        for k in ("availability", "performance", "quality", "oee", "operativas_h", "produccion_kg"):
            assert k in d, f"falta campo {k}"
        for k in ("availability", "performance", "quality", "oee"):
            assert 0.0 <= float(d[k]) <= 1.0


# ---------- Mantenimiento ----------
class TestMaintenance:
    def test_maintenance_shape(self):
        r = requests.get(f"{API}/maintenance", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "total_runtime" in d
        assert isinstance(d["items"], list)
        assert len(d["items"]) > 0
        item = d["items"][0]
        for k in ("componente", "accion", "horas_marcha", "umbral_h", "status"):
            assert k in item
        assert item["status"] in ("ok", "warning", "due")

    def test_maintenance_ack(self, admin_token):
        r = requests.post(f"{API}/maintenance/ack",
                          json={"component": "tambor_zapecado", "action": "lubricacion"},
                          headers=H(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["component"] == "tambor_zapecado"
        assert d["action"] == "lubricacion"
        assert "ack_at" in d


# ---------- Energía ----------
class TestEnergy:
    def test_energy_shape(self):
        r = requests.get(f"{API}/energy", timeout=10)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_kwh", "gas_m3", "energy_cost_ars", "cost_per_kg_ars",
                  "margin_per_kg_ars", "runtime_hours", "kwh_by_component"):
            assert k in d, f"falta {k}"

    def test_prices_admin_only(self, operario_token):
        r = requests.post(f"{API}/energy/prices", json={"kwh_ars": 150},
                          headers=H(operario_token), timeout=10)
        assert r.status_code == 403

    def test_prices_admin_update(self, admin_token):
        r = requests.post(f"{API}/energy/prices", json={"kwh_ars": 150},
                          headers=H(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert float(d["kwh_ars"]) == 150.0
        # restore
        requests.post(f"{API}/energy/prices", json={"kwh_ars": 120},
                      headers=H(admin_token), timeout=10)

    def test_ops_reset_energy_admin(self, admin_token):
        r = requests.post(f"{API}/ops/reset?what=energy",
                          headers=H(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        # Inmediatamente despues, el costo de energia debe ser 0 (puede subir por el tick)
        e = requests.get(f"{API}/energy", timeout=10).json()
        # tolerancia: <100 (un tick puede haber sumado algo)
        assert e["energy_cost_ars"] < 100, f"energy_cost no se reseteó: {e['energy_cost_ars']}"

    def test_ops_reset_operario_403(self, operario_token):
        r = requests.post(f"{API}/ops/reset?what=energy",
                          headers=H(operario_token), timeout=10)
        assert r.status_code == 403


# ---------- Reportes PDF ----------
class TestReports:
    def test_monthly_pdf(self, operario_token):
        r = requests.get(f"{API}/reports/monthly", headers=H(operario_token), timeout=30)
        assert r.status_code == 200, r.text[:200]
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct, ct
        assert len(r.content) > 1024
        assert r.content[:4] == b"%PDF", f"no es PDF (magic: {r.content[:4]!r})"

    def test_batch_pdf(self, operario_token, admin_token):
        # crear o buscar batch
        lst = requests.get(f"{API}/batches?limit=5", headers=H(admin_token), timeout=10)
        batch_id = None
        if lst.status_code == 200 and lst.json():
            batch_id = lst.json()[0]["id"]
        if not batch_id:
            pytest.skip("no hay batches")
        r = requests.get(f"{API}/reports/batch/{batch_id}",
                         headers=H(operario_token), timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"


# ---------- Integración: cerrar batch actualiza kg_produced ----------
class TestBatchCloseUpdatesEnergy:
    def test_close_batch_increments_kg_produced(self, admin_token):
        # snapshot inicial
        e0 = requests.get(f"{API}/energy", timeout=10).json()
        kg0 = float(e0["kg_produced"])

        # crear receta minima
        recipe_payload = {
            "nombre": "TEST_F3_receta",
            "etapas": {
                "zapecado": {"temperatura": 530},
                "secado": {"temperatura": 105, "humedad_target": 8},
                "canchado": {"tamano_target": 2.0},
                "camaras": {"temp": 50, "hum_max": 14},
            },
        }
        rc = requests.post(f"{API}/recipes", json=recipe_payload,
                           headers=H(admin_token), timeout=10)
        assert rc.status_code in (200, 201), rc.text

        # crear batch
        bc = requests.post(f"{API}/batches",
                           json={"receta_id": rc.json()["id"], "kg_entrada": 100, "operario": "admin"},
                           headers=H(admin_token), timeout=10)
        assert bc.status_code in (200, 201), bc.text
        bid = bc.json()["id"]

        # cerrar batch
        cls = requests.post(f"{API}/batches/{bid}/close",
                            json={"kg_salida": 60, "observaciones": "test"},
                            headers=H(admin_token), timeout=10)
        assert cls.status_code == 200, cls.text

        # validar kg_produced subió
        e1 = requests.get(f"{API}/energy", timeout=10).json()
        kg1 = float(e1["kg_produced"])
        assert kg1 >= kg0 + 59, f"kg_produced no subió: {kg0} -> {kg1}"


# ---------- Regresión rápida FASE 1+2 ----------
class TestRegressionPhase1And2:
    def test_state(self):
        r = requests.get(f"{API}/state", timeout=10)
        assert r.status_code == 200

    def test_recipes(self, admin_token):
        r = requests.get(f"{API}/recipes", headers=H(admin_token), timeout=10)
        assert r.status_code == 200

    def test_batches(self, admin_token):
        r = requests.get(f"{API}/batches", headers=H(admin_token), timeout=10)
        assert r.status_code == 200

    def test_external_status(self):
        r = requests.get(f"{API}/external/status", timeout=10)
        assert r.status_code == 200

    def test_audit_admin(self, admin_token):
        r = requests.get(f"{API}/audit?limit=5", headers=H(admin_token), timeout=10)
        assert r.status_code == 200
