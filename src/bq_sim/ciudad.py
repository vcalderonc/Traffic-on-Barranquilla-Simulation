"""Conocimiento de la ciudad: lugares, estrato de cada zona y demanda según la hora.

* ``LUGARES``: sitios desde donde puede salir el vehículo o por donde debe pasar.
  Varios son monumentos sobre rotondas (Ventana al Mundo, Aleta del Tiburón,
  Rotonda Malecón 72), así que pasar por ellos es pasar por la rotonda.
* ``estrato(lon, lat)``: estrato aproximado del barrio más cercano
  (``data/estratos.json``); define el estilo de los edificios, la mezcla visual de
  vehículos, la vegetación y cuántos vendedores ambulantes hay.
* ``factor_demanda(hora)``: horas pico de Barranquilla (mañana, mediodía y tarde).
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

from . import config as C

# id -> (nombre, lon, lat)
LUGARES = {
    "buenavista": ("Centros comerciales Buenavista (Calle 98)", -74.82767, 11.01315),
    "plaza_parque": ("C.C. Plaza del Parque", -74.82636, 11.01507),
    "ventana_mundo": ("Ventana al Mundo (rotonda Vía 40 con Circunvalar)", -74.83143, 11.03316),
    "puerta_oro": ("Centro de Eventos Puerta de Oro", -74.79984, 11.02372),
    "caiman_rio": ("Caimán del Río", -74.79599, 11.02305),
    "luna_rio": ("La Luna del Río", -74.78816, 11.01513),
    "malecon_72": ("Rotonda Malecón 72", -74.78567, 11.01271),
    "aleta_tiburon": ("Aleta del Tiburón · Ventana de Campeones (rotonda)", -74.77274, 10.99831),
}

# Perfil horario de demanda (multiplica la escala base). Picos: 6:30-8:30, 11:30-13:30
# (en Barranquilla mucha gente almuerza en casa) y 17:00-19:30. De madrugada, poco tráfico.
# Con más de ~1.7 la red (sobre todo las glorietas) se satura y SUMO entra en trancón
# permanente, así que el pico se deja en 1.6-1.65 veces la demanda base.
PERFIL_DEMANDA = (
    (0.0, 0.30), (5.0, 0.40), (6.0, 0.85), (6.75, 1.45), (7.5, 1.60), (8.5, 1.25),
    (10.0, 1.00), (11.75, 1.30), (12.5, 1.42), (13.5, 1.10), (15.5, 1.05), (17.0, 1.45),
    (18.0, 1.65), (19.5, 1.30), (21.0, 0.85), (23.0, 0.45), (24.0, 0.30),
)


def factor_demanda(hora: float) -> float:
    return _interpolar(PERFIL_DEMANDA, hora)


# Gente a pie: el Malecón se llena al atardecer y en la noche (brisa, menos calor), casi
# nadie camina al mediodía bajo el sol; en el resto de la ciudad el patrón sigue la jornada.
PERFIL_PASEO = (
    (0.0, 0.25), (5.0, 0.35), (6.0, 0.90), (7.5, 0.80), (10.0, 0.45), (12.0, 0.35),
    (15.0, 0.55), (16.5, 1.20), (18.0, 1.80), (20.0, 1.70), (21.5, 1.00), (23.0, 0.40), (24.0, 0.25),
)
PERFIL_CIUDAD_PIE = (
    (0.0, 0.20), (5.0, 0.35), (6.5, 1.20), (8.0, 1.30), (10.0, 1.00), (12.0, 1.30),
    (14.0, 0.90), (17.0, 1.40), (19.0, 1.20), (21.0, 0.70), (23.0, 0.30), (24.0, 0.20),
)


def _interpolar(perfil, hora: float) -> float:
    h = hora % 24.0
    for (h0, f0), (h1, f1) in zip(perfil[:-1], perfil[1:]):
        if h0 <= h <= h1:
            return f0 + (f1 - f0) * (h - h0) / (h1 - h0)
    return 1.0


def factor_peatones(hora: float, grupo: str = "ciudad") -> float:
    return _interpolar(PERFIL_PASEO if grupo == "paseo" else PERFIL_CIUDAD_PIE, hora)


def es_hora_pico(hora: float) -> bool:
    return factor_demanda(hora) >= 1.35


@lru_cache(maxsize=1)
def _barrios() -> tuple:
    datos = json.loads((C.RAIZ / "data" / "estratos.json").read_text(encoding="utf-8"))
    return tuple((b["lon"], b["lat"], b["estrato"], b["nombre"]) for b in datos["barrios"])


def barrio(lon: float, lat: float) -> tuple[str, int]:
    """Barrio más cercano (aproximación de Voronoi sobre los centros de OSM)."""
    k = math.cos(math.radians(lat))
    lon_b, lat_b, est, nombre = min(_barrios(), key=lambda b: ((b[0] - lon) * k) ** 2 + (b[1] - lat) ** 2)
    return nombre, est


def estrato(lon: float, lat: float) -> int:
    return barrio(lon, lat)[1]
