# PRD — Gemelo Digital Yerba Mate

## Problema original
Aplicación Python/Tkinter que simula la producción de Yerba Mate con protocolos
industriales (Modbus TCP, MQTT, OPC UA). Migrar a un stack web (React + FastAPI)
manteniendo los protocolos y agregando IA (Gemini), clima real (Open-Meteo) y
funcionalidad industrial avanzada (recetas, batches, alarmas ISA-18.2, OEE,
mantenimiento, reportes PDF, replay, what-if, mass-flow realista).

## Fases del roadmap
- **Fase 1** ✅ Recetas, Batches, Mass-Flow básico, SVG Mimics, Auth JWT.
- **Fase 2** ✅ Clientes Modbus/OPC UA, drift calibration, CSV calibration.
- **Fase 3** ✅ Alarmas ISA-18.2, OEE, Mantenimiento, PDF mensual, costos energéticos (chips).
- **Fase 4** ✅ Replay desde CSVs, What-If con presets, Mass-flow realista con
  inheritance T/H + readiness timers + transfer mermas.

## Lo construido (último estado, mayo 2026)
### Backend (FastAPI + threads asyncio)
- Simulador termodinámico realista con acoplamientos físicos:
  - Zapecado SP dinámico = 350 + 1.4·vel.chips − 1.2·(vel.tambor − 30)
  - Secado T = SP − 2.5·(vel.aire − 2.5); HR baja ∝ √(vel.aire)
  - Canchado grosor = 10 − 0.07·rpm; rpm_real=0 si off/falla
  - Cámaras 1-12 con τ, vapor opcional, modo pasivo
- **Setpoints manuales independientes** del valor real (no se confunden)
- **τ (constante de tiempo) configurable** por etapa
- **Inyección de fallas** por etapa (8 fallas en total)
- **Override manual** de T/HR ambiente (cuando Open-Meteo está caído)
- **Aceleración global** configurable (1×, 60×, 1h/s, 1d/s)
- Servidores Modbus TCP (5020) + OPC UA (4840) + cliente MQTT
- Recetas con aplicación a etapas, lotes con genealogía completa
- OEE, alarmas ISA-18.2, mantenimiento preventivo
- Replay histórico desde CSVs diarios; What-If con 3 escenarios paralelos
- Mass-Flow asíncrono con transferencias entre etapas

### Frontend (React + Tailwind + Recharts + Phosphor)
- 13 tabs: Dashboard, Flujo de masa, Zapecado, Secado, Canchado, Cámaras, Recetas,
  Lotes, Operaciones, Industria 4.0, Replay & What-if, IA Gemini, Configuración
- Mímicos SVG animados + P&ID estático (toggle global)
- Mímicos muestran **valor REAL vs SP** (cuando algo está off muestra 0 rpm, MILL OFF, etc.)
- **WeatherControl**: badge clickable con T/HR actual, buscador de ciudades, override manual
- **SpeedControl**: dropdown con presets de aceleración
- **Tour interactivo** (1er turno) reabierble desde header
- **Manuales** integrados (markdown viewer)
- **useLocalSync hook**: evita race condition en toggles (2.5s freeze tras edición local)

## Endpoints clave
- `POST /api/zapecado` `{velocidad_tambor, velocidad_chip, estado_alimentacion, temperatura_obj, tau, falla_quemador, falla_motor_tambor}`
- `POST /api/secado` `{velocidad_aire, estado, temperatura_obj, humedad_obj, tau_t, falla_ventilador, falla_serpentin}`
- `POST /api/canchado` `{velocidad_molino, estado, tamano_particula_obj, tau_p, falla_motor, rodamiento_caliente}`
- `POST /api/camaras/{idx}` `{carga_kg, ventilador, temperatura_obj, humedad_obj, co2_obj, vapor_activo, vapor_caudal_kgh, vapor_setpoint_*, tau, falla_*, fuga_vapor, puerta_abierta}`
- `POST /api/weather/manual` `{temperature, humidity}` (admin)
- `POST /api/config` `{simulacion: {aceleracion}}`
- `GET /api/state` — snapshot completo con sensores derivados, fallas, SPs

## Exposición Modbus / OPC UA
Todos los SP, valores reales, τ y fallas están expuestos:
- **Modbus** unit 0=zap, 1=sec, 2=can, 3..14=cámaras, 100=globales. Holding regs + coils.
- **OPC UA** namespace `YerbaProcess`. Nodos `Zapecado`, `Secado`, `Canchado`,
  `Camara1..12`, `Simulacion`. Todos writable.

## Credenciales
- admin / admin (administrador)
- operario / operario (operario, sin permisos de admin)

## Backlog priorizado
- **P1**: Agregar "Molienda fina" y "Empaque" como etapas finales del Mass Flow.
- **P2**: Reportes PDF por batch individual (hoy solo mensual).
- **P2**: Splitting de `server.py` (1214 líneas) en routers por dominio.
- **P3**: WeatherManualBody como Pydantic model en lugar de dict crudo.

## Health check (mayo 2026)
- Tests: 32/32 nuevos iter8+iter9 pass + suite previa funcional.
- Conocidos fallos pre-existentes: `test_data_excel`, `test_zapecado_to_secado_with_merma` (ajenos a estos cambios).
- Open-Meteo: rate-limited el 19/5/2026 → fallback a default 24°C o override manual.
