# Instructivo de Ejecución · Cómo levantar el Gemelo Digital

> **Audiencia**: TI, integrador, equipo de mantenimiento.
> **Tiempo estimado**: 10-15 min (instalación limpia) · 1 min (reinicio).

---

## Tabla de contenidos

1. [Requisitos del entorno](#1-requisitos-del-entorno)
2. [Arranque rápido (entorno ya instalado)](#2-arranque-rápido-entorno-ya-instalado)
3. [Instalación desde cero](#3-instalación-desde-cero)
4. [Puertos que usa el sistema](#4-puertos-que-usa-el-sistema)
5. [Variables de entorno (.env)](#5-variables-de-entorno-env)
6. [Verificación post-arranque](#6-verificación-post-arranque)
7. [Comandos diarios útiles](#7-comandos-diarios-útiles)
8. [Troubleshooting express](#8-troubleshooting-express)

---

## 1. Requisitos del entorno

| Componente | Versión mínima | Cómo verificar |
|---|---|---|
| Linux (Debian/Ubuntu) | 22.04+ | `lsb_release -a` |
| Python | 3.11+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| MongoDB | 6+ (corriendo local o en cluster) | `mongosh --eval 'db.runCommand({ping:1})'` |
| Yarn | 1.22+ | `yarn --version` |
| Supervisor | 4+ | `supervisord --version` |
| Mosquitto (MQTT broker) | 2+ (opcional, sólo si querés Node-RED ↔ gemelo) | `mosquitto -h` |

> **Nota**: En la plataforma Emergent todo esto **ya está instalado** y supervisado. Los comandos manuales sólo aplican a instalaciones on-premise.

---

## 2. Arranque rápido (entorno ya instalado)

Una sola línea levanta todo:

```bash
sudo supervisorctl restart backend frontend
```

Verificá:

```bash
sudo supervisorctl status
# backend                          RUNNING   pid 1234, uptime 0:00:05
# frontend                         RUNNING   pid 1235, uptime 0:00:05
# mongodb                          RUNNING   pid 1100, uptime 1:30:00
```

Abrí el navegador en la URL configurada (variable `REACT_APP_BACKEND_URL` en `frontend/.env`) o, en local, `http://localhost:3000`.

**Login default**:
- `admin` / `admin` (rol completo)
- `operario` / `operario` (rol restringido)

> **Cambiá las contraseñas en el primer ingreso** desde la UI (Perfil → cambiar contraseña).

---

## 3. Instalación desde cero

### 3.1 Backend

```bash
cd /app/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Servicios industriales opcionales:
pip install paho-mqtt asyncua pymodbus
```

### 3.2 Frontend

```bash
cd /app/frontend
yarn install
```

### 3.3 MongoDB

Tiene que estar corriendo en `mongodb://localhost:27017` (o lo que indique `MONGO_URL` en `backend/.env`). La base se crea automáticamente al primer login.

### 3.4 Configurar `.env`

Ver capítulo [5](#5-variables-de-entorno-env).

### 3.5 Supervisor

Usar el archivo `/etc/supervisor/conf.d/yerba.conf` (ya provisto). Sólo correr:

```bash
sudo supervisorctl reread && sudo supervisorctl update
sudo supervisorctl start all
```

---

## 4. Puertos que usa el sistema

| Puerto | Servicio | Quién escucha | Bidireccional |
|---|---|---|---|
| `3000` | Frontend React (dev) | `yarn start` | n/a |
| `8001` | FastAPI backend | uvicorn | REST + WebSocket |
| `27017` | MongoDB | mongod | persistencia |
| `5020` | **Modbus TCP server (gemelo)** | `pymodbus.server` | ✅ PLC puede leer **y** escribir |
| `4840` | **OPC UA server (gemelo)** | `asyncua.server` | ✅ |
| `1883` | MQTT broker (mosquitto) | externo | ✅ gemelo publica y se suscribe a `yerba/cmd/#` |

> Si tu PLC corre Modbus client en TCP/5020 (estándar IEC 61131-3), apuntalo a la IP del servidor del gemelo.

---

## 5. Variables de entorno (.env)

**`backend/.env`** (no commitear; ya viene pre-cargada):

```ini
MONGO_URL=mongodb://localhost:27017
DB_NAME=yerba_twin
CORS_ORIGINS=*
EMERGENT_LLM_KEY=sk-emergent-xxxxxxxxxxxx
JWT_SECRET=cambiame-en-produccion
ADMIN_RECOVERY_CODE=YERBA-RECOVER-2026
```

**`frontend/.env`** (no commitear):

```ini
REACT_APP_BACKEND_URL=https://gemelo.miempresa.com
WDS_SOCKET_PORT=443
```

> ⚠️ **Nunca** uses defaults hardcodeados en código: si el `.env` no está, falla rápido y se ve enseguida.

---

## 6. Verificación post-arranque

Ejecutar en orden:

```bash
# 1. Backend responde
curl -s http://localhost:8001/api/ | jq .
# {"app":"Gemelo Digital Yerba Mate","status":"ok","version":"2.1.0"}

# 2. Servicios industriales
curl -s http://localhost:8001/api/services/status | jq .

# 3. Estado del simulador
curl -s http://localhost:8001/api/state | jq .zapecado.temperatura

# 4. Modbus server (necesita pymodbus client en otra terminal)
python3 -c "from pymodbus.client.tcp import ModbusTcpClient as C; c=C('localhost',5020); c.connect(); print(c.read_holding_registers(0,5,unit=1).registers); c.close()"

# 5. OPC UA discovery
python3 -c "from asyncua.sync import Client; c=Client('opc.tcp://localhost:4840'); c.connect(); print([n for n in c.nodes.objects.get_children()]); c.disconnect()"
```

Si los 5 pasos responden sin error, el sistema está sano.

---

## 7. Comandos diarios útiles

```bash
# Ver logs en vivo
tail -F /var/log/supervisor/backend.*.log
tail -F /var/log/supervisor/frontend.*.log

# Reiniciar todo
sudo supervisorctl restart all

# Sólo backend (después de cambiar Python)
sudo supervisorctl restart backend

# Sólo frontend (después de yarn add)
sudo supervisorctl restart frontend

# Backup base de datos
mongodump --uri="$MONGO_URL" --out=/backup/yerba-$(date +%F)

# Exportar histórico de CSV
ls /app/backend/data/yerba_history_*.csv
```

---

## 8. Troubleshooting express

| Síntoma | Acción |
|---|---|
| `502 Bad Gateway` en la UI | `sudo supervisorctl restart backend` y revisar `/var/log/supervisor/backend.err.log` |
| Login devuelve `401` con credenciales correctas | Borrá cookies del navegador; el JWT puede estar caducado. |
| Modbus / OPC UA badges en rojo | Verificá `backend/.env` que no haya seteo conflictivo; revisá puerto libre con `ss -tlnp \| grep 5020`. |
| Open-Meteo 429 / weather rojo | Es el rate limit público. El gemelo cambia automáticamente a fallback sintético estacional. No requiere acción. |
| IA responde "Falta EMERGENT_LLM_KEY" | Recargá el `.env`, reiniciá backend, y confirmá `EMERGENT_LLM_KEY` en `backend/.env`. |
| MQTT no recibe `yerba/cmd/*` | Verificá broker accesible: `mosquitto_sub -h <broker> -t 'yerba/#' -v`. |

Para casos no listados → `manual_tecnico.md` capítulo 14.
