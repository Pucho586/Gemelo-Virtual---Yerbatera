# Gemelo Digital Frigorífico (Proof of Concept)

Este directorio contiene una prueba de concepto (PoC) de un **Gemelo Digital para un Frigorífico** (Planta de Procesamiento de Carne), adaptando la base conceptual del proyecto original de Yerba Mate.

## Arquitectura del Proyecto

El sistema está compuesto por las siguientes piezas clave, todas contenidas en el directorio `poc_frigorifico/`:

*   **Backend (FastAPI):** Provee una API REST para interactuar con la simulación, gestionar la base de datos y servir la interfaz gráfica. El punto de entrada principal es `main.py`.
*   **Base de Datos (SQLite):** Toda la información persistente, incluyendo el historial de temperaturas (telemetría), logs del sistema y la trazabilidad de tropas de carne, se almacena localmente en un archivo SQLite llamado `frigorifico.db`. Este archivo se crea automáticamente al iniciar el sistema (gestionado en `database.py`).
*   **Simulador Físico/Termodinámico:** El archivo `simulator.py` contiene los modelos matemáticos que calculan el comportamiento térmico de 5 cámaras frigoríficas distintas (Oreo, Mantenimiento, Túnel de Congelado, Cámara de Congelados y Sala de Desposte), tomando en cuenta factores como el aislamiento, el estado de las puertas y la carga térmica de la carne.
*   **Capa de Comunicaciones Industriales:** El archivo `comms.py` simula la conexión con hardware real (PLCs, sensores) mediante protocolos industriales como **Modbus TCP, OPC UA y MQTT**.
*   **Frontend (React + Tailwind CSS):** La interfaz de usuario es una aplicación de una sola página (SPA) construida con React (usando scripts CDN para no requerir un proceso de *build* con Node) y estilizada con Tailwind CSS. Se encuentra en `frontend/index.html`.

## Funcionalidades Principales

1.  **Modos de Operación:**
    *   **Simulador:** El sistema funciona de manera puramente teórica, ideal para planeamiento y análisis ("What-if").
    *   **Gemelo Digital:** El sistema se "conecta" (simuladamente) a la planta real. Empieza a recibir datos de sensores (con ruido) a través de los protocolos industriales.
2.  **Detección de Fallas por Divergencia:** En el modo "Gemelo", el sistema calcula y muestra en paralelo el "Modelo Teórico" (termodinámica pura) y la "Temperatura del Sensor (Real)". Si la diferencia entre ambos supera los 3°C, el sistema infiere una anomalía física (ej. fuga de gas, falla de compresor) y lanza una alerta visual.
3.  **Consola SCADA:** Permite enviar comandos a los actuadores de la planta (ej. abrir/cerrar puertas) utilizando los protocolos de comunicación configurados.
4.  **Trazabilidad:** Permite ingresar tropas de carne al sistema, lo cual afecta la carga térmica de las cámaras correspondientes.

## Almacenamiento de Datos

Todos los datos se guardan en el archivo **`poc_frigorifico/frigorifico.db`**.
*   **Tabla `temperatura_log`:** Almacena el historial de las temperaturas registradas en cada cámara a lo largo del tiempo.
*   **Tabla `tropas`:** Almacena el registro de los lotes (tropas) de carne ingresados, su peso y en qué cámara se encuentran.

## Instrucciones de Uso

Para ejecutar este PoC, se requieren las siguientes dependencias de Python (listadas en `requirements.txt` en la raíz del repo, o se pueden instalar manualmente):

```bash
pip install fastapi uvicorn aiosqlite
```

Para iniciar el servidor:

```bash
cd poc_frigorifico
uvicorn main:app --port 8080 --reload
```

Una vez iniciado, abre un navegador web y navega a: **http://localhost:8080**
