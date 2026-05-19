# Gemelo Digital · Yerba Mate (Yerbatera Industrial Twin)

## Problema original

Migración del gemelo digital Python+Tkinter del usuario (repo https://github.com/Pucho586/Gemelo-Virtual---Yerbatera) a una plataforma web industrial moderna. 4 etapas (Zapecado, Secado, Canchado, 4 Cámaras de Maduración), 3 servidores industriales (Modbus TCP, MQTT, OPC UA), clima ambiente real, persistencia local, IA Gemini 3 Flash. Objetivo final: convertirlo en un gemelo virtual industrial vendible a yerbateras.

## Arquitectura

```
React (frontend + auth JWT) ─┬─► FastAPI /api/* (REST + WebSocket)
                              │
                              └─► Bridges en threads:
                                   ├─ YerbaProcessSimulator (mass flow + ambient + mode)
                                   ├─ Modbus TCP   :5020 (7 unit IDs)
                                   ├─ OPC UA       :4840 (namespace YerbaProcess)
                                   ├─ MQTT client  → broker externo
                                   ├─ Open-Meteo   (clima ambiente)
                                   ├─ PersistenceService (CSV diario + xlsx)
                                   ├─ AIService (Gemini 3 Flash)
                                   └─ MongoDB (users, batches, recetas custom)
```

## Usuarios

- **Admin** (admin/admin): configura todo, gestiona usuarios, cambia modo Simulador↔Gemelo, crea/borra recetas
- **Operario** (operario/operario): dashboard, ajustes en vivo, crea/cierra lotes, usa IA, aplica recetas

## Requerimientos núcleo (estáticos)

1. Mantener funcionando los 3 servidores industriales (Modbus / MQTT / OPC UA).
2. Simulación realista con clima ambiente real (Open-Meteo) - base Posadas, configurable.
3. Persistencia local en CSV/Excel configurable.
4. UI moderna estilo SCADA con gráficos en vivo y mímicos.
5. IA Gemini 3 Flash (chat + anomalías + forecast).
6. Cero dependencia de cloud privado: corre 100% local.
7. Auth local con admin + operario + recuperación por código maestro.
8. Switch Gemelo↔Simulador (configurable, solo admin).
9. Recetas industriales y trazabilidad por lotes.

## Implementado

### Iteración 1 (v2.0) — Base Industrial

- Migración Python+Tkinter → React + FastAPI
- 4 etapas + 4 cámaras + 3 servidores industriales preservados
- Clima Open-Meteo, persistencia CSV/Excel
- IA Gemini 3 Flash (chat + anomalías + forecast)
- 20/20 tests backend

### Iteración 2 + 3 (v2.1) — Industria-ready

- **Autenticación JWT** (admin/operario) + recuperación con código maestro
- **Recetas** (4 presets: suave/fuerte/barbacuá/orgánica + custom)
- **Lotes/Batches** con kg_in/kg_out/merma/operario en MongoDB
- **Flujo de masa** entre etapas (humedad de salida de zapecado afecta secado, throughput configurable)
- **Switch Modo Simulador ↔ Gemelo**: en modo "twin" el simulador deja de calcular y solo refleja valores externos (PLC, MQTT in, API)
- **Mímicos**: SVG animado + P&ID ISA-style con toggle en header
- **Tabs persistentes** (no se re-animan al cambiar)
- **Role gating**: operario no ve config; switch de modo solo admin
- 48/48 tests backend (100%)

## Backlog / Mejoras futuras

### FASE 2 — Industria 4.0 real (próxima)
- [ ] **Cliente Modbus/OPC UA bidireccional**: configurás un PLC real y el twin lo POLLea y compara
- [ ] **Modo Shadow**: corre simulador y lectura PLC en paralelo, detecta drift
- [ ] **Subscriber MQTT IN**: recibe valores desde topics externos en modo twin
- [ ] **Calibración por CSV**: subir histórico real, ajustar τ, ruido, dinámicas
- [ ] **Audit trail completo**: cada acción de usuario en MongoDB

### FASE 3 — Operaciones
- [ ] **Alarmas ISA-18.2** con ACK persistente
- [ ] **OEE** (disponibilidad × rendimiento × calidad)
- [ ] **Mantenimiento predictivo** (horas marcha, próximo service)
- [ ] **Energía & costos** (kWh, gas, $/kg)
- [ ] **Reportes PDF** mensuales

### FASE 4 — Entrenamiento
- [ ] **Modo replay** de CSV histórico a 10x
- [ ] **Modo "qué pasaría si"** (bifurcar simulación)
- [ ] **Validación de operario** (escenarios de fallas predefinidos)

### Quick wins
- [ ] Brute-force lockout en /api/auth/login (5 fallos → 15 min)
- [ ] CORS_ORIGINS explícito en vez de *
- [ ] Cambiar contraseña desde la UI (endpoint ya existe)
- [ ] Editor de usuarios (admin crea/borra operarios)

## Cómo correr localmente

```bash
# Backend
cd backend
pip install -r requirements.txt
# Generar y guardar JWT_SECRET en .env (no debe cambiar entre reinicios)
echo "JWT_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
echo "ADMIN_RECOVERY_CODE=mi-codigo-secreto" >> .env
echo "EMERGENT_LLM_KEY=tu_key_aca" >> .env
uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend
cd frontend
yarn install
yarn start    # http://localhost:3000
```

Por defecto se crea **admin/admin** y **operario/operario** (idempotente).
Modbus en `:5020`, OPC UA en `opc.tcp://:4840/yerba/`, MQTT publishing si tenés broker en `:1883`.
