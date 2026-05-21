# Índice general · Documentación del Gemelo Digital de Yerba Mate

> **Versión del sistema**: v2.4 — Mayo 2026
> **Stack**: React 18 · FastAPI · MongoDB · Modbus TCP · OPC UA · MQTT · Gemini 3 Flash
> **Idioma del producto**: Español (rioplatense)

Esta documentación está organizada por **rol de lector**. Empezá por el manual que aplica a tu rol y, cuando lo necesites, saltá al manual técnico o al instructivo de integración.

---

## Manuales disponibles

| # | Documento | Para quién | Qué encontrás |
|---|-----------|------------|---------------|
| **00** | `00_indice.md` | Todos | Este índice y guía de lectura. |
| **01** | `01_instructivo_ejecucion.md` | TI · Mantenimiento · Integrador | Cómo levantar el sistema, requisitos, puertos, supervisor, troubleshooting. Empezá por acá si nunca corriste el gemelo. |
| **02** | `manual_operaciones.md` | Operario · Supervisor de turno · Jefe de producción | Uso día-a-día del gemelo: login, dashboard, recetas, lotes, alarmas, OEE, reportes. |
| **03** | `manual_gemelo_virtual.md` | Operario avanzado · Ingeniero de procesos · Integrador | Qué es un Gemelo Digital, los 4 modos (simulator / shadow / twin / replay) y **cómo correrlo en paralelo con MQTT / Modbus / OPC UA** (PLC real o Node-RED). |
| **04** | `manual_machine_learning.md` | Ingeniero de procesos · Supervisor · Data team | Cómo funciona la IA integrada: Gemini 3 Flash (chat + diagnóstico), detección de anomalías por reglas + LLM, forecast por mínimos cuadrados, optimización de procesos y *what-if* scenarios. |
| **05** | `manual_tecnico.md` | Desarrollador · DevOps · Integrador instrumentación | Arquitectura completa: layout de carpetas, modelo físico, mapeo Modbus/OPC UA, schemas Mongo, JWT, alarmas ISA-18.2, OEE, reportes PDF. |
| **06** | `instructivo_nodered.md` | Integrador · Ingeniero de control | Conectar **Node-RED** y cámaras de maduración remotas vía MQTT al gemelo (modo bidireccional). Flow examples + troubleshooting. |

---

## Rutas de aprendizaje sugeridas

### 🟢 Soy operario nuevo (primer día de turno)
1. Pediles el usuario `operario` al admin.
2. Abrí el gemelo, presioná **Tour** (botón ámbar en el header) — te guía por los componentes principales.
3. Leé `manual_operaciones.md`, capítulos 1 a 5.
4. Hacé un *dry-run* en **modo Simulador** cargando hoja verde desde la tab `Flujo de masa`.

### 🔵 Soy ingeniero de procesos
1. Leé `manual_gemelo_virtual.md` para entender los modos.
2. Leé `manual_machine_learning.md` capítulos 3-5 para *what-if* y optimización.
3. En la tab `Replay & What-if`, capturá un snapshot del baseline y probá variaciones.
4. Pedí a IA (tab `IA · Gemini`) diagnóstico ante una anomalía concreta.

### 🟠 Soy integrador / vengo a conectar un PLC real
1. Leé `01_instructivo_ejecucion.md` y levantá el sistema.
2. Leé `manual_gemelo_virtual.md` capítulos 5-7 (modos `shadow` / `twin`).
3. Si usás Node-RED, leé `instructivo_nodered.md` completo.
4. Mapeos Modbus / OPC UA / tópicos MQTT en `manual_tecnico.md` capítulo 6.

### 🔴 Soy desarrollador / quiero extender el código
1. `manual_tecnico.md` completo.
2. Carpetas clave: `backend/twin/` (lógica), `backend/server.py` (endpoints REST), `frontend/src/components/` (UI), `backend/twin/yerba_simulator.py` (modelo físico puro).

---

## Convenciones

- Las variables que el **operador o el PLC pueden escribir** (manipuladas) están listadas en cada manual con prefijo `MV:`.
- Los **setpoints** (SP) son objetivos del operador — el sistema sólo los persigue si está activado el PID interno o un controlador externo escribe la manipulada correspondiente.
- Las **lecturas de sensores** se calculan a partir del estado físico del simulador y se exponen en tres protocolos a la vez: Modbus TCP (`:5020`), OPC UA (`:4840`) y MQTT (`yerba/...`).
- Todos los timestamps son UTC ISO-8601.

---

## ¿Dudas? ¿Falta algo?

- Documentación dentro de la app: botón **Manual** en el header (icono libro ámbar).
- Tour interactivo: botón **Tour** (icono birrete).
- Para soporte técnico: revisar `manual_tecnico.md` capítulo 14 (Troubleshooting).
