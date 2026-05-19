"""Iteration 6: chips-de-madera migration + editable shifts/thresholds/PCI tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---- /api/energy: no gas, has chips ----
def test_energy_returns_chips_not_gas():
    r = requests.get(f"{API}/energy", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    # Must contain chips keys
    for k in ("chips_kg", "chips_cost_ars", "chip_calorific_mj_kg",
              "shifts_per_day", "hours_per_shift", "planned_hours_per_day",
              "energy_cost_ars", "prices"):
        assert k in body, f"missing {k}"
    assert "kg_chips_ars" in body["prices"]
    # Must NOT have gas anywhere
    flat = str(body).lower()
    assert "gas_m3" not in flat
    assert "m3_gas" not in flat
    assert "m3gas" not in flat
    # numeric energy cost (no crash)
    assert isinstance(body["energy_cost_ars"], (int, float))
    # planned = shifts * hours
    assert abs(body["planned_hours_per_day"] - body["shifts_per_day"] * body["hours_per_shift"]) < 1e-6


# ---- POST /api/energy/prices persists kwh, chips, yerba, PCI ----
def test_set_prices_persists(admin_headers):
    payload = {"kwh_ars": 125.5, "kg_chips_ars": 99.0, "kg_yerba_venta_ars": 3600.0, "chip_calorific_mj_kg": 18.5}
    r = requests.post(f"{API}/energy/prices", json=payload, headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    # GET back
    g = requests.get(f"{API}/energy", timeout=15).json()
    assert g["prices"]["kwh_ars"] == 125.5
    assert g["prices"]["kg_chips_ars"] == 99.0
    assert g["prices"]["kg_yerba_venta_ars"] == 3600.0
    assert g["chip_calorific_mj_kg"] == 18.5
    # Restore defaults
    requests.post(f"{API}/energy/prices",
                  json={"kwh_ars": 120, "kg_chips_ars": 95, "kg_yerba_venta_ars": 3500, "chip_calorific_mj_kg": 17},
                  headers=admin_headers, timeout=15)


def test_set_prices_requires_admin():
    r = requests.post(f"{API}/energy/prices", json={"kwh_ars": 200}, timeout=15)
    assert r.status_code in (401, 403), r.status_code

    # operario should also be rejected
    op = requests.post(f"{API}/auth/login",
                       json={"username": "operario", "password": "operario"}, timeout=15).json()
    r2 = requests.post(f"{API}/energy/prices", json={"kwh_ars": 200},
                       headers={"Authorization": f"Bearer {op['access_token']}"}, timeout=15)
    assert r2.status_code == 403, r2.status_code


# ---- POST /api/ops/shifts ----
def test_set_shifts_persists(admin_headers):
    r = requests.post(f"{API}/ops/shifts", json={"shifts_per_day": 2, "hours_per_shift": 6.0},
                      headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["shifts_per_day"] == 2
    assert j["hours_per_shift"] == 6.0
    assert j["planned_hours_per_day"] == 12.0
    # Confirm via /energy
    e = requests.get(f"{API}/energy", timeout=15).json()
    assert e["shifts_per_day"] == 2
    assert e["hours_per_shift"] == 6.0
    assert e["planned_hours_per_day"] == 12.0
    # restore defaults
    requests.post(f"{API}/ops/shifts", json={"shifts_per_day": 3, "hours_per_shift": 8.0},
                  headers=admin_headers, timeout=15)


def test_set_shifts_requires_admin():
    r = requests.post(f"{API}/ops/shifts", json={"shifts_per_day": 1}, timeout=15)
    assert r.status_code in (401, 403)


# ---- POST /api/maintenance/thresholds ----
def test_set_thresholds_persists(admin_headers):
    payload = {"thresholds": {"tambor_zapecado": {"lubricacion": 600, "rulemanes": 2500}}}
    r = requests.post(f"{API}/maintenance/thresholds", json=payload, headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    m = requests.get(f"{API}/maintenance", timeout=15).json()
    item = next((x for x in m["items"]
                 if x["componente"] == "tambor_zapecado" and x["accion"] == "lubricacion"), None)
    assert item is not None
    assert item["umbral_h"] == 600
    item2 = next((x for x in m["items"]
                  if x["componente"] == "tambor_zapecado" and x["accion"] == "rulemanes"), None)
    assert item2["umbral_h"] == 2500
    # restore defaults
    requests.post(f"{API}/maintenance/thresholds",
                  json={"thresholds": {"tambor_zapecado": {"lubricacion": 500, "rulemanes": 2000}}},
                  headers=admin_headers, timeout=15)


def test_set_thresholds_requires_admin():
    r = requests.post(f"{API}/maintenance/thresholds",
                      json={"thresholds": {"tambor_zapecado": {"lubricacion": 100}}}, timeout=15)
    assert r.status_code in (401, 403)


# ---- /api/reports/monthly: PDF with 'Chips de madera' ----
def test_report_monthly_pdf_has_chips(admin_headers):
    r = requests.get(f"{API}/reports/monthly", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    # Extract text via pypdf (the PDF stream is FlateDecode-compressed)
    from io import BytesIO
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(r.content))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    assert "Chips de madera" in text, f"Reporte mensual no menciona 'Chips de madera'. Texto: {text[:400]}"
    assert "Gas natural" not in text
    assert "m³ gas" not in text.lower()
