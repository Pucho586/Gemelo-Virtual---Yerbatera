# Gemelo Digital · Yerba Mate (Yerbatera Industrial Twin) — v2.3 (FASE 3)

## Problema original

Migración del gemelo digital Python+Tkinter del usuario (repo https://github.com/Pucho586/Gemelo-Virtual---Yerbatera) a plataforma web industrial moderna apta para producción real en yerbateras.

## Arquitectura

```
React (frontend + auth JWT) ─┬─► FastAPI /api/* (REST + WebSocket)
                              │
                              └─► Bridges (threads / async):
                                   ├─ YerbaProcessSimulator (3 modos: simulator/shadow/twin)
                                   ├─ Modbus TCP server   :5020  (OUT)
                                   ├─ OPC UA server       :4840  (OUT)
                                   ├─ MQTT publisher (OUT)
                                   ├─ Modbus TCP client    (IN)  ★ FASE 2
                                   ├─ OPC UA client        (IN)  ★ FASE 2
                                   ├─ MQTT subscriber      (IN)  ★ FASE 2
                                   ├─ AlarmEngine ISA-18.2 ★ FASE 3
                                   ├─ OperationsService (OEE + maint + energía) ★ FASE 3
                                   ├─ ReportsBuilder (PDF) ★ FASE 3
                                   ├─ Open-Meteo · PersistenceService · AIService · AuditService
                                   └─ MongoDB (users, batches, recipes, audit_log, alarms, alarm_rules, ops_state)
```

## Usuarios

- **Admin** (admin/admin): TODO — configuración, modo, recetas, lotes, calibración, fuentes externas, audit, alarmas rules, precios energía, reset contadores
- **Operario** (operario/operario): dashboard, ajustes en vivo, lotes, IA, recetas (aplicar), ACK alarmas, ACK mantenimiento, ver OEE/energía (lectura), descargar reportes

## Modos de operación

| Modo | Cálculo matemático | Lectura externa | Drift display |
|------|--------------------|-----------------|---------------|
| **simulator** (verde) | ✅ activo | ❌ ignorado | – |
| **shadow** (azul) | ✅ activo | ✅ se lee | ✅ compara |
| **twin** (amber) | ❌ pausado | ✅ alimenta simulator | ✅ trivial |

## Implementado por iteración

### v2.0 — Migración base (iter 1) — 20/20 tests
- React + FastAPI, simulador con ambient real, Modbus/MQTT/OPC UA servers, CSV/Excel, IA Gemini

### v2.1 — Industria-ready (iter 2-3) — 48/48 tests
- Auth JWT + recovery, Recetas, Lotes con merma, Modo switch, Mímicos SVG/P&ID, tabs persistentes

### v2.2 — Industria 4.0 (iter 4) — 66/66 tests
- Clientes Modbus + OPC UA + MQTT subscriber, modo Shadow, drift sim vs PLC, calibración por CSV, audit trail

### v2.3 — Operaciones (iter 5) — 89/89 tests ★
- **Alarmas ISA-18.2**: 7 reglas default + custom, 4 prioridades, ACK persistente, RTN-with/without-ACK, restore desde DB tras reinicio
- **OEE**: Disponibilidad × Rendimiento × Calidad con ventana móvil
- **Mantenimiento predictivo**: 7 componentes (tambor, secador, molino, 4 ventiladores), umbrales lubricación/rulemanes/overhaul, ACK con timestamp
- **Energía & costos**: kWh por componente + m³ gas estimado + $/kg producido + margen + revenue (precios editables)
- **Reportes PDF**: mensual (OEE, lotes, alarmas, energía, mantenimiento) y por lote (técnico)
- **Badge global de alarmas activas** en header
- 1 bug corregido (None-safety en reports.py) + 1 hardening (rebuild active alarms tras reinicio)

## Backlog próximo

### FASE 4 — Entrenamiento (próxima)
- [ ] Modo replay de CSV histórico a 10x velocidad
- [ ] Modo "qué pasaría si" (bifurcar simulación)
- [ ] Escenarios de fallas predefinidos para entrenar operarios

### Quick wins (P1)
- [ ] Editor de usuarios desde UI (admin crea/borra/cambia rol)
- [ ] Cambio de password desde UI
- [ ] Brute-force lockout en login (5 fallos → 15 min)
- [ ] Persistir calibración aplicada en YAML
- [ ] Cleanup periódico de PDFs en data/reports

### Refinamientos técnicos
- [ ] `hours_at_ack` en maintenance (mejorar precisión del comentario en operations.py)
- [ ] Formula de gas_m3 más rigurosa (mover constantes a config)
- [ ] OEE: produced_window con frágil división por 0.01 → usar ventanas reales basadas en histórico

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
PDFs: `backend/data/reports/`. CSVs históricos: `backend/data/`.
