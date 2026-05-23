import asyncio
import random
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Optional

from simulator import FrigorificoSimulator
from comms import CommsManager
import database

app = FastAPI(title="Gemelo Digital Frigorífico - Fase 6 (Fallos & Comms Activas)")

simulador = FrigorificoSimulator()
comms_manager = CommsManager()

# Variables para simular fallas externas
simular_falla_activa = False

async def simulador_loop():
    """Tick del simulador cada segundo."""
    tick_count = 0
    while True:
        simulador.tick(dt=1.0)

        # Simular llegada de telemetría si está en modo Gemelo
        if simulador.modo == "gemelo" and comms_manager.modbus_status.startswith("Conectado"):
            telemetria = {}
            for c in simulador.camaras:
                # El sensor real dice que estamos cerca del teórico...
                lectura_sensor = c.temperatura_teorica + random.uniform(-0.5, 0.5)

                # PERO si inyectamos una falla, la Cámara de Oreo se rompe (el sensor marca 10 grados más de lo que la teoría predice)
                if simular_falla_activa and c.nombre == "Cámara de Oreo":
                    lectura_sensor = c.temperatura_teorica + 10.0

                telemetria[c.nombre] = lectura_sensor

            simulador.aplicar_telemetria(telemetria)

        # Guardar en base de datos
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
    modo: str

class ConfigPatch(BaseModel):
    modbus_host: Optional[str] = None
    opcua_endpoint: Optional[str] = None
    mqtt_broker: Optional[str] = None

class TempObjPatch(BaseModel):
    temp_objetivo: float

class CommsCommand(BaseModel):
    protocolo: str
    camara_idx: int
    accion: str # ej: "abrir_puerta", "cerrar_puerta"

class FallaPatch(BaseModel):
    falla_activa: bool

# --- Endpoints del Simulador Térmico ---
@app.get("/api/state")
async def get_state():
    return {
        "modo": simulador.modo,
        "falla_inyectada": simular_falla_activa,
        "camaras": simulador.estado_global()
    }

@app.post("/api/falla")
async def toggle_falla(patch: FallaPatch):
    global simular_falla_activa
    simular_falla_activa = patch.falla_activa
    return {"ok": True, "falla_activa": simular_falla_activa}

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

@app.post("/api/comms/send")
async def send_industrial_command(cmd: CommsCommand):
    """Envía un comando a la planta a través del protocolo industrial elegido."""
    exito = comms_manager.send_command(cmd.protocolo, cmd.dict())
    if not exito:
        raise HTTPException(status_code=400, detail=f"No se pudo enviar comando. El protocolo {cmd.protocolo} está desconectado.")

    # Si la comunicación funcionó, aplicamos el cambio en el sistema
    camara = simulador.camaras[cmd.camara_idx]
    if cmd.accion == "abrir_puerta":
        camara.puerta_abierta = True
    elif cmd.accion == "cerrar_puerta":
        camara.puerta_abierta = False

    return {"ok": True, "mensaje": f"Comando {cmd.accion} enviado exitosamente a {camara.nombre} vía {cmd.protocolo}"}

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
