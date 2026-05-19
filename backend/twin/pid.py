"""Controlador PID genérico con anti-windup y switch ON/OFF.

Pensado para que cada etapa tenga uno o más PIDs internos que pueden
quedar desactivados (control manual del operador o desde PLC externo) o
activados (auto-tuning a un setpoint).

Convención:
- pv: process variable (medida actual)
- sp: setpoint (objetivo)
- u:  output (manipulated variable) → vel.chips, posición calefactor, caudal vapor, etc.

Salida saturada entre out_min y out_max. La integral se acota cuando la
salida está saturada (anti-windup clamping).
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PID:
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    out_min: float = 0.0
    out_max: float = 100.0
    enabled: bool = False
    sp: float = 0.0
    integral: float = 0.0
    prev_error: float = 0.0
    last_output: float = 0.0
    direct_action: bool = True  # True: salida sube si pv < sp (e.g., calefactor)

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0

    def step(self, pv: float, dt: float) -> Optional[float]:
        """Una iteración. Devuelve la salida sugerida (manipulada) o None si OFF."""
        if not self.enabled:
            return None
        error = (self.sp - pv) if self.direct_action else (pv - self.sp)
        # Predicción P
        p_term = self.kp * error
        # Predicción D (sobre error)
        d_term = self.kd * (error - self.prev_error) / max(dt, 0.001)
        # Predicción I tentativa
        tentative_integral = self.integral + error * dt
        i_term = self.ki * tentative_integral
        out = p_term + i_term + d_term
        # Anti-windup clamping: si la salida saturó, no acumulamos integral
        saturated = False
        if out > self.out_max:
            out = self.out_max
            saturated = True
        elif out < self.out_min:
            out = self.out_min
            saturated = True
        if not saturated:
            self.integral = tentative_integral
        self.prev_error = error
        self.last_output = out
        return out

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "kp": self.kp, "ki": self.ki, "kd": self.kd,
            "sp": self.sp,
            "out_min": self.out_min, "out_max": self.out_max,
            "integral": round(self.integral, 4),
            "last_output": round(self.last_output, 3),
            "direct_action": self.direct_action,
        }

    def update_params(self, *, kp=None, ki=None, kd=None, sp=None,
                      enabled=None, out_min=None, out_max=None,
                      direct_action=None, reset=False):
        if kp is not None: self.kp = float(kp)
        if ki is not None: self.ki = float(ki)
        if kd is not None: self.kd = float(kd)
        if sp is not None: self.sp = float(sp)
        if out_min is not None: self.out_min = float(out_min)
        if out_max is not None: self.out_max = float(out_max)
        if direct_action is not None: self.direct_action = bool(direct_action)
        if enabled is not None:
            new_enabled = bool(enabled)
            # Al transicionar OFF→ON, reset para evitar saltos
            if new_enabled and not self.enabled:
                self.reset()
            self.enabled = new_enabled
        if reset:
            self.reset()
