import asyncio
import random
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict

from simulator import FrigorificoSimulator
from comms import CommsManager
import database

app = FastAPI(title="Gemelo Digital Frigorífico - Fase 5 (Comms & Config)")

simulador = FrigorificoSimulator()
comms_manager = CommsManager()

async def simulador_loop():
    """Tick del simulador cada segundo."""
    tick_count = 0
    while True:
        simulador.tick(dt=1.0)

        # Simular llegada de telemetría si está en modo Gemelo y conectado
        if simulador.modo == "gemelo" and comms_manager.modbus_status.startswith("Conectado"):
            # Simulamos que un PLC real nos manda temperaturas aleatorias cerca del objetivo
            telemetria_simulada_de_plc = {
                c.nombre: c.temp_objetivo + random.uniform(-1.0, 1.0) for c in simulador.camaras
            }
            simulador.aplicar_telemetria(telemetria_simulada_de_plc)

        # Guardar en base de datos cada 5 ticks
        if tick_count % 5 == 0:
            estados = simulador.estado_global()
            await database.save_estado(estados)

        tick_count += 1
        await asyncio.sleep(1.0)

@app.on_event("startup")
async def startup_event():
    await database.init_db()
    asyncio.create_task(simulador_loop())

# --- Modelos Pydantic ---
class PuertaPatch(BaseModel):
    abierta: bool

class TropaCreate(BaseModel):
    numero_tropa: str
    peso_kg: float
    camara_inicial: str

class ModoPatch(BaseModel):
    modo: str # "simulador" o "gemelo"

class ConfigPatch(BaseModel):
    modbus_host: str = None
    opcua_endpoint: str = None
    mqtt_broker: str = None

class TempObjPatch(BaseModel):
    temp_objetivo: float

# --- Endpoints del Simulador Térmico ---
@app.get("/api/state")
async def get_state():
    return {
        "modo": simulador.modo,
        "camaras": simulador.estado_global()
    }

@app.post("/api/camaras/{idx}/puerta")
async def patch_puerta(idx: int, patch: PuertaPatch):
    if idx < 0 or idx >= len(simulador.camaras):
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    camara = simulador.camaras[idx]
    camara.puerta_abierta = patch.abierta
    return {"ok": True, "camara": camara.nombre, "puerta_abierta": camara.puerta_abierta}

@app.post("/api/camaras/{idx}/objetivo")
async def patch_objetivo(idx: int, patch: TempObjPatch):
    if idx < 0 or idx >= len(simulador.camaras):
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    camara = simulador.camaras[idx]
    camara.temp_objetivo = patch.temp_objetivo
    return {"ok": True, "camara": camara.nombre, "temp_objetivo": camara.temp_objetivo}

# --- Endpoints de Modo y Comunicaciones ---
@app.post("/api/mode")
async def set_modo(patch: ModoPatch):
    if patch.modo not in ["simulador", "gemelo"]:
        raise HTTPException(status_code=400, detail="Modo inválido")
    simulador.modo = patch.modo

    if patch.modo == "gemelo":
        comms_manager.connect_all()
    else:
        comms_manager.disconnect_all()

    return {"ok": True, "modo": simulador.modo}

@app.get("/api/comms")
async def get_comms_status():
    return comms_manager.get_status()

@app.post("/api/config")
async def update_config(patch: ConfigPatch):
    new_cfg = {k: v for k, v in patch.dict().items() if v is not None}
    comms_manager.update_config(new_cfg)
    return {"ok": True, "config": comms_manager.config}

# --- Endpoints de Datos y Trazabilidad ---
@app.get("/api/history")
async def get_history(limit: int = 50):
    return await database.get_historial(limit)

@app.post("/api/tropas")
async def crear_tropa(tropa: TropaCreate):
    camaras_nombres = [c.nombre for c in simulador.camaras]
    if tropa.camara_inicial not in camaras_nombres:
        raise HTTPException(status_code=400, detail=f"La cámara '{tropa.camara_inicial}' no existe.")
    try:
        await database.crear_tropa(tropa.numero_tropa, tropa.peso_kg, tropa.camara_inicial)
        return {"ok": True, "mensaje": f"Tropa {tropa.numero_tropa} ingresada a {tropa.camara_inicial}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.get("/api/tropas")
async def listar_tropas():
    return await database.get_tropas()

# --- Frontend Estático ---
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")
