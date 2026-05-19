# PRD — Gemelo Digital Yerba Mate

## Problema original
Aplicación Python/Tkinter que simula la producción de Yerba Mate con protocolos
industriales (Modbus TCP, MQTT, OPC UA). Migrar a un stack web (React + FastAPI)
manteniendo los protocolos y agregando IA (Gemini), clima real (Open-Meteo) y
funcionalidad industrial avanzada (recetas, batches, alarmas ISA-18.2, OEE,
mantenimiento, reportes PDF, replay, what-if, mass-flow realista).

## Fases del roadmap
- Fase 1 ✅ Recetas, Batches, Mass-Flow básico, SVG Mimics, Auth JWT
- Fase 2 ✅ Clientes Modbus/OPC UA, drift calibration, CSV calibration
- Fase 3 ✅ Alarmas ISA-18.2, OEE, Mantenimiento, PDF mensual, costos energéticos
- Fase 4 ✅ Replay desde CSVs, What-If, Mass-flow con inheritance T/H + readiness
- **Fase 5 (mayo 2026) ✅ Rediseño físico puro + PID configurable + forecast horario**

## Estado actual (Iteración 10 — modelo físico puro)
### Simulador
- **Modelo físico real** (sin τ→SP escondido): balance energético/másico por etapa.
- **Variables manipuladas** por etapa (lo que el operador o PLC ajusta):
  - Zapecado: `vel.chip` (kg/h), `vel.tambor` (rpm)
  - Secado: `posicion_calefactor` (0-100%), `vel.aire` (m/s)
  - Canchado: `vel.molino` (rpm)
  - Cámaras: `vapor_caudal_kgh`, `vent_pos`, `vapor_activo`
- **SPs** (objetivos del operador) — sólo referencia, no fuerzan al sistema.
- **PID interno opcional por etapa** (default OFF) con Kp/Ki/Kd tunables y reset.
- **Open-Meteo forecast horario** (96h) consumido cuando aceleración > 1×.
- **Reloj simulado** que avanza con factor aceleración (1× / 60× / 1h-s / 1d-s).
- 8 fallas (quemador, motor tambor, ventilador, serpentín, motor molino,
  rodamiento caliente, fuga vapor, puerta abierta).

### Protocolos expuestos
- **Modbus TCP (5020)**: regs 0..16 por unidad (incluye PID y manipuladas reales),
  coils para fallas, unidad 100 globales.
- **OPC UA (4840)**: `YerbaProcess.{Zapecado, Secado, Canchado, Camara1..12, Simulacion}` con PIDs.
- **MQTT**: topics `yerba/{zapecado,secado,canchado,camara_N,ambient,sim,forecast}`
  con PV + SP + manipuladas + PID + faults cada 5s.

### Frontend
- 13 tabs operativas con mímicos SVG/P&ID, charts, sensores derivados.
- **PidPanel** reutilizable: toggle AUTO/MANUAL, Kp/Ki/Kd, Out, Σerr, reset.
- **SpeedControl** + **WeatherControl** en header.
- Layout 2 columnas en cámaras (mímico + reales vs SP a izq, controles a der).
- `useLocalSync` hook que evita race condition de toggles.
- Manuales markdown integrados (operaciones + técnico).

## Tests
- 14/15 tests nuevos en iteración 10 pasan + 4/4 regression OK.
- Tests pre-existentes (`test_data_excel`, `test_zapecado_to_secado_with_merma`)
  fallan por motivos previos a esta refactorización.

## Credenciales
- admin / admin
- operario / operario

## Backlog priorizado
- **P1**: Agregar "Molienda fina" y "Empaque" como etapas finales del Mass Flow.
- **P2**: Reportes PDF por batch individual.
- **P2**: Refactor `server.py` (1214+ líneas) en routers por dominio.
- **P3**: Unificar acción inversa de PID (Canchado usa kp<0 vs direct_action=False).
- **P3**: Exponer factor de acople zapecado→secado humidity como parámetro.

## Health check (mayo 2026)
- Open-Meteo rate-limited (forecast_count puede ser 0; manual override disponible).
- Default ambient: 24°C / 70% (Posadas, Misiones).
- Zapecado T estable @ defaults: ~350-380°C (calibrado).
- Secado T sin calefactor: cae al ambiente (correcto — sin PID escondido).
