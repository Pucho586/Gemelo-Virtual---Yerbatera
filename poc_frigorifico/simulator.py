import time

class CamaraFrio:
    """Modelo físico simplificado de una cámara frigorífica."""
    def __init__(self, nombre: str, temp_objetivo: float, aislamiento_k: float = 0.05, poder_enfriamiento: float = 1.5):
        self.nombre = nombre
        self.temp_objetivo = temp_objetivo

        # Estado actual
        self.temperatura_actual = 15.0 # Empieza a temperatura ambiente (ej: 15°C)
        self.compresor_encendido = True
        self.puerta_abierta = False

        # Constantes térmicas
        self.aislamiento_k = aislamiento_k # Tasa de pérdida de frío (calentamiento)
        self.poder_enfriamiento = poder_enfriamiento # Cuántos grados baja por tick cuando el compresor anda
        self.temp_ambiente = 25.0

    def tick(self, dt: float = 1.0):
        """Avanza la simulación dt minutos."""
        # 1. Pérdida de frío (ganancia de calor del ambiente)
        # Sigue la ley de enfriamiento de Newton: pérdida proporcional a la diferencia de temp.
        tasa_calentamiento = self.aislamiento_k
        if self.puerta_abierta:
            tasa_calentamiento *= 5.0 # Si la puerta está abierta, entra calor mucho más rápido

        delta_temp = (self.temp_ambiente - self.temperatura_actual) * tasa_calentamiento * dt
        self.temperatura_actual += delta_temp

        # 2. Enfriamiento (si el compresor está encendido)
        if self.compresor_encendido:
            self.temperatura_actual -= self.poder_enfriamiento * dt

        # 3. Lógica de control simple (Termostato / Histéresis)
        # Si la temperatura sube 1 grado por encima del objetivo, encendemos
        if self.temperatura_actual > self.temp_objetivo + 1.0:
            self.compresor_encendido = True
        # Si baja hasta el objetivo, apagamos
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

if __name__ == "__main__":
    print("--- Iniciando Prueba de Concepto: Simulador Frigorífico ---")
    camara_oreo = CamaraFrio(nombre="Cámara de Oreo 1", temp_objetivo=2.0)

    print("Simulando primeros 20 minutos (1 tick = 1 minuto simulado)...\n")
    for minuto in range(1, 21):
        # En el minuto 10 alguien abre la puerta
        if minuto == 10:
            print(">> [EVENTO] Operario abre la puerta de la cámara.")
            camara_oreo.puerta_abierta = True

        # En el minuto 13 la cierran
        if minuto == 13:
            print(">> [EVENTO] Operario cierra la puerta.")
            camara_oreo.puerta_abierta = False

        camara_oreo.tick()
        estado = camara_oreo.estado()
        print(f"Minuto {minuto:02d} | Temp: {estado['temp_actual']}°C | Compresor: {estado['compresor']} | Puerta: {estado['puerta']}")
        time.sleep(0.1) # Para verlo en consola
