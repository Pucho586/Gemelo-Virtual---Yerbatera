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

---

## 2.1. Nomenclatura Modbus clásica (Modicon)

En un PLC/SCADA real las direcciones Modbus **no** se escriben como "holding register 5". Se usa la **notación Modicon de 5 dígitos**, donde el primer dígito indica el *tipo* de dato y el resto es el número de referencia **base 1**:

| Rango Modicon | Tipo de dato | Función Modbus | Acceso | Uso en el gemelo |
|---------------|--------------|----------------|--------|------------------|
| `0xxxx` (00001…) | **Coil** (salida discreta) | 01 leer / 05·15 escribir | Lectura **y** escritura | Comandos / fallas (on-off) |
| `1xxxx` (10001…) | Discrete Input (entrada discreta) | 02 leer | Solo lectura | *(no usado)* |
| `3xxxx` (30001…) | Input Register | 04 leer | Solo lectura | *(no usado)* |
| `4xxxx` (40001…) | **Holding Register** | 03 leer / 06·16 escribir | Lectura **y** escritura | PV, MV, SP, parámetros |

> **Cómo se traduce**: el *holding register* interno **HR0** es la referencia **40001**; **HR5** es **40006** (40001 + 5). El *coil* interno **C0** es **00001**. Es decir: **Modicon = 40001 + índice** (registros) o **00001 + índice** (coils).

**Dos aclaraciones importantes de esta implementación:**

1. El gemelo publica **todas las medidas (PV) en holding registers `4xxxx`**, no en input registers `3xxxx`. Esto es a propósito: así el PLC lee todo por función 03 y no hay que mezclar áreas. Si tu SCADA espera las PV en `3xxxx`, mapealas igual a `4xxxx` (son de solo lectura *por convención*: el gemelo las pisa en cada ciclo, no las escribas).
2. Los valores enteros vienen **escalados**: casi todo es **×10** (un decimal), la **partícula del canchado es ×100** (dos decimales), y `CO₂`, `carga` y `throughput` van **sin escala**. Ejemplos: en Zapecado `40001 = 4203` → **420.3 °C**; en Canchado `40002 = 375` → **3.75 mm**. Siempre **dividí por el factor** al leer y **multiplicá** al escribir.

### Selección de equipo: `unit id` (slave id)

Cada etapa/cámara es una **unidad Modbus distinta** (campo *unit id* / *slave id* del frame). Con **una sola IP:puerto** (`:5020`) accedés a todas cambiando el unit id:

| Unit id | Equipo |
|---------|--------|
| `0` | Zapecado (horno) |
| `1` | Secado |
| `2` | Canchado (molino) |
| `3` … `14` | Cámaras de maduración 1 … 12 |
| `20` `21` `22` | Escenarios *what-if* 1 · 2 · 3 |
| `100` | Globales (aceleración, throughput) |

---

## 2.2. Mapa de direcciones por equipo

Referencias en **Modicon** (base 1). `R` = solo lectura (PV/estado), `R/W` = el PLC puede escribir (MV/SP/comando). El resto de los holding registers de cada unidad exponen el estado del PID interno (kp, ki, kd, salida) como solo lectura.

### Unit id 0 — Zapecado

| Referencia | Variable | Escala | Acceso | Tipo |
|-----------|----------|--------|--------|------|
| `40001` | Temperatura del horno | ×10 | R | PV |
| `40002` | Velocidad de tambor | ×1 | R/W | MV |
| `40003` | Velocidad de chips (alimentación) | ×1 | R/W | MV |
| `40006` | Temperatura objetivo (0 = auto) | ×10 | R/W | SP |
| `40005` | Setpoint efectivo | ×10 | R | — |
| `40013` | Velocidad de chips **real** | ×10 | R | MV real |
| `40014` | Velocidad de tambor **real** | ×10 | R | MV real |
| `00001` | Falla quemador | — | R/W | Comando |
| `00002` | Falla motor de tambor | — | R/W | Comando |

### Unit id 1 — Secado

| Referencia | Variable | Escala | Acceso | Tipo |
|-----------|----------|--------|--------|------|
| `40001` | Temperatura | ×10 | R | PV |
| `40002` | Humedad relativa | ×10 | R | PV |
| `40003` | Velocidad de aire | ×10 | R/W | MV |
| `40008` | Posición del calefactor | ×10 | R/W | MV |
| `40005` | Temperatura objetivo | ×10 | R/W | SP |
| `40006` | Humedad objetivo | ×10 | R/W | SP |
| `00001` | Falla ventilador | — | R/W | Comando |
| `00002` | Falla serpentín / calefactor | — | R/W | Comando |

### Unit id 2 — Canchado

| Referencia | Variable | Escala | Acceso | Tipo |
|-----------|----------|--------|--------|------|
| `40001` | Velocidad del molino | ×10 | R/W | MV |
| `40002` | Tamaño de partícula | **×100** | R | PV |
| `40004` | Tamaño de partícula objetivo (0 = auto) | **×100** | R/W | SP |
| `40005` | Setpoint de partícula efectivo | **×100** | R | — |
| `00001` | Falla motor del molino | — | R/W | Comando |
| `00002` | Rodamiento caliente | — | R/W | Comando |

### Unit id 3…14 — Cámaras de maduración

| Referencia | Variable | Escala | Acceso | Tipo |
|-----------|----------|--------|--------|------|
| `40001` | Temperatura | ×10 | R | PV |
| `40002` | Humedad relativa | ×10 | R | PV |
| `40003` | CO₂ | ×1 | R | PV |
| `40004` | Temperatura objetivo | ×10 | R/W | SP |
| `40005` | Humedad objetivo | ×10 | R/W | SP |
| `40010` | Vapor activo (0/1) | ×1 | R/W | MV |
| `40011` | Caudal de vapor | ×10 | R/W | MV |
| `00001` | Falla ventilador | — | R/W | Comando |
| `00002` | Fuga de vapor | — | R/W | Comando |
| `00003` | Puerta abierta | — | R/W | Comando |

> Cámara *n* → unit id `n + 2` (Cámara 1 = unit 3, Cámara 2 = unit 4, … Cámara 12 = unit 14).

### Unit id 100 — Globales

| Referencia | Variable | Escala | Acceso |
|-----------|----------|--------|--------|
| `40001` | Aceleración de simulación | ×10 | R/W |
| `40002` | Throughput (kg/h) | ×1 | R/W |

> **OPC UA / MQTT**: las mismas variables se exponen como nodos `Objeto.Variable` (OPC UA, con `Writable` en las MV/SP/comando) y como topics `yerba/<etapa>/<variable>` (publicación de PV) / `yerba_in/<etapa>/<variable>` (suscripción a comandos). El direccionamiento vivo y por variable está en la app: **Integración → Protocolos → Variables expuestas**.

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
2. Protocolo Modbus activado. Zapecado es **unit id 0** (ver §2.2):
   - **PV** — Temperatura del horno → **`40001`** (holding register, ×10, solo lectura).
   - **MV** — Velocidad de chips → **`40003`** (holding register, ×1, escribible).
3. En el PLC (unit id 0):
   - `T := leer_HR(40001) / 10.0`   *(divido por la escala ×10)*
   - `error := 450 - T`
   - `chips := PID(error)`  *(tu algoritmo)*
   - `escribir_HR(40003, chips)`
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

## 7. Uso multiusuario: bancos de trabajo y panel del docente

Para que **varios alumnos trabajen a la vez sin pisarse**, el gemelo soporta
**bancos de trabajo**: cada banco es una **planta virtual independiente**, con su
propio simulador y sus propios servidores industriales en **puertos desplazados**.

### 7.1. ¿Cómo se separan los puertos?

| Banco | Modbus TCP | OPC UA | Prefijo MQTT |
|-------|-----------|--------|--------------|
| Principal (default) | `5020` | `4840` | `yerba/…` |
| Banco 1 (offset 1) | `5021` | `4841` | `yerba/b1/…` |
| Banco 2 (offset 2) | `5022` | `4842` | `yerba/b2/…` |
| Banco *n* | `5020 + n` | `4840 + n` | `yerba/b<id>/…` |

- **Modbus / OPC UA**: cada banco escucha en **su propio puerto** de la misma IP del servidor. El PLC/SCADA de cada alumno apunta al puerto de **su** banco (misma dirección `40001/00001` y unit ids que en §2.2 — solo cambia el puerto).
- **MQTT**: un solo broker compartido, separado por **prefijo de topic**. El banco 1 publica en `yerba/b1/zapecado` y escucha comandos en `yerba/b1/cmd/#`.

### 7.2. El alumno elige su banco

En el header de la app hay un **selector de banco** (ícono de monitor 🖥). El alumno
elige el banco que le asignaron y **toda su sesión** (web + WebSocket + REST) opera
sobre ese banco. Su PLC se conecta al puerto Modbus/OPC correspondiente.

### 7.3. Panel del docente

En **Integración → Docente** (requiere rol admin) el docente tiene un panel con
**todos los bancos en vivo**. Por cada banco puede:

- **Monitorear** el proceso en tiempo real (T de zapecado, T/HR de secado, partícula de canchado, modo, control activo, cámaras).
- **Crear / eliminar** bancos y asignarles un alumno.
- **Inyectar fallas** (quemador, ventilador, serpentín, motor, rodamiento, etc.) para que el alumno las diagnostique y resuelva.
- **Congelar / reanudar** la simulación de un banco (pausa la física sin perder el estado).
- **Reiniciar** el banco a su estado inicial.
- **Asignar una consigna** (título + criterio) que el alumno ve como objetivo.

> **Flujo típico de clase**: el docente crea un banco por alumno → le asigna una consigna
> (ej. "llevar el zapecado a 450 °C con un PID en el PLC") → el alumno selecciona su banco,
> programa su PLC contra el puerto Modbus del banco y arma el SCADA → el docente monitorea,
> inyecta una falla sorpresa y observa cómo el alumno la resuelve.

> **Nota técnica**: el banco **Principal** conserva los puertos y la persistencia históricos.
> Los bancos adicionales viven en memoria (no persisten a disco) y se pierden si se reinicia
> el backend; están pensados para la sesión de clase.

---

## 8. Referencias

- `01_instructivo_ejecucion.md` — cómo levantar el sistema.
- `manual_gemelo_virtual.md` — los 4 modos del gemelo (simulator/shadow/twin/replay) y uso en paralelo con MQTT/Modbus/OPC UA.
- `manual_tecnico.md` — arquitectura, mapeos de protocolo, schemas.
- `instructivo_nodered.md` — conectar Node-RED y cámaras remotas por MQTT.
- En la app: **Integración → Protocolos** (direccionamiento por variable) e **Industria 4.0** (fuentes externas / drift).
