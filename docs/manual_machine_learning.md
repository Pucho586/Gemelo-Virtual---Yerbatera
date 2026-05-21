# Manual de Machine Learning · IA integrada y optimización de procesos

> **Audiencia**: Ingeniero de procesos, supervisor, data team, integrador.
> **Versión**: v2.4 (mayo 2026).
> **Tecnologías**: Gemini 3 Flash (LLM) · Mínimos cuadrados · Reglas determinísticas · What-if simulations.

---

## Tabla de contenidos

1. [¿Por qué hay ML en un gemelo de yerba mate?](#1-por-qué-hay-ml-en-un-gemelo-de-yerba-mate)
2. [Arquitectura general de la inteligencia](#2-arquitectura-general-de-la-inteligencia)
3. [Capa 1 — Detección de anomalías por reglas](#3-capa-1--detección-de-anomalías-por-reglas)
4. [Capa 2 — Diagnóstico con LLM (Gemini 3 Flash)](#4-capa-2--diagnóstico-con-llm-gemini-3-flash)
5. [Capa 3 — Forecast estadístico (mínimos cuadrados)](#5-capa-3--forecast-estadístico-mínimos-cuadrados)
6. [Capa 4 — Optimización por simulaciones what-if](#6-capa-4--optimización-por-simulaciones-what-if)
7. [Chat con la IA · uso desde la UI](#7-chat-con-la-ia--uso-desde-la-ui)
8. [Cómo optimizamos un proceso en la práctica (ejemplo paso a paso)](#8-cómo-optimizamos-un-proceso-en-la-práctica-ejemplo-paso-a-paso)
9. [Privacidad, costos y límites](#9-privacidad-costos-y-límites)
10. [Roadmap de ML](#10-roadmap-de-ml)

---

## 1. ¿Por qué hay ML en un gemelo de yerba mate?

Porque el proceso tiene **3 problemas característicos** que las reglas tradicionales del SCADA no resuelven solas:

1. **Variabilidad estacional/materia prima**: la humedad de la hoja verde varía entre 45-60% según mes, lluvia previa, edad del corte. El SP "óptimo" de aire en secado no es fijo.
2. **Compromisos multi-objetivo**: bajar humedad final cuesta más combustible/aire, pero sobre-secar arruina el sabor. Hay que minimizar costo respetando calidad.
3. **Eventos raros**: ahogamiento del quemador, fugas de vapor, sobrecalentamiento de rodamientos. Difíciles de catalogar a priori.

La IA + simulaciones ayudan en cada uno. **No reemplaza al operador** — le da contexto y simula alternativas.

---

## 2. Arquitectura general de la inteligencia

```
                ┌──────────────────────────────────────────────┐
                │   YerbaProcessSimulator (estado actual)      │
                └──────────────┬───────────────────────────────┘
                               │ snapshot 1Hz
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
   ┌───────────────┐  ┌──────────────┐  ┌───────────────────┐
   │ Capa 1        │  │ Capa 3       │  │ Capa 4            │
   │ Reglas        │  │ Forecast     │  │ What-If           │
   │ determinísticas│  │ lineal       │  │ Simulaciones     │
   │ (Python puro) │  │ (least sq.)  │  │ paralelas        │
   └───────┬───────┘  └──────┬───────┘  └─────────┬─────────┘
           │                 │                    │
           └────────┬────────┘                    │
                    ▼                             │
           ┌────────────────────┐                 │
           │ Capa 2             │                 │
           │ Gemini 3 Flash LLM │  diagnóstico    │
           │ (Emergent LLM Key) │ ◄───────────────┘
           └────────┬───────────┘
                    │ recomendación texto
                    ▼
              [ UI: AIPanel ]
              [ Alarms enriched ]
              [ /api/ai/anomalies ]
```

| Capa | Tecnología | Latencia | Para qué |
|---|---|---|---|
| 1 — Reglas | If/then en Python | <10 ms | Detección rápida y barata. Sin LLM. |
| 2 — LLM | Gemini 3 Flash via Emergent LLM key | 1-3 s | Explicación + acción sugerida en lenguaje natural. |
| 3 — Forecast | Mínimos cuadrados en NumPy puro | <100 ms | Adelantarse 30 pasos: ¿esto sigue subiendo? |
| 4 — What-If | Hasta 3 simulators paralelos | 1-2 s | "¿Qué pasaría si bajo SP a 90°C?" |

---

## 3. Capa 1 — Detección de anomalías por reglas

Implementada en `twin/ai_service.py` función `_detect_static_anomalies()`. Ejemplos:

| Regla | Severity | Acción sugerida |
|---|---|---|
| `zapecado.T > 580°C` | high | "Peligro térmico, abrir damper y reducir chips." |
| `zapecado.T > 540 y estado_alim=true` | medium | "Revisar vel. de chips." |
| `secado.HR > 35 y estado=true` | medium | "Aumentar vel. de aire." |
| `secado.HR < 6` | medium | "Yerba sobre-secada, bajar T o aire." |
| `canchado.particula < 1.0mm` | low | "Bajar rpm del molino." |
| `camara.CO2 > 5500 ppm` | high | "Encender ventilador YA." |
| `\|camara.T − T_obj\| > 4°C` | low | "Cámara desviada." |

> Estas reglas son **rápidas y predecibles** — la base sobre la que el LLM razona después.

Endpoint: `GET /api/ai/anomalies?use_ai=false` — devuelve solo reglas (~10 ms).

---

## 4. Capa 2 — Diagnóstico con LLM (Gemini 3 Flash)

Se invoca con `GET /api/ai/anomalies?use_ai=true`. El backend:

1. Calcula las anomalías de Capa 1.
2. Si hay al menos una, llama a Gemini 3 Flash con el system prompt:

   ```
   Sos un ingeniero experto en procesos industriales de yerba mate.
   Asistís a un operario que monitorea un gemelo digital con etapas:
   Zapecado (~400-600°C), Secado (80-110°C, 30→7% humedad), Canchado
   (molienda gruesa) y 4 Cámaras de maduración (T 30-40°C, HR 70-85%,
   CO2 ~3000 ppm). Respondé en español rioplatense, breve, técnico y
   concreto. Si te pasan datos, usalos; si faltan, pedilos. Usá unidades
   del SI. Cuando sugieras cambios, explicá el porqué.
   ```

3. Mensaje user: anomalías + estado completo del gemelo (JSON).
4. Respuesta del LLM: máx 4 frases, causa probable + acción inmediata.

### Ejemplo de respuesta

```
Causa probable: la velocidad del tambor está en 8 rpm con vel.chip = 60 kg/h
→ ahogamiento parcial, combustión incompleta. Solución inmediata: subir
tambor a 14 rpm y mantener chips. En 90 s deberías ver la temperatura
bajar 30-50 °C.
```

> **Diseño**: el LLM **nunca actúa** automáticamente. Sólo recomienda. El operador o el PLC ejecutan.

---

## 5. Capa 3 — Forecast estadístico (mínimos cuadrados)

Implementación en `ai_service.py` `_linear_forecast()`. Sobre los últimos 60 puntos:

```
y = a + b·x        (slope b, intercept a)
b = Σ(x-x̄)(y-ȳ) / Σ(x-x̄)²
a = ȳ − b·x̄
forecast[i] = a + b·(n+i)
```

Por defecto se predicen 4 series:
- `zapecado_temp`
- `secado_temp`
- `secado_hum`
- `cam1_co2`

Endpoint: `GET /api/ai/forecast?horizon=30` — devuelve 30 pasos futuros (~30 s con dt=1 s, ~30 min con aceleración ×60).

### ¿Por qué lineal y no LSTM?

- Costo cero (CPU local).
- Sin warm-up.
- Suficiente para horizontes cortos (1-5 min) que es lo que el operador necesita.
- Cuando se acumule suficiente data, el roadmap contempla TimeGPT / Prophet para horizontes largos (ver capítulo [10](#10-roadmap-de-ml)).

---

## 6. Capa 4 — Optimización por simulaciones what-if

### Concepto

What-if = correr el simulador **en paralelo** con valores distintos al baseline, sin afectar el proceso real.

- Servicio: `WhatIfService` (`backend/twin/whatif_service.py`).
- Capacidad: hasta **3 escenarios paralelos** simultáneos.
- Cada escenario corre en su propio `YerbaProcessSimulator` y publica en Modbus units 20-22, OPC UA y MQTT con prefijo `whatif/{id}/`.

### Casos de uso típicos

| Pregunta del operario | Escenario what-if |
|---|---|
| ¿Si bajo SP a 90°C, llego al 7% HR en el mismo tiempo? | `{secado: {temperatura_obj: 90, velocidad_aire: 3.5}}` |
| ¿Si aumento throughput a 1000 kg/h, qué pasa con CO2? | `{simulacion: {throughput_kgh: 1000}}` |
| ¿Bajo costo si dejo el calefactor en 60% en vez de 80%? | `{secado: {posicion_calefactor: 60}}` |

### Flujo desde la UI

1. Tab **Replay & What-if**.
2. Botón **Capturar baseline** → snapshot del estado actual.
3. Editar overrides en el JSON del escenario.
4. **Crear**.
5. Comparar gráficos: baseline vs whatif₁ vs whatif₂.

Endpoints:
- `POST /api/whatif` — crear escenario.
- `POST /api/whatif/snapshot` — clonar baseline.
- `GET /api/whatif` — lista.
- `POST /api/whatif/{id}` — modificar overrides.

---

## 7. Chat con la IA · uso desde la UI

### Acceso
Tab **IA · Gemini** (icono ✨).

### Cómo funciona
- Cada operario tiene una `session_id` propia (guardada en localStorage).
- Toda la conversación se mantiene en memoria del backend (no se persiste en Mongo por privacidad).
- Cada mensaje del operario se enriquece con el **estado actual del gemelo en JSON** antes de mandarlo a Gemini.

### Buenas preguntas

> "Estoy viendo que el zapecado oscila ±20°C alrededor del SP. ¿Qué probarías?"

> "¿Cómo interpreto que la cámara 2 tiene HR 92% pero la cámara 3 tiene 68% con el mismo SP?"

> "Tengo 30 minutos antes de cambio de turno. ¿Está la receta `secado_optimo_verano` con los valores correctos para hoy que llovió ayer?"

> "Aumentá la velocidad del aire de secado 0.5 m/s." — la IA te explica el efecto pero **no aplica el cambio** (decisión humana).

### Reset
- Botón **Reset sesión** → borra historial. Útil después de turno o para arrancar limpio.

---

## 8. Cómo optimizamos un proceso en la práctica (ejemplo paso a paso)

**Problema**: el secado consume 15 kWh por kg producido. Queremos bajar a 12 sin perder calidad (HR final 6.5-7.5%).

### Paso 1 — Identificar baseline
- Tab `Operaciones → Energía`: vemos `cost_per_kg_ars` y `kwh_by_component.secado`.
- Estado actual: `pos_cal=80%`, `vel_aire=3.0 m/s`, `T_obj=105°C`, throughput=800 kg/h, HR_final=7.1%.

### Paso 2 — Hipótesis con IA (Gemini)
Le preguntamos en chat:
> "Quiero bajar el consumo de secado de 15 a 12 kWh/kg manteniendo HR final 6.5-7.5%. ¿Qué tres palancas probarías?"

Respuesta esperada:
> 1. Bajar T_obj de 105°C a 95°C — menos pérdida térmica por paredes.
> 2. Subir vel_aire de 3.0 a 3.5 m/s — más arrastre de HR, compensa menos T.
> 3. Recortar throughput a 700 kg/h si la planta lo permite — más tiempo de residencia.

### Paso 3 — Validar con What-If
Creamos 3 escenarios paralelos:
- A: `T_obj=95, vel_aire=3.5`
- B: `T_obj=100, vel_aire=3.2`
- C: `throughput=700`

Esperamos 5-10 min (×60 aceleración) y miramos:
- HR final estabilizada en cada uno.
- kWh integrado.

### Paso 4 — Decidir y aplicar
El escenario A da HR=6.8% (en spec) y kWh/kg=12.1 → ganador.

### Paso 5 — Aplicar en planta
- Receta nueva: `secado_optimo_v3`.
- Aplicar al baseline (`POST /api/recipes/secado_optimo_v3/apply`).
- Monitorear primeras 2 horas: si todo OK, dejar; si algo se va, rollback con receta anterior.

### Paso 6 — Documentar
- Reporte mensual PDF (`GET /api/reports/monthly`) registra el ahorro.

---

## 9. Privacidad, costos y límites

### Privacidad
- El chat va a Gemini 3 Flash vía la **Emergent LLM Key** (no a OpenAI ni a Google directamente).
- **No mandamos datos identificables** (sin nombres de operarios, sin datos personales). Sólo telemetría de proceso.
- Conversaciones se guardan **sólo en memoria del backend**. Reinicio = se borran.

### Costos
- Un chat ~2-3 segundos de inferencia, costo despreciable con uso normal (<100 mensajes/turno).
- Si te pasás del cupo del key, el backend cae a las Capas 1 y 3 (reglas + forecast) sin perder funcionalidad crítica.

### Límites del modelo
- **Gemini no ve la planta real** — sólo ve lo que el simulador le pasa.
- **No actúa automáticamente** — sólo recomienda.
- **Conocimiento estático** hasta su cutoff (~2025). Mejor para razonamiento que para datos de mercado.

---

## 10. Roadmap de ML

| # | Feature | Prioridad | Notas |
|---|---|---|---|
| 1 | Forecast con Prophet/TimeGPT para horizontes >1h | P2 | Requiere datasets de >1 mes de operación. |
| 2 | Detector de anomalías por Isolation Forest sobre histórico | P2 | Para captar patrones no cubiertos por reglas. |
| 3 | Aprendizaje del PID óptimo por bayesian optimization (Optuna) | P2 | Trade-off offline. |
| 4 | Voice assistant (Whisper + TTS) para operarios con manos ocupadas | P3 | Emergent LLM Key soporta Whisper. |
| 5 | Replay con velocidad adaptativa según importancia del evento | P3 | "Saltar" tramos planos automáticamente. |
| 6 | Self-tuning de mermas en `mass_flow` por mínimos cuadrados sobre últimos 30 lotes | P2 | Calibración continua. |

---

> **Pregunta frecuente**: ¿Puedo usar otro modelo distinto a Gemini?
> Sí — la Emergent LLM Key soporta también Claude Sonnet 4.5 y OpenAI GPT-5.2 con el mismo SDK. Cambiá `GEMINI_MODEL` y `PROVIDER` en `ai_service.py`. Para el chat de operario, Gemini Flash es la opción más barata + rápida.
