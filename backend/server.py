"""FastAPI server: gemelo digital de yerba mate (v2.1 con auth, recetas, lotes)."""
import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from twin.audit import AuditService  # noqa: E402
from twin.auth import (  # noqa: E402
    create_access_token, create_refresh_token, decode_token, get_current_user,
    get_recovery_code, hash_password, seed_users, verify_password,
)
from twin.batches import BatchService  # noqa: E402
from twin.calibration import apply_calibration_to_simulator, calibrate_from_csv  # noqa: E402
from twin.recipes import apply_recipe_to_simulator, get_default_recipes  # noqa: E402
from twin.runtime import get_runtime  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("yerba")

# ---------- DB ----------
mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]
batch_service = BatchService(db)
audit_service = AuditService(db)


# ---------- Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_users(db)
    await batch_service.ensure_indexes()
    await audit_service.ensure_indexes()
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


# ---------- Auth dependency wrappers ----------
async def current_user_dep(request: Request) -> Dict[str, Any]:
    return await get_current_user(request, db)


async def admin_only(request: Request) -> Dict[str, Any]:
    user = await get_current_user(request, db)
    if user.get("role") != "admin":
        raise HTTPException(403, "Requiere rol admin")
    return user


# ---------- Schemas ----------
class LoginBody(BaseModel):
    username: str
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class RecoverBody(BaseModel):
    username: str
    recovery_code: str
    new_password: str


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
    ui: Optional[Dict[str, Any]] = None


class ModeBody(BaseModel):
    mode: str  # "simulator" | "twin" | "shadow"


class ThroughputBody(BaseModel):
    kgh: float


class BatchCreateBody(BaseModel):
    operario: Optional[str] = None
    receta_id: Optional[str] = None
    receta_nombre: Optional[str] = None
    kg_entrada: float
    observaciones: Optional[str] = ""


class BatchCloseBody(BaseModel):
    kg_salida: float
    observaciones: Optional[str] = ""


# ---------- Health ----------
@api.get("/")
async def root():
    return {"app": "Gemelo Digital Yerba Mate", "status": "ok", "version": "2.1.0"}


# ---------- AUTH ----------
@api.post("/auth/login")
async def login(body: LoginBody, response: Response):
    user = await db.users.find_one({"username": body.username.lower().strip()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Usuario o contraseña inválidos")
    access = create_access_token(user["id"], user["username"], user["role"])
    refresh = create_refresh_token(user["id"])
    response.set_cookie("access_token", access, httponly=True, samesite="lax", max_age=8 * 3600, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax", max_age=14 * 86400, path="/")
    return {
        "access_token": access,
        "user": {"id": user["id"], "username": user["username"], "role": user["role"], "display": user.get("display", user["username"])},
    }


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(current_user_dep)):
    return user


@api.post("/auth/change-password")
async def change_password(body: ChangePasswordBody, user=Depends(current_user_dep)):
    full = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.current_password, full["password_hash"]):
        raise HTTPException(401, "Contraseña actual incorrecta")
    if len(body.new_password) < 4:
        raise HTTPException(400, "Mínimo 4 caracteres")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"ok": True}


@api.post("/auth/recover")
async def recover(body: RecoverBody):
    if body.recovery_code != get_recovery_code():
        raise HTTPException(401, "Código de recuperación inválido")
    user = await db.users.find_one({"username": body.username.lower().strip()})
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    if len(body.new_password) < 4:
        raise HTTPException(400, "Mínimo 4 caracteres")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"ok": True}


@api.get("/auth/users")
async def list_users(user=Depends(admin_only)):
    cursor = db.users.find({}, {"_id": 0, "password_hash": 0})
    return await cursor.to_list(length=100)


# ---------- ESTADO ----------
@api.get("/state")
async def get_state():
    return get_runtime().simulator.get_state()


@api.get("/history")
async def get_history(n: int = 600):
    return get_runtime().simulator.get_history(n=n)


@api.get("/services/status")
async def services_status():
    return get_runtime().service_status


# ---------- MODO Gemelo/Simulador ----------
@api.get("/mode")
async def get_mode():
    rt = get_runtime()
    return {"mode": rt.simulator.mode, "throughput_kgh": rt.simulator.throughput_kgh}


@api.post("/mode")
async def set_mode(body: ModeBody, request: Request, user=Depends(admin_only)):
    rt = get_runtime()
    rt.simulator.set_mode(body.mode)
    rt.update_config({"simulacion": {"mode": body.mode}})
    await audit_service.log(user["username"], "set_mode", {"mode": body.mode}, ip=request.client.host if request.client else None)
    return {"mode": body.mode}


@api.post("/throughput")
async def set_throughput(body: ThroughputBody, user=Depends(admin_only)):
    rt = get_runtime()
    rt.simulator.set_throughput(body.kgh)
    rt.update_config({"simulacion": {"throughput_kgh": body.kgh}})
    return {"throughput_kgh": body.kgh}


# ---------- CONTROLES ----------
@api.post("/zapecado")
async def patch_zapecado(p: ZapecadoPatch, user=Depends(current_user_dep)):
    get_runtime().simulator.set_zapecado(**p.model_dump(exclude_none=True))
    return get_runtime().simulator.get_state()["zapecado"]


@api.post("/secado")
async def patch_secado(p: SecadoPatch, user=Depends(current_user_dep)):
    get_runtime().simulator.set_secado(**p.model_dump(exclude_none=True))
    return get_runtime().simulator.get_state()["secado"]


@api.post("/canchado")
async def patch_canchado(p: CanchadoPatch, user=Depends(current_user_dep)):
    get_runtime().simulator.set_canchado(**p.model_dump(exclude_none=True))
    return get_runtime().simulator.get_state()["canchado"]


@api.post("/camaras/{idx}")
async def patch_camara(idx: int, p: CamaraPatch, user=Depends(current_user_dep)):
    rt = get_runtime()
    if idx < 0 or idx >= len(rt.simulator.camaras):
        raise HTTPException(404, "Cámara no encontrada")
    rt.simulator.set_camara(idx, **p.model_dump(exclude_none=True))
    return rt.simulator.get_state()["camaras"][idx]


# ---------- CONFIG ----------
@api.get("/config")
async def get_config():
    return get_runtime().config


@api.post("/config")
async def patch_config(p: ConfigPatch, user=Depends(admin_only)):
    cfg = get_runtime().update_config(p.model_dump(exclude_none=True))
    return {"saved": True, "config": cfg}


# ---------- CLIMA ----------
@api.get("/weather")
async def get_weather():
    rt = get_runtime()
    if rt.weather is None:
        return {"available": False}
    return {"available": True, "location": rt.weather.location, "current": rt.weather.last_payload}


@api.post("/weather/location")
async def set_weather_location(loc: WeatherLocation, user=Depends(admin_only)):
    rt = get_runtime()
    if rt.weather is None:
        raise HTTPException(500, "Servicio de clima no inicializado")
    await rt.weather.set_location(loc.latitude, loc.longitude, loc.city)
    rt.update_config({"weather": {"latitude": loc.latitude, "longitude": loc.longitude, "city": loc.city}})
    rt.service_status["weather"]["city"] = loc.city
    return {"ok": True, "location": rt.weather.location, "current": rt.weather.last_payload}


@api.get("/weather/search")
async def search_weather(q: str):
    from twin.weather import search_city
    return await search_city(q)


# ---------- IA ----------
@api.post("/ai/chat")
async def ai_chat(req: ChatRequest, user=Depends(current_user_dep)):
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


# ---------- RECETAS ----------
@api.get("/recipes")
async def list_recipes():
    """Recetas por defecto + personalizadas guardadas en MongoDB."""
    defaults = get_default_recipes()
    custom = await db.recipes.find({}, {"_id": 0}).to_list(length=200)
    return defaults + custom


@api.post("/recipes/{recipe_id}/apply")
async def apply_recipe(recipe_id: str, user=Depends(current_user_dep)):
    rt = get_runtime()
    # Buscar en defaults
    recipes = get_default_recipes()
    found = next((r for r in recipes if r["id"] == recipe_id), None)
    if not found:
        found = await db.recipes.find_one({"id": recipe_id}, {"_id": 0})
    if not found:
        raise HTTPException(404, "Receta no encontrada")
    apply_recipe_to_simulator(rt.simulator, found)
    return {"applied": True, "recipe": found, "state": rt.simulator.get_state()}


@api.post("/recipes")
async def create_recipe(recipe: Dict[str, Any], user=Depends(admin_only)):
    rid = recipe.get("id") or f"custom-{uuid.uuid4().hex[:8]}"
    recipe["id"] = rid
    recipe["custom"] = True
    await db.recipes.replace_one({"id": rid}, recipe, upsert=True)
    return recipe


@api.delete("/recipes/{recipe_id}")
async def delete_recipe(recipe_id: str, user=Depends(admin_only)):
    res = await db.recipes.delete_one({"id": recipe_id})
    return {"deleted": res.deleted_count}


# ---------- LOTES / BATCHES ----------
@api.get("/batches")
async def list_batches(user=Depends(current_user_dep)):
    return await batch_service.list_batches(limit=200)


@api.get("/batches/active")
async def active_batch(user=Depends(current_user_dep)):
    return await batch_service.get_active()


@api.post("/batches")
async def create_batch(body: BatchCreateBody, user=Depends(current_user_dep)):
    active = await batch_service.get_active()
    if active:
        raise HTTPException(409, f"Ya hay un lote activo: {active['id']}. Cerralo primero.")
    return await batch_service.create_batch(body.model_dump(), user["username"])


@api.post("/batches/{batch_id}/close")
async def close_batch(batch_id: str, body: BatchCloseBody, user=Depends(current_user_dep)):
    b = await batch_service.close_batch(batch_id, body.model_dump())
    if not b:
        raise HTTPException(404, "Lote no encontrado")
    return b


@api.post("/batches/{batch_id}/cancel")
async def cancel_batch(batch_id: str, user=Depends(current_user_dep)):
    b = await batch_service.cancel_batch(batch_id)
    if not b:
        raise HTTPException(404, "Lote no encontrado")
    return b


# ---------- DATA ----------
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


# ---------- FASE 2: External sources, drift, calibration, audit ----------
class ExternalSourceBody(BaseModel):
    enabled: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = None
    interval: Optional[float] = None
    endpoint: Optional[str] = None
    broker: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    topic_base: Optional[str] = None
    namespace_idx: Optional[int] = None
    mapping: Optional[Dict[str, Any]] = None


class CalibrationApplyBody(BaseModel):
    calibration: Dict[str, Any]


@api.get("/external/status")
async def external_status():
    rt = get_runtime()
    return {
        "mirror": rt.mirror.snapshot(),
        "drift": rt.last_drift,
        "modbus_client": rt.service_status.get("modbus_client"),
        "opcua_client": rt.service_status.get("opcua_client"),
        "mqtt_subscriber": rt.service_status.get("mqtt_subscriber"),
        "config": rt.config.get("external", {}),
    }


@api.post("/external/{section}")
async def configure_external(section: str, body: ExternalSourceBody, request: Request, user=Depends(admin_only)):
    if section not in ("modbus_client", "opcua_client", "mqtt_subscriber"):
        raise HTTPException(404, "Sección desconocida")
    rt = get_runtime()
    kwargs = body.model_dump(exclude_none=True)
    rt.reconfigure_external(section, **kwargs)
    await audit_service.log(user["username"], f"configure_external.{section}", kwargs,
                            ip=request.client.host if request.client else None)
    return {"ok": True, "status": rt.service_status[section]}


@api.get("/drift")
async def get_drift():
    return get_runtime().last_drift


@api.post("/calibration/analyze")
async def calibration_analyze(file_text: Dict[str, str], user=Depends(admin_only)):
    """Body: {"csv": "ts,zap_temperatura,...\\n..."}.
    Devuelve análisis sin aplicar."""
    csv_text = file_text.get("csv", "")
    if not csv_text:
        raise HTTPException(400, "Falta 'csv'")
    try:
        result = calibrate_from_csv(csv_text, sample_interval_s=5.0)
        return result
    except Exception as e:
        raise HTTPException(500, f"Error procesando CSV: {e}")


@api.post("/calibration/apply")
async def calibration_apply(body: CalibrationApplyBody, request: Request, user=Depends(admin_only)):
    rt = get_runtime()
    apply_calibration_to_simulator(rt.simulator, body.calibration)
    await audit_service.log(user["username"], "calibration_apply", body.calibration,
                            ip=request.client.host if request.client else None)
    return {"ok": True}


@api.get("/audit")
async def audit_log(limit: int = 200, username: Optional[str] = None, user=Depends(current_user_dep)):
    # Operario solo ve sus propias acciones; admin ve todo
    if user.get("role") != "admin":
        username = user["username"]
    return await audit_service.list_recent(limit=limit, username=username)


# ---------- WebSocket ----------
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
