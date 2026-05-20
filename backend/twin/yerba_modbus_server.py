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
        Crea contextos: 0 zapecado, 1 secado, 2 canchado, 3..14 cámaras (hasta 12),
        20..22 escenarios what-if 1..3.
        Compatible con pymodbus <3.10 (slaves=) y >=3.10 (devices=).
        """
        contexts = {}
        # Etapas + cámaras
        for i in range(15):  # 3 etapas + 12 cámaras
            contexts[i] = _CTX_CLS(
                di=ModbusSequentialDataBlock(0, [0] * 10),
                co=ModbusSequentialDataBlock(0, [0] * 10),
                hr=ModbusSequentialDataBlock(0, [0] * 64),
                ir=ModbusSequentialDataBlock(0, [0] * 64),
            )
        # What-if scenarios (unit IDs 20, 21, 22)
        for i in (20, 21, 22):
            contexts[i] = _CTX_CLS(
                di=ModbusSequentialDataBlock(0, [0] * 10),
                co=ModbusSequentialDataBlock(0, [0] * 10),
                hr=ModbusSequentialDataBlock(0, [0] * 16),
                ir=ModbusSequentialDataBlock(0, [0] * 16),
            )
        # Unit 100: globales (aceleración, throughput)
        contexts[100] = _CTX_CLS(
            di=ModbusSequentialDataBlock(0, [0] * 4),
            co=ModbusSequentialDataBlock(0, [0] * 4),
            hr=ModbusSequentialDataBlock(0, [0] * 8),
            ir=ModbusSequentialDataBlock(0, [0] * 8),
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

    def _apply_external_writes(self):
        """Detecta escrituras externas en holding regs / coils y aplica al simulador.

        Para Modbus, comparamos con _last_writes (lo que NOSOTROS escribimos en
        el ciclo anterior). Si hay diferencia = un cliente Modbus externo escribió.
        """
        if not hasattr(self, "_last_writes"):
            self._last_writes = {}
        lw = self._last_writes

        def reg(slave, addr):
            try:
                return self.context[slave].getValues(3, addr, count=1)[0]
            except Exception:
                return None

        def coil(slave, addr):
            try:
                return bool(self.context[slave].getValues(1, addr, count=1)[0])
            except Exception:
                return None

        def diff(key, current, applier):
            prev = lw.get(key)
            if prev is None or current is None:
                return
            if current == prev:
                return
            try:
                applier(current)
            except Exception:
                pass

        # Zapecado (unit 0): coils fallas + reg 5 (T_obj manual)
        diff("zap_falla_q",  coil(0, 0), lambda v: self.simulador.set_zapecado(falla_quemador=v))
        diff("zap_falla_m",  coil(0, 1), lambda v: self.simulador.set_zapecado(falla_motor_tambor=v))
        diff("zap_t_obj",    reg(0, 5),  lambda v: self.simulador.set_zapecado(temperatura_obj=(None if v == 0 else v / 10.0)))
        diff("zap_v_chip",   reg(0, 2),  lambda v: self.simulador.set_zapecado(velocidad_chip=float(v)))
        diff("zap_v_tambor", reg(0, 1),  lambda v: self.simulador.set_zapecado(velocidad_tambor=float(v)))

        # Secado (unit 1)
        diff("sec_falla_v",  coil(1, 0), lambda v: self.simulador.set_secado(falla_ventilador=v))
        diff("sec_falla_s",  coil(1, 1), lambda v: self.simulador.set_secado(falla_serpentin=v))
        diff("sec_t_obj",    reg(1, 4),  lambda v: self.simulador.set_secado(temperatura_obj=v / 10.0))
        diff("sec_h_obj",    reg(1, 5),  lambda v: self.simulador.set_secado(humedad_obj=v / 10.0))
        diff("sec_v_aire",   reg(1, 2),  lambda v: self.simulador.set_secado(velocidad_aire=v / 10.0))
        diff("sec_pos_cal",  reg(1, 7),  lambda v: self.simulador.set_secado(posicion_calefactor=v / 10.0))

        # Canchado (unit 2)
        diff("can_falla_m",  coil(2, 0), lambda v: self.simulador.set_canchado(falla_motor=v))
        diff("can_rod",      coil(2, 1), lambda v: self.simulador.set_canchado(rodamiento_caliente=v))
        diff("can_part_obj", reg(2, 3),  lambda v: self.simulador.set_canchado(tamano_particula_obj=(None if v == 0 else v / 100.0)))
        diff("can_rpm",      reg(2, 0),  lambda v: self.simulador.set_canchado(velocidad_molino=v / 10.0))

        # Globales (unit 100)
        diff("sim_acel",     reg(100, 0), lambda v: setattr(self.simulador, "aceleracion", v / 10.0))
        diff("sim_throughput", reg(100, 1), lambda v: setattr(self.simulador, "throughput_kgh", float(v)))

        # Cámaras (unit 3..14)
        for i in range(min(12, len(self.simulador.camaras))):
            u = i + 3
            diff(f"cam{i}_falla_v", coil(u, 0), lambda v, ii=i: self.simulador.set_camara(ii, falla_ventilador=v))
            diff(f"cam{i}_fuga",    coil(u, 1), lambda v, ii=i: self.simulador.set_camara(ii, fuga_vapor=v))
            diff(f"cam{i}_puerta",  coil(u, 2), lambda v, ii=i: self.simulador.set_camara(ii, puerta_abierta=v))
            diff(f"cam{i}_t_obj",   reg(u, 3),  lambda v, ii=i: self.simulador.set_camara(ii, temperatura_obj=v / 10.0))
            diff(f"cam{i}_h_obj",   reg(u, 4),  lambda v, ii=i: self.simulador.set_camara(ii, humedad_obj=v / 10.0))
            diff(f"cam{i}_vap_on",  reg(u, 9),  lambda v, ii=i: self.simulador.set_camara(ii, vapor_activo=bool(v)))
            diff(f"cam{i}_vap_kgh", reg(u, 10), lambda v, ii=i: self.simulador.set_camara(ii, vapor_caudal_kgh=v / 10.0))

    def _update_registers(self):
        """Bidireccional: lee escrituras externas, luego publica el estado."""
        # PASO 1: detectar escrituras externas → simulador
        self._apply_external_writes()
        # PASO 2: publicar estado del simulador → clientes
        """
        Escribe en Holding Registers (func_code=3) y Coils (func_code=1) de cada unidad.
        Convención de escalado: enteros = valor*10 (excepto carga/co2 sin decimales).

        Unit 0 Zapecado HR:
          [0] T actual×10 · [1] vel.tambor · [2] vel.chip · [3] alim
          [4] T_SP×10 (efectivo) · [5] T_obj manual×10 (0=auto) · [6] tau×10
        Unit 0 Coils: [0] falla_quemador · [1] falla_motor_tambor

        Unit 1 Secado HR:
          [0] T×10 · [1] H×10 · [2] vel.aire×10 · [3] estado
          [4] T_obj×10 · [5] H_obj×10 · [6] tau_t×10
        Unit 1 Coils: [0] falla_ventilador · [1] falla_serpentin

        Unit 2 Canchado HR:
          [0] vel.molino×10 · [1] particula×100 · [2] estado
          [3] particula_obj×100 · [4] particula_sp_efectivo×100 · [5] tau_p×10
        Unit 2 Coils: [0] falla_motor · [1] rodamiento_caliente

        Unit 3..14 Cámaras HR:
          [0] T×10 · [1] H×10 · [2] CO2 · [3] T_obj×10 · [4] H_obj×10 · [5] CO2_obj
          [6] carga · [7] dias×100 · [8] vent · [9] vapor_on · [10] vapor_kgh×10
          [11] vapor_T_sp×10 · [12] vapor_H_sp×10 · [13] tau
        Unit 3..14 Coils: [0] falla_ventilador · [1] fuga_vapor · [2] puerta_abierta

        Unit 100 HR (simulación global): [0] aceleracion×10 · [1] throughput_kgh
        """
        # Unidad 0: Zapecado
        try:
            zap = self.simulador.zapecado
            self.context[0].setValues(3, 0, [
                int(zap.temperatura * 10),
                int(zap.velocidad_tambor),
                int(zap.velocidad_chip),
                int(getattr(zap, "estado_alimentacion", 0)),
                int(zap.get_setpoint() * 10),
                int((zap.temperatura_obj or 0) * 10),
                int(zap.tau * 10),
                # PID interno
                int(zap.pid.enabled),
                int(zap.pid.kp * 100),
                int(zap.pid.ki * 100),
                int(zap.pid.kd * 100),
                int(zap.pid.last_output * 10),
                # Manipuladas reales
                int(zap.vel_chip_real() * 10),
                int(zap.vel_tambor_real() * 10),
            ])
            self.context[0].setValues(1, 0, [
                int(zap.falla_quemador), int(zap.falla_motor_tambor),
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
                int(sec.temperatura_obj * 10),
                int(sec.humedad_obj * 10),
                int(sec.tau_t * 10),
                # Manipulada: posición calefactor (0-100%)
                int(sec.posicion_calefactor * 10),
                # PID T
                int(sec.pid_t.enabled),
                int(sec.pid_t.kp * 100),
                int(sec.pid_t.ki * 100),
                int(sec.pid_t.last_output * 10),
                # PID H
                int(sec.pid_h.enabled),
                int(sec.pid_h.kp * 100),
                int(sec.pid_h.ki * 100),
                int(sec.pid_h.last_output * 10),
                # Manipulada real
                int(sec.pos_cal_real() * 10),
                int(sec.vel_aire_real() * 10),
            ])
            self.context[1].setValues(1, 0, [
                int(sec.falla_ventilador), int(sec.falla_serpentin),
            ])
        except Exception:
            pass

        # Unidad 2: Canchado
        try:
            can = self.simulador.canchado
            self.context[2].setValues(3, 0, [
                int(can.velocidad_molino * 10),
                int(can.tamano_particula * 100),
                int(getattr(can, "estado", 0)),
                int((can.tamano_particula_obj or 0) * 100),
                int(can.get_setpoint() * 100),
                int(can.tau_p * 10),
                # PID
                int(can.pid.enabled),
                int(can.pid.kp * 100),
                int(can.pid.ki * 100),
                int(can.pid.last_output * 10),
                # rpm real
                int(can.vel_molino_real() * 10),
            ])
            self.context[2].setValues(1, 0, [
                int(can.falla_motor), int(can.rodamiento_caliente),
            ])
        except Exception:
            pass

        # Unidades 3..14: Cámaras (hasta 12). Si hay menos, se ceran las extra.
        try:
            for i in range(12):
                if i < len(self.simulador.camaras):
                    cam = self.simulador.camaras[i]
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
                        int(getattr(cam, "vapor_activo", 0)),
                        int(getattr(cam, "vapor_caudal_kgh", 0) * 10),
                        int(getattr(cam, "vapor_setpoint_temp", 0) * 10),
                        int(getattr(cam, "vapor_setpoint_hum", 0) * 10),
                        int(getattr(cam, "tau", 600)),
                    ])
                    self.context[i + 3].setValues(1, 0, [
                        int(cam.falla_ventilador), int(cam.fuga_vapor), int(cam.puerta_abierta),
                    ])
                else:
                    self.context[i + 3].setValues(3, 0, [0] * 14)
                    self.context[i + 3].setValues(1, 0, [0, 0, 0])
        except Exception:
            pass

        # Unidad 100: Globales (aceleración + throughput)
        try:
            self.context[100].setValues(3, 0, [
                int(self.simulador.aceleracion * 10),
                int(self.simulador.throughput_kgh),
            ])
        except Exception:
            pass

        # PASO 3: actualizar cache _last_writes con lo que acabamos de publicar
        try:
            lw = self._last_writes
            zap = self.simulador.zapecado
            sec = self.simulador.secado
            can = self.simulador.canchado
            lw["zap_falla_q"] = bool(zap.falla_quemador)
            lw["zap_falla_m"] = bool(zap.falla_motor_tambor)
            lw["zap_t_obj"] = int((zap.temperatura_obj or 0) * 10)
            lw["zap_v_chip"] = int(zap.velocidad_chip)
            lw["zap_v_tambor"] = int(zap.velocidad_tambor)
            lw["sec_falla_v"] = bool(sec.falla_ventilador)
            lw["sec_falla_s"] = bool(sec.falla_serpentin)
            lw["sec_t_obj"] = int(sec.temperatura_obj * 10)
            lw["sec_h_obj"] = int(sec.humedad_obj * 10)
            lw["sec_v_aire"] = int(sec.velocidad_aire * 10)
            lw["sec_pos_cal"] = int(sec.posicion_calefactor * 10)
            lw["can_falla_m"] = bool(can.falla_motor)
            lw["can_rod"] = bool(can.rodamiento_caliente)
            lw["can_part_obj"] = int((can.tamano_particula_obj or 0) * 100)
            lw["can_rpm"] = int(can.velocidad_molino * 10)
            lw["sim_acel"] = int(self.simulador.aceleracion * 10)
            lw["sim_throughput"] = int(self.simulador.throughput_kgh)
            for i, cam in enumerate(self.simulador.camaras):
                lw[f"cam{i}_falla_v"] = bool(cam.falla_ventilador)
                lw[f"cam{i}_fuga"] = bool(cam.fuga_vapor)
                lw[f"cam{i}_puerta"] = bool(cam.puerta_abierta)
                lw[f"cam{i}_t_obj"] = int(cam.temperatura_obj * 10)
                lw[f"cam{i}_h_obj"] = int(cam.humedad_obj * 10)
                lw[f"cam{i}_vap_on"] = int(getattr(cam, "vapor_activo", 0))
                lw[f"cam{i}_vap_kgh"] = int(getattr(cam, "vapor_caudal_kgh", 0) * 10)
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
