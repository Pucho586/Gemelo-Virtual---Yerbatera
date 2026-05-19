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

### v2.6 — Sensores derivados + Mermas editables + Visibilidad cruzada (iter 9) ★
- **Sensores de campo derivados** en el snapshot del simulator:
  - Zapecado: termocupla K entrada (T gases), termocupla K salida (T yerba), capacitivo/NIR salida (H), vibrómetro
  - Secado: PT100 aire entrada/salida, PT100 zona, NIR final, bulbo húmedo extracción
  - Canchado: PT100 rodamientos, encoder rpm, vibrómetros 3 ejes, NIR opcional salida
  - Cámaras: PT100 pared, PT100 centro pila, capacitivo HR, NDIR CO₂, T línea vapor, caudalímetro vapor
- **Visibilidad cruzada**: cada página de etapa muestra `kg_actual`, acumulados, merma y T_in/H_in heredadas del flujo de masa
- **Mermas editables desde UI**: nuevo editor admin en Flujo de masa (% por etapa, 0-95)
- Componente reusable `<StageBlock />` + `<ChamberSensorsBlock />`

### v2.5 — Mass-flow + Snapshot→What-if + rodamientos (iter 8) — 49/49 tests ★
- **Trazabilidad de masa lote-por-lote**: nuevo servicio `MassFlowService` con 5 etapas (Recepción → Zapecado → Secado → Canchado → Estacionamiento)
- Cada etapa registra `kg_actual`, `kg_acum_in/out`, `merma_kg`, `T_in/H_in` heredadas de la etapa anterior
- UI: nueva tab **"Flujo de masa"** con pipeline horizontal, carga de hoja verde, botones → de transferencia, log de eventos
- **Snapshot → What-if**: botón en panel what-if que captura setpoints actuales del baseline como base del nuevo escenario
- **`rulemanes` → `rodamientos`** en todo el sistema (terminología técnica correcta es-AR) con migración automática de Mongo
- **Documentación**: agregados puntos de medición reales (termocuplas K, PT100, NIR, NDIR) por etapa, mermas referenciales INYM
- Backend bug fix: route ordering `/whatif/snapshot` antes de `/whatif/{id}`

### v2.4 — FASE 4 + Cámaras configurables + Vapor (iter 7) — 16/16 backend, frontend OK ★
- **Cámaras configurables** (1-12) desde UI con +/- buttons
- **Inyección de vapor por cámara**: toggle, caudal (kg/h), setpoints T y HR, acumulador kg
- **Replay mode**: carga CSV histórico, play/pause/seek, velocidad 0.25×-120×
- **What-if mode**: hasta 3 escenarios paralelos con overrides JSON, vista comparativa baseline vs variantes con color coding
- **Exposición SCADA por escenario**:
  - Modbus TCP unit IDs 20/21/22 (HR registers 0-7 = OEE, $/kg, kWh, chips, T zap, T sec, HR final, prod)
  - OPC UA `/Plant/WhatIf/scenarioN/{OEE,CostoPorKg,kWhAcum,ChipsKgAcum,...}`
  - MQTT topics `yerba/whatif/scenarioN/{kpi}`
- Nuevo tab "Replay & What-if" (Fase4View.jsx)
- 1 bug fix de route ordering aplicado por testing agent

### v2.3.1 — Chips de madera + parámetros editables (iter 6) — 8/8 + 22/22 regresión ★
- Migración completa **gas natural → chips de madera** (combustible para zapecado)
- Fix crítico: `operations.py::energy_cost_ars()` ya no crashea con AttributeError
- Nuevo parámetro editable: **PCI (poder calorífico inferior) de los chips** en MJ/kg (default 17, rango 5-25). Escala el consumo automáticamente.
- Editables desde UI por admin:
  - Precios: kWh, kg chips, kg yerba venta
  - Turnos: cantidad por día + horas por turno → calcula horas planificadas
  - Umbrales de mantenimiento por (componente, acción)
- Endpoints nuevos: `POST /api/ops/shifts`, `POST /api/maintenance/thresholds`
- `POST /api/energy/prices` extendido con `chip_calorific_mj_kg`
- PDFs mensuales ya muestran "Chips de madera" textual
- Documentación generada: `/app/docs/manual_operaciones.md` + `/app/docs/manual_tecnico.md`

### v2.3 — Operaciones (iter 5) — 89/89 tests ★
- **Alarmas ISA-18.2**: 7 reglas default + custom, 4 prioridades, ACK persistente, RTN-with/without-ACK, restore desde DB tras reinicio
- **OEE**: Disponibilidad × Rendimiento × Calidad con ventana móvil
- **Mantenimiento predictivo**: 7 componentes (tambor, secador, molino, 4 ventiladores), umbrales lubricación/rodamientos/overhaul, ACK con timestamp
- **Energía & costos**: kWh por componente + m³ gas estimado + $/kg producido + margen + revenue (precios editables)
- **Reportes PDF**: mensual (OEE, lotes, alarmas, energía, mantenimiento) y por lote (técnico)
- **Badge global de alarmas activas** en header
- 1 bug corregido (None-safety en reports.py) + 1 hardening (rebuild active alarms tras reinicio)

## Backlog próximo

### FASE 4 — Entrenamiento (✅ COMPLETADA en iter 7)
- [x] Modo replay de CSV histórico con velocidad configurable
- [x] Modo "qué pasaría si" (3 escenarios paralelos)
- [x] Exposición de escenarios what-if por Modbus/OPC UA/MQTT para SCADA/PLC
- [ ] Catálogo de escenarios de falla predefinidos (nice-to-have)

### Cámaras y vapor (✅ COMPLETADO en iter 7)
- [x] Cantidad configurable (1-12)
- [x] Inyección de vapor por cámara con setpoints

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
