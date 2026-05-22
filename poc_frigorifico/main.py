import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from simulator import FrigorificoSimulator
import database

app = FastAPI(title="Gemelo Digital Frigorífico - Fase 4 (Completa)")

simulador = FrigorificoSimulator()

async def simulador_loop():
    """Tick del simulador cada segundo y guardado en BD."""
    tick_count = 0
    while True:
        simulador.tick(dt=1.0)

        # Guardar en base de datos cada 5 "minutos" simulados (5 segundos reales)
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

# --- Endpoints del Simulador Térmico ---
@app.get("/api/state")
async def get_state():
    return simulador.estado_global()

@app.post("/api/camaras/{idx}/puerta")
async def patch_puerta(idx: int, patch: PuertaPatch):
    if idx < 0 or idx >= len(simulador.camaras):
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    camara = simulador.camaras[idx]
    camara.puerta_abierta = patch.abierta
    return {"ok": True, "camara": camara.nombre, "puerta_abierta": camara.puerta_abierta}

# --- Endpoints de Datos y Trazabilidad (Fase 3) ---
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

# --- Frontend Estático (Fase 4) ---
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")
