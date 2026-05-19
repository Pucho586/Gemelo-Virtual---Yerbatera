"""Recetas industriales (presets de producto final)."""
from typing import Any, Dict, List

# Cada receta define setpoints para las 4 etapas + duración objetivo de maduración.
DEFAULT_RECIPES: List[Dict[str, Any]] = [
    {
        "id": "suave",
        "nombre": "Yerba Suave (6 meses)",
        "descripcion": "Perfil suave, baja amargura. Maduración corta.",
        "color": "#86EFAC",
        "zapecado": {"target_temp": 480, "velocidad_tambor": 18, "velocidad_chip": 40},
        "secado": {"target_temp": 95, "target_humedad": 8.0, "velocidad_aire": 3.0},
        "canchado": {"target_particula": 4.0, "velocidad_molino": 70},
        "camaras": {
            "temperatura_objetivo": 30,
            "humedad_objetivo": 75,
            "co2_objetivo": 2800,
            "dias_maduracion": 180,
        },
    },
    {
        "id": "fuerte",
        "nombre": "Yerba Fuerte (24 meses)",
        "descripcion": "Sabor intenso, maduración prolongada para máxima estabilización.",
        "color": "#FCA5A5",
        "zapecado": {"target_temp": 520, "velocidad_tambor": 20, "velocidad_chip": 55},
        "secado": {"target_temp": 100, "target_humedad": 7.0, "velocidad_aire": 4.5},
        "canchado": {"target_particula": 3.0, "velocidad_molino": 95},
        "camaras": {
            "temperatura_objetivo": 32,
            "humedad_objetivo": 78,
            "co2_objetivo": 3200,
            "dias_maduracion": 720,
        },
    },
    {
        "id": "barbacua",
        "nombre": "Yerba Barbacuá (ahumada)",
        "descripcion": "Método tradicional, ahumado lento. Yerba premium.",
        "color": "#FCD34D",
        "zapecado": {"target_temp": 450, "velocidad_tambor": 12, "velocidad_chip": 25},
        "secado": {"target_temp": 70, "target_humedad": 9.0, "velocidad_aire": 1.5},
        "canchado": {"target_particula": 5.0, "velocidad_molino": 55},
        "camaras": {
            "temperatura_objetivo": 28,
            "humedad_objetivo": 72,
            "co2_objetivo": 2600,
            "dias_maduracion": 90,
        },
    },
    {
        "id": "organica",
        "nombre": "Yerba Orgánica Certificada",
        "descripcion": "Estándar orgánico, sin químicos, maduración media.",
        "color": "#93C5FD",
        "zapecado": {"target_temp": 460, "velocidad_tambor": 16, "velocidad_chip": 35},
        "secado": {"target_temp": 90, "target_humedad": 8.5, "velocidad_aire": 2.8},
        "canchado": {"target_particula": 4.0, "velocidad_molino": 68},
        "camaras": {
            "temperatura_objetivo": 30,
            "humedad_objetivo": 72,
            "co2_objetivo": 2900,
            "dias_maduracion": 365,
        },
    },
]


def get_default_recipes() -> List[Dict[str, Any]]:
    return [dict(r) for r in DEFAULT_RECIPES]


def apply_recipe_to_simulator(simulator, recipe: Dict[str, Any]):
    """Aplica todos los setpoints de una receta al simulador."""
    z = recipe.get("zapecado", {})
    s = recipe.get("secado", {})
    c = recipe.get("canchado", {})
    cam = recipe.get("camaras", {})

    simulator.set_zapecado(
        velocidad_tambor=z.get("velocidad_tambor"),
        velocidad_chip=z.get("velocidad_chip"),
    )
    simulator.set_secado(velocidad_aire=s.get("velocidad_aire"))
    simulator.set_canchado(velocidad_molino=c.get("velocidad_molino"))
    for i in range(len(simulator.camaras)):
        simulator.set_camara(
            i,
            temperatura_obj=cam.get("temperatura_objetivo"),
            humedad_obj=cam.get("humedad_objetivo"),
            co2_obj=cam.get("co2_objetivo"),
        )
