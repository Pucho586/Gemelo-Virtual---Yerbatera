# Manual de control PLC ↔ SCADA · Gemelo Digital de Yerba Mate

> **Audiencia**: Alumnos y docentes de automatización / control de procesos.
> **Objetivo**: Controlar el proceso desde un **PLC** y visualizar/operar desde un **SCADA**, usando el gemelo como si fuese la planta real.

---

## 1. Idea general

El gemelo digital **simula la planta con física real** (balances de masa y energía). No es una animación con valores "de mentira": si abrís vapor, la temperatura sube porque el vapor aporta entalpía; si subís los chips, sube la temperatura del zapecado.

Para una práctica de automatización, el gemelo cumple el rol de **proceso físico**:

```
   ┌──────────────┐        escribe MV/SP         ┌──────────────────────┐
   │   Tu PLC     │ ───────────────────────────► │                      │
   │ (programa de │                              │   GEMELO DIGITAL     │
   │  control)    │ ◄─────────────────────────── │  (la "planta")       │
   └──────────────┘        lee PV (medidas)      │  física en tiempo    │
                                                 │  real                │
   ┌──────────────┐        lee PV / MV / SP      │                      │
   │   SCADA      │ ◄─────────────────────────── │  Modbus TCP :5020    │
   │ (visualiza y │ ───────────────────────────► │  OPC UA   :4840      │
   │  opera)      │        escribe (opcional)    │  MQTT     yerba/...   │
   └──────────────┘                              └──────────────────────┘
```

El gemelo expone las variables **por tres protocolos a la vez**: **Modbus TCP**, **OPC UA** y **MQTT**. El PLC y el SCADA se conectan al que prefieras.

---

## 2. Variables de entrada y de salida

Sí: **las variables son de entrada Y de salida**. Es la base de la práctica.

| Tipo | Qué es | Quién la escribe | Ejemplos |
|------|--------|------------------|----------|
| **Salida (PV)** | Variable de proceso / medida del "sensor" | El gemelo (solo lectura para vos) | Temperatura de zapecado, humedad de secado, tamaño de partícula, CO₂ de cámara |
| **Entrada — MV** | Variable manipulada / actuador | **El PLC** (o el operador) | Velocidad de chips, posición del calefactor, velocidad de aire, rpm del molino, caudal de vapor |
| **Entrada — SP** | Setpoint / objetivo | El PLC o el operador | Temperatura objetivo, humedad objetivo, grosor objetivo |
| **Entrada — comando** | Fallas / permisos / válvulas | El PLC o el operador | Falla quemador, alimentación on/off, ventilador on/off |

- En **Modbus**, las **MV/SP/comandos** son *holding registers* y *coils* **escribibles**; las **PV** son registros que el gemelo actualiza para que los leas.
- En **OPC UA**, las **MV/SP/comandos** son nodos con `Writable`; las **PV** son solo-lectura.
- En **MQTT**, el gemelo **publica** las PV en `yerba/...` y se **suscribe** a comandos en `yerba_in/...`.

> **El direccionamiento exacto** (registro Modbus, nodo OPC UA, topic MQTT) de cada variable está en la app: **Integración → Protocolos → Variables expuestas**. Ahí ves, para cada variable, su unit/registro, su nodo `Objeto.Variable` y su topic.

---

## 3. Sistema de control por etapa (¡importante!)

Cada etapa (Zapecado, Secado, Canchado, Cámaras) tiene un **sistema de control seleccionable**, que decide **quién ajusta la variable manipulada** para llegar al setpoint. Lo elegís en la vista de cada etapa, en el panel **"Sistema de control"**, y hay un badge que muestra el modo activo.

| Modo | Quién controla la MV | Cuándo usarlo |
|------|----------------------|---------------|
| **Manual** | El operador la fija a mano | Pruebas manuales, dejar la MV libre |
| **ON/OFF** | Controlador todo-o-nada con histéresis (termostato) | Enseñar control bang-bang |
| **PID** | El PID interno del gemelo persigue el SP | Enseñar sintonía Kp/Ki/Kd |
| **PLC externo** | **Tu programa de PLC** escribe la MV | **La práctica de automatización** |

### ⚠️ Regla de oro para controlar desde el PLC

Para que **tu PLC** controle una etapa, poné esa etapa en modo **PLC externo** (o **Manual**). Si la dejás en **PID** o **ON/OFF**, el controlador interno del gemelo va a **pisar** cada segundo el valor que escribas desde el PLC (van a "pelear" por la MV).

- **PLC externo / Manual** → el gemelo **no toca** la MV; la escribe tu PLC. ✅
- **PID / ON/OFF** → el gemelo ajusta la MV solo. El PLC solo lee. ❌ para control externo.

Además, para que las escrituras externas se apliquen, el **modo del gemelo** (botón "Modo" en el header) debe estar en **Gemelo** (twin) o **Shadow**. En **Simulador** puro el gemelo ignora fuentes externas.

---

## 4. Flujo de trabajo de una práctica (paso a paso)

1. **Levantá el gemelo** (ver `01_instructivo_ejecucion.md`) y entrá como `admin`.
2. En el header, poné el **Modo** en **Gemelo** (twin).
3. En cada etapa que vaya a controlar el PLC, abrí la vista y en **Sistema de control** elegí **PLC externo**.
4. En **Integración → Protocolos**, activá el protocolo que vas a usar (ej. **Modbus TCP**) y anotá el direccionamiento de las variables (registros de las MV que vas a escribir y de las PV que vas a leer).
5. **Programá el PLC**:
   - Leé las **PV** (medidas) de los registros/nodos de salida.
   - Calculá tu lógica de control (tu propio PID, ON/OFF, secuencia, etc.).
   - Escribí las **MV** en los registros/nodos de entrada.
6. **Conectá el SCADA** al mismo servidor (Modbus/OPC UA) y armá las pantallas leyendo las PV (y, si querés, MV/SP).
7. Verificá el lazo cerrado: tu PLC cambia la MV → la física del gemelo responde → la PV cambia → el SCADA lo muestra → tu PLC reacciona.

---

## 5. Ejemplo concreto (Zapecado, control de temperatura)

**Consigna**: mantener el zapecado en 450 °C con un control hecho en el PLC.

1. Zapecado → **Sistema de control: PLC externo**. Modo del gemelo: **Gemelo**.
2. Protocolo Modbus activado. En **Protocolos** anotás (ejemplo — verificá los valores reales en la app):
   - **PV** — `zapecado.temperatura` (registro de lectura).
   - **MV** — `velocidad_chip` (registro de escritura).
3. En el PLC:
   - `T := leer(PV zapecado.temperatura)`
   - `error := 450 - T`
   - `chips := PID(error)`  *(tu algoritmo)*
   - `escribir(MV velocidad_chip, chips)`
4. El gemelo recibe la nueva `velocidad_chip`, calcula el balance térmico y actualiza la temperatura. Tu SCADA grafica `zapecado.temperatura` subiendo hacia 450 °C.

Si en vez de programar el PID en el PLC querés compararlo con el PID interno del gemelo, cambiá el modo a **PID** y sintonizá Kp/Ki/Kd desde la misma pantalla.

---

## 6. Consejos para el aula

- Empezá en **modo Simulador** con **Sistema de control: Manual** para que los alumnos "sientan" la física moviendo las MV con los sliders.
- Pasá a **PID interno** para enseñar sintonía sin PLC.
- Después conectá el **PLC** (modo **PLC externo** + gemelo en **Gemelo**) para la práctica de automatización real.
- Usá el **toggle de Animación** (header) para hacer los mímicos más atractivos en una demo, o apagarlo para ahorrar recursos.
- El botón **Manual** (header) y el **Tour** guían a los alumnos nuevos.

---

## 7. Referencias

- `01_instructivo_ejecucion.md` — cómo levantar el sistema.
- `manual_gemelo_virtual.md` — los 4 modos del gemelo (simulator/shadow/twin/replay) y uso en paralelo con MQTT/Modbus/OPC UA.
- `manual_tecnico.md` — arquitectura, mapeos de protocolo, schemas.
- `instructivo_nodered.md` — conectar Node-RED y cámaras remotas por MQTT.
- En la app: **Integración → Protocolos** (direccionamiento por variable) e **Industria 4.0** (fuentes externas / drift).
