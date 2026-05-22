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
        """Avanza la simulación dt minutos."""
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
        for camara in self.camaras:
            camara.tick(dt)

    def estado_global(self) -> List[dict]:
        return [c.estado() for c in self.camaras]

if __name__ == "__main__":
    print("--- Simulador Frigorífico: 5 Cámaras Principales ---")
    simulador = FrigorificoSimulator()

    print("Simulando primeros 15 minutos (1 tick = 1 minuto simulado)...")
    for minuto in range(1, 16):
        # Eventos aleatorios
        if minuto == 5:
            print("\n>> [EVENTO] Comienza el turno de desposte (abren puertas).")
            simulador.sala_desposte.puerta_abierta = True
            simulador.camara_oreo.puerta_abierta = True

        if minuto == 10:
            print("\n>> [EVENTO] Se cierra la cámara de oreo.")
            simulador.camara_oreo.puerta_abierta = False

        simulador.tick()
        estados = simulador.estado_global()

        # Mostrar resumen en línea
        resumen = " | ".join([f"{e['nombre'][:4]}: {e['temp_actual']}°C" for e in estados])
        print(f"Min {minuto:02d} -> {resumen}")
        time.sleep(0.2)
