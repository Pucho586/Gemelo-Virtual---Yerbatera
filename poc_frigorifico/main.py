import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from simulator import FrigorificoSimulator

app = FastAPI(title="Gemelo Digital Frigorífico - Fase 2")

# Instancia global del simulador
simulador = FrigorificoSimulator()

# Tarea en segundo plano para hacer avanzar la simulación
async def simulador_loop():
    """Tick del simulador cada segundo."""
    while True:
        # En la realidad 1 tick podría ser 1 segundo o 1 minuto.
        # Aquí 1 segundo real = 1 minuto simulado para ver cambios rápidos.
        simulador.tick(dt=1.0)
        await asyncio.sleep(1.0)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulador_loop())

# --- Modelos Pydantic ---
class PuertaPatch(BaseModel):
    abierta: bool

# --- Endpoints ---
@app.get("/")
async def root():
    return {"status": "ok", "app": "Gemelo Digital Frigorífico"}

@app.get("/api/state")
async def get_state():
    """Devuelve el estado térmico de todas las cámaras."""
    return simulador.estado_global()

@app.post("/api/camaras/{idx}/puerta")
async def patch_puerta(idx: int, patch: PuertaPatch):
    """Permite abrir o cerrar la puerta de una cámara específica."""
    if idx < 0 or idx >= len(simulador.camaras):
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    camara = simulador.camaras[idx]
    camara.puerta_abierta = patch.abierta

    return {
        "ok": True,
        "camara": camara.nombre,
        "puerta_abierta": camara.puerta_abierta
    }
