# PRD — Gemelo Digital Yerba Mate

## Problema original
Migrar app Python/Tkinter de simulación de Yerba Mate a web (React + FastAPI)
con protocolos industriales (Modbus, MQTT, OPC UA), IA (Gemini), clima real
(Open-Meteo) y funcionalidad industrial completa.

## Estado (mayo 2026) — Fase 6 BIDIRECCIONAL + 7 ETAPAS

### Características core
- **Modelo físico puro** (sin τ→SP escondido). Balance energético/másico real.
- **PID interno opcional** por etapa (Kp/Ki/Kd tunable, default OFF).
- **Variables manipuladas** explícitas: vel.chip, vel.tambor, posición calefactor, vel.aire, caudal vapor, rpm, vent.pos.
- **Forecast horario** Open-Meteo (96h) usado cuando aceleración > 1×.
- **Reloj simulado** que avanza con factor configurable (1× / 60× / 1h-s / 1d-s).
- **8 inyecciones de falla** por etapa.
- **Mass Flow 7 etapas end-to-end**: Recepción → Zapecado → Secado → Canchado → Estacionamiento → Molienda fina → Empaque (NEW mayo 2026).

### Modo BIDIRECCIONAL (todos los protocolos)
- **MQTT** subscriber `yerba/cmd/#` parsea comandos JSON.
- **Modbus TCP** (`_apply_external_writes` polling-diff cada 200ms).
- **OPC UA** (`_apply_external_writes` cada 2s).
- Manual override del clima persistente.

### Documentación (mayo 2026)
- `00_indice.md` — **NEW** índice general con rutas de lectura por rol.
- `01_instructivo_ejecucion.md` — **NEW** cómo levantar el sistema, puertos, .env, troubleshooting.
- `manual_operaciones.md` — flujo operativo desde UI (con TOC).
- `manual_gemelo_virtual.md` — **NEW** qué es un gemelo, los 4 modos, uso en paralelo con MQTT/Modbus/OPC UA.
- `manual_machine_learning.md` — **NEW** IA integrada: Gemini 3 Flash, anomalías, forecast, optimización what-if.
- `manual_tecnico.md` — arquitectura completa (con TOC).
- `instructivo_nodered.md` — integración Node-RED (con TOC).

### Protocolos
| Proto | Puerto | Latencia in | Latencia out | Modo |
|-------|--------|-------------|--------------|------|
| MQTT  | broker | <100 ms | 5 s | Bidir |
| Modbus TCP | 5020 | ~200 ms | ~200 ms | Bidir |
| OPC UA | 4840 | ~2 s | ~2 s | Bidir |
| REST | /api/* | on-demand | on-demand | Bidir |

### Frontend
- 13 tabs operativas, mímicos SVG/P&ID, sensores derivados.
- PidPanel, FaultPanel, SpeedControl, WeatherControl.
- useLocalSync hook (anti race condition).
- TourModal (6 pasos), DocsModal markdown viewer.
- MassFlowView con 7 etapas (incluye Molienda fina + Empaque).

## Mermas referenciales (yerba mate end-to-end)
- recepcion: 0%
- zapecado: 35% (evaporación 50→25% hum)
- secado: 22% (25→6%)
- canchado: 4%
- estacionamiento: 0.5%
- **molienda_fina**: 3% (zarandeo, polvo, palitos)
- **empaque**: 0.5% (descarte por defectos)

Rendimiento típico: 1000 kg hoja verde → ~470 kg yerba empaquetada (47%).

## Tests
- Iteración 11: 13/15 bidir tests pass.
- Verificación post-cambios: flujo end-to-end de 7 etapas validado por curl (469.76 kg final desde 1000 kg).

## Credenciales
- admin / admin
- operario / operario

## Modos del simulador
- `simulator` (default): física pura controlada desde UI/API.
- `shadow`: refleja lecturas externas sin recalcular física.
- `twin`: simula y compara vs planta real, emite correcciones.
- `replay`: reproduce CSV histórico.

## Backlog priorizado
- **P1**: Refactor `server.py` (1233 líneas) → routers por dominio.
- **P2**: Reportes PDF por batch individual (endpoint ya existe `/api/reports/batch/{id}`, falta UI para descargarlo desde lote).
- **P2**: TimeGPT/Prophet para forecast horizontes >1h.
- **P3**: ACL MQTT por topic + OPC UA con seguridad Sign+Encrypt.
- **P3**: Replay con velocidad adaptativa según importancia del evento.
- **P3**: Self-tuning de mermas por mínimos cuadrados sobre últimos 30 lotes.

## Notas
- Open-Meteo tiene rate limit. Fallback estacional sintético implementado.
- OPC UA: nodos están bajo `Objects/{Zapecado,Secado,Canchado,Camara1..12,Simulacion}` namespace=2.
- Mass flow: cuando `estacionamiento → molienda_fina`, el simulador no descarga las cámaras automáticamente; el operario puede ajustar `carga_kg` manualmente si quiere reflejar la salida en cámaras específicas.
