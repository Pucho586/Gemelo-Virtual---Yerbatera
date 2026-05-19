"""FastAPI server: expone el gemelo digital de yerba mate."""
import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from twin.runtime import get_runtime  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("yerba")


# ---------- Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    rt = get_runtime()
    rt.start_all()
    await rt.start_async_services()
    logger.info("Twin runtime ready")
    yield
    logger.info("Shutting down")


app = FastAPI(title="Gemelo Digital Yerba Mate", lifespan=lifespan)
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Schemas ----------
class ZapecadoPatch(BaseModel):
    velocidad_tambor: Optional[float] = None
    velocidad_chip: Optional[float] = None
    estado_alimentacion: Optional[bool] = None


class SecadoPatch(BaseModel):
    velocidad_aire: Optional[float] = None
    estado: Optional[bool] = None


class CanchadoPatch(BaseModel):
    velocidad_molino: Optional[float] = None
    estado: Optional[bool] = None


class CamaraPatch(BaseModel):
    carga_kg: Optional[float] = None
    ventilador: Optional[bool] = None
    temperatura_obj: Optional[float] = None
    humedad_obj: Optional[float] = None
    co2_obj: Optional[float] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    include_state: bool = True


class WeatherLocation(BaseModel):
    latitude: float
    longitude: float
    city: str = ""


class ConfigPatch(BaseModel):
    modbus: Optional[Dict[str, Any]] = None
    mqtt: Optional[Dict[str, Any]] = None
    opcua: Optional[Dict[str, Any]] = None
    simulacion: Optional[Dict[str, Any]] = None
    persistence: Optional[Dict[str, Any]] = None
    weather: Optional[Dict[str, Any]] = None
    limits: Optional[Dict[str, Any]] = None


# ---------- Endpoints básicos ----------
@api.get("/")
async def root():
    return {"app": "Gemelo Digital Yerba Mate", "status": "ok"}


@api.get("/state")
async def get_state():
    return get_runtime().simulator.get_state()


@api.get("/history")
async def get_history(n: int = 600):
    return get_runtime().simulator.get_history(n=n)


@api.get("/services/status")
async def services_status():
    return get_runtime().service_status


# ---------- Controles ----------
@api.post("/zapecado")
async def patch_zapecado(p: ZapecadoPatch):
    get_runtime().simulator.set_zapecado(**p.model_dump(exclude_none=True))
    return get_runtime().simulator.get_state()["zapecado"]


@api.post("/secado")
async def patch_secado(p: SecadoPatch):
    get_runtime().simulator.set_secado(**p.model_dump(exclude_none=True))
    return get_runtime().simulator.get_state()["secado"]


@api.post("/canchado")
async def patch_canchado(p: CanchadoPatch):
    get_runtime().simulator.set_canchado(**p.model_dump(exclude_none=True))
    return get_runtime().simulator.get_state()["canchado"]


@api.post("/camaras/{idx}")
async def patch_camara(idx: int, p: CamaraPatch):
    rt = get_runtime()
    if idx < 0 or idx >= len(rt.simulator.camaras):
        raise HTTPException(404, "Cámara no encontrada")
    rt.simulator.set_camara(idx, **p.model_dump(exclude_none=True))
    return rt.simulator.get_state()["camaras"][idx]


# ---------- Configuración ----------
@api.get("/config")
async def get_config():
    return get_runtime().config


@api.post("/config")
async def patch_config(p: ConfigPatch):
    cfg = get_runtime().update_config(p.model_dump(exclude_none=True))
    return {"saved": True, "config": cfg}


# ---------- Clima ----------
@api.get("/weather")
async def get_weather():
    rt = get_runtime()
    if rt.weather is None:
        return {"available": False}
    return {
        "available": True,
        "location": rt.weather.location,
        "current": rt.weather.last_payload,
    }


@api.post("/weather/location")
async def set_weather_location(loc: WeatherLocation):
    rt = get_runtime()
    if rt.weather is None:
        raise HTTPException(500, "Servicio de clima no inicializado")
    await rt.weather.set_location(loc.latitude, loc.longitude, loc.city)
    # Guardar en config
    rt.update_config({"weather": {
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "city": loc.city,
    }})
    rt.service_status["weather"]["city"] = loc.city
    return {"ok": True, "location": rt.weather.location, "current": rt.weather.last_payload}


@api.get("/weather/search")
async def search_weather(q: str):
    from twin.weather import search_city
    return await search_city(q)


# ---------- IA ----------
@api.post("/ai/chat")
async def ai_chat(req: ChatRequest):
    rt = get_runtime()
    sid = req.session_id or f"session-{uuid.uuid4().hex[:10]}"
    ctx = rt.simulator.get_state() if req.include_state else None
    try:
        reply = await rt.ai.chat(sid, req.message, context=ctx)
    except Exception as e:
        logger.exception("AI chat failed")
        raise HTTPException(500, f"Error IA: {e}")
    return {"session_id": sid, "reply": reply, "history": rt.ai.get_history(sid)}


@api.get("/ai/history/{session_id}")
async def ai_history(session_id: str):
    return get_runtime().ai.get_history(session_id)


@api.post("/ai/reset/{session_id}")
async def ai_reset(session_id: str):
    get_runtime().ai.reset_session(session_id)
    return {"ok": True}


@api.get("/ai/anomalies")
async def ai_anomalies(use_ai: bool = True):
    rt = get_runtime()
    state = rt.simulator.get_state()
    return await rt.ai.analyze_anomalies(state, use_ai=use_ai)


@api.get("/ai/forecast")
async def ai_forecast(horizon: int = 30):
    rt = get_runtime()
    hist = rt.simulator.get_history(n=120)
    return rt.ai.forecast(hist, horizon_steps=horizon)


# ---------- Persistencia ----------
@api.get("/data/files")
async def list_data_files():
    rt = get_runtime()
    if rt.persistence is None:
        return []
    return rt.persistence.list_files()


@api.get("/data/download/{name}")
async def download_data_file(name: str):
    rt = get_runtime()
    if rt.persistence is None:
        raise HTTPException(500, "Persistencia no inicializada")
    p = rt.persistence.get_file_path(name)
    if not p:
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(p, filename=name, media_type="text/csv")


@api.get("/data/excel")
async def export_excel(name: Optional[str] = None):
    rt = get_runtime()
    if rt.persistence is None:
        raise HTTPException(500, "Persistencia no inicializada")
    try:
        path = rt.persistence.build_excel(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return FileResponse(path, filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------- WebSocket en tiempo real ----------
@app.websocket("/api/ws")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    rt = get_runtime()
    try:
        while True:
            state = rt.simulator.get_state()
            await websocket.send_text(json.dumps(state))
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    except Exception as e:
        logger.warning(f"WS error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass


app.include_router(api)
