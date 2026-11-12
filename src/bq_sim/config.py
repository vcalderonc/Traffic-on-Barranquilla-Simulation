"""Rutas del proyecto y parámetros globales del modelo de simulación.

Todos los valores numéricos que gobiernan el modelo están aquí para que se puedan
citar en el informe y cambiar en un solo lugar.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DATOS_OSM = RAIZ / "data" / "osm"
DIR_SUMO = RAIZ / "sumo"
DIR_MODELOS = RAIZ / "modelos"
DIR_SALIDAS = RAIZ / "salidas"
DIR_VISOR = RAIZ / "visor"

OSM_CRUDO = DATOS_OSM / "malecon_raw.osm"
OSM_RED = DATOS_OSM / "barranquilla_malecon.osm.gz"
RED_SUMO = DIR_SUMO / "barranquilla.net.xml.gz"
TIPOS_VEH = DIR_SUMO / "vtypes.add.xml"
RUTAS_FONDO = DIR_SUMO / "trafico_fondo.rou.xml.gz"
RUTAS_CORREDORES = DIR_SUMO / "corredores.rou.xml"
PEATONES_OD = DIR_SUMO / "peatones_od.json"   # pares origen-destino a pie (los lanza MundoSUMO)
CONFIG_SUMO = DIR_SUMO / "barranquilla.sumocfg"

# Recuadro geográfico (sur, oeste, norte, este): Gran Malecón del Río (de la Ventana de
# Campeones a la Unidad Funcional 3), Vía 40, Buenavista, Plaza del Parque, Ventana al Mundo,
# Av. del Río, Av. Calle 72, Calle 76-84, Carreras 50-54.
BBOX = (10.995, -74.838, 11.036, -74.770)

# Límite urbano en Colombia (Ley 2251 de 2022): 50 km/h salvo señal que indique otro.
VEL_URBANA_MS = 50 / 3.6
VEL_VIA40_MS = 60 / 3.6

PASO_SIM_S = 0.25          # paso de integración de SUMO (s)
G = 9.81


def sumo_home() -> Path:
    """Ubicación de SUMO: variable SUMO_HOME o el paquete pip ``eclipse-sumo``."""
    if os.environ.get("SUMO_HOME"):
        return Path(os.environ["SUMO_HOME"])
    import sumo  # paquete eclipse-sumo

    return Path(sumo.SUMO_HOME)


def binario(nombre: str) -> str:
    """Ruta a un ejecutable de SUMO (sumo, sumo-gui, netconvert, duarouter...)."""
    exe = nombre + (".exe" if os.name == "nt" else "")
    ruta = sumo_home() / "bin" / exe
    return str(ruta) if ruta.exists() else nombre


@dataclass
class Clima:
    """Condición ambiental de un episodio: afecta percepción y adherencia."""

    nombre: str
    mu: float              # coeficiente de fricción llanta-pavimento
    alcance_m: float       # alcance efectivo de los sensores
    ruido: float           # factor multiplicador del ruido de medición
    p_omision: float       # probabilidad base de no detectar un objeto en un ciclo


CLIMAS = {
    "despejado": Clima("despejado", mu=0.80, alcance_m=90.0, ruido=1.0, p_omision=0.03),
    "lluvia": Clima("lluvia", mu=0.45, alcance_m=55.0, ruido=2.0, p_omision=0.10),
    "noche": Clima("noche", mu=0.75, alcance_m=45.0, ruido=1.6, p_omision=0.12),
}

# Hora del día a la que corresponde cada clima "fijo" (para el visor y el modo en vivo)
HORA_CLIMA = {"despejado": 15.0, "lluvia": 15.0, "noche": 21.5}


def luminosidad(hora: float) -> float:
    """Luz natural de 0 (noche) a 1 (día) en Barranquilla (11° N: amanece ~5:50, oscurece ~18:20).

    Rampas suaves de amanecer (5:20-6:40) y atardecer (17:30-18:50).
    """
    import math

    h = hora % 24.0

    def rampa(x, a, b):
        t = min(1.0, max(0.0, (x - a) / (b - a)))
        return 0.5 - 0.5 * math.cos(math.pi * t)

    return rampa(h, 5.33, 6.67) * (1.0 - rampa(h, 17.5, 18.83))


def clima_dinamico(hora: float, lluvia: bool) -> Clima:
    """Clima efectivo según la hora (luz) y la lluvia: interpola entre día y noche.

    Coincide con los climas fijos en los extremos: a mediodía sin lluvia es
    ``despejado``; de noche sin lluvia es ``noche``; a mediodía con lluvia es ``lluvia``.
    Lluvia de noche suma ambas degradaciones (lo peor de los dos mundos).
    """
    luz = luminosidad(hora)
    dia, noche = CLIMAS["despejado"], CLIMAS["noche"]
    alcance = noche.alcance_m + luz * (dia.alcance_m - noche.alcance_m)
    ruido = noche.ruido + luz * (dia.ruido - noche.ruido)
    p_om = noche.p_omision + luz * (dia.p_omision - noche.p_omision)
    mu = noche.mu + luz * (dia.mu - noche.mu)
    nombre = "día" if luz > 0.95 else "noche" if luz < 0.05 else ("amanecer" if hora % 24 < 12 else "atardecer")
    if lluvia:
        ll = CLIMAS["lluvia"]
        alcance *= ll.alcance_m / dia.alcance_m
        ruido *= ll.ruido / dia.ruido
        p_om = 1.0 - (1.0 - p_om) * (1.0 - ll.p_omision)
        mu = ll.mu
        nombre = f"lluvia ({nombre})"
    return Clima(nombre, mu=round(mu, 3), alcance_m=round(alcance, 1), ruido=round(ruido, 3),
                 p_omision=round(p_om, 3))


@dataclass
class Recompensas:
    """Función de recompensa (reward shaping) del documento Stack Tech."""

    choque: float = -100.0
    casi_choque: float = -10.0       # TTC mínimo < 1 s (una vez por evento)
    pare: float = -20.0              # cruzar una señal de PARE sin detenerse
    semaforo_rojo: float = -20.0
    frenada_brusca: float = -0.1     # por paso con desaceleración > 50 % de la máxima
    exceso_velocidad: float = -0.05  # por paso por encima del límite + 5 %
    intervencion: float = -1.0       # el guardrail o el instructor tuvo que intervenir
    progreso: float = 0.10           # por paso a la velocidad límite (proporcional)
    llegada: float = 10.0
    lento_sin_motivo: float = -0.03  # por paso por debajo del 40 % del límite sin motivo


@dataclass
class ParamEventos:
    """Tasas de los eventos estocásticos que se generan frente al vehículo autónomo."""

    tasa_por_km: dict = field(default_factory=lambda: {
        "peaton": 1.6,        # peatón que cruza fuera de la cebra
        "animal": 0.8,        # perro o iguana que cruza
        "obra": 0.6,          # carril cerrado con conos
        "frenada_lider": 0.8,  # el vehículo de adelante frena de golpe
    })
    dist_aparicion_m: tuple = (12.0, 85.0)  # distancia delante del ego donde aparece
