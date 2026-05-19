# core/yerba_modbus_server.py
import asyncio

# --- Compatibility layer for different pymodbus versions ---
try:
    # pymodbus >= 3.10
    from pymodbus.datastore import (
        ModbusServerContext,
        ModbusDeviceContext,
        ModbusSequentialDataBlock,
    )
    _CTX_CLS = ModbusDeviceContext
    _SERVER_CTX_PARAM = "devices"
except ImportError:  # pragma: no cover - fallback for older versions
    # pymodbus < 3.10
    from pymodbus.datastore import (
        ModbusServerContext,
        ModbusSlaveContext,
        ModbusSequentialDataBlock,
    )
    _CTX_CLS = ModbusSlaveContext
    _SERVER_CTX_PARAM = "slaves"

try:
    from pymodbus.device import ModbusDeviceIdentification  # pymodbus < 3.10
except ImportError:
    from pymodbus.pdu.device import ModbusDeviceIdentification  # pymodbus >= 3.10

# StartAsyncTcpServer is available from pymodbus.server in 3.x
# (In very old 2.x, the path was different; this code targets 3.x series.)
from pymodbus.server import StartAsyncTcpServer


class YerbaModbusServer:
    def __init__(self, simulador, config):
        self.simulador = simulador
        self.ip = config.get("ip", "127.0.0.1")
        self.port = config.get("port", 5020)
        self.rate = config.get("rate", 1.0)  # seconds
        self.context = self._build_context()

    def _build_context(self):
        """
        Crea 7 contextos (0..6): 0 zapecado, 1 secado, 2 canchado, 3-6 cámaras.
        Compatible con pymodbus <3.10 (slaves=) y >=3.10 (devices=).
        """
        contexts = {}
        for i in range(7):
            contexts[i] = _CTX_CLS(
                di=ModbusSequentialDataBlock(0, [0] * 10),
                co=ModbusSequentialDataBlock(0, [0] * 10),
                hr=ModbusSequentialDataBlock(0, [0] * 64),
                ir=ModbusSequentialDataBlock(0, [0] * 64),
            )

        # Construir ModbusServerContext usando el nombre de parámetro correcto
        kwargs = {"single": False, _SERVER_CTX_PARAM: contexts}
        return ModbusServerContext(**kwargs)

    async def _update_loop(self):
        while True:
            try:
                self._update_registers()
            except Exception as e:  # pragma: no cover
                print("Error en Modbus update:", e)
            await asyncio.sleep(self.rate)

    def _update_registers(self):
        """
        Escribe en Holding Registers (func_code=3) de cada unidad.
        Los *int()* son simples escalados para enteros.
        Ajusta índices y longitudes según tu simulador real.
        """
        # Unidad 0: Zapecado
        try:
            zap = self.simulador.zapecado
            self.context[0].setValues(3, 0, [
                int(zap.temperatura * 10),
                int(zap.velocidad_tambor),
                int(zap.velocidad_chip),
                int(getattr(zap, "estado_alimentacion", 0)),
            ])
        except Exception:
            pass

        # Unidad 1: Secado
        try:
            sec = self.simulador.secado
            self.context[1].setValues(3, 0, [
                int(sec.temperatura * 10),
                int(sec.humedad * 10),
                int(sec.velocidad_aire * 10),
                int(getattr(sec, "estado", 0)),
            ])
        except Exception:
            pass

        # Unidad 2: Canchado
        try:
            can = self.simulador.canchado
            self.context[2].setValues(3, 0, [
                int(can.velocidad_molino * 10),
                int(can.tamano_particula * 10),
                int(getattr(can, "estado", 0)),
            ])
        except Exception:
            pass

        # Unidades 3..6: Cámaras
        try:
            for i, cam in enumerate(self.simulador.camaras):
                if i >= 4:
                    break
                self.context[i + 3].setValues(3, 0, [
                    int(cam.temperatura * 10),
                    int(cam.humedad * 10),
                    int(cam.co2),
                    int(cam.temperatura_obj * 10),
                    int(cam.humedad_obj * 10),
                    int(cam.co2_obj),
                    int(cam.carga_kg),
                    int(cam.tiempo_maduracion * 100),
                    int(getattr(cam, "ventilador", 0)),
                ])
        except Exception:
            pass

    async def start_async(self):
        identity = ModbusDeviceIdentification()
        identity.VendorName = "YerbaSim"
        identity.ProductCode = "YS01"
        identity.VendorUrl = "https://ciudad-electrica.com.ar"
        identity.ProductName = "Simulador Yerba Mate"
        identity.ModelName = "YerbaTwin"
        identity.MajorMinorRevision = "1.0"

        # Loop de actualización
        asyncio.create_task(self._update_loop())

        await StartAsyncTcpServer(
            context=self.context,
            identity=identity,
            address=(self.ip, self.port),
        )

    def start(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.start_async())
        loop.run_forever()
