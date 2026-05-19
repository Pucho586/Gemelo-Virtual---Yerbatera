"""Servicio de clima usando Open-Meteo (sin API key)."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any
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
    """Obtiene la temperatura y humedad actuales en una coordenada."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(OPEN_METEO_URL, params=params)
        r.raise_for_status()
        data = r.json()
    cur = data.get("current", {})
    return {
        "temperature": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "wind_speed": cur.get("wind_speed_10m"),
        "weather_code": cur.get("weather_code"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
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
    """Mantiene el clima actualizado y se lo inyecta al simulador."""

    def __init__(self, simulator, location: Dict[str, Any] | None = None, interval_seconds: int = 600):
        self.simulator = simulator
        self.location = {**DEFAULT_LOCATION, **(location or {})}
        self.interval = interval_seconds
        self._task: asyncio.Task | None = None
        self.last_payload: Dict[str, Any] = {}

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
                })
                self.last_payload = {**data, **self.location}
                logger.info(f"Weather updated: {temp}°C / {hum}% @ {self.location.get('city')}")
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")

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
