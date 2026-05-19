"""Iteration 9 backend tests.

Validates the deep-physics + race-condition + weather-override fixes:
  BUG #1 → POST /api/weather/manual sets ambient.{temp,humidity,source}
  BUG #2 → Zapecado coupling (chip/tambor → temperatura_sp_efectivo)
           Secado coupling (velocidad_aire → cooling effect on temperatura)
  BUG #3 → velocidad_tambor_real / velocidad_molino_real go to 0 when off/faulted
  REGRESSION → /api/state stays well-formed, sliders POSTs still work.
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": "admin", "password": "admin"}, timeout=10)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(autouse=True)
def restore_defaults(admin_session):
    """Reset critical sliders to known defaults after each test."""
    yield
    admin_session.post(f"{API}/zapecado", json={
        "velocidad_chip": 30, "velocidad_tambor": 15, "estado_alimentacion": True,
        "temperatura_obj": None, "falla_motor_tambor": False, "falla_quemador": False,
    })
    admin_session.post(f"{API}/secado", json={
        "velocidad_aire": 2.5, "temperatura_obj": 95, "estado": True,
        "falla_ventilador": False, "falla_serpentin": False,
    })
    admin_session.post(f"{API}/canchado", json={
        "velocidad_molino": 60, "estado": True,
        "tamano_particula_obj": None, "falla_motor": False,
    })


def _state(s=None):
    r = (s or requests).get(f"{API}/state", timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- BUG #1: weather manual override ----------
class TestWeatherManual:
    def test_manual_sets_ambient(self, admin_session):
        r = admin_session.post(f"{API}/weather/manual", json={"temperature": 17.5, "humidity": 82})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["ambient"]["temp"] == 17.5
        assert body["ambient"]["humidity"] == 82

        st = _state(admin_session)
        assert st["ambient"]["temp"] == 17.5
        assert st["ambient"]["humidity"] == 82
        assert st["ambient"]["source"] == "manual"
        assert st["ambient"]["updated_at"] is not None

    def test_manual_requires_admin(self):
        # plain requests, no auth cookie
        r = requests.post(f"{API}/weather/manual", json={"temperature": 20, "humidity": 50})
        assert r.status_code in (401, 403)


# ---------- BUG #2: Zapecado coupling ----------
class TestZapecadoCoupling:
    def test_sp_efectivo_formula_at_defaults(self, admin_session):
        # Make sure chip=30, tambor=15, obj=None
        admin_session.post(f"{API}/zapecado", json={
            "velocidad_chip": 30, "velocidad_tambor": 15, "temperatura_obj": None,
            "estado_alimentacion": True,
        })
        time.sleep(1.2)
        st = _state(admin_session)
        z = st["zapecado"]
        # formula: 350 + 1.4*chip - max(0,(tambor-30)*1.2)
        expected = 350 + 1.4 * 30 - max(0.0, (15 - 30) * 1.2)
        assert abs(z["temperatura_sp_efectivo"] - expected) < 0.5
        assert z["temperatura_obj"] is None

    def test_sp_efectivo_increases_with_chip(self, admin_session):
        admin_session.post(f"{API}/zapecado", json={
            "velocidad_chip": 150, "velocidad_tambor": 15, "temperatura_obj": None,
            "estado_alimentacion": True,
        })
        time.sleep(1.2)
        z = _state(admin_session)["zapecado"]
        # 350 + 1.4*150 - 0  = 560
        assert 555 <= z["temperatura_sp_efectivo"] <= 565

    def test_sp_drops_with_tambor_increase(self, admin_session):
        """tambor>30 introduces cooling penalty in SP formula."""
        admin_session.post(f"{API}/zapecado", json={
            "velocidad_chip": 100, "velocidad_tambor": 50, "temperatura_obj": None,
            "estado_alimentacion": True,
        })
        time.sleep(1.2)
        z = _state(admin_session)["zapecado"]
        # 350 + 1.4*100 - 1.2*(50-30) = 350+140-24 = 466
        assert 462 <= z["temperatura_sp_efectivo"] <= 470


# ---------- BUG #2: Secado coupling ----------
class TestSecadoCoupling:
    def test_aire_increases_cooling(self, admin_session):
        admin_session.post(f"{API}/secado", json={
            "velocidad_aire": 2.5, "temperatura_obj": 95, "estado": True,
        })
        time.sleep(2)
        t0 = _state(admin_session)["secado"]["temperatura"]
        # bump air to 10 m/s → target_t = 95 - 2.5*(10-2.5) = 76.25
        admin_session.post(f"{API}/secado", json={"velocidad_aire": 10})
        time.sleep(6)
        t1 = _state(admin_session)["secado"]["temperatura"]
        assert t1 < t0, f"T should drop after aire 2.5→10 (t0={t0}, t1={t1})"


# ---------- BUG #3: real rpm / SP exposure ----------
class TestRealSpeeds:
    def test_state_has_real_fields(self, admin_session):
        st = _state(admin_session)
        assert "velocidad_tambor_real" in st["zapecado"]
        assert "velocidad_molino_real" in st["canchado"]
        assert "temperatura_sp_efectivo" in st["zapecado"]

    def test_tambor_real_zero_when_off(self, admin_session):
        admin_session.post(f"{API}/zapecado", json={"estado_alimentacion": False})
        time.sleep(1.0)
        z = _state(admin_session)["zapecado"]
        assert z["velocidad_tambor_real"] == 0, z

    def test_tambor_real_zero_on_motor_fault(self, admin_session):
        admin_session.post(f"{API}/zapecado", json={
            "estado_alimentacion": True, "falla_motor_tambor": True,
        })
        time.sleep(1.0)
        z = _state(admin_session)["zapecado"]
        assert z["velocidad_tambor_real"] == 0
        # SP still shown as configured
        assert z["velocidad_tambor"] == 15

    def test_molino_real_zero_when_off(self, admin_session):
        admin_session.post(f"{API}/canchado", json={"estado": False})
        time.sleep(1.0)
        c = _state(admin_session)["canchado"]
        assert c["velocidad_molino_real"] == 0
        assert c["velocidad_molino"] == 60  # SP intact

    def test_molino_real_zero_on_motor_fault(self, admin_session):
        admin_session.post(f"{API}/canchado", json={"estado": True, "falla_motor": True})
        time.sleep(1.0)
        c = _state(admin_session)["canchado"]
        assert c["velocidad_molino_real"] == 0


# ---------- REGRESSION ----------
class TestRegression:
    def test_state_well_formed(self, admin_session):
        st = _state(admin_session)
        for k in ("zapecado", "secado", "canchado", "camaras", "ambient", "flujo"):
            assert k in st
        assert isinstance(st["camaras"], list)
        assert len(st["camaras"]) >= 1

    def test_toggle_off_persists(self, admin_session):
        """BUG #4 regression: turning OFF must stay OFF for a few seconds
        (no auto-toggle by simulator)."""
        admin_session.post(f"{API}/canchado", json={"estado": False})
        for _ in range(5):
            time.sleep(1)
            assert _state(admin_session)["canchado"]["estado"] is False
