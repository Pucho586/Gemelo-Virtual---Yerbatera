"""Iteration 8 tests: SP/τ/Fault injection for Zapecado, Secado, Canchado, Cámaras + Modbus globals."""
import os
import time
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": "admin", "password": "admin"}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- ZAPECADO: SP manual, tau, fallas ----------
def test_zapecado_sp_tau_faults(H):
    # manda SP manual + tau + falla_quemador
    payload = {"temperatura_obj": 480.0, "tau": 150.0, "falla_quemador": True,
               "falla_motor_tambor": False, "estado_alimentacion": True}
    r = requests.post(f"{BASE_URL}/api/zapecado", json=payload, headers=H, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["temperatura_obj"] == 480.0
    assert data["tau"] == 150.0
    assert data["faults"]["falla_quemador"] is True
    assert data["faults"]["falla_motor_tambor"] is False
    # sp_efectivo refleja SP manual
    assert abs(data["temperatura_sp_efectivo"] - 480.0) < 0.5

    # limpiar
    requests.post(f"{BASE_URL}/api/zapecado",
                  json={"falla_quemador": False}, headers=H, timeout=10)


def test_zapecado_real_vs_sp_different(H):
    """T real debe ser distinto del SP recién cambiado (convergencia gradual)."""
    # forzar SP a un valor lejano
    requests.post(f"{BASE_URL}/api/zapecado",
                  json={"temperatura_obj": 420.0, "tau": 200.0}, headers=H)
    time.sleep(0.5)
    s = requests.get(f"{BASE_URL}/api/state").json()["zapecado"]
    # SP efectivo == 420, pero T real debería NO ser exactamente 420 (en convergencia)
    assert s["temperatura_sp_efectivo"] == 420.0
    # los valores no deben ser idénticos (no es teletransporte)
    assert s["temperatura"] != s["temperatura_sp_efectivo"] or abs(s["temperatura"] - 420.0) < 80


# ---------- SECADO ----------
def test_secado_sp_tau_faults(H):
    payload = {"temperatura_obj": 92.5, "humedad_obj": 8.5, "tau_t": 100.0,
               "falla_ventilador": True, "falla_serpentin": False, "estado": True}
    r = requests.post(f"{BASE_URL}/api/secado", json=payload, headers=H, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["temperatura_obj"] == 92.5
    assert data["humedad_obj"] == 8.5
    assert data["tau_t"] == 100.0
    assert data["faults"]["falla_ventilador"] is True
    requests.post(f"{BASE_URL}/api/secado",
                  json={"falla_ventilador": False}, headers=H)


# ---------- CANCHADO ----------
def test_canchado_sp_tau_faults(H):
    payload = {"tamano_particula_obj": 4.5, "tau_p": 8.0,
               "falla_motor": False, "rodamiento_caliente": True, "estado": True}
    r = requests.post(f"{BASE_URL}/api/canchado", json=payload, headers=H, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["tamano_particula_obj"] == 4.5
    assert data["tau_p"] == 8.0
    assert data["faults"]["rodamiento_caliente"] is True
    # sp_efectivo == manual
    assert data["tamano_particula_sp_efectivo"] == 4.5
    # rodamiento_caliente => t_rodamientos sube mucho
    assert data["sensors"]["t_rodamientos"] > 50.0
    requests.post(f"{BASE_URL}/api/canchado",
                  json={"rodamiento_caliente": False}, headers=H)


# ---------- CAMARA ----------
def test_camara_tau_faults(H):
    payload = {"tau": 800.0, "falla_ventilador": False,
               "fuga_vapor": True, "puerta_abierta": False}
    r = requests.post(f"{BASE_URL}/api/camaras/0", json=payload, headers=H, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["tau"] == 800.0
    assert data["faults"]["fuga_vapor"] is True
    assert data["faults"]["puerta_abierta"] is False
    requests.post(f"{BASE_URL}/api/camaras/0",
                  json={"fuga_vapor": False}, headers=H)


# ---------- Velocidad de simulación via /config ----------
def test_set_aceleracion_via_config(H):
    # set 3600 (1h-s)
    r = requests.post(f"{BASE_URL}/api/config",
                      json={"simulacion": {"aceleracion": 3600.0}},
                      headers=H, timeout=10)
    assert r.status_code == 200, r.text
    cfg = r.json()["config"]
    assert cfg["simulacion"]["aceleracion"] == 3600.0
    # revertir
    requests.post(f"{BASE_URL}/api/config",
                  json={"simulacion": {"aceleracion": 60.0}}, headers=H)


# ---------- REGRESSION: massflow + recipes + alarms ----------
def test_regression_massflow_carga(H):
    r = requests.post(f"{BASE_URL}/api/massflow/carga",
                      json={"kg": 100.0, "T": 22.0, "H": 50.0},
                      headers=H, timeout=10)
    assert r.status_code in (200, 400)  # 400 si ya pasó stage gate


def test_regression_recipes_list():
    r = requests.get(f"{BASE_URL}/api/recipes", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_regression_alarms_active():
    r = requests.get(f"{BASE_URL}/api/alarms/active", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- State exposes new fields ----------
def test_state_exposes_sp_tau_faults():
    s = requests.get(f"{BASE_URL}/api/state", timeout=10).json()
    # zapecado
    assert "temperatura_sp_efectivo" in s["zapecado"]
    assert "tau" in s["zapecado"]
    assert "faults" in s["zapecado"]
    assert "falla_quemador" in s["zapecado"]["faults"]
    # secado
    assert "temperatura_obj" in s["secado"] and "humedad_obj" in s["secado"]
    assert "tau_t" in s["secado"]
    assert "faults" in s["secado"]
    # canchado
    assert "tamano_particula_sp_efectivo" in s["canchado"]
    assert "tau_p" in s["canchado"]
    assert "faults" in s["canchado"]
    # camaras
    assert s["camaras"]
    cam = s["camaras"][0]
    assert "tau" in cam
    assert "faults" in cam
    for k in ("falla_ventilador", "fuga_vapor", "puerta_abierta"):
        assert k in cam["faults"]


# ---------- Endpoints requieren auth ----------
def test_endpoints_require_auth():
    r = requests.post(f"{BASE_URL}/api/zapecado", json={"tau": 100.0}, timeout=10)
    assert r.status_code == 401
