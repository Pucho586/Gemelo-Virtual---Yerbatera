# Manual Técnico — Gemelo Digital Yerbatera

**Versión:** v2.3 (Fase 3)
**Stack:** React 18 + FastAPI + MongoDB
**Origen:** Migración del Tkinter original (https://github.com/Pucho586/Gemelo-Virtual---Yerbatera)
**Audiencia:** Desarrollador, integrador, ingeniero de instrumentación, equipo de mantenimiento de TI.

---

## 1. Arquitectura general

```
┌────────────────────────────────────────────────────────────────────┐
│                          NAVEGADOR                                 │
│  React 18 + Tailwind + Recharts + axios + JWT cookie/localStorage  │
└──────────────────────┬─────────────────────────────────────────────┘
                       │ HTTPS · /api/*  · WebSocket /api/ws
                       ▼
┌────────────────────────────────────────────────────────────────────┐
│                         FastAPI (uvicorn 8001)                     │
│  ├─ Routers: auth, state, mode, recetas, lotes, alarms, oee,       │
│  │           maintenance, energy, reports, drift, calibration,     │
│  │           audit, weather, config                                │
│  ├─ JWT Auth (HS256) + bcrypt + cookie httpOnly                    │
│  ├─ AuditService → Mongo `audit_log`                               │
│  └─ Runtime (asyncio background task) ───────────────────┐         │
└──────────────────────────────────────────────────────────┼─────────┘
                                                          │
                       ┌──────────────────────────────────┼──────────────────────────┐
                       ▼                                  ▼                          ▼
              YerbaProcessSimulator           AlarmEngine (ISA-18.2)        OperationsService
              (tick = ~50 ms sim)             reglas + history Mongo         OEE + maint + costos
                       │                                  │                          │
                       ├──► Modbus TCP server :5020       │                          │
                       │     (units 0-14 stages+cams,     │                          │
                       │      20-22 whatif)                │                          │
                       ├──► OPC UA server :4840            │                          │
                       │     (12 chamber slots + WhatIf)   │                          │
                       ├──► MQTT publisher (broker ext)    │                          │
                       ├──► Modbus client (IN)             │                          │
                       ├──► OPC UA client  (IN)            │                          │
                       ├──► MQTT subscriber                │                          │
                       ├──► Weather (Open-Meteo)           │                          │
                       ├──► PersistenceService (CSV/XLSX)  │                          │
                       ├──► ReplayService (FASE 4)         │                          │
                       └──► WhatIfService (FASE 4)         │                          │
                            └─► 3 sims paralelas →         │                          │
                                Modbus 20-22 / OPCUA / MQTT│                          │
                                                          ▼                          ▼
                                                       MongoDB                MongoDB `ops_state`
                                                  (alarms_active,             reports/*.pdf
                                                   alarms_history,            (ReportLab)
                                                   alarm_rules)
```

**Modos de operación** (controlados por `RuntimeMode` enum):

| Modo | Simulador | Cliente externo | CSV histórico | Drift |
|------|-----------|-----------------|---------------|-------|
| `simulator` | tick activo | ignorado | n/a | n/a |
| `shadow` | tick activo | leído pero NO inyectado | n/a | calculado |
| `twin` | tick pausado | inyectado al estado | n/a | trivial |
| `replay` | tick pausado | ignorado | feed al estado | n/a |

---

## 2. Estructura del repositorio

```
/app/
├── backend/
│   ├── .env                       # JWT_SECRET, ADMIN_RECOVERY_CODE, EMERGENT_LLM_KEY, MONGO_URL
│   ├── requirements.txt
│   ├── config_yerba.yaml          # Config de servidores, persistencia, simulación
│   ├── server.py                  # FastAPI app + routers + lifespan
│   ├── data/                      # CSVs históricos, reportes PDF, calibraciones
│   └── twin/
│       ├── yerba_simulator.py     # Modelo matemático de las 3 etapas + cámaras
│       ├── runtime.py             # Orquestador del tick + bridges OUT/IN
│       ├── weather.py             # Cliente Open-Meteo
│       ├── persistence.py         # CSV/XLSX auto-save
│       ├── ai_service.py          # Gemini 3 Flash (emergentintegrations)
│       ├── auth.py                # JWT + bcrypt + recovery
│       ├── recipes.py             # CRUD de recetas
│       ├── batches.py             # Ciclo de vida del lote
│       ├── audit.py               # Audit log a Mongo
│       ├── external_sources.py    # Clientes Modbus / OPC UA / MQTT
│       ├── calibration.py         # CSV → offset/gain
│       ├── alarms.py              # AlarmEngine ISA-18.2 + reglas
│       ├── operations.py          # OEE + mantenimiento + energía + costos
│       ├── replay_service.py      # FASE 4 — replay de CSV histórico
│       ├── whatif_service.py      # FASE 4 — escenarios paralelos + SCADA exposure
│       └── reports.py             # ReportLab PDF builder
└── frontend/
    ├── .env                       # REACT_APP_BACKEND_URL
    ├── package.json
    └── src/
        ├── App.js                 # Router de pestañas + Auth gate
        ├── lib/
        │   ├── api.js             # axios client + endpoints
        │   ├── auth.jsx           # AuthContext + isAdmin/isOperator
        │   └── useLiveState.js    # WebSocket hook (1 Hz state stream)
        └── components/
            ├── UI.jsx             # Card, Btn, NumberInput, TextInput, Toggle, Metric...
            ├── Charts.jsx         # Recharts wrappers
            ├── Dashboard.jsx      # Tablero principal
            ├── Mimics.jsx         # SVG/P&ID animados
            ├── ConfigView.jsx     # Configuración global (admin)
            ├── AIPanel.jsx        # Chat + anomalies + forecast (Gemini)
            ├── Login.jsx          # Login + recover password
            ├── RecetasView.jsx
            ├── LotesView.jsx
            ├── Industria40View.jsx  # Drift + clientes IN + calibración
            ├── OperacionesView.jsx  # Alarmas + OEE + Mant + Energía + Reportes
            ├── Fase4View.jsx        # FASE 4 — Replay & What-if
            ├── ZapecadoView.jsx
            ├── SecadoView.jsx
            ├── CanchadoView.jsx
            └── CamarasView.jsx
```

---

## 3. Backend en profundidad

### 3.1 Modelo matemático (`yerba_simulator.py`)

Cada etapa es un modelo de primer orden con perturbaciones:

```
T(t+dt) = T(t) + ((T_setpoint - T(t)) / tau_térmica) * dt + ε(ambient, viento, humedad)
H(t+dt) = H(t) + balance_de_masa_húmeda(T, flujo, humedad_ambiente) * dt
```

- **Zapecado**: T = 200-400 °C, tiempo de residencia ~3-5 s.
- **Secado**: T = 70-110 °C, tiempo ~ 2-4 h, baja humedad a 4-6%.
- **Canchado**: molino de martillos, throughput controlado por velocidad de rotor.
- **Cámaras de reposo (4)**: ventilador ON/OFF, T ambiente ±2 °C, hum estabilizada.

El clima de Open-Meteo se inyecta como `ambient_temp` y `ambient_humidity` y afecta la inercia térmica de cada etapa.

### 3.2 Runtime (`runtime.py`)

```python
async def loop():
    while running:
        if mode == "twin":
            state = read_external_clients()  # NO simula
        else:
            simulator.step(dt)
            state = simulator.snapshot()
            if mode == "shadow":
                ext = read_external_clients()
                drift = compare(state, ext)
        publish_modbus(state)
        publish_opcua(state)
        publish_mqtt(state)
        alarm_engine.evaluate(state)
        ops_service.tick(state, dt_sim_seconds=dt * accel)
        await broadcast_ws(state)
        await asyncio.sleep(0.05)
```

Aceleración (`config.simulacion.aceleracion`): 1 = real-time, 60 = 1 min real por segundo. Aplica a kWh, horas de marcha, consumo de chips, etc.

### 3.3 Auth (`auth.py`)

- Algoritmo: HS256 (PyJWT)
- Hash de password: bcrypt (12 rounds)
- Token TTL: 12 h
- Cookie: `yerba_token`, `HttpOnly`, `Secure`, `SameSite=Lax`
- Fallback: `Bearer` en header (para entornos sin cookies)
- Recovery: `ADMIN_RECOVERY_CODE` env-var → endpoint `POST /api/auth/recover`
- Idempotente: admin/admin y operario/operario se crean al arranque si no existen.

### 3.4 Industria 4.0

**Servidores (OUT)** — exponen el estado al ecosistema industrial:

| Protocolo | Puerto | Detalles |
|-----------|-------:|----------|
| Modbus TCP | 5020 | Unit IDs: zapecado=0, secado=1, canchado=2, cámaras=3..14, globales=100. Registers holding (R/W) + coils (fallas). |
| OPC UA | 4840 | Namespace `YerbaProcess`. Objetos: `Zapecado`, `Secado`, `Canchado`, `Camara1..12`, `Simulacion`. |
| MQTT | broker externo | Topics `yerba/{etapa}` con payload JSON. Publica cada N s (default 5). |

**Clientes (IN)** — leen del PLC real cuando el modo es `shadow` o `twin`:

- Mismo set de protocolos.
- Mapeo configurable de tag → variable interna desde la UI (Industria 4.0).
- Polling interval por protocolo.

#### Mapeo Modbus completo (función 3 = Holding Registers, función 1 = Coils)

**Unidad 0 — Zapecado**
| Reg | Variable | Escala |
|----:|----------|--------|
| 0 | T actual | ×10 |
| 1 | velocidad_tambor | rpm |
| 2 | velocidad_chip | kg/h |
| 3 | estado_alimentacion | 0/1 |
| 4 | T setpoint efectivo | ×10 |
| 5 | T setpoint manual (0=auto) | ×10 |
| 6 | τ térmica | ×10 |

| Coil | Variable |
|----:|----------|
| 0 | falla_quemador |
| 1 | falla_motor_tambor |

**Unidad 1 — Secado**
| Reg | Variable | Escala |
|----:|----------|--------|
| 0 | T actual | ×10 |
| 1 | HR actual | ×10 |
| 2 | velocidad_aire | ×10 |
| 3 | estado | 0/1 |
| 4 | T setpoint | ×10 |
| 5 | HR setpoint | ×10 |
| 6 | τ térmica | ×10 |

| Coil | Variable |
|----:|----------|
| 0 | falla_ventilador |
| 1 | falla_serpentin |

**Unidad 2 — Canchado**
| Reg | Variable | Escala |
|----:|----------|--------|
| 0 | velocidad_molino | ×10 |
| 1 | tamano_particula | ×100 |
| 2 | estado | 0/1 |
| 3 | particula setpoint manual (0=auto) | ×100 |
| 4 | particula setpoint efectivo | ×100 |
| 5 | τ molino | ×10 |

| Coil | Variable |
|----:|----------|
| 0 | falla_motor |
| 1 | rodamiento_caliente |

**Unidades 3..14 — Cámaras (hasta 12)**
| Reg | Variable | Escala |
|----:|----------|--------|
| 0 | T actual | ×10 |
| 1 | HR actual | ×10 |
| 2 | CO₂ | ppm |
| 3 | T setpoint | ×10 |
| 4 | HR setpoint | ×10 |
| 5 | CO₂ setpoint | ppm |
| 6 | carga | kg |
| 7 | días maduración | ×100 |
| 8 | ventilador | 0/1 |
| 9 | vapor_activo | 0/1 |
| 10 | vapor_caudal | ×10 |
| 11 | vapor SP T | ×10 |
| 12 | vapor SP HR | ×10 |
| 13 | τ cámara | s |

| Coil | Variable |
|----:|----------|
| 0 | falla_ventilador |
| 1 | fuga_vapor |
| 2 | puerta_abierta |

**Unidad 100 — Globales de simulación**
| Reg | Variable | Escala |
|----:|----------|--------|
| 0 | aceleracion (factor compresión tiempo) | ×10 |
| 1 | throughput_kgh | kg/h |

#### OPC UA — nodos disponibles

Bajo `Objects/YerbaProcess`:

- `Zapecado`: `Temperatura`, `TemperaturaObjetivo`, `Tau`, `FallaQuemador`, `FallaMotorTambor`
- `Secado`: `Temperatura`, `Humedad`, `TemperaturaObjetivo`, `HumedadObjetivo`, `TauTermico`, `FallaVentilador`, `FallaSerpentin`
- `Canchado`: `VelocidadMolino`, `TamanoParticula`, `TamanoParticulaObjetivo`, `TauMolino`, `FallaMotor`, `RodamientoCaliente`
- `Camara1..12`: `Temperatura`, `Humedad`, `CO2`, `DiasMaduracion`, `TemperaturaObjetivo`, `HumedadObjetivo`, `VaporActivo`, `VaporCaudalKgh`, `VaporSetpointTemp`, `VaporSetpointHum`, `VaporKgAcum`, `Tau`, `FallaVentilador`, `FugaVapor`, `PuertaAbierta`, `Activa`
- `Simulacion`: `Aceleracion`, `ThroughputKgh`, `Modo`
- `WhatIf/{scenario_id}`: KPIs de cada escenario (ver §3.10)

Todas las variables están marcadas como writable (`set_writable()`) para que un cliente OPC UA externo pueda escribir sobre ellas — el simulador lo respetará si el modo es `twin`.

### 3.5 Alarmas ISA-18.2 (`alarms.py`)

Estados implementados:
```
nueva ──► unacked_active ──ACK──► acked_active ──RTN──► acked_rtn → normal
                  │                       │
                  └─RTN─► unacked_rtn ──ACK──► normal
```

Persistencia:
- `alarm_rules`: configuración estática (id, name, tag, op, threshold, priority, enabled).
- `alarms_active`: alarmas en curso (rebuild on restart from history `unacked_*`).
- `alarms_history`: append-only log.

Operadores: `>`, `<`, `>=`, `<=`, `==`. Tag puede ser un path JSON (`state.zapecado.temperatura`) o `tag_any_cam` (cualquier cámara cumple).

### 3.6 OperationsService (`operations.py`)

Contadores en memoria, persistidos en `ops_state` (Mongo, single doc `id=singleton`):
- `runtime_hours` por componente
- `kwh_accum` por componente (= potencia_kW × horas_marcha)
- `chips_kg_accum` (combustible para zapecado)
- `kg_input`, `kg_produced` (de lotes cerrados)
- `prices`: kWh, kg chips, kg yerba venta
- `chip_calorific_mj_kg`: PCI editable (default 17, rango 5-25)
- `shifts_per_day`, `hours_per_shift`
- `thresholds` y `maint_acks`

**Consumo de chips** (escala con PCI):
```python
chips_rate_kg_h = max(0, (T_zapecado - T_amb) / 100 * 1.8 * (17 / PCI_actual))
```

**OEE** (ventana móvil 24 h):
```
Disponibilidad = horas operativas del secador / horas planificadas
Rendimiento = kg producidos / (throughput_nominal × horas operativas)
Calidad = kg producidos / kg ingresados
OEE = D × R × Q
```

### 3.7 Reportes (`reports.py`)

ReportLab `SimpleDocTemplate`. Hojas A4 con:
- Header con logo/título/período
- KPIs en bloques
- Tablas de lotes / alarmas / mantenimiento
- Curvas (matplotlib → PNG embebido) si se solicita
- Footer con número de página

Salidas en `backend/data/reports/{tipo}_{fecha|id}.pdf`.

### 3.8 IA (`ai_service.py`)

Modelo: **Gemini 3 Flash** vía `emergentintegrations` (clave `EMERGENT_LLM_KEY` en `.env`).

Endpoints:
- `POST /api/ai/chat` — sesión multi-turno con `session_id`.
- `GET /api/ai/anomalies` — análisis del estado actual.
- `GET /api/ai/forecast` — predicción a horizonte N pasos.

Las preguntas reciben como contexto el snapshot del simulador, alarmas activas y OEE. La respuesta es en español.

### 3.9 ReplayService (`replay_service.py`) — FASE 4

Reproductor de CSV histórico que alimenta el simulador en modo `replay`.

```python
class ReplayService:
    def start(file, speed=10.0, start_row=0): ...   # arranca un thread daemon
    def stop(): ...
    def pause(paused: bool): ...
    def seek(row: int): ...                          # también aplica la fila inmediatamente
    def set_speed(speed: float): ...                 # 0.25 a 120
    def status() -> dict: ...                        # active, paused, cursor, total, progress, ts_at_cursor
```

Cuando el modo es `replay`, el bucle del simulador (`yerba_simulator.update()`) **no** recalcula; en su lugar el thread del replay escribe cada fila del CSV directamente en los atributos del simulator:

```
sim.zapecado.temperatura = row["zap_temperatura"]
sim.secado.temperatura   = row["sec_temperatura"]
sim.secado.humedad       = row["sec_humedad"]
sim.canchado.velocidad_molino = row["can_velocidad_molino"]
for i, cam in enumerate(sim.camaras):
    cam.temperatura = row[f"cam{i+1}_temperatura"]
    cam.humedad     = row[f"cam{i+1}_humedad"]
    cam.co2         = row[f"cam{i+1}_co2"]
```

> Las columnas del CSV están **1-indexadas** (`cam1_*`, `cam2_*`...) por compatibilidad con persistencia histórica.

El throughput entre filas se controla con `sleep(1 / speed)` en el thread, asegurando avance regular sin importar la frecuencia original del muestreo.

### 3.10 WhatIfService (`whatif_service.py`) — FASE 4

Corre hasta **3 escenarios paralelos**. Cada escenario es un `WhatIfScenario` con:
- Un `YerbaProcessSimulator` instanciado a partir de una copia del `config` baseline + overrides aplicados con notación punto (`"zapecado.velocidad_chip": 25` o `{"zapecado": {"velocidad_chip": 25}}`).
- Contadores propios de kWh, chips, runtime, producción.
- KPIs calculados al vuelo: OEE, costo/kg, kWh acum, chips kg, T zapecado, T secado, HR final, producción kg.

**Snapshot → What-if** (endpoint `POST /api/whatif/snapshot`): captura los setpoints actuales del baseline (`zapecado.velocidad_chip`, `zapecado.velocidad_tambor`, `secado.velocidad_aire`, `canchado.velocidad_molino`, `simulacion.throughput_kgh`) y arma overrides automáticamente; `extra_overrides` del usuario se mergean por encima. Útil para preguntarse "¿qué pasaría si en este mismo momento de la corrida ajusto X parámetro?" sin escribir JSON desde cero.

Bucle único (`_loop`, thread daemon):
```
cada 1s:
    for cada scenario:
        scenario.step(ambient_t, ambient_h)         # avanza simulator + acumula
        kpis = scenario.compute_kpis(prices)         # calcula los 8 KPIs
        publicar a:
            - OPC UA: /Plant/WhatIf/scenario{N}/{KPI}
            - Modbus: unit {20,21,22}.HR[0..7] = KPI × 10
            - MQTT: yerba/whatif/scenario{N}/{KPI}
```

**Exposición a SCADA / PLC** — el mismo set de 8 KPIs aparece en los 3 protocolos en paralelo, por escenario:

| Protocolo | Endpoint del escenario N |
|-----------|--------------------------|
| Modbus TCP | unit ID `19 + N` (scenario1=20, scenario2=21, scenario3=22), HR[0..7] |
| OPC UA | `/Plant/WhatIf/scenarioN/OEE`, `.../CostoPorKg`, `.../kWhAcum`, `.../ChipsKgAcum`, `.../TempZapecado`, `.../TempSecado`, `.../HumFinal`, `.../ProduccionKg` |
| MQTT | `yerba/whatif/scenarioN/{OEE\|CostoPorKg\|kWhAcum\|ChipsKgAcum\|TempZapecado\|TempSecado\|HumFinal\|ProduccionKg}` |

Esto le permite al SCADA leer y comparar baseline vs. variantes en tiempo real sin modificar la lógica del PLC.

### 3.11 Cámaras dinámicas + inyección de vapor

`YerbaProcessSimulator.set_camaras_count(n)` permite crecer/encoger la lista de cámaras entre 1 y `MAX_CAMARAS = 12` en caliente. Modbus pre-aloca 12 slots (unit IDs 3..14) y OPC UA pre-aloca 12 nodos (`Camara1` … `Camara12`) con una variable `Activa: bool` que indica si la cámara existe en la corrida actual.

Cada `CamaraMaduracion` ahora tiene tres modos de operación:
1. **Vapor activo + caudal > 0** → tau corto (~60-180s), busca `vapor_setpoint_temp`/`vapor_setpoint_hum`. Acumula `vapor_kg_acum`.
2. **Solo ventilador** → tau original (600s default), busca `temperatura_obj`/`humedad_obj`.
3. **Pasivo** → 70% ambiente + 30% setpoint.

El consumo de vapor se calcula como `vapor_caudal_kgh × dt_h` y queda disponible para análisis de costos (caldera, agua, gas si la caldera lo usa, etc.).

### 3.12 MassFlowService (`mass_flow.py`) — trazabilidad de masa

Sigue el flujo de hoja de yerba a través de las 5 etapas controladas (`recepcion`, `zapecado`, `secado`, `canchado`, `estacionamiento`). Cada `StageMass` mantiene:

- `kg_actual`: masa en proceso en la etapa
- `kg_acum_in`, `kg_acum_out`: contadores históricos
- `merma_kg_acum`: pérdida total
- `T_in`, `H_in`: condiciones de entrada (heredadas del paso anterior)
- `ts_last_in`, `ts_last_out`

**Operaciones**:

```python
mass_flow.cargar_hoja_verde(kg, T=None, H=None, user="...")
# defaults: T = sim.ambient_temp, H = 55.0 (hoja recién cosechada)
# si recepción ya tenía masa, T y H se promedian ponderadamente

mass_flow.transferir(de, a, kg=None, user="...")
# kg=None → transfiere todo
# valida secuencia: sólo permite avanzar al stage siguiente
# kg_out = kg_in × (1 - merma_pct[de])
# dst.T_in = simulator output T del stage `de`
# dst.H_in = simulator output H del stage `de`
# si dst es 'estacionamiento', reparte a la cámara con menor carga (load balancing)

mass_flow.set_merma(stage, pct)   # admin only, 0 ≤ pct ≤ 0.95
mass_flow.reset()                  # admin only
mass_flow.snapshot()               # estado completo + últimos 50 eventos del log
```

**Mermas por defecto** (referencial, INYM):

| Etapa | Merma | Justificación |
|-------|------:|---------------|
| Recepción | 0.0% | Sólo pesaje, sin pérdida |
| Zapecado | 35.0% | Evaporación intensa (55% hum → 25% hum) |
| Secado | 22.0% | Segunda evaporación (25% → 4-7% hum) |
| Canchado | 4.0% | Polvo, partículas finas que se aspiran |
| Estacionamiento | 0.5% | Respiración mínima de la yerba |

**Lectura de T_out / H_out** por etapa (en `_read_stage_output`):

| Etapa de origen | T_out (sensor) | H_out (sensor) |
|-----------------|----------------|----------------|
| Recepción | T ambiente clima | 55.0 (constante) |
| Zapecado | `sim.zapecado.temperatura` | `sim.flujo['zap_out_humedad']` |
| Secado | `sim.secado.temperatura` | `sim.secado.humedad` |
| Canchado | `sim.secado.temperatura - 5` | `sim.secado.humedad` |

---

## 4. Modelo de datos (MongoDB)

> Convención: todos los documentos devueltos por la API excluyen `_id` con `find_one({...}, {"_id": 0})`.

### Colecciones

| Colección | Documento clave | Campos principales |
|-----------|-----------------|--------------------|
| `users` | `username` | username, password_hash (bcrypt), role, created_at |
| `recipes` | `id` (uuid) | id, nombre, setpoints {zapecado, secado, canchado, camaras}, created_at, created_by |
| `batches` | `id` (uuid) | id, receta_id, receta_nombre, kg_input, kg_output, merma, started_at, finished_at, status, alarms_during, snapshots[] |
| `audit_log` | `_id` Mongo | ts, username, action, payload, ip |
| `alarm_rules` | `id` | name, tag, op, threshold, priority, description, enabled |
| `alarms_active` | `id` | regla actual + value_at_trigger + last_value + status + ts + ack_by/ack_at |
| `alarms_history` | `_id` | mismo schema que active, append-only |
| `ops_state` | `id = "singleton"` | runtime_hours, kwh_accum, chips_kg_accum, kg_*, prices, chip_calorific_mj_kg, thresholds, maint_acks, shifts |
| `weather_cache` | `key` | ciudad, lat, lon, last_fetch, payload |

---

## 5. API REST

> Todas bajo prefijo `/api`. Auth con cookie JWT o header `Authorization: Bearer ...`.

### 5.1 Auth
- `POST /auth/login` → `{ access_token, user }`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/change-password` `{current_password, new_password}`
- `POST /auth/recover` `{username, recovery_code, new_password}`
- `GET /auth/users` (admin)

### 5.2 Estado y modo
- `GET /state` → snapshot completo (zapecado, secado, canchado, camaras[], ambient)
- `GET /history?n=600` → buffer reciente
- `GET /services/status` → ON/OFF + errores por servicio
- `GET /mode` / `POST /mode` `{mode: simulator|shadow|twin}`
- `POST /throughput` `{kgh}`
- `WS /ws` → broadcast a 1 Hz del state

### 5.3 Controles por etapa

Todos aceptan campos opcionales (envían sólo los que cambian). **Cualquiera de estos
valores también se refleja en Modbus y OPC UA** (ver §3.4).

#### `POST /zapecado`
```json
{
  "velocidad_tambor": 15,        // rpm
  "velocidad_chip": 30,          // kg/h
  "estado_alimentacion": true,
  "temperatura_obj": 480,        // SP manual °C. Mandar null para volver a SP dinámico
  "tau": 90,                     // constante de tiempo térmica (s sim)
  "falla_quemador": false,       // INYECCIÓN DE FALLA: quemador no calienta
  "falla_motor_tambor": false    // INYECCIÓN DE FALLA: tambor parado
}
```

#### `POST /secado`
```json
{
  "velocidad_aire": 2.5,         // m/s
  "estado": true,
  "temperatura_obj": 95,         // SP °C (típico 90-100)
  "humedad_obj": 7,              // SP HR final %  (piso al que se llega)
  "tau_t": 120,                  // constante de tiempo térmica (s sim)
  "falla_ventilador": false,     // FALLA: sin circulación de aire
  "falla_serpentin": false       // FALLA: calefactor caído
}
```

#### `POST /canchado`
```json
{
  "velocidad_molino": 60,
  "estado": true,
  "tamano_particula_obj": 4.5,   // SP grosor mm. null para SP dinámico (10 − 0.07·rpm)
  "tau_p": 5,                    // constante de tiempo molino (s sim)
  "falla_motor": false,          // FALLA: molino parado, encoder=0
  "rodamiento_caliente": false   // FALLA: T_rodamientos +35°C y vibX +4 mm/s
}
```

#### `POST /camaras/{idx}`
```json
{
  "carga_kg": 1200,
  "ventilador": true,
  "temperatura_obj": 35,         // SP T °C
  "humedad_obj": 75,             // SP HR %
  "co2_obj": 3000,
  "vapor_activo": false,         // inyección por techo ON/OFF
  "vapor_caudal_kgh": 20,
  "vapor_setpoint_temp": 40,
  "vapor_setpoint_hum": 85,
  "tau": 600,                    // constante de tiempo cámara (s sim)
  "falla_ventilador": false,     // FALLA: sin circulación → CO2 sube
  "fuga_vapor": false,           // FALLA: se consume vapor sin efecto útil
  "puerta_abierta": false        // FALLA: pérdida acelerada hacia ambiente
}
```

#### Configuración global de simulación
- `POST /config` `{simulacion: {aceleracion: N}}` — N ∈ {1, 60, 3600, 86400} típico
  (1× real, 1 min/s, 1 h/s, 1 día/s). También se puede setear desde el control de
  velocidad del header (admin).

### 5.4 Recetas
- `GET /recipes`
- `POST /recipes` (admin)
- `POST /recipes/{id}/apply`
- `DELETE /recipes/{id}` (admin)

### 5.5 Lotes
- `GET /batches`
- `GET /batches/active`
- `POST /batches` `{receta_id, kg_input}`
- `POST /batches/{id}/close` `{kg_output}`
- `POST /batches/{id}/cancel`

### 5.6 Industria 4.0
- `GET /external/status`
- `POST /external/{section}` (modbus|opcua|mqtt)
- `GET /drift`
- `POST /calibration/analyze` `{csv}` → preview
- `POST /calibration/apply` `{calibration}`
- `GET /audit?limit=200&username=`

### 5.7 Alarmas
- `GET /alarms/active`
- `GET /alarms/history?limit=&priority=&status=`
- `POST /alarms/ack` `{alarm_id}`
- `GET /alarms/rules`
- `POST /alarms/rules` (admin) — upsert
- `DELETE /alarms/rules/{id}` (admin)

### 5.8 OEE / Mantenimiento / Energía
- `GET /oee?window_hours=24`
- `GET /maintenance`
- `POST /maintenance/ack` `{component, action}`
- `POST /maintenance/thresholds` (admin) `{thresholds: {comp: {action: hours}}}`
- `GET /energy`
- `POST /energy/prices` (admin) `{kwh_ars?, kg_chips_ars?, kg_yerba_venta_ars?, chip_calorific_mj_kg?}`
- `POST /ops/shifts` (admin) `{shifts_per_day?, hours_per_shift?}`
- `POST /ops/reset?what=all|runtime|energy|production` (admin)

### 5.9 Reportes
- `GET /reports/monthly` → PDF
- `GET /reports/batch/{id}` → PDF

### 5.10 FASE 4 — Replay
- `GET /replay/files` → lista de CSVs en `backend/data/`
- `GET /replay/status` → `{active, paused, file, speed, cursor, total, progress, ts_at_cursor}`
- `POST /replay/start` (admin) `{file, speed?, start_row?}` — pone modo en `replay`
- `POST /replay/stop` (admin) — restaura modo `simulator`
- `POST /replay/pause` (admin) `{paused: bool}`
- `POST /replay/seek` (admin) `{row: int}`
- `POST /replay/speed` (admin) `{speed: float}` — 0.25 a 120

### 5.11 FASE 4 — What-if
- `GET /whatif` → lista escenarios con KPIs
- `POST /whatif` (admin) `{name, overrides}` — máx 3 escenarios
- `POST /whatif/{id}` (admin) `{overrides}` — actualiza overrides (reinicia contadores)
- `DELETE /whatif/{id}` (admin)
- `POST /whatif/reset` (admin) — borra todos

> **Importante**: orden de rutas. `/whatif/reset` debe declararse ANTES de `/whatif/{scenario_id}` en `server.py`. Mismo patrón aplica a `/camaras/count` antes de `/camaras/{idx}`.

### 5.12 Cámaras dinámicas
- `POST /camaras/count` (admin) `{count: 1..12}` — agrega/quita cámaras desde el final, persiste en `config_yerba.yaml`
- `POST /camaras/{idx}` `{carga_kg?, ventilador?, temperatura_obj?, humedad_obj?, co2_obj?, vapor_activo?, vapor_caudal_kgh?, vapor_setpoint_temp?, vapor_setpoint_hum?}`

### 5.13 MassFlow (trazabilidad de masa)
- `GET /massflow` → snapshot completo de las 5 etapas + log de últimos 50 eventos
- `POST /massflow/carga` `{kg, T?, H?}` — carga hoja verde a Recepción (any user)
- `POST /massflow/transferir` `{de, a, kg?}` — transfiere a la etapa siguiente con merma e inherencia T/H
- `POST /massflow/merma` (admin) `{stage, pct}` — ajusta % de merma de una etapa
- `POST /massflow/reset` (admin) — reset total

### 5.14 What-if extras
- `POST /whatif/snapshot` (admin) `{name, extra_overrides}` — captura baseline + merge de overrides extras

### 5.15 Config + clima + IA + datos
- `GET /config` / `POST /config`
- `GET /weather` / `POST /weather/location` / `GET /weather/search?q=`
- `POST /ai/chat` / `GET /ai/history/{sid}` / `POST /ai/reset/{sid}`
- `GET /ai/anomalies` / `GET /ai/forecast?horizon=`
- `GET /data/files` / `GET /data/download/{name}` / `GET /data/excel?name=`

---

## 6. Frontend

### 6.1 Stack

- **React 18** (CRA)
- **Tailwind CSS** + variables `--amber`, `--green`, `--red`, `--border`, `--text` para tematizar.
- **Recharts** para gráficos.
- **@phosphor-icons/react** para iconos.
- **axios** para HTTP, **WebSocket nativo** para stream.
- **localStorage** para token de respaldo y persistencia de pestaña activa.

### 6.2 Convenciones

- Componentes funcionales, hooks.
- Cada elemento interactivo y todo elemento con info crítica lleva `data-testid` único.
- Páginas: default export. Componentes reutilizables: named export.
- Estado de servidor refrescado con `setInterval` cada 4-8 s según criticidad; WebSocket solo para el state principal.

### 6.3 Hook clave: `useLiveState`

Centraliza conexión WS, reconnect exponential backoff, parseo del payload y exposición como `state`.

---

## 7. Configuración (`config_yerba.yaml`)

```yaml
modbus:
  ip: 0.0.0.0
  port: 5020
  rate: 1.0
mqtt:
  broker: localhost
  port: 1883
  topic: yerba
  interval: 5
  user: ""
  pass: ""
  keepalive: 60
opcua:
  host: 0.0.0.0
  port: 4840
  path: /yerba/
  namespace: YerbaProcess
  interval: 1000
simulacion:
  aceleracion: 60
persistence:
  enabled: true
  interval_seconds: 5
weather:
  latitude: -27.37
  longitude: -55.90
  city: Posadas, Misiones, Argentina
  interval_seconds: 600
```

---

## 8. Variables de entorno

### Backend (`/app/backend/.env`)

```bash
MONGO_URL=mongodb://localhost:27017
DB_NAME=yerba_twin
JWT_SECRET=<256-bit hex generado con secrets.token_hex(32)>
ADMIN_RECOVERY_CODE=yerbatera-recovery-2026
EMERGENT_LLM_KEY=<universal key>
```

### Frontend (`/app/frontend/.env`)

```bash
REACT_APP_BACKEND_URL=https://<dominio>.preview.emergentagent.com
```

> **Nunca** hardcodear URLs ni ports. Toda config viene de `.env` para que el mismo bundle corra en dev/staging/prod.

---

## 9. Despliegue local

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001  # solo en dev; en prod usar supervisor

# Frontend
cd frontend
yarn install
yarn build      # producción
yarn start      # dev (3000)
```

En el contenedor Emergent: ambos servicios son manejados por **supervisor**. Hot-reload activo. Comando de reinicio manual:

```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

Logs:
- `/var/log/supervisor/backend.err.log`
- `/var/log/supervisor/backend.out.log`
- `/var/log/supervisor/frontend.err.log`

---

## 10. Pruebas

### Backend
- Curl con `Authorization: Bearer` desde `REACT_APP_BACKEND_URL` (no localhost en este entorno).
- Tests pytest sugeridos en `/app/backend/tests/` (futuro: cobertura sobre alarms, ops, recipes).

### Frontend
- Selectores por `data-testid`.
- Smoke screenshot tras cada cambio mayor.
- Testing agent v3 fork para regresión completa.

### Integraciones industriales
- Modbus: probar con `modpoll` o `pymodbus` REPL apuntando a `localhost:5020`.
- OPC UA: `opcua-client-gui` apuntando a `opc.tcp://localhost:4840/yerba/`.
- MQTT: subscriber con `mosquitto_sub -t 'yerba/#'`.

---

## 11. Próximos hitos (roadmap)

### FASE 4 — Entrenamiento (✅ COMPLETADA)
- [x] Modo **replay** de CSV histórico con velocidad 0.25× - 120×.
- [x] Modo **"qué pasaría si"** (3 escenarios paralelos vs baseline).
- [x] Exposición de cada escenario a **PLC / SCADA** vía Modbus / OPC UA / MQTT.
- [x] Cámaras configurables (1-12) + inyección de vapor por cámara.
- [ ] Catálogo de escenarios de falla predefinidos (entrenamiento estructurado).
- [ ] "Snapshot → What-if": botón para capturar el estado actual del baseline como punto de partida de un escenario, sin escribir JSON.

### Quick wins (P1)
- [ ] Gestión de usuarios desde UI (admin CRUD + cambio de rol).
- [ ] Brute-force lockout (5 intentos / 15 min).
- [ ] Persistir calibración aplicada en YAML.
- [ ] Cleanup periódico de PDFs antiguos en `data/reports`.
- [ ] PDF por lote: ampliar curvas e historial.

### Refinamientos técnicos
- [ ] `hours_at_ack` exacto en mantenimiento (en lugar de aproximación).
- [ ] OEE con ventana basada en histórico real, no proporcional.
- [ ] Migrar la constante `BASE_CHIP_CALORIFIC_MJ_KG` a `config_yerba.yaml`.
- [ ] Refactor `external_sources.py`: eliminar warnings de `coroutine never awaited` en OPC UA client.
- [ ] CamaraMimic SVG: ajustar tamaños de TEMP/HR para que no queden cortados en algunas resoluciones.

---

## 12. Decisiones de diseño relevantes

| Decisión | Motivo |
|----------|--------|
| FastAPI sobre Flask | Soporte nativo `async`, WebSocket, OpenAPI auto-generado |
| Mongo sobre Postgres | Esquemas flexibles para snapshots de lotes y reglas dinámicas |
| Bcrypt sobre Argon2 | Mejor soporte en Python embebido, suficiente seguridad para entorno on-prem |
| JWT en cookie + Bearer fallback | Cookie httpOnly para mitigar XSS, Bearer para integraciones |
| Tick async vs thread | Permite mezclar Modbus sync (pymodbus 3.7.4) con OPC UA async sin GIL pain |
| ReportLab sobre WeasyPrint | Sin dependencia de browsers headless, deterministico, footprint chico |
| Emergent LLM key | Llave universal del agente, evita exponer secretos por integrador |
| `chip_calorific_mj_kg` editable | Diferentes plantas usan chips con humedades distintas; PCI cambia consumo lineal |

---

## 13. Contacto / soporte

Issues técnicos: equipo de desarrollo Emergent.
Soporte de planta: TI interno + manual de operaciones (`manual_operaciones.md`).
