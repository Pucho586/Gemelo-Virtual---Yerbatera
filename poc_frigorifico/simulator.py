import time
from typing import Dict, List

class CamaraFrio:
    """Modelo físico simplificado de una cámara frigorífica."""
    def __init__(self, nombre: str, temp_objetivo: float, aislamiento_k: float, poder_enfriamiento: float):
        self.nombre = nombre
        self.temp_objetivo = temp_objetivo

        # Estado actual
        self.temperatura_actual = 15.0 # Empieza a temperatura ambiente
        self.compresor_encendido = True
        self.puerta_abierta = False

        # Constantes térmicas
        self.aislamiento_k = aislamiento_k
        self.poder_enfriamiento = poder_enfriamiento
        self.temp_ambiente = 25.0

    def tick(self, dt: float = 1.0):
        """Avanza la simulación dt minutos (Modo Simulador)."""
        tasa_calentamiento = self.aislamiento_k
        if self.puerta_abierta:
            tasa_calentamiento *= 5.0

        delta_temp = (self.temp_ambiente - self.temperatura_actual) * tasa_calentamiento * dt
        self.temperatura_actual += delta_temp

        if self.compresor_encendido:
            self.temperatura_actual -= self.poder_enfriamiento * dt

        # Termostato
        if self.temperatura_actual > self.temp_objetivo + 1.0:
            self.compresor_encendido = True
        elif self.temperatura_actual <= self.temp_objetivo:
            self.compresor_encendido = False

    def estado(self) -> dict:
        return {
            "nombre": self.nombre,
            "temp_actual": round(self.temperatura_actual, 2),
            "temp_objetivo": self.temp_objetivo,
            "compresor": "ON" if self.compresor_encendido else "OFF",
            "puerta": "ABIERTA" if self.puerta_abierta else "CERRADA"
        }

class FrigorificoSimulator:
    """Gestiona el conjunto de cámaras del frigorífico."""
    def __init__(self):
        self.modo = "simulador" # "simulador" o "gemelo"

        # 1. Oreo: Enfriamiento inicial, mucha carga térmica (alta potencia).
        self.camara_oreo = CamaraFrio("Cámara de Oreo", temp_objetivo=2.0, aislamiento_k=0.08, poder_enfriamiento=2.0)

        # 2. Mantenimiento: Conservación de media res fresca.
        self.camara_mantenimiento = CamaraFrio("Mantenimiento", temp_objetivo=0.0, aislamiento_k=0.05, poder_enfriamiento=1.0)

        # 3. Túnel Rápido: Congelación extrema muy rápida.
        self.tunel_rapido = CamaraFrio("Túnel de Congelado", temp_objetivo=-30.0, aislamiento_k=0.10, poder_enfriamiento=4.0)

        # 4. Congelados: Depósito a largo plazo.
        self.camara_congelados = CamaraFrio("Cámara de Congelados", temp_objetivo=-18.0, aislamiento_k=0.02, poder_enfriamiento=0.8)

        # 5. Desposte: Sala de trabajo, temperatura moderada.
        self.sala_desposte = CamaraFrio("Sala de Desposte", temp_objetivo=10.0, aislamiento_k=0.15, poder_enfriamiento=1.5)

        self.camaras: List[CamaraFrio] = [
            self.camara_oreo,
            self.camara_mantenimiento,
            self.tunel_rapido,
            self.camara_congelados,
            self.sala_desposte
        ]

    def tick(self, dt: float = 1.0):
        # Si está en modo "gemelo", la física se pausa y los datos vienen de afuera.
        if self.modo == "simulador":
            for camara in self.camaras:
                camara.tick(dt)

    def aplicar_telemetria(self, telemetria: Dict[str, float]):
        """Aplica datos reales provenientes de sensores externos (Modbus/OPC UA/MQTT)."""
        if self.modo != "gemelo":
            return

        for camara in self.camaras:
            if camara.nombre in telemetria:
                camara.temperatura_actual = telemetria[camara.nombre]

    def estado_global(self) -> List[dict]:
        return [c.estado() for c in self.camaras]
