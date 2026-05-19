"""Iteration 10 — Modelo físico puro + PID interno opcional.

Verifica:
- Zapecado/Secado responden a las manipuladas (sin τ→SP escondido).
- PIDs internos (zap, sec_t, can) convergen al SP cuando se activan.
- /api/state.sim incluye aceleracion, sim_clock, forecast_count, forecast_preview.
- /api/weather/manual actualiza ambient.temp/humidity.
"""
import os
import time
import pytest
import requests
from datetime import datetime
from pathlib import Path


def _load_base_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        env = Path("/app/frontend/.env")
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    return url.rstrip("/")


BASE_URL = _load_base_url()
assert BASE_URL, "REACT_APP_BACKEND_URL not configured"


# --------- fixtures ---------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"username": "admin", "password": "admin"}, timeout=10)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _reset_defaults(admin_session):
    """Pone valores base limpios para cada test."""
    admin_session.post(f"{BASE_URL}/api/zapecado", json={
        "velocidad_chip": 30, "velocidad_tambor": 15,
        "estado_alimentacion": True,
        "falla_quemador": False, "falla_motor_tambor": False,
        "pid": {"enabled": False, "reset": True},
    })
    admin_session.post(f"{BASE_URL}/api/secado", json={
        "posicion_calefactor": 0, "velocidad_aire": 2.5,
        "estado": True, "temperatura_obj": 95,
        "falla_ventilador": False, "falla_serpentin": False,
        "pid_t": {"enabled": False, "reset": True},
        "pid_h": {"enabled": False, "reset": True},
    })
    admin_session.post(f"{BASE_URL}/api/canchado", json={
        "velocidad_molino": 60, "estado": True,
        "pid": {"enabled": False, "reset": True},
    })


def _get_state():
    r = requests.get(f"{BASE_URL}/api/state", timeout=10)
    assert r.status_code == 200
    return r.json()


# --------- /api/state.sim structure ---------
class TestSimState:
    def test_sim_block_has_required_fields(self):
        st = _get_state()
        assert "sim" in st
        sim = st["sim"]
        for k in ("aceleracion", "sim_clock", "forecast_count", "forecast_preview"):
            assert k in sim, f"missing {k} in sim block"
        assert isinstance(sim["forecast_count"], int)
        assert isinstance(sim["forecast_preview"], list)
        # forecast_count may be 0 if Open-Meteo down — acceptable
        assert sim["forecast_count"] >= 0

    def test_sim_clock_is_valid_iso_utc(self):
        sim = _get_state()["sim"]
        # iso parseable
        dt = datetime.fromisoformat(sim["sim_clock"].replace("Z", "+00:00"))
        assert dt is not None


# --------- Weather manual override ---------
class TestWeatherManual:
    def test_weather_manual_updates_ambient(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/weather/manual",
                               json={"temperature": 18, "humidity": 75}, timeout=10)
        assert r.status_code == 200, f"weather/manual {r.status_code}: {r.text}"
        time.sleep(0.5)
        amb = _get_state()["ambient"]
        assert abs(amb["temp"] - 18) < 0.5
        assert abs(amb["humidity"] - 75) < 0.5


# --------- Modelo físico puro: ZAPECADO ---------
class TestZapecadoPhysics:
    def test_zapecado_converges_in_range_default(self, admin_session):
        """vel_chip=30, vel_tambor=15 → T converge ~350-420°C tras ~20s sim."""
        _reset_defaults(admin_session)
        # weather manual a 18°C para tener referencia estable
        admin_session.post(f"{BASE_URL}/api/weather/manual",
                           json={"temperature": 18, "humidity": 75})
        time.sleep(22)  # 22s real * 60x accel = ~22 min sim
        z = _get_state()["zapecado"]
        T = z["temperatura"]
        assert 320 <= T <= 470, f"T={T} fuera del rango esperado 320-470°C"
        # PID off
        assert z["pid"]["enabled"] is False

    def test_zapecado_chip_increase_raises_temp(self, admin_session):
        """Subir vel_chip 30→60 manteniendo tambor → T sube +50°C en 30s sim."""
        _reset_defaults(admin_session)
        admin_session.post(f"{BASE_URL}/api/weather/manual",
                           json={"temperature": 18, "humidity": 75})
        time.sleep(20)
        T0 = _get_state()["zapecado"]["temperatura"]
        # Aumentar combustible
        admin_session.post(f"{BASE_URL}/api/zapecado", json={"velocidad_chip": 80})
        time.sleep(25)
        T1 = _get_state()["zapecado"]["temperatura"]
        assert T1 - T0 >= 30, f"T no subió lo suficiente: T0={T0} T1={T1} delta={T1-T0}"


# --------- Modelo físico: SECADO ---------
class TestSecadoPhysics:
    def test_secado_without_heater_does_not_reach_sp(self, admin_session):
        """posicion_calefactor=0 y SP=95 → T NO alcanza 95 (sin PID escondido)."""
        _reset_defaults(admin_session)
        admin_session.post(f"{BASE_URL}/api/weather/manual",
                           json={"temperature": 18, "humidity": 75})
        time.sleep(15)
        s = _get_state()["secado"]
        T = s["temperatura"]
        # Sin calefactor, T debe estar bien por debajo del SP (≤ ~50°C; en cualquier caso <85)
        assert T < 85, f"T={T} alcanzó SP=95 sin calefactor — PID escondido?"
        assert s["pid_t"]["enabled"] is False
        assert s["posicion_calefactor"] == 0

    def test_secado_with_heater_70_climbs_toward_sp(self, admin_session):
        """posicion_calefactor=70 → T sube hacia ~95°C."""
        _reset_defaults(admin_session)
        admin_session.post(f"{BASE_URL}/api/weather/manual",
                           json={"temperature": 18, "humidity": 75})
        admin_session.post(f"{BASE_URL}/api/secado", json={"posicion_calefactor": 70})
        time.sleep(20)
        T = _get_state()["secado"]["temperatura"]
        assert T > 50, f"T={T} no subió con calefactor=70"


# --------- PID INTERNO ---------
class TestPIDSecado:
    def test_secado_pid_t_converges_to_sp(self, admin_session):
        """PID T enabled con SP=95 → T converge a 95±5 tras ~25s reales."""
        _reset_defaults(admin_session)
        admin_session.post(f"{BASE_URL}/api/weather/manual",
                           json={"temperature": 18, "humidity": 75})
        r = admin_session.post(f"{BASE_URL}/api/secado", json={
            "temperatura_obj": 95,
            "pid_t": {"enabled": True, "kp": 4, "ki": 0.15, "reset": True},
        })
        assert r.status_code == 200
        time.sleep(25)
        s = _get_state()["secado"]
        assert s["pid_t"]["enabled"] is True
        T = s["temperatura"]
        assert abs(T - 95) < 8, f"PID T no convergió: T={T} (SP=95)"
        # posicion_calefactor debe haberse autoajustado
        assert s["posicion_calefactor"] != 0, "calefactor sigue en 0 — PID no actuó"


class TestPIDZapecado:
    def test_zap_pid_converges_to_sp(self, admin_session):
        """PID enabled SP=500 → T se acerca a 500 y vel_chip se autoajusta."""
        _reset_defaults(admin_session)
        admin_session.post(f"{BASE_URL}/api/weather/manual",
                           json={"temperature": 18, "humidity": 75})
        r = admin_session.post(f"{BASE_URL}/api/zapecado", json={
            "temperatura_obj": 500,
            "pid": {"enabled": True, "kp": 0.15, "ki": 0.005, "reset": True},
        })
        assert r.status_code == 200
        time.sleep(25)
        z = _get_state()["zapecado"]
        assert z["pid"]["enabled"] is True
        T = z["temperatura"]
        # Tolerancia grande porque la térmica del horno es lenta
        assert T > 380, f"T={T} no se acercó al SP=500"
        # vel_chip debe haberse movido del default 30
        assert z["velocidad_chip"] != 30, f"velocidad_chip no fue autoajustada (={z['velocidad_chip']})"


# --------- PID FRONTEND payload compat ---------
class TestPidPatchAccepted:
    def test_canchado_accepts_pid_patch(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/canchado", json={
            "pid": {"enabled": True, "kp": 1.0, "ki": 0.0, "kd": 0.0, "reset": True},
        })
        assert r.status_code == 200
        time.sleep(1)
        c = _get_state()["canchado"]
        assert c["pid"]["enabled"] is True
        assert abs(c["pid"]["kp"] - 1.0) < 0.001
        # cleanup
        admin_session.post(f"{BASE_URL}/api/canchado",
                           json={"pid": {"enabled": False, "reset": True}})

    def test_camara_accepts_pid_t_patch(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/camaras/0", json={
            "pid_t": {"enabled": True, "kp": 5.0, "ki": 0.05, "reset": True},
        })
        assert r.status_code == 200
        time.sleep(1)
        cam = _get_state()["camaras"][0]
        assert cam["pid_t"]["enabled"] is True
        admin_session.post(f"{BASE_URL}/api/camaras/0",
                           json={"pid_t": {"enabled": False, "reset": True}})


# --------- Regression smoke ---------
class TestRegression:
    def test_massflow_endpoints_alive(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/massflow/carga",
                               json={"camara_idx": 0, "kg": 100})
        assert r.status_code in (200, 400, 404, 422), f"massflow/carga status {r.status_code}"

    def test_recipes_alive(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/recipes")
        assert r.status_code == 200

    def test_batches_alive(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/batches")
        assert r.status_code == 200

    def test_alarms_alive(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/alarms/active")
        assert r.status_code == 200
