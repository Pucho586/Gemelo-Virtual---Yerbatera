import time
from typing import Dict, List

class CamaraFrio:
    """Modelo físico simplificado de una cámara frigorífica."""
    def __init__(self, nombre: str, temp_objetivo: float, aislamiento_k: float, poder_enfriamiento: float):
        self.nombre = nombre
        self.temp_objetivo = temp_objetivo

        # Estado físico real (sensores)
        self.temperatura_actual = 15.0

        # Estado teórico del gemelo (lo que debería ser)
        self.temperatura_teorica = 15.0

        self.compresor_encendido = True
        self.puerta_abierta = False

        # Constantes térmicas
        self.aislamiento_k = aislamiento_k
        self.poder_enfriamiento = poder_enfriamiento
        self.temp_ambiente = 25.0

        self.falla_detectada = False

    def _calcular_delta_temp(self, temp_base: float, dt: float) -> float:
        """Calcula el cambio de temperatura basado en las leyes de la termodinámica."""
        tasa_calentamiento = self.aislamiento_k
        if self.puerta_abierta:
            tasa_calentamiento *= 5.0

        delta_temp = (self.temp_ambiente - temp_base) * tasa_calentamiento * dt

        if self.compresor_encendido:
            delta_temp -= self.poder_enfriamiento * dt

        return delta_temp

    def tick(self, dt: float = 1.0, modo: str = "simulador"):
        """Avanza la simulación dt minutos."""

        # 1. El modelo teórico SIEMPRE avanza según la física pura (nuestra expectativa)
        delta_teorico = self._calcular_delta_temp(self.temperatura_teorica, dt)
        self.temperatura_teorica += delta_teorico

        # 2. En modo simulador, la realidad ES la teoría
        if modo == "simulador":
            self.temperatura_actual = self.temperatura_teorica

        # (En modo gemelo, self.temperatura_actual se actualiza desde afuera en aplicar_telemetria)

        # 3. Termostato (control local)
        if self.temperatura_actual > self.temp_objetivo + 1.0:
            self.compresor_encendido = True
        elif self.temperatura_actual <= self.temp_objetivo:
            self.compresor_encendido = False

        # 4. Detección de Fallas (Magia del Gemelo Digital)
        # Si la realidad difiere de la teoría en más de 3°C, hay un problema (ej. motor roto, sensor roto, fuga)
        if abs(self.temperatura_actual - self.temperatura_teorica) > 3.0:
            self.falla_detectada = True
        else:
            self.falla_detectada = False

    def estado(self) -> dict:
        return {
            "nombre": self.nombre,
            "temp_actual": round(self.temperatura_actual, 2),
            "temp_teorica": round(self.temperatura_teorica, 2),
            "temp_objetivo": self.temp_objetivo,
            "compresor": "ON" if self.compresor_encendido else "OFF",
            "puerta": "ABIERTA" if self.puerta_abierta else "CERRADA",
            "falla": self.falla_detectada
        }

class FrigorificoSimulator:
    """Gestiona el conjunto de cámaras del frigorífico."""
    def __init__(self):
        self.modo = "simulador" # "simulador" o "gemelo"

        self.camara_oreo = CamaraFrio("Cámara de Oreo", temp_objetivo=2.0, aislamiento_k=0.08, poder_enfriamiento=2.0)
        self.camara_mantenimiento = CamaraFrio("Mantenimiento", temp_objetivo=0.0, aislamiento_k=0.05, poder_enfriamiento=1.0)
        self.tunel_rapido = CamaraFrio("Túnel de Congelado", temp_objetivo=-30.0, aislamiento_k=0.10, poder_enfriamiento=4.0)
        self.camara_congelados = CamaraFrio("Cámara de Congelados", temp_objetivo=-18.0, aislamiento_k=0.02, poder_enfriamiento=0.8)
        self.sala_desposte = CamaraFrio("Sala de Desposte", temp_objetivo=10.0, aislamiento_k=0.15, poder_enfriamiento=1.5)

        self.camaras: List[CamaraFrio] = [
            self.camara_oreo,
            self.camara_mantenimiento,
            self.tunel_rapido,
            self.camara_congelados,
            self.sala_desposte
        ]

    def tick(self, dt: float = 1.0):
        for camara in self.camaras:
            camara.tick(dt, self.modo)

    def aplicar_telemetria(self, telemetria: Dict[str, float]):
        """Aplica datos reales provenientes de sensores externos."""
        if self.modo != "gemelo":
            return

        for camara in self.camaras:
            if camara.nombre in telemetria:
                camara.temperatura_actual = telemetria[camara.nombre]

    def estado_global(self) -> List[dict]:
        return [c.estado() for c in self.camaras]
