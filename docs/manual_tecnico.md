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
                       ├──► OPC UA server :4840            │                          │
                       ├──► MQTT publisher (broker ext)    │                          │
                       ├──► Modbus client (IN)             │                          │
                       ├──► OPC UA client  (IN)            │                          │
                       ├──► MQTT subscriber                │                          │
                       ├──► Weather (Open-Meteo)           │                          │
                       └──► PersistenceService (CSV/XLSX)  │                          │
                                                          ▼                          ▼
                                                       MongoDB                MongoDB `ops_state`
                                                  (alarms_active,             reports/*.pdf
                                                   alarms_history,            (ReportLab)
                                                   alarm_rules)
```

**Modos de operación** (controlados por `RuntimeMode` enum):

| Modo | Simulador | Cliente externo | Drift |
|------|-----------|-----------------|-------|
| `simulator` | tick activo | ignorado | n/a |
| `shadow` | tick activo | leído pero NO inyectado | calculado |
| `twin` | tick pausado | inyectado al estado | trivial |

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
| Modbus TCP | 5020 | 7 unit IDs (zapecado=0, secado=1, canchado=2, cam0-3=3-6). Registers holding (R/W) y input (RO). |
| OPC UA | 4840 | Namespace `YerbaProcess`. Variables organizadas por jerarquía de objetos: `/Plant/Zapecado/Temperature`, etc. |
| MQTT | broker externo | Topics `yerba/{etapa}` con payload JSON. Publica cada N s (default 5). |

**Clientes (IN)** — leen del PLC real cuando el modo es `shadow` o `twin`:

- Mismo set de protocolos.
- Mapeo configurable de tag → variable interna desde la UI (Industria 4.0).
- Polling interval por protocolo.

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
- `POST /zapecado` `{setpoint?, alimentacion?}`
- `POST /secado` `{...}`
- `POST /canchado` `{...}`
- `POST /camaras/{idx}` `{ventilador?, temp_target?}`

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

### 5.10 Config + clima + IA + datos
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

### Fase 4 — Entrenamiento (próxima)
- [ ] Modo **replay** de CSV histórico a 10× velocidad.
- [ ] Modo **"qué pasaría si"** (fork de simulación con parámetros alternativos vs baseline).
- [ ] Catálogo de escenarios de falla predefinidos.

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
