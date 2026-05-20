# PRD — Gemelo Digital Yerba Mate

## Problema original
Migrar app Python/Tkinter de simulación de Yerba Mate a web (React + FastAPI)
con protocolos industriales (Modbus, MQTT, OPC UA), IA (Gemini), clima real
(Open-Meteo) y funcionalidad industrial completa.

## Estado (mayo 2026) — Fase 6 BIDIRECCIONAL

### Características core
- **Modelo físico puro** (sin τ→SP escondido). Balance energético/másico real.
- **PID interno opcional** por etapa (Kp/Ki/Kd tunable, default OFF).
- **Variables manipuladas** explícitas: vel.chip, vel.tambor, posición calefactor, vel.aire, caudal vapor, rpm, vent.pos.
- **Forecast horario** Open-Meteo (96h) usado cuando aceleración > 1×.
- **Reloj simulado** que avanza con factor configurable (1× / 60× / 1h-s / 1d-s).
- **8 inyecciones de falla** por etapa.

### Modo BIDIRECCIONAL (todos los protocolos)
- **MQTT** subscriber `yerba/cmd/#` parsea comandos JSON y los aplica al simulator.
  - `yerba/cmd/{etapa}` con JSON payload (cualquier campo del Patch model)
  - `yerba/cmd/camara/<idx>` para una cámara específica
  - `yerba/cmd/weather` para override manual del ambient
  - `yerba/cmd/sim` para globales (acel, throughput, mode)
  - Atajo raw value: `yerba/cmd/zapecado/velocidad_chip` payload `45`
- **Modbus TCP** (`_apply_external_writes` polling-diff cada 200ms).
- **OPC UA** (`_apply_external_writes` cada 2s).
- Manual override del clima persistente (no es pisado por forecast cuando
  `weather_meta.source ∈ {manual, mqtt-cmd}`).

### Documentación
- `manual_operaciones.md` — flujo operativo desde la UI.
- `manual_tecnico.md` — arquitectura, modelo físico, mapeo Modbus/OPC UA, MQTT, modo bidireccional.
- `instructivo_nodered.md` — integración Node-RED, cámaras remotas, ejemplos de flow, troubleshooting.

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
- Tour interactivo, DocsModal markdown viewer.
- Theme dark global con textarea fix CSS.

## Tests
- Iteración 11: 13/15 bidir tests pass (los 2 fallos fueron causa root del bug
  weather override, ya fixeado).
- 8 docs/test_reports historicos.

## Credenciales
- admin / admin
- operario / operario

## Modos del simulador
- `simulator` (default): física pura controlada desde UI/API.
- `shadow`: refleja lecturas externas sin recalcular física.
- `twin`: simula y compara vs planta real, emite correcciones.

## Backlog priorizado
- **P1**: "Molienda fina" y "Empaque" en Mass Flow (etapas finales).
- **P2**: Reportes PDF por batch individual.
- **P2**: Refactor `server.py` (1233 líneas) → routers por dominio.
- **P3**: ACL MQTT por topic + OPC UA con seguridad Sign+Encrypt.
- **P3**: Replay desde stream MQTT real (grabar/reproducir planta).

## Notas
- Open-Meteo tiene rate limit. Fallback estacional sintético implementado.
- Para tests de MQTT en CI: instalar mosquitto `apt-get install -y mosquitto`.
- OPC UA: nodos están bajo `Objects/{Zapecado,Secado,Canchado,Camara1..12,Simulacion}` namespace=2.
