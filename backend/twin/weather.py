"""Servicio de clima usando Open-Meteo (sin API key)."""
import asyncio
import logging
import bisect
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple
import httpx

logger = logging.getLogger(__name__)

# Por defecto: Posadas, Misiones, Argentina
DEFAULT_LOCATION = {
    "latitude": -27.3667,
    "longitude": -55.8967,
    "city": "Posadas, Misiones, Argentina",
}

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


async def fetch_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """Obtiene clima actual + forecast horario 96h (4 días)."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "hourly": "temperature_2m,relative_humidity_2m",
        "forecast_days": 4,
        "timezone": "UTC",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(OPEN_METEO_URL, params=params)
        r.raise_for_status()
        data = r.json()
    cur = data.get("current", {})
    hourly = data.get("hourly", {})
    # forecast: lista de (timestamp_utc_iso, temp, hum)
    forecast: List[Tuple[str, float, float]] = []
    times = hourly.get("time", []) or []
    temps = hourly.get("temperature_2m", []) or []
    hums = hourly.get("relative_humidity_2m", []) or []
    for ts, t, h in zip(times, temps, hums):
        if t is not None and h is not None:
            forecast.append((ts, float(t), float(h)))
    return {
        "temperature": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "wind_speed": cur.get("wind_speed_10m"),
        "weather_code": cur.get("weather_code"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "forecast_hourly": forecast,
    }


async def search_city(query: str, count: int = 5):
    """Busca ciudades por nombre (geocoding gratuito de Open-Meteo)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(GEOCODE_URL, params={"name": query, "count": count, "language": "es"})
        r.raise_for_status()
        data = r.json()
    results = []
    for item in data.get("results", []) or []:
        label_parts = [item.get("name")]
        if item.get("admin1"):
            label_parts.append(item["admin1"])
        if item.get("country"):
            label_parts.append(item["country"])
        results.append({
            "label": ", ".join([p for p in label_parts if p]),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "country": item.get("country"),
        })
    return results


class WeatherService:
    """Mantiene el clima actualizado + forecast horario para simulación acelerada."""

    def __init__(self, simulator, location: Dict[str, Any] | None = None, interval_seconds: int = 600):
        self.simulator = simulator
        self.location = {**DEFAULT_LOCATION, **(location or {})}
        self.interval = interval_seconds
        self._task: asyncio.Task | None = None
        self.last_payload: Dict[str, Any] = {}
        self.forecast_hourly: List[Tuple[datetime, float, float]] = []

    async def refresh(self):
        try:
            data = await fetch_weather(self.location["latitude"], self.location["longitude"])
            temp = data.get("temperature")
            hum = data.get("humidity")
            if temp is not None and hum is not None:
                self.simulator.set_weather(temp, hum, {
                    "latitude": self.location["latitude"],
                    "longitude": self.location["longitude"],
                    "city": self.location.get("city", ""),
                    "updated_at": data["fetched_at"],
                    "wind_speed": data.get("wind_speed"),
                    "weather_code": data.get("weather_code"),
                    "source": "open-meteo",
                })
                self.last_payload = {**data, **self.location}
                logger.info(f"Weather updated: {temp}°C / {hum}% @ {self.location.get('city')} · forecast pts={len(data.get('forecast_hourly') or [])}")
            # Guardar forecast en estructura indexable
            fc = data.get("forecast_hourly") or []
            parsed = []
            for ts, t, h in fc:
                try:
                    # Open-Meteo entrega tiempos sin TZ pero ya en UTC (timezone=UTC)
                    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc) if "T" in ts else None
                    if dt is None: continue
                    parsed.append((dt, t, h))
                except Exception:
                    pass
            self.forecast_hourly = sorted(parsed, key=lambda x: x[0])
            # Inyectar forecast en simulator para que pueda interpolarlo
            self.simulator.set_forecast(self.forecast_hourly)
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")

    def get_at(self, sim_time: datetime) -> Tuple[float, float] | None:
        """Devuelve (T, HR) interpolado al sim_time. None si no hay forecast."""
        if not self.forecast_hourly:
            return None
        times = [pt[0] for pt in self.forecast_hourly]
        idx = bisect.bisect_left(times, sim_time)
        if idx <= 0:
            return (self.forecast_hourly[0][1], self.forecast_hourly[0][2])
        if idx >= len(times):
            return (self.forecast_hourly[-1][1], self.forecast_hourly[-1][2])
        # Interpolación lineal entre idx-1 e idx
        t0, T0, H0 = self.forecast_hourly[idx-1]
        t1, T1, H1 = self.forecast_hourly[idx]
        span = (t1 - t0).total_seconds() or 1
        f = max(0.0, min(1.0, (sim_time - t0).total_seconds() / span))
        return (T0 + (T1 - T0) * f, H0 + (H1 - H0) * f)

    async def _loop(self):
        while True:
            await self.refresh()
            await asyncio.sleep(self.interval)

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
        loop = loop or asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())

    async def set_location(self, latitude: float, longitude: float, city: str = ""):
        self.location = {"latitude": float(latitude), "longitude": float(longitude), "city": city}
        await self.refresh()
