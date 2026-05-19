# Gemelo Digital · Yerba Mate (Yerbatera Industrial Twin) — v2.2 (FASE 2)

## Problema original

Migración del gemelo digital Python+Tkinter (repo https://github.com/Pucho586/Gemelo-Virtual---Yerbatera) a plataforma web industrial moderna apta para producción. Objetivo: gemelo virtual potente para industria real con conexión bidireccional a PLC, calibración real, audit y modo Shadow.

## Arquitectura

```
React (frontend + auth JWT) ─┬─► FastAPI /api/* (REST + WebSocket)
                              │
                              └─► Bridges en threads/async:
                                   ├─ YerbaProcessSimulator (mass flow + ambient + mode)
                                   ├─ Modbus TCP server   :5020  (publica simulador)
                                   ├─ OPC UA server       :4840  (publica simulador)
                                   ├─ MQTT publisher       → broker externo (OUT)
                                   ├─ Modbus TCP client    ← PLC externo (IN)   ★ FASE 2
                                   ├─ OPC UA client        ← PLC externo (IN)   ★ FASE 2
                                   ├─ MQTT subscriber      ← topics externos    ★ FASE 2
                                   ├─ Open-Meteo (clima)
                                   ├─ PersistenceService (CSV/Excel)
                                   ├─ AIService (Gemini 3 Flash)
                                   ├─ AuditService (MongoDB)                    ★ FASE 2
                                   ├─ Calibration (CSV → τ fit)                 ★ FASE 2
                                   └─ MongoDB (users, batches, recipes, audit_log)
```

## Modos de operación

| Modo | Cálculo matemático | Lectura externa | Drift display |
|------|--------------------|-----------------|---------------|
| **simulator** (verde) | ✅ activo | ❌ ignorado | – |
| **shadow** (azul) ★ | ✅ activo | ✅ se lee | ✅ compara |
| **twin** (amber) | ❌ pausado | ✅ alimenta simulator | ✅ trivial |

## Usuarios

- **Admin** (admin/admin): todo (Config, modo, recetas, lotes, calibración, fuentes externas, audit global)
- **Operario** (operario/operario): dashboard, ajustes en vivo, lotes, IA, recetas (solo aplicar), audit propio

## Implementado por iteración

### v2.0 — Migración base (iter 1) — 20/20 tests
- React + FastAPI con simulador mejorado (ambient real Posadas)
- Modbus/MQTT/OPC UA servidores publicando
- Persistencia CSV/Excel
- IA Gemini 3 Flash

### v2.1 — Industria-ready (iter 2-3) — 48/48 tests
- Auth JWT local (admin/operario + recovery code)
- Recetas (suave/fuerte/barbacuá/orgánica + custom)
- Lotes con merma %
- Switch Simulador ↔ Gemelo
- Mímicos SVG y P&ID
- Tabs persistentes

### v2.2 — Industria 4.0 (iter 4) — 66/66 tests ★
- **Cliente Modbus TCP**: configurable host/port, polleo automático
- **Cliente OPC UA**: endpoint configurable, lee nodos
- **Suscriptor MQTT IN**: broker configurable, parse JSON / valor
- **Modo Shadow** (3er modo): simulador + externo en paralelo + drift
- **Drift calculator**: tag-a-tag, % error, coloreado por severidad
- **Calibración por CSV**: regresión por mínimos cuadrados ajusta τ
- **Audit trail**: MongoDB con filtro por rol
- **Closed-loop testing**: cliente apunta a 127.0.0.1:5020 sin PLC físico

## Backlog próximo

### Quick wins (P1)
- [ ] Persistir calibración en config YAML (hoy se pierde al reiniciar)
- [ ] Editor de usuarios desde UI (admin crea/borra/cambia rol)
- [ ] Cambio de password desde UI (endpoint ya existe)
- [ ] Brute-force lockout en login (5 fallos → 15 min)
- [ ] CORS_ORIGINS explícito en producción

### FASE 3 — Operaciones (P2)
- [ ] **Alarmas ISA-18.2** con ACK persistente
- [ ] **OEE** (disponibilidad × rendimiento × calidad)
- [ ] **Mantenimiento predictivo** (horas marcha, próximo service por componente)
- [ ] **Energía & costos** (kWh, gas, $/kg producido)
- [ ] **Reportes PDF** mensuales (consumo, lotes, mermas, alarmas)

### FASE 4 — Entrenamiento (P3)
- [ ] **Modo replay** de CSV histórico a 10x
- [ ] **Modo "qué pasaría si"** (bifurcar simulación)
- [ ] **Escenarios de fallas** predefinidos para entrenamiento de operarios

## Cómo correr localmente

```bash
# Backend
cd backend
pip install -r requirements.txt
echo "JWT_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
echo "ADMIN_RECOVERY_CODE=mi-codigo-secreto" >> .env
echo "EMERGENT_LLM_KEY=tu_key_aca" >> .env
uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend
cd frontend
yarn install
yarn start
```

Usuarios por defecto idempotentes: **admin/admin** y **operario/operario**.

## Comunicación industrial

### OUT (publicar al SCADA/PLC)
- Modbus TCP `0.0.0.0:5020` (7 unit IDs)
- OPC UA `opc.tcp://0.0.0.0:4840/yerba/`
- MQTT topics `yerba/{etapa}` (broker configurable)

### IN (leer del PLC real)
- Modbus TCP client → configurable IP/port/registros
- OPC UA client → endpoint configurable
- MQTT subscriber → topics `yerba_in/{etapa}/{var}` (JSON o número)
