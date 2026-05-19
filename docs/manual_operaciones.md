# Manual de Operaciones — Gemelo Digital Yerbatera

**Versión:** v2.3 (Fase 3 — Operaciones)
**Idioma:** Español
**Destinatario:** Operario de planta, supervisor de turno, jefe de producción.

---

## 1. Introducción

Este sistema es un **gemelo digital** de una planta de procesamiento de yerba mate. Reproduce en tiempo real el flujo de masa y energía a través de las etapas industriales:

```
RECEPCIÓN ──► ZAPECADO ──► SECADO ──► CANCHADO ──► CÁMARAS DE REPOSO ──► MOLIENDA/EMPAQUE
```

Permite operar en tres modos:

| Modo | Para qué sirve | Quién lo usa |
|------|----------------|--------------|
| **Simulador** (verde) | Entrenamiento, pruebas, "qué pasa si". La planta no se ve afectada. | Operario en formación, ingeniero de procesos |
| **Sombra** (azul) | El sistema lee el PLC real y compara contra el modelo matemático. Detecta drift y miscalibraciones. | Equipo de mantenimiento e instrumentación |
| **Gemelo** (ámbar) | El PLC real alimenta el modelo. El simulador se pausa. Reportes y OEE reflejan planta real. | Supervisor de producción en planta operativa |
| **Replay** (violeta) | Reproduce un CSV histórico al ritmo que elijas. Útil para certificar operarios con eventos reales pasados. | Capacitación / RRHH industrial |

---

## 2. Acceso al sistema

### 2.1 Login

Abrí el navegador (Chrome / Firefox / Edge actualizado) en la URL provista por TI.

**Usuarios por defecto** (cambiar contraseña en el primer ingreso):

| Usuario  | Contraseña | Rol       | Permisos |
|----------|-----------|-----------|----------|
| `admin`  | `admin`   | admin     | Configuración total, modo, recetas, precios, alarmas, mantenimiento, cámaras count, what-if |
| `operario` | `operario` | operator | Dashboard, lotes, ACK alarmas, lectura OEE/energía, reportes, what-if (solo lectura) |

> **Importante**: cambiá la contraseña en el primer ingreso desde **Perfil → Cambiar contraseña**. Los datos por defecto se quitaron de la pantalla de login para evitar exposición innecesaria.

### 2.2 Recuperación de contraseña

En la pantalla de login → "¿Olvidaste la contraseña?" → ingresá usuario + **código maestro** (lo guarda el administrador en `backend/.env` como `ADMIN_RECOVERY_CODE`) + nueva contraseña.

---

## 3. Pantallas principales

### 3.1 Dashboard

Vista resumen con:
- **Tarjetas por etapa** (Zapecado, Secado, Canchado, Cámaras 0-3): temperatura, humedad, alimentación.
- **Gráficos en tiempo real** (Recharts): últimos 600 puntos refrescados a 1 Hz vía WebSocket.
- **Selector de modo** (header): permite cambiar simulador / sombra / gemelo (solo admin).
- **Badge global de alarmas activas** en el header — clic para saltar a la tab Operaciones → Alarmas.

### 3.2 Mímicos (P&ID / SVG)

Vista animada del flujo de masa. Cada etapa muestra:
- Estado de alimentación (ON/OFF en color)
- Temperatura/humedad medidas
- Setpoints aplicados
- Animación de partículas representando el flujo de yerba

Alternar entre SVG animado y P&ID estático con el botón del header.

### 3.3 Recetas

Permite gestionar recetas de proceso. Cada receta define:
- Setpoints de temperatura por etapa (Zapecado, Secado, Canchado)
- Humedad objetivo
- Duración por etapa
- Velocidad del molino canchador

**Acciones:**
- Crear receta (admin)
- Aplicar receta al simulador / planta (admin u operario)
- Eliminar receta (admin)

### 3.4 Lotes

Cada lote representa una corrida de producción. El sistema graba:
- Receta usada, kg de yerba verde de entrada, kg de canchada de salida (merma calculada)
- Timestamps de inicio/fin y duración por etapa
- Snapshot de variables clave (T, H, kWh, alarmas asociadas)

**Acciones:**
- Iniciar lote nuevo (selecciona receta + kg entrada)
- Cerrar lote (registra kg salida → cálculo de merma)
- Cancelar lote
- Descargar **reporte PDF técnico por lote** desde Operaciones → Reportes

### 3.5 Industria 4.0 (Shadow / drift)

Configura los **clientes** (lecturas entrantes) Modbus, OPC UA y MQTT cuando la planta tiene un PLC real:
- Habilitar/deshabilitar por protocolo
- Registrar tags y mapeo a variables internas
- Ver lecturas crudas y drift vs simulador (en modo sombra)
- Aplicar **calibración por CSV**: subir un archivo con (timestamp, valor_real) → el sistema calcula offset/gain y los inyecta como factores de corrección

### 3.6 Operaciones (Alarmas / OEE / Mantenimiento / Energía / Reportes)

Pestaña central de gestión industrial. Detalle en sección 5.

### 3.7 Configuración

Disponible solo para admin. Permite ajustar:
- Servidores expuestos (Modbus TCP `:5020`, OPC UA `:4840`, MQTT)
- Ubicación geográfica para clima (Open-Meteo, búsqueda por ciudad)
- Aceleración de la simulación (1× = tiempo real, 60× = 1 min real por segundo)
- Persistencia automática (cada N segundos a CSV/Excel)
- Histórico descargable (CSV / XLSX por día)

### 3.7.5 Flujo de masa (proceso real con trazabilidad)

Pestaña **"Flujo de masa"** — modela el flujo de hoja de yerba a través de las etapas industriales tal como ocurre en planta.

**Proceso completo de elaboración de yerba mate** (referencia normativa: INYM, RES GMC 24/13 Mercosur):

```
COSECHA ──► RECEPCIÓN / PESAJE ──► ZAPECADO ──► SECADO ──► CANCHADO ──► ESTACIONAMIENTO ──► MOLIENDA FINA ──► EMPAQUE
              50-55% hum             3-5 s          3-8 h     1-3 cm        6-24 meses          separa hojas        500g-1kg
                                     300-550°C       80-120°C  molienda      o acelerada         de palitos          mezclas
                                     H_out 22-30%   H_out 4-7% gruesa        con vapor 30-90d
```

El gemelo digital opera y controla en detalle las **5 etapas centrales**: Recepción → Zapecado → Secado → Canchado → Estacionamiento (cámaras de maduración). La Molienda Fina y el Empaque quedan fuera del scope industrial actual (suelen ser plantas distintas o líneas separadas).

**¿Cómo funciona la pestaña?**

1. **Cargar hoja verde**: ingresá kg que llegaron al patio, opcionalmente la T y H de la hoja (default: T ambiente, H 55%).
2. **Pipeline visual**: ves las 5 etapas en horizontal, con `kg actual` en cada una, `acumulado in/out`, **merma acumulada en kg y %**, y la T y H de entrada (heredadas de la etapa anterior).
3. **Botón flecha →** entre etapa N y N+1: transfiere todo lo que hay en la etapa actual a la siguiente, aplicando la merma típica:
   - Recepción → Zapecado: **0%** (sólo pesaje)
   - Zapecado → Secado: **35%** (evaporación de la hoja: 55% hum → 25% hum)
   - Secado → Canchado: **22%** (segunda evaporación: 25% → 4-7% hum)
   - Canchado → Estacionamiento: **4%** (polvo y partículas finas)
   - Estacionamiento → siguiente: **0.5%** (respiración mínima)
4. **T y H heredadas**: la T y H de salida de cada etapa (medidas por los sensores reales) pasan como T_in y H_in de la siguiente. Por ejemplo, si el zapecado opera a 350°C y deja la hoja con 25% de humedad, esos valores aparecen como condición de entrada del secado.
5. **Top-up**: podés agregar más yerba verde a Recepción durante el día — se promedia ponderadamente con la masa existente.
6. **Distribución automática**: al transferir al Estacionamiento, los kg se reparten en la cámara con menor carga actual (load balancing).
7. **Log de eventos**: las últimas 50 cargas y transferencias quedan registradas con timestamp, usuario, kg, merma, T_out y H_out.

**Merma editable**: el admin puede ajustar el % de merma por etapa según la realidad de la planta (algunas yerbas pierden más en zapecado, otras menos).

### 3.7.6 Puntos de medición (sensores reales en planta)

| Etapa | Sensor | Tecnología | Ubicación física | Rango típico |
|-------|--------|------------|------------------|--------------|
| **Zapecado** | T entrada | Termocupla tipo K | Entrada del cilindro rotativo (zona de llama directa) | 300-550 °C |
| **Zapecado** | T salida hoja | Termocupla tipo K | Salida del tambor zapecador | 110-130 °C |
| **Zapecado** | H salida | Sensor capacitivo o NIR | Banda de salida del zapecado | 22-30 % |
| **Zapecado** | Vibración | Acelerómetro 3 ejes | Eje del tambor | mantenimiento |
| **Secado** | T aire entrada | PT100 o termocupla K | Cámara de combustión del secadero | 80-120 °C |
| **Secado** | T zona | PT100 | Cintas/cilindro del secadero (zonas múltiples) | 70-110 °C |
| **Secado** | H final | Higrómetro NIR infrarrojo | Salida del secadero | 4-7 % |
| **Secado** | H aire | Higrómetro bulbo húmedo | Aire de extracción | — |
| **Canchado** | T rodamientos | PT100 | Carcasa del molino canchador | <70 °C (mant.) |
| **Canchado** | Vibración | Acelerómetro 3 ejes | Bancada del molino | mantenimiento |
| **Canchado** | Velocidad rotor | Encoder | Eje del molino | rpm |
| **Estacionamiento** | T pared | PT100 | Pared de la cámara | 25-45 °C |
| **Estacionamiento** | T centro pila | PT100 | Centro de la pila de yerba | 25-45 °C |
| **Estacionamiento** | H relativa | Sensor capacitivo | Cámara | 40-90 % |
| **Estacionamiento** | CO₂ | Sensor NDIR | Cámara | 500-6000 ppm |
| **Estacionamiento** | T línea vapor | Termoresistencia | Línea de aprovisionamiento (si hay inyección) | 100-180 °C |
| **Estacionamiento** | Caudal vapor | Caudalímetro vortex o másico | Cabezal de cámara | 0-200 kg/h |

> Referencias: INYM (Instituto Nacional de la Yerba Mate), normativa Mercosur RTM RES GMC 24/13, literatura técnica de Andina S.A., CARP S.A. y plantas misioneras. La variante exacta depende de antigüedad del equipamiento.

### 3.8 Replay & What-if (Fase 4)

Pestaña central de **entrenamiento** y **simulación paralela**.

**Replay histórico**:
- Cargá un CSV diario (`yerba_history_YYYY-MM-DD.csv`) y reproducí lo ocurrido.
- Velocidad ajustable entre **0.25× y 120×**.
- Controles: Play, Pausa, Detener, Timeline (clic para saltar a una posición), velocidad en vivo.
- Mientras está activo, el modo del header cambia a "Replay" (violeta).
- Útil para: certificar operarios con eventos reales pasados, hacer post-mortems de turnos problemáticos, revisar un episodio de alarma.

**What-if (escenarios paralelos)**:
- Hasta **3 escenarios** corriendo en paralelo al baseline.
- Cada escenario tiene un nombre y **overrides** en formato JSON. Ejemplos típicos:
  ```json
  { "secado": { "temperatura_setpoint": 105 }, "throughput_kgh": 600 }
  { "zapecado": { "velocidad_chip": 25 } }
  ```
- Tabla comparativa en vivo: OEE, costo/kg, kWh acumulado, chips acumulados, T zapecado, T secado, HR final, producción.
- **Verde** = mejor que baseline; **rojo** = peor. La interpretación depende del KPI (más OEE/producción es mejor; menos costo/kWh/chips/HR final es mejor).

**Exposición a PLC / SCADA** — cada escenario es visible en tiempo real para tu PLC o SCADA:
- **Modbus TCP**: unit IDs **20** (scenario1), **21** (scenario2), **22** (scenario3). Registros holding (HR) 0-7:
  - HR[0] = OEE × 10 (entero 0-1000)
  - HR[1] = Costo/kg × 10 (ARS)
  - HR[2] = kWh × 10
  - HR[3] = Chips kg × 10
  - HR[4] = T zapecado × 10 (°C)
  - HR[5] = T secado × 10 (°C)
  - HR[6] = HR final × 10 (%)
  - HR[7] = Producción kg (entero)
- **OPC UA**: nodos `/Plant/WhatIf/scenario1/OEE`, `.../CostoPorKg`, `.../kWhAcum`, `.../ChipsKgAcum`, `.../TempZapecado`, `.../TempSecado`, `.../HumFinal`, `.../ProduccionKg`.
- **MQTT**: topics `yerba/whatif/scenario1/OEE`, `yerba/whatif/scenario1/CostoPorKg`, etc.

Esto permite que el SCADA muestre, lado a lado, el KPI real del baseline y el predictivo del escenario, sin tocar la lógica del PLC.

### 3.9 Cámaras de maduración

Cantidad de cámaras **configurable de 1 a 12** desde la pestaña Cámaras (botones +/− en el encabezado, solo admin).

Cada cámara tiene dos sistemas de control independientes:
- **Ventilador**: ON/OFF. Cuando está ON, la cámara busca su setpoint clásico (T objetivo, HR objetivo). Cuando está OFF, se mezcla parcialmente con el ambiente.
- **Inyección de vapor**: ON/OFF + caudal en kg/h (0-200) + setpoint propio de temperatura y humedad. Cuando el vapor está activo, fuerza a la cámara hacia esos setpoints con una constante de tiempo mucho más corta (control rápido). El acumulado de kg de vapor inyectado queda registrado para costos.

> El consumo de vapor permite simular maduración real con inyección, no solo intercambio térmico pasivo. Ideal para plantas que usan caldera + serpentín en cada cámara.

---

## 4. Flujo operativo del día

### 4.1 Arranque de turno

1. Login con tu usuario.
2. Revisar **badge de alarmas** en header. Si hay alarmas urgentes → ir a Operaciones → Alarmas → ACK las que ya fueron atendidas; abrir orden de trabajo para las pendientes.
3. Verificar en Dashboard que las 3 etapas estén en setpoint.
4. Revisar **OEE últimas 24 h** → si está por debajo del 60%, investigar qué turno bajó la disponibilidad/calidad.

### 4.2 Inicio de lote

1. Ir a **Lotes** → "Nuevo lote".
2. Elegir **Receta** (la que coincida con el tipo de yerba a procesar).
3. Cargar **kg verde de entrada** estimados.
4. Confirmar. El sistema:
   - Aplica setpoints de la receta a las 3 etapas.
   - Registra timestamp de inicio.
   - Comienza a acumular kWh y kg de chips consumidos.

### 4.3 Durante el lote

- Monitorear Dashboard y Mímicos.
- Atender alarmas inmediatamente con ACK + acción correctiva.
- Si una variable se aleja del setpoint sin alarma, podés **ajustar en vivo** desde la pantalla de la etapa correspondiente (Zapecado / Secado / Canchado / Cámaras).

### 4.4 Cierre de lote

1. Pesar kg de canchado obtenido.
2. Ir a **Lotes** → fila del lote activo → "Cerrar lote".
3. Cargar kg de salida. El sistema calcula:
   - **Merma** = kg_entrada − kg_salida
   - Actualiza producción acumulada y calidad para OEE.
4. Descargar PDF del lote desde Operaciones → Reportes (informe técnico).

### 4.5 Cierre de turno

1. Pasar alarmas pendientes al operario entrante (las dejadas en `unacked_active` son críticas).
2. Anotar lotes abiertos.
3. (Opcional) Descargar **reporte mensual** acumulado desde Operaciones → Reportes para el archivo del turno.

---

## 5. Operaciones — pestaña central

### 5.1 Alarmas (ISA-18.2)

Cada alarma tiene **prioridad**, **tag**, **operador de comparación** y **umbral**:
- **Urgente** (rojo): seguridad de personas o riesgo de pérdida total de lote.
- **Alta** (ámbar): probable pérdida de calidad si no se actúa en pocos minutos.
- **Media** (amarillo): desviación que merece registro y eventual ACK.
- **Baja** (gris): informativa.

**Estados ISA-18.2:**
- `unacked_active`: alarma activa, no reconocida → **ACK** la silencia.
- `acked_active`: condición sigue presente, ya fue reconocida.
- `unacked_rtn`: la condición volvió a normal (Return To Normal) pero falta reconocer → ACK la elimina.
- `normal`: histórico.

**Reglas default** (configurables por admin):
1. Temperatura zapecado > 380 °C → URGENTE (riesgo de quemar yerba).
2. Temperatura secado < 70 °C → ALTA (humedad final fuera de spec).
3. Humedad final > 8% → ALTA (rechazo de empaque).
4. OEE < 50% (15 min) → MEDIA.
5. Ventilador cámara cualquiera apagado > 30 min → MEDIA.
6. Drift sim vs PLC > 10% → MEDIA (mantenimiento e instrumentación).
7. Chips por kg producido > umbral → BAJA (eficiencia energética).

Admin puede **agregar/editar/borrar** reglas custom desde la subpestaña.

### 5.2 OEE (Overall Equipment Effectiveness)

```
OEE = Disponibilidad × Rendimiento × Calidad
```

- **Disponibilidad** = horas operativas / horas planificadas (cuántas horas el secador estuvo encendido vs cuántas se planificó).
- **Rendimiento** = producción real / producción nominal (cuántos kg se hicieron vs cuántos podrían haberse hecho a throughput nominal).
- **Calidad** = kg buenos (canchado) / kg totales (entrada).

**Horas planificadas** = `turnos_por_día × horas_por_turno` (editable en sección Energía).

Benchmarks:
- **85%+ Clase mundial**.
- **60-85% Promedio industrial**.
- **<60% Oportunidad de mejora**.

### 5.3 Mantenimiento predictivo

Lleva **horas de marcha acumuladas** por componente y compara contra umbrales editables:

| Componente | Lubricación | Rodamientos | Overhaul |
|------------|------------:|----------:|---------:|
| Tambor zapecado | 500 h | 2000 h | 4000 h |
| Secador | 500 h | 2000 h | 4000 h |
| Molino canchado | 400 h | 1500 h | 3000 h |
| Ventiladores cámara (0-3) | 800 h | 4000 h | 8000 h |

Estados:
- `ok`: <80% del umbral
- `warning`: 80-100% → planificar tarea
- `due`: >100% → ya vencida, registrar urgente

**ACK de mantenimiento** registra: usuario, timestamp, horas en el momento del ACK. Reinicia el contador para esa acción/componente.

**Editar umbrales** (admin): subpestaña Mantenimiento → "Editar". Permite tunear según experiencia local.

### 5.4 Energía y costos

Calcula en tiempo real:
- **kWh totales** y por componente
- **kg de chips de madera** consumidos (combustible para zapecado). Estimación basada en delta de temperatura y poder calorífico de los chips.
- **Costo total** = kWh × precio_kWh + kg_chips × precio_chips
- **Costo por kg producido** = costo total / kg canchada
- **Ingresos** = kg producidos × precio venta yerba
- **Margen por kg** = precio venta − costo por kg

**Editables (admin):**
- Precio kWh industrial (ARS)
- Precio kg chips de madera (ARS)
- Precio kg yerba venta (ARS)
- **Poder calorífico de los chips (MJ/kg)** — referencia 17 MJ/kg (madera seca). Si la planta usa chips más húmedos, bajar a 14-15; muy secos, subir a 18-19. El sistema escala automáticamente el consumo de chips inversamente al PCI.
- Cantidad de turnos por día (1-4)
- Horas por turno (1-24 h)

### 5.5 Reportes PDF

Generador integrado con ReportLab:

**Reporte mensual** (ejecutivo):
- OEE + sus tres componentes
- Lotes producidos del período
- Top alarmas y su frecuencia
- Costo energético total y por kg
- Estado de mantenimiento
- kWh y chips totales

**Reporte por lote** (técnico):
- Receta aplicada, kg in/out, merma
- Curvas de T y H por etapa
- Alarmas disparadas durante el lote
- Tiempo total y por etapa

Descarga automática (PDF en `backend/data/reports/`).

---

## 6. Buenas prácticas

1. **ACK responsable**: silenciar alarmas no soluciona el problema. ACK = "vi la alarma, voy a actuar". Después tomar acción.
2. **Lotes con kg reales**: si el operario carga estimados, el OEE de calidad será inexacto.
3. **Pesar bien los chips antes de cargar al silo** para que el costo energético cierre con la realidad.
4. **Revisar drift en modo sombra una vez por semana** — si supera 10% en alguna variable, calibrar el instrumento o aplicar CSV de calibración.
5. **Cambiar contraseña** al ingresar por primera vez. Avisar al admin para que cree usuarios nominales (un operario por persona).
6. **Reportes mensuales archivados**: descargar el último día hábil y guardarlo. Sirve como evidencia para auditoría SGC.

---

## 7. Resolución de problemas habituales

| Problema | Posible causa | Acción |
|----------|---------------|--------|
| Dashboard no actualiza | WebSocket caído | Refrescar página. Si persiste, avisar a TI. |
| Modo sombra muestra drift alto en una sola variable | Sensor descalibrado o tag mal mapeado | Industria 4.0 → revisar mapping; aplicar calibración CSV. |
| Alarma se dispara y limpia constantemente | Umbral muy ajustado o variable ruidosa | Admin → Alarmas → Reglas → ajustar umbral o agregar dead-band. |
| OEE muy bajo | Disponibilidad baja → equipo apagado mucho tiempo; Rendimiento bajo → throughput; Calidad baja → merma. | Mirar los 3 componentes individualmente para diagnosticar. |
| Costo por kg explota | Precio chips o kWh actualizado a la alza, o consumo real de chips desproporcionado | Revisar precios (Operaciones → Energía → Precios) y verificar PCI editable. |
| PDF mensual sale vacío | Sin lotes en el período | Iniciar al menos un lote y cerrarlo antes de generar el reporte. |

---

## 8. Glosario

- **OEE**: Overall Equipment Effectiveness — métrica estándar de manufactura.
- **ISA-18.2**: Norma de manejo de alarmas en plantas industriales.
- **PCI**: Poder Calorífico Inferior (MJ/kg).
- **Drift**: diferencia entre el valor simulado matemáticamente y el valor real medido por sensor.
- **ACK** (Acknowledge): reconocimiento de una alarma por parte del operario.
- **Setpoint**: valor objetivo que el control intenta mantener.
- **Merma**: pérdida de masa entre entrada y salida de un lote.
- **Throughput**: producción nominal por hora (kg/h).

---

## 9. Soporte

- Soporte técnico de planta: TI interno.
- Recuperación de admin: usar `ADMIN_RECOVERY_CODE` configurado en `backend/.env`.
- Bug en el sistema: capturar pantalla + descargar `backend/data/yerba_history_YYYY-MM-DD.csv` del día y enviar a desarrollo.
