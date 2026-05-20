# Instructivo · Integración Node-RED + Cámaras Reales en Tiempo Real

> Versión: mayo 2026 · Aplica a la versión BIDIRECCIONAL del Gemelo Digital de Yerba Mate

---

## 1. Resumen

El Gemelo Digital del proceso de yerba mate se comporta como un **PLC virtual** —
expone su estado por **Modbus TCP**, **OPC UA** y **MQTT**, y acepta escrituras
en cualquiera de los tres protocolos. Esto permite:

- **Modo simulador puro**: el operador opera todo desde la UI web.
- **Modo "shadow"**: un PLC real o cámaras físicas envían lecturas reales y el
  gemelo refleja en tiempo real lo que pasa en planta (sin actuar).
- **Modo "twin" (digital twin completo)**: el PLC o Node-RED envía datos del
  campo, el gemelo los procesa, y el sistema responde escribiendo manipuladas
  de vuelta al PLC para cerrar el lazo.

Este documento describe cómo conectar **Node-RED** a este gemelo y cómo
incorporar cámaras reales que están en otra ciudad (vía MQTT remoto).

---

## 2. Arquitectura propuesta

```
┌───────────────────────────────┐                ┌────────────────────────────┐
│  Planta remota (otra ciudad)  │                │   Gemelo Digital (cloud)   │
│                               │                │                            │
│  ┌──────────┐   ┌──────────┐  │    MQTT TLS    │  ┌──────────────────────┐  │
│  │ Cámara 1 │   │ Cámara N │──┼───────────────▶│  │  YerbaMqttPublisher  │  │
│  │ PT100×2  │   │ PT100×2  │  │   yerba/cmd/   │  │  (subscriber bidir.) │  │
│  │ NDIR CO₂ │   │ NDIR CO₂ │  │   camara/N     │  └──────────┬───────────┘  │
│  └────┬─────┘   └────┬─────┘  │                │             │              │
│       │              │        │                │             ▼              │
│       └──────┬───────┘        │                │  ┌──────────────────────┐  │
│              ▼                │                │  │  Simulator Runtime   │  │
│       ┌──────────────┐        │                │  │  (proceso puro PID)  │  │
│       │  Node-RED    │────────┼───────────────▶│  └──────────┬───────────┘  │
│       │  Broker MQTT │        │   yerba/cmd/   │             │              │
│       └──────────────┘        │   weather...   │             ▼              │
│                               │                │  ┌──────────────────────┐  │
└───────────────────────────────┘                │  │  Servidores OUT:     │  │
                                                 │  │  · MQTT pub          │  │
                                                 │  │  · Modbus TCP 5020   │  │
                                                 │  │  · OPC UA 4840       │  │
                                                 │  │  · REST /api/state   │  │
                                                 │  └──────────────────────┘  │
                                                 └────────────────────────────┘
```

---

## 3. Bidireccionalidad — qué se escribe y qué se lee

### 3.1 MQTT (recomendado para Node-RED / IoT remoto)

**Topics que el gemelo PUBLICA** (cada 5 s, QoS 0):

| Topic | Payload (JSON) |
|-------|----------------|
| `yerba/zapecado` | `{pv_temperatura, sp_temperatura, manipuladas, pid, faults}` |
| `yerba/secado` | `{pv_temperatura, pv_humedad, sp_*, manipuladas, pid_t, pid_h, faults}` |
| `yerba/canchado` | `{pv_tamano_particula, manipuladas, pid, faults}` |
| `yerba/camara_1` (1..N) | `{pv_*, sp_*, manipuladas, pid_t, faults, carga_kg, dias_maduracion}` |
| `yerba/ambient` | `{temperatura, humedad, city, source}` |
| `yerba/sim` | `{aceleracion, throughput_kgh, mode, sim_clock}` |
| `yerba/forecast` | `{hourly_next_24h: [{time, temp, hum}]}` |

**Topics que el gemelo ESCUCHA** (suscripción `yerba/cmd/#`):

| Topic | Payload | Efecto |
|-------|---------|--------|
| `yerba/cmd/zapecado` | `{velocidad_chip, velocidad_tambor, temperatura_obj, falla_quemador, pid:{...}}` | Aplica al simulador |
| `yerba/cmd/secado` | `{posicion_calefactor, velocidad_aire, temperatura_obj, humedad_obj, falla_*, pid_t:{...}, pid_h:{...}}` | Aplica al simulador |
| `yerba/cmd/canchado` | `{velocidad_molino, tamano_particula_obj, falla_motor, pid:{...}}` | Aplica al simulador |
| `yerba/cmd/camara/<idx>` | `{carga_kg, ventilador, vapor_activo, vapor_caudal_kgh, temperatura_obj, falla_*}` | Aplica a cámara `idx` |
| `yerba/cmd/weather` | `{temperature, humidity}` | Override manual ambient |
| `yerba/cmd/sim` | `{aceleracion, throughput_kgh, mode}` | Globales |

**Atajo "raw value"**: si publicás un número crudo en `yerba/cmd/zapecado/velocidad_chip`
con payload `45`, el gemelo lo interpreta como `{"velocidad_chip": 45}`.

### 3.2 Modbus TCP (puerto 5020)

Cualquier *holding register* o *coil* que el gemelo expone como writable
acepta escrituras externas. En el siguiente ciclo (≈ 200 ms) el simulador
detecta el cambio y lo aplica.

**Tabla compacta de escrituras útiles**:

| Unit | Reg/Coil | Variable | Escala |
|-----:|---------|----------|--------|
| 0 | reg 5 | T objetivo zapecado (0 = auto) | ×10 |
| 0 | reg 1 | vel.tambor (rpm) | — |
| 0 | reg 2 | vel.chip (kg/h) | — |
| 0 | coil 0 | falla quemador | 0/1 |
| 1 | reg 4 | T objetivo secado | ×10 |
| 1 | reg 5 | HR objetivo secado | ×10 |
| 1 | reg 2 | vel.aire (m/s) | ×10 |
| 1 | reg 7 | posición calefactor (%) | ×10 |
| 2 | reg 0 | vel.molino canchado | ×10 |
| 2 | reg 3 | tamaño partícula objetivo (mm, 0=auto) | ×100 |
| 3..14 | reg 3 | T objetivo cámara | ×10 |
| 3..14 | reg 4 | HR objetivo cámara | ×10 |
| 3..14 | reg 9 | vapor activo | 0/1 |
| 3..14 | reg 10 | caudal vapor (kg/h) | ×10 |
| 100 | reg 0 | aceleración simulación | ×10 |

Ver `manual_tecnico.md` §3.4 para mapeo completo.

### 3.3 OPC UA (puerto 4840)

Endpoint: `opc.tcp://<host>:4840/yerba/` · Namespace: `YerbaProcess`

Nodos escribibles para control externo:
- `YerbaProcess.Zapecado.{TemperaturaObjetivo, FallaQuemador, FallaMotorTambor}`
- `YerbaProcess.Secado.{TemperaturaObjetivo, HumedadObjetivo, FallaVentilador, FallaSerpentin}`
- `YerbaProcess.Canchado.{TamanoParticulaObjetivo, FallaMotor, RodamientoCaliente}`
- `YerbaProcess.Camara<N>.{TemperaturaObjetivo, HumedadObjetivo, VaporActivo, VaporCaudalKgh, FallaVentilador, FugaVapor, PuertaAbierta}`
- `YerbaProcess.Simulacion.{Aceleracion, ThroughputKgh, Modo}`

---

## 4. Flow de ejemplo en Node-RED para cámaras remotas

### 4.1 Caso de uso

Tenés 4 cámaras de maduración en una planta en otra ciudad, cada una con
sensores **PT100 (T)**, **higrómetro NIR (HR)** y **NDIR CO₂**. Querés que el
gemelo refleje los valores reales y que las alarmas/IA del gemelo te avisen.

### 4.2 Pre-requisito: broker MQTT accesible

Tu gemelo conecta a un broker MQTT (configurable en `/app/backend/config_yerba.yaml`).
Configurá el mismo broker en Node-RED:

```yaml
# config_yerba.yaml
mqtt:
  broker: broker.tu-empresa.com
  port: 8883
  user: yerba_user
  pass: ${MQTT_PASS}
  topic: yerba
  interval: 5
  keepalive: 60
```

Si necesitás TLS, usa un puerto seguro (8883) y certificados.

### 4.3 Flow Node-RED — Publicar lectura de cámara real al gemelo

```
[Modbus Read PLC] ──▶ [function: build payload] ──▶ [mqtt out → yerba/cmd/camara/0]
```

**Function "build payload"** (JavaScript en Node-RED):

```js
// msg.payload viene del Modbus del PLC local con [T_x10, HR_x10, CO2]
const reg = msg.payload;
const t = reg[0] / 10;
const hr = reg[1] / 10;
const co2 = reg[2];

// Forzamos al gemelo a "creer" estos valores como SP (modo shadow)
msg.topic = "yerba/cmd/camara/0";
msg.payload = {
  carga_kg: 1200,           // dato fijo o desde otro nodo
  temperatura_obj: t,        // el gemelo intentará seguir este SP
  humedad_obj: hr,
  co2_obj: co2,
  // Si querés que el gemelo congele su PID y use directamente lo real:
  pid_t: { enabled: false }
};
return msg;
```

### 4.4 Flow Node-RED — Leer alarmas del gemelo

```
[mqtt in: yerba/secado] ──▶ [function: check alarms] ──▶ [Telegram out]
```

```js
const data = msg.payload;
if (data.pv_humedad > 12) {
  msg.payload = `⚠️ Alarma secado: HR = ${data.pv_humedad.toFixed(1)}% (límite 12%)`;
  return msg;
}
return null;
```

### 4.5 Flow Node-RED — Comandar el gemelo desde un dashboard local

```
[dashboard switch: PID auto/manual] ──▶ [mqtt out → yerba/cmd/secado]
```

Payload del switch:
```json
{ "pid_t": { "enabled": true, "kp": 4.0, "ki": 0.15, "reset": true } }
```

### 4.6 Flow Node-RED — Ejemplo end-to-end con cámaras remotas

1. Node-RED en cada cámara lee los sensores físicos cada 1-5 s.
2. Publica en MQTT a `yerba/cmd/camara/<id_cam>` con los valores reales.
3. El gemelo recibe → reemplaza T/HR/CO₂ esperados → PID del gemelo reacciona
   automáticamente y publica las manipuladas (caudal vapor, ventilador).
4. Node-RED se suscribe a `yerba/camara_<id>` para leer las manipuladas
   calculadas por el gemelo y las aplica en el PLC local (control real).

Resultado: el gemelo controla la planta remota a través de Node-RED como
"broker de protocolos".

---

## 5. Funcionamiento en tiempo real

### 5.1 Modos de operación

El simulador se inicializa en modo `simulator`. Cambiarlo desde la UI o
publicando en `yerba/cmd/sim {"mode": "shadow"}`:

- `simulator` (default): el gemelo simula la física pura. Los `yerba/cmd/*`
  modifican las variables del simulador y lo controlan.
- `shadow`: el gemelo recibe los PV reales desde MQTT/Modbus (NO los simula);
  publica sus propios sensores derivados y alarmas.
- `twin`: el gemelo simula, compara con la planta real (drift detection), y
  re-emite manipuladas hacia el PLC para corregir desviaciones.

### 5.2 Reloj simulado vs reloj real

Con `aceleracion > 1`, el gemelo avanza más rápido que el reloj real y
consume el **forecast horario de Open-Meteo** para el ambient. Para uso con
cámaras reales mantené siempre `aceleracion = 1.0`.

### 5.3 Latencia esperada

| Cliente | Publicación | Detección de escritura |
|---------|-------------|------------------------|
| MQTT (gemelo→cliente) | cada 5 s |  - |
| MQTT (cliente→gemelo) | inmediato | <100 ms |
| Modbus TCP | cada 200 ms |  ~200 ms |
| OPC UA | cada 2 s |  ~2 s |
| REST `/api/state` | on-demand |  - |

Para control en tiempo real recomendamos **MQTT** (es el más rápido en RTT).

### 5.4 Seguridad

- **MQTT**: usar `username/password` + TLS (`mqtts://`).
- **Modbus**: cliente VPN o lista blanca por IP.
- **OPC UA**: configurar `mode` y `policy` para certificados (no implementado
  en este MVP).
- **REST**: JWT (cookies + headers) para todos los endpoints `POST`.

### 5.5 Persistencia

El gemelo guarda:
- Historial de PV cada 1 s en `yerba_history_YYYY-MM-DD.csv` (rotación diaria).
- Configuración en `config_yerba.yaml`.
- Lotes/recetas/alarmas en memoria con snapshot a disco cada cambio.

Para replay histórico, ver `manual_operaciones.md` §6.

---

## 6. Pruebas rápidas

### 6.1 Test bidireccional MQTT (con `mosquitto_pub`)

```bash
# Activar PID de secado con SP=98°C
mosquitto_pub -h <broker> -t yerba/cmd/secado -m '{"temperatura_obj":98,"pid_t":{"enabled":true,"kp":4,"ki":0.15,"reset":true}}'

# Setear T ambiente 16°C manualmente
mosquitto_pub -h <broker> -t yerba/cmd/weather -m '{"temperature":16,"humidity":85}'

# Simular falla quemador
mosquitto_pub -h <broker> -t yerba/cmd/zapecado -m '{"falla_quemador":true}'

# Suscribirse a todo lo del gemelo
mosquitto_sub -h <broker> -t "yerba/#" -v
```

### 6.2 Test bidireccional Modbus (con `pymodbus`)

```python
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient('host-gemelo', port=5020); c.connect()

# Setear T objetivo zapecado = 480°C
c.write_register(address=5, value=4800, slave=0)

# Activar falla quemador
c.write_coil(address=0, value=True, slave=0)

# Leer T actual
print(c.read_holding_registers(0, count=7, slave=0).registers)
```

### 6.3 Test bidireccional OPC UA (con `python-opcua`)

```python
from opcua import Client
c = Client("opc.tcp://host-gemelo:4840/yerba/"); c.connect()

# Escribir SP T del secado
node = c.get_objects_node().get_child(["2:Secado", "2:TemperaturaObjetivo"])
node.set_value(98.5)

# Activar falla
falla = c.get_objects_node().get_child(["2:Camara1", "2:FallaVentilador"])
falla.set_value(True)
```

---

## 7. Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| Escribo a Modbus y se "vuelve atrás" en 200 ms | El simulador está sobrescribiendo porque modo=`simulator` y el valor se está siendo recalculado por física | Cambiar a modo `shadow`, o aceptar que el simulador imponga su estado. |
| MQTT cmd no surte efecto | Topic mal formado, o el broker no está conectado al gemelo | Revisar logs `tail -f /var/log/supervisor/backend.err.log \| grep MQTT` |
| OPC UA TimeoutError | Firewall del cliente | Abrir puerto 4840 TCP |
| Aceleración alta con cámaras reales | El forecast pisa los valores reales | Dejar `aceleracion = 1.0` cuando hay datos en vivo |
| El PID está ON pero la manipulada no se mueve | El PID está saturado (out_min/out_max) o el set point ya está alcanzado | Revisar `pid.last_output` y `integral` en el estado |

---

## 8. Próximos pasos

- Soporte de **autenticación MQTT por topic** (ACL).
- **OPC UA con seguridad** (`Sign+Encrypt` + cert client).
- **Bridge MQTT-Modbus interno** para que escribir en MQTT propague a Modbus y viceversa (hoy ya es el caso porque ambos van al mismo `simulator`).
- **Replay desde cámaras reales** (grabar el stream MQTT de planta y reproducirlo).

---

Para detalles del modelo físico, balances energéticos y mapping de registros
completo, ver `manual_tecnico.md`. Para uso operativo desde la UI web, ver
`manual_operaciones.md`.
