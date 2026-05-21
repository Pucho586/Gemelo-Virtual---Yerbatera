# Manual del Gemelo Virtual · Uso en paralelo con MQTT / Modbus / OPC UA

> **Audiencia**: Operario avanzado, ingeniero de procesos, integrador de control.
> **Versión**: v2.4 (mayo 2026) — modo bidireccional verificado.

---

## Tabla de contenidos

1. [¿Qué es un Gemelo Digital y por qué este es distinto?](#1-qué-es-un-gemelo-digital-y-por-qué-este-es-distinto)
2. [Los 4 modos del simulador](#2-los-4-modos-del-simulador)
3. [Filosofía del modelo físico puro (¡importante!)](#3-filosofía-del-modelo-físico-puro-importante)
4. [Cómo cambiar de modo](#4-cómo-cambiar-de-modo)
5. [Uso en paralelo con MQTT (broker + Node-RED + cámaras remotas)](#5-uso-en-paralelo-con-mqtt-broker--node-red--cámaras-remotas)
6. [Uso en paralelo con Modbus TCP (PLC clásico)](#6-uso-en-paralelo-con-modbus-tcp-plc-clásico)
7. [Uso en paralelo con OPC UA (SCADA empresarial)](#7-uso-en-paralelo-con-opc-ua-scada-empresarial)
8. [Patrones de despliegue recomendados](#8-patrones-de-despliegue-recomendados)
9. [Seguridad y autenticación](#9-seguridad-y-autenticación)
10. [Diagnóstico cuando algo no actualiza](#10-diagnóstico-cuando-algo-no-actualiza)

---

## 1. ¿Qué es un Gemelo Digital y por qué este es distinto?

Un **gemelo digital** (digital twin) es una **réplica virtual** de un activo físico que se mantiene sincronizada con él. La sincronización puede ser:

- **Off-line**: cargás un CSV histórico y comparás (replay).
- **On-line en sombra**: el activo manda lecturas y el gemelo las refleja, sin cerrar lazo.
- **On-line bidireccional**: el gemelo y el activo intercambian datos; el gemelo puede pedirle al activo que ajuste un actuador.

La mayoría de los simuladores de planta son **de caja negra**: tomás un setpoint (SP) y el simulador "interpola" a ese valor con un `tau` artificial. Eso es útil para hacer demos, pero **no entrena al operador** porque la realidad no se comporta así.

**Este gemelo es distinto**: usa un **modelo físico puro** (balance de masa + balance de energía). Si abrís una válvula de vapor, la temperatura sube *porque el vapor aporta entalpía real*. Si no la abrís, no sube. **No hay tau escondido**. El operador entrena con la misma dinámica que tendrá en planta.

Esto habilita varios casos de uso simultáneos:

| Caso | Modo |
|---|---|
| Entrenar operarios nuevos sin tocar la planta | **Simulator** |
| Detectar drift entre el modelo y la planta real (calibración de sensores) | **Shadow** |
| Reemplazar al PLC durante mantenimiento (controlar desde la web) | **Twin** + Modbus/OPC UA escrituras |
| Auditar un evento pasado (reproducir un CSV) | **Replay** |

---

## 2. Los 4 modos del simulador

| Modo | Quién calcula la física | De dónde vienen las lecturas | Para qué |
|---|---|---|---|
| **Simulator** (verde) 🟢 | El simulador interno | Calculadas por el modelo | Entrenamiento, what-if, demo, integración offline |
| **Shadow** (azul) 🔵 | El simulador interno, pero **también** lee del PLC | Internas + externas en paralelo, se comparan (`/api/drift`) | Calibración, validación de instrumentación |
| **Twin** (ámbar) 🟡 | **No calcula**, sólo aplica clamps + ruido | El PLC / Node-RED escribe vía Modbus o OPC UA | Reemplazo temporal del sistema legado |
| **Replay** (violeta) 🟣 | Lee un CSV histórico, fila por fila | El CSV | Capacitación con incidentes reales pasados |

Indicador visual: en el header está el **botón Modo** con color y label.

---

## 3. Filosofía del modelo físico puro (¡importante!)

> Si entendés esto, todo el resto del manual cobra sentido.

### Lo que NO hace el simulador
- ❌ No "tira" la temperatura al SP por interpolación.
- ❌ No "respeta" un SP de humedad si nadie ajusta caudal de aire/vapor.
- ❌ No esconde dinámicas detrás de constantes mágicas.

### Lo que SÍ hace
Cada etapa tiene variables manipuladas (MV) que el operador (o un PLC externo) ajusta. La física responde:

| Etapa | MVs disponibles | Lo que pasa |
|---|---|---|
| **Zapecado** | velocidad_chip (combustible), velocidad_tambor (rpm), estado_alimentación | Balance térmico: `C·dT/dt = P_chips − P_pared − P_aire − P_yerba`. Si subís chip, sube T. Si subís rpm, baja T (más extracción de gases). |
| **Secado** | posicion_calefactor (0-100%), velocidad_aire (m/s), estado | Balance térmico + balance de humedad de la yerba. El calefactor aporta `P_cal`; el aire arrastra HR y enfría. Para bajar HR, **necesitás aire**. |
| **Canchado** | velocidad_molino (rpm) | Tamaño de partícula = función directa de rpm con dinámica ~5s. |
| **Cámaras** | vapor_caudal_kgh, vapor_activo, ventilador, vent_pos, puerta_abierta | Balance térmico con vapor como aporte; ventilador como extractor; paredes como pérdida pasiva. |

### Los PIDs internos son OPCIONALES
Cada etapa tiene un PID interno **apagado por defecto** (`pid.enabled = false`). Si lo activás desde la UI o por API, el PID ajusta automáticamente la MV correspondiente para llegar al SP. Esto sirve para **entrenar sintonía de Kp/Ki/Kd**, no para "trampear" el modelo.

> Si querés que tu PLC externo cierre el lazo, **dejá los PIDs internos apagados** y mandá las MVs por Modbus/OPC UA/MQTT.

---

## 4. Cómo cambiar de modo

### Desde la UI
1. Login como `admin`.
2. En el header, clic en **Modo Simulador** → cicla a Shadow → Twin → vuelve.
3. Para `Replay`, ir a tab **Replay & What-if** → elegir CSV → Start.

### Desde la API REST

```bash
curl -X POST $BASE/api/mode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode":"twin"}'
```

### Desde MQTT (sin la UI)

```bash
mosquitto_pub -h <broker> -t yerba/cmd/sim -m '{"mode":"twin"}'
```

---

## 5. Uso en paralelo con MQTT (broker + Node-RED + cámaras remotas)

Es el caso más común para **operación distribuida** (planta + cámaras en otra ciudad).

### 5.1 Topics que **publica** el gemelo (output)

| Topic | Payload | Periodo |
|---|---|---|
| `yerba/zapecado/temperatura` | float (°C) | 1s |
| `yerba/zapecado/velocidad_chip` | float (kg/h) | 1s |
| `yerba/secado/temperatura` | float (°C) | 1s |
| `yerba/secado/humedad` | float (%) | 1s |
| `yerba/canchado/tamano_particula` | float (mm) | 1s |
| `yerba/camara/{i}/temperatura` | float (°C) | 1s |
| `yerba/camara/{i}/humedad` | float (%) | 1s |
| `yerba/camara/{i}/co2` | float (ppm) | 1s |
| `yerba/state/full` | JSON completo del simulador | 5s |
| `yerba/alarms/active` | array JSON de alarmas activas | 5s |

### 5.2 Topics que **escucha** el gemelo (input — bidireccional)

| Topic | Payload | Efecto |
|---|---|---|
| `yerba/cmd/zapecado` | JSON `{"velocidad_chip":45, "estado_alimentacion":true}` | Aplica MVs en Zapecado |
| `yerba/cmd/secado` | JSON `{"posicion_calefactor":60, "velocidad_aire":3.2}` | Aplica MVs en Secado |
| `yerba/cmd/canchado` | JSON `{"velocidad_molino":75}` | Aplica MVs en Canchado |
| `yerba/cmd/camara/{i}` | JSON `{"vapor_activo":true, "vapor_caudal_kgh":40}` | Aplica MVs en cámara `i` |
| `yerba/cmd/weather` | JSON `{"temperature":18.5,"humidity":92}` | Override manual de clima |
| `yerba/cmd/sim` | JSON `{"mode":"twin","aceleracion":60,"throughput_kgh":900}` | Globales |
| **Atajo** `yerba/cmd/zapecado/velocidad_chip` | `45` (raw value) | Sólo ese campo |

### 5.3 Flujo Node-RED típico

```
[mqtt-in yerba/state/full] ─► [function: extraer T_camara_2] ─► [if T>40] ─►
   ┌──► [mqtt-out yerba/cmd/camara/1] payload `{"ventilador":true}`
   └──► [mqtt-out yerba/alarms/notify] payload `Alarma cámara 2`
```

Ejemplo completo de flow en `instructivo_nodered.md` capítulo 5.

### 5.4 Cámaras físicas remotas

Si tenés sondas reales (PT100 + capacitivo HR + NDIR CO2) en una cámara remota:

1. ESP32 / Raspberry / PLC compacto local lee los sensores cada 2s.
2. Publica a `yerba/camara/N/temperatura`, `yerba/camara/N/humedad`, `yerba/camara/N/co2`.
3. **El gemelo, en modo `twin`**, sobreescribe sus valores internos con esos.
4. La UI muestra los valores reales en la tab Cámaras como si fueran calculados.

> Detalle: en modo `twin`, el simulador **no recalcula** la física de esa cámara. En modo `shadow`, recalcula Y compara.

---

## 6. Uso en paralelo con Modbus TCP (PLC clásico)

Para PLCs Schneider, Siemens (S7-1500 con Modbus), Allen-Bradley con módulo Modbus, etc.

### 6.1 Mapa de registros (holding registers, function code 03/06/16)

El servidor escucha en TCP `:5020`. Cada unit ID es una etapa:

| Unit | Etapa | Registros principales (16-bit, x100 para floats) |
|---|---|---|
| 1 | Zapecado | 0: T_actual·100, 1: T_obj·100, 2: vel_chip·10, 3: vel_tambor·10, 4: estado_alim (0/1), 5: falla_quemador, 6: falla_motor_tambor |
| 2 | Secado | 0: T·100, 1: T_obj·100, 2: HR·100, 3: HR_obj·100, 4: vel_aire·10, 5: pos_cal·10, 6: estado, 7: falla_vent, 8: falla_serp |
| 3 | Canchado | 0: rpm·10, 1: rpm_obj·10, 2: tam_particula·100, 3: tam_obj·100, 4: estado, 5: falla_motor, 6: rod_caliente |
| 10..21 | Cámara 1..12 | 0: T·100, 1: HR·100, 2: CO2 (raw ppm), 3: vapor_kgh·10, 4: vapor_activo, 5: vent_pos·10, 6: vent_on, 7: puerta_abierta, 8: fuga_vapor |

### 6.2 Lecturas (PLC → SCADA)

```python
from pymodbus.client.tcp import ModbusTcpClient as C
c = C("ip_gemelo", 5020)
c.connect()
# Leer T zapecado
r = c.read_holding_registers(0, 5, unit=1)
T = r.registers[0] / 100.0
print(f"Zapecado T = {T} °C")
c.close()
```

### 6.3 Escrituras (PLC → gemelo, bidireccional)

```python
# Setear vel_chip a 50 kg/h
c.write_register(2, 500, unit=1)   # 500 / 10 = 50
# Cerrar válvula de vapor cámara 1
c.write_register(4, 0, unit=10)
```

El gemelo aplica las escrituras al simulator con **polling-diff cada 200ms**.

> Detalle de implementación: ver `backend/twin/yerba_modbus_server.py` función `_apply_external_writes`.

### 6.4 Caso real: PLC controla, gemelo simula proceso

1. Modo `simulator` activo.
2. El PLC lee T zapecado (registro 0 unit 1).
3. El PLC calcula nueva vel_chip con su PID.
4. El PLC escribe nueva vel_chip (registro 2 unit 1).
5. El gemelo aplica el cambio → en 1s ves la T responder físicamente.

Esto te permite **probar la lógica del PLC sin tocar la planta** (HIL — hardware in the loop).

---

## 7. Uso en paralelo con OPC UA (SCADA empresarial)

Para SCADA tipo Ignition, Wonderware, AVEVA System Platform, etc.

### 7.1 Endpoint y namespace

- Endpoint: `opc.tcp://<ip>:4840/freeopcua/server/`
- Namespace index: `2` (default).
- Modo: SecurityPolicy=None (válido sólo en red privada; ver `manual_tecnico.md` cap 11 para Sign+Encrypt).

### 7.2 Nodos disponibles

```
Objects/
├── Zapecado/
│   ├── Temperatura          (Double, RO)
│   ├── TemperaturaObj       (Double, RW)
│   ├── VelocidadChip        (Double, RW)
│   ├── VelocidadTambor      (Double, RW)
│   ├── EstadoAlimentacion   (Boolean, RW)
│   └── ...
├── Secado/
│   ├── Temperatura, Humedad, VelocidadAire, PosCalefactor, Estado ...
├── Canchado/...
├── Camara1/...
├── Camara2/...
├── ...
└── Simulacion/
    ├── Aceleracion          (Double, RW)
    ├── ThroughputKgh        (Double, RW)
    └── Modo                 (String, RW)
```

### 7.3 Cliente Python ejemplo

```python
from asyncua.sync import Client
c = Client("opc.tcp://localhost:4840")
c.connect()
ns = 2
# Leer T zapecado
T = c.get_node(f"ns={ns};s=Zapecado.Temperatura").get_value()
# Escribir velocidad chip
c.get_node(f"ns={ns};s=Zapecado.VelocidadChip").set_value(45.0)
c.disconnect()
```

### 7.4 Polling-diff en OPC UA

Las escrituras externas son detectadas con un loop cada **2 segundos**. Si tu SCADA actualiza valores muy rápido, considerá Modbus (200ms) o MQTT (~50ms publish, callback inmediato).

---

## 8. Patrones de despliegue recomendados

### Patrón A — Entrenamiento puro
```
[Operario] ──► [UI web (browser)] ──► [Gemelo en modo simulator]
```
Nada externo. Más fácil. Para capacitar nuevos operarios.

### Patrón B — Co-piloto del PLC (recomendado en producción)
```
[Planta] ◄──► [PLC] ◄──► [Gemelo en modo shadow]
                          ├─► UI web (operario)
                          └─► IA / Reportes / Alarmas
```
El PLC sigue siendo la autoridad. El gemelo refleja y avisa de desvíos.

### Patrón C — Distribuido con cámaras remotas (caso INYM multiplanta)
```
[Cámaras Apóstoles] ──MQTT──► [Gemelo (cloud)] ──MQTT──► [Cámaras Posadas]
                                  ▲                        ▲
                                  └── PLC zapecado/secado ─┘
                                  └── Operario UI web ─────┘
```
Un solo gemelo coordina cámaras físicas en varias plantas + el control local en una de ellas.

### Patrón D — Reemplazo temporal del PLC (modo twin)
```
[Operario UI] ──► [Gemelo modo twin] ──► [Actuadores planta vía Modbus]
                       ▲
                       └── usado para mantenimiento de PLC original
```
**Usar con cuidado y mecanismo de fallback**.

---

## 9. Seguridad y autenticación

| Capa | Mecanismo actual | Recomendación productiva |
|---|---|---|
| Web | JWT en cookie httpOnly + bearer header. bcrypt. | Cambiar `JWT_SECRET` por uno aleatorio fuerte. HTTPS obligatorio. |
| Modbus | Sin auth (TCP plano). | Aislar en VLAN. Firewall sólo desde IP del PLC. |
| OPC UA | SecurityPolicy=None. | Activar Sign+Encrypt y exigir certificado de cliente (ver `manual_tecnico.md` cap 11). |
| MQTT | Default abierto. | ACL en mosquitto por usuario/topic. TLS en puerto 8883. |

> Para producción, mínimo: VPN site-to-site + HTTPS + JWT con secret fuerte + MQTT con TLS + ACL.

---

## 10. Diagnóstico cuando algo no actualiza

| Síntoma | Posible causa | Cómo verificar |
|---|---|---|
| Escribo por MQTT pero no cambia el simulador | El subscriber MQTT está apagado o `mode=twin` con sección distinta. | Ver `/api/services/status` → `mqtt_subscriber.running`. |
| Escribo por Modbus pero no cambia el simulador | El polling-diff necesita 200ms. ¿Estás escribiendo y leyendo *demasiado rápido*? | Esperá 1s y leé el holding register de nuevo. Verificá `unit_id`. |
| El operador mueve el slider en la UI pero el dato lo sobreescribe el PLC | Estás en modo `twin` o `shadow` y el PLC pisa el valor cada 200ms. | Cambiá a `simulator` para entrenar, o coordiná la prioridad. |
| El override de clima manual lo sobreescribe el forecast | `aceleracion > 1` activa el forecast. El gemelo respeta `manual` y `mqtt-cmd` automáticamente. | Verificá `/api/state` → `ambient.source`. |
| Cámara remota no aparece | Topic mal escrito (debe ser `yerba/cmd/camara/{i}`). | `mosquitto_sub -h broker -t 'yerba/cmd/#' -v` para ver tráfico. |

Para casos complejos: revisar logs en `/var/log/supervisor/backend.err.log` y abrir issue con la línea exacta del log.

---

> **Próximo paso recomendado**: leé `manual_machine_learning.md` para entender cómo la IA (Gemini 3 Flash) ayuda a optimizar lo que el gemelo simula.
