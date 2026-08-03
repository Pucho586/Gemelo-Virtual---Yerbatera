# Ficha del alumno · Práctica PLC ↔ SCADA con el Gemelo Digital

> **Imprimir una por alumno/grupo.** El docente completa el recuadro de abajo antes de repartir.

---

## 📋 Tus datos (completa el docente)

| | |
|---|---|
| **Alumno / grupo** | _______________________________ |
| **Banco asignado** | Banco n.° ______ |
| **IP del servidor** | ______ . ______ . ______ . ______ |
| **Puerto Modbus TCP** | `5020 + n.° de banco` = __________ |
| **Puerto OPC UA** | `4840 + n.° de banco` = __________ |
| **Prefijo MQTT** | `yerba/b______/…` |
| **Consigna** | _______________________________ |

---

## 🚀 Puesta en marcha (5 pasos)

1. **Entrá a la web** del gemelo (te pasa la dirección el docente) con usuario `operario`.
2. En el header, **elegí TU banco** en el selector 🖥. Todo lo que veas y toques es tu planta — no molesta a nadie más.
3. En la etapa que vayas a controlar, **Sistema de control → PLC externo** (si la dejás en PID u ON/OFF, el gemelo te pisa lo que escriba tu PLC).
4. **Conectá tu PLC** a la IP del servidor y **tu puerto Modbus** (el de tu banco, no el 5020 a secas — ese es del banco Principal).
5. **Conectá tu SCADA** al mismo puerto y armá las pantallas leyendo las PV.

---

## 🔢 Direcciones Modbus que vas a usar (notación Modicon)

**Elegí el equipo con el *unit id* (slave id):** `0` Zapecado · `1` Secado · `2` Canchado · `3`–`14` Cámaras 1-12.

| Equipo (unit) | Leés (PV) | Escribís (MV / SP) |
|---|---|---|
| **Zapecado (0)** | `40001` T horno (×10) | `40003` vel. chips (×1) · `40006` T objetivo (×10) |
| **Secado (1)** | `40001` T (×10) · `40002` HR (×10) | `40008` calefactor (×10) · `40003` vel. aire (×10) |
| **Canchado (2)** | `40002` partícula (×100) | `40001` rpm molino (×10) |
| **Cámara n (n+2)** | `40001` T · `40002` HR · `40003` CO₂ | `40010` vapor on/off · `40011` caudal vapor (×10) |

**Escalas**: el valor viaja como entero. `(×10)` = dividí por 10 al leer (4203 → 420.3 °C) y multiplicá por 10 al escribir. Coils `00001/00002/00003` = fallas/comandos.

*Mapa completo: manual 07 (`manual_control_plc_scada.md`), sección 2.2 — o en la app: Integración → Protocolos.*

---

## ✅ Checklist de la práctica

- [ ] Veo mi banco en el selector y las medidas se mueven en la web.
- [ ] Mi PLC **lee** una PV (compará el número con la pantalla del gemelo — ¡ojo con la escala!).
- [ ] La etapa está en **PLC externo** y el modo del gemelo en **Gemelo** (twin).
- [ ] Mi PLC **escribe** una MV y la física responde (subí los chips → mirá la temperatura).
- [ ] Mi SCADA grafica la PV en tiempo real.
- [ ] Lazo cerrado: mi programa lleva la PV al valor de la consigna y la mantiene.
- [ ] Si aparece una **falla** (el docente puede inyectarla 😈): diagnosticá con las PV y resolvela.

---

## 🆘 Si algo no anda

| Síntoma | Causa típica |
|---|---|
| Leo todo 0 | Unit id equivocado, o puerto de otro banco |
| Leo valores ×10 raros | Te olvidaste de dividir por la escala |
| Escribo y no pasa nada | Etapa en PID/ON-OFF (ponela en **PLC externo**) o gemelo en modo Simulador (ponelo en **Gemelo**) |
| Los valores no se mueven | Tu banco está **congelado** — pedile al docente que lo reanude |
| Todos vemos lo mismo | Están todos en el mismo banco — elegí el tuyo en el selector 🖥 |
