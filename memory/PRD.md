# Gemelo Digital · Yerba Mate (Yerbatera Industrial Twin)

## Problema original

El usuario tenía un gemelo digital en Python + Tkinter para simular el proceso industrial yerbatero (4 etapas: Zapecado, Secado, Canchado y 4 Cámaras de Maduración), expuesto por Modbus TCP, MQTT y OPC UA. Pidió migrarlo a React + FastAPI manteniendo TODA la comunicación industrial, mejorar las gráficas, agregar clima ambiental real, persistencia local en CSV/Excel e IA Gemini 3 Flash (asistente conversacional + detección de anomalías + forecast). Repo origen: https://github.com/Pucho586/Gemelo-Virtual---Yerbatera

## Arquitectura

```
React (frontend) ─┬─► FastAPI /api/* (REST + WebSocket)
                  │
                  └─► Bridges en threads:
                       ├─ YerbaProcessSimulator (1Hz)
                       ├─ Modbus TCP   :5020
                       ├─ OPC UA       :4840
                       ├─ MQTT client  → broker externo
                       ├─ Open-Meteo   (clima ambiente)
                       ├─ PersistenceService (CSV diario + xlsx on demand)
                       └─ AIService (Gemini 3 Flash via emergentintegrations)
```

## Usuarios

- **Operario de planta**: monitoreo en vivo, ajustes de consigna, chat con IA, exportación de turno.
- **Ingeniero de proceso**: análisis histórico, calibración de cámaras, validación de comunicación industrial con PLC/SCADA real.

## Requerimientos núcleo (estáticos)

1. Mantener funcionando los 3 servidores industriales (Modbus / MQTT / OPC UA).
2. Simulación realista con clima ambiente real (Open-Meteo) - base Posadas, configurable.
3. Persistencia local en CSV/Excel configurable.
4. UI moderna estilo SCADA con gráficos en vivo.
5. IA Gemini 3 Flash (chat + anomalías + forecast).
6. Cero dependencia de cloud privado: corre 100% local.

## Implementado (Jan 2026 · v2.0)

### Backend `/app/backend/`
- ✅ `twin/yerba_simulator.py` - simulador mejorado: temperatura ambiente real, setpoint dinámico en zapecado, piso ambiente en secado, intercambio térmico realista en cámaras
- ✅ `twin/yerba_modbus_server.py` - Modbus TCP 0.0.0.0:5020 (7 unit IDs)
- ✅ `twin/mqtt_publisher.py` - publica en `yerba/{etapa}`
- ✅ `twin/opcua_server.py` - opc.tcp://0.0.0.0:4840/yerba/
- ✅ `twin/weather.py` - Open-Meteo (sin API key) + geocoding
- ✅ `twin/persistence.py` - CSV diario + builder Excel
- ✅ `twin/ai_service.py` - Gemini 3 Flash (gemini-3-flash-preview) via emergentintegrations: chat multi-turno, anomalías con diagnóstico AI, forecast lineal
- ✅ `twin/runtime.py` - singleton que orquesta todo
- ✅ `server.py` - FastAPI con 20+ endpoints + WebSocket /api/ws

### Frontend `/app/frontend/`
- ✅ Stack: React 19 + Recharts + @phosphor-icons/react + IBM Plex Sans + JetBrains Mono
- ✅ Estética SCADA "Tactical Control Room" (oscura, hairline grids, amber para IA)
- ✅ 7 tabs: Dashboard / Zapecado / Secado / Canchado / Cámaras / IA·Gemini / Configuración
- ✅ WebSocket en vivo + polling fallback (`useLiveState`)
- ✅ Header con 5 badges de estado (WS, Modbus, MQTT, OPC UA, Clima)
- ✅ Charts: Zapecado con ReferenceLine 600°C, Secado doble eje, Canchado area, Cámaras comparativo con selector temp/HR/CO₂
- ✅ Editor de cámaras (carga, ventilador, setpoints) con feedback instantáneo
- ✅ Panel IA con anomalías, diagnóstico Gemini, chat y forecast
- ✅ Configuración completa (Modbus/MQTT/OPC UA/Simulación/Persistencia/Clima con geocoding)

### Pruebas
- ✅ **Backend**: 20/20 pytest cases (`/app/backend/tests/test_yerba_api.py`)
- ✅ **Frontend**: 100% de los flujos críticos verificados

## Backlog / Mejoras futuras

### P1
- [ ] Modelo de respiración exotérmica de la yerba en cámaras (libera calor al madurar) - hoy el CO₂ está modelado, pero no el calor metabólico
- [ ] Dashboard "histórico": graficar archivos CSV pasados (no solo serie en memoria)
- [ ] Alertas push: cuando aparece anomalía nivel "high", notificar (browser notification)

### P2
- [ ] Tabla de "recetas" por producto (yerba suave / barbacuá / orgánica) que ajusta setpoints automáticamente
- [ ] Modo "replay": cargar un CSV histórico y reproducirlo en la UI
- [ ] Predicción no lineal (Prophet o scikit-learn) en lugar de regresión lineal simple

### P3
- [ ] Empaquetado standalone con PyInstaller + Electron para distribución en planta
- [ ] Multi-planta: selector de planta y separar histórico por planta

## Cómo correr localmente

```bash
# Backend
cd backend
pip install -r requirements.txt
echo "EMERGENT_LLM_KEY=tu_key_aca" >> .env
uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend
cd frontend
yarn install
yarn start    # http://localhost:3000
```

Modbus quedará en `localhost:5020`, OPC UA en `opc.tcp://localhost:4840/yerba/`, MQTT publicando si tenés un broker en `localhost:1883`.
