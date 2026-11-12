"""Demanda de tráfico: vehículos de fondo, peatones y configuración de SUMO.

Se usa ``randomTrips.py`` (herramienta oficial de SUMO) con semilla fija, así cada
corrida es reproducible. El factor de borde (``--fringe-factor``) hace que buena
parte de los viajes entren y salgan por los extremos del área, como el tráfico
que cruza la zona del Malecón por la Vía 40 y la Av. Calle 72.
"""
from __future__ import annotations

import subprocess
import sys

from . import config as C


def _random_trips(salida, extra: list[str], semilla: int) -> None:
    script = C.sumo_home() / "tools" / "randomTrips.py"
    cmd = [sys.executable, str(script), "-n", str(C.RED_SUMO), "-o", str(salida),
           "--seed", str(semilla), "--validate", "--remove-loops"] + extra
    subprocess.run(cmd, check=True)


# Flujos de corredor (vehículos/hora por sentido, antes de la escala de demanda).
# Los viajes aleatorios reparten el tráfico por toda la red y casi no usan las vías
# periféricas como la Avenida del Río; estos flujos ponen el tráfico donde la ciudad
# realmente lo tiene: la Vía 40, el Malecón y los grandes corredores.
CORREDORES = {
    "Vía 40": 600,
    "Avenida del Río": 260,
    "Avenida Calle 72": 400,
    "Avenida Carrera 46": 400,
    "Calle 84": 300,
    "Calle 98": 350,
    "Carrera 53": 350,
    "Carrera 51B": 300,
    "Calle 79": 250,
    "Calle 76": 250,
}


# Horizonte de la demanda: todo se genera como flujos (<flow>/<personFlow>) que duran
# más de cuatro días simulados. Antes eran viajes sueltos hasta t = 4000 s y, como los
# episodios se encadenan sobre la misma corrida de SUMO, pasada la primera hora simulada
# la ciudad se iba quedando sin tráfico de fondo (D-26).
HORIZONTE_S = 400_000


def generar_corredores(duracion_s: int = HORIZONTE_S, salida=None) -> list[dict]:
    """Un flujo por sentido entre los extremos de cada corredor (SUMO enruta el más rápido)."""
    import math

    import sumolib

    salida = salida or C.RUTAS_CORREDORES
    red = sumolib.net.readNet(str(C.RED_SUMO))
    flujos = []
    for nombre, vph in CORREDORES.items():
        aristas = [e for e in red.getEdges() if e.getName() == nombre and e.allows("passenger")]
        if len(aristas) < 2:
            continue
        medios = {e: e.getShape()[len(e.getShape()) // 2] for e in aristas}
        # extremos del corredor: el par de tramos más alejados
        a, b = max(((p, q) for p in aristas for q in aristas),
                   key=lambda pq: math.dist(medios[pq[0]], medios[pq[1]]))
        p1, p2 = medios[a], medios[b]
        ux, uy = p2[0] - p1[0], p2[1] - p1[1]
        largo = math.hypot(ux, uy)
        ux, uy = ux / largo, uy / largo

        def rumbo(e):
            (x1, y1), (x2, y2) = e.getShape()[0], e.getShape()[-1]
            d = math.hypot(x2 - x1, y2 - y1) or 1.0
            return ((x2 - x1) / d) * ux + ((y2 - y1) / d) * uy

        for sentido, (origen, destino, signo) in {"ida": (p1, p2, 1), "vuelta": (p2, p1, -1)}.items():
            desde = [e for e in aristas if signo * rumbo(e) > 0.4]
            if not desde:
                continue
            e_ini = min(desde, key=lambda e: math.dist(medios[e], origen))
            e_fin = min(desde, key=lambda e: math.dist(medios[e], destino))
            ruta, _costo = red.getShortestPath(e_ini, e_fin, vClass="passenger")
            if not ruta or e_ini == e_fin:
                continue
            en_via = sum(e.getLength() for e in ruta if e.getName() == nombre)
            total = sum(e.getLength() for e in ruta)
            if en_via < 0.5 * total or total < 800:
                continue
            flujos.append({"id": f"corr_{len(flujos)}", "via": nombre, "sentido": sentido,
                           "desde": e_ini.getID(), "hasta": e_fin.getID(), "vph": vph,
                           "largo_m": round(total)})
    with open(salida, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n')
        for fl in flujos:
            f.write(f'    <!-- {fl["via"]} ({fl["sentido"]}, {fl["largo_m"]} m) -->\n'
                    f'    <flow id="{fl["id"]}" type="mezcla" begin="0" end="{duracion_s}" '
                    f'period="exp({fl["vph"] / 3600:.5f})" from="{fl["desde"]}" to="{fl["hasta"]}" '
                    f'departLane="best" departSpeed="max"/>\n')
        f.write("</routes>\n")
    return flujos


# Zonas de paseo (lon_min, lat_min, lon_max, lat_max, segundos entre llegadas): gente que
# camina por el Malecón, por los andenes de Buenavista y por la zona comercial de la 72.
ZONAS_PASEO = {
    "Gran Malecón": (-74.8010, 11.0040, -74.7760, 11.0275, 2.0),
    "Buenavista y Plaza del Parque": (-74.8305, 11.0115, -74.8235, 11.0175, 3.5),
    "Calle 72 comercial": (-74.8060, 10.9995, -74.7960, 11.0075, 4.5),
}


def _pares_peatones(zonas: dict, grupo: str, semilla: int, pares_por_zona: int,
                    dist_max_m: float = 1e9) -> list[dict]:
    """Pares origen-destino a pie dentro de cada zona, con su tasa de llegadas (personas/s).

    ``zonas``: nombre -> (lon_min, lat_min, lon_max, lat_max, segundos entre llegadas).
    Entre todos los pares de una zona suman la tasa de la zona.
    """
    import math
    import random

    import sumolib

    red = sumolib.net.readNet(str(C.RED_SUMO))
    rng = random.Random(semilla)
    pares = []
    for nombre, (x0, y0, x1, y1, periodo) in zonas.items():
        aristas = []
        for e in red.getEdges():
            # solo se empieza y se termina a pie en un andén o un sendero peatonal: si el
            # tramo es una calzada que también admite peatones, la persona aparecería
            # encima de los carros (D-34)
            if e.getLength() < 15 or not any(ln.allows("pedestrian") and not ln.allows("passenger")
                                             for ln in e.getLanes()):
                continue
            x, y = e.getShape()[len(e.getShape()) // 2]
            lon, lat = red.convertXY2LonLat(x, y)
            if x0 <= lon <= x1 and y0 <= lat <= y1:
                aristas.append((e.getID(), x, y))
        if len(aristas) < 2:
            continue
        tasa = 1.0 / (periodo * pares_por_zona)
        hechos = 0
        while hechos < pares_por_zona:
            (a, xa, ya), (b, xb, yb) = rng.sample(aristas, 2)
            if math.hypot(xa - xb, ya - yb) > dist_max_m:
                continue
            pares.append({"de": a, "a": b, "tasa": round(tasa, 6), "grupo": grupo, "zona": nombre})
            hechos += 1
    return pares


def generar_peatones(periodo_s: float = 0.9, semilla: int = 43) -> dict:
    """Peatones de toda el área (viajes de hasta 1.2 km) y paseantes del Malecón, Buenavista y la 72.

    Los ``personFlow`` de SUMO se expanden completos al cargar la simulación (con un
    horizonte de días eran cientos de miles de personas y la carga tomaba minutos), así
    que aquí solo se guardan los pares y sus tasas; ``MundoSUMO`` lanza a cada persona
    por TraCI con llegadas de Poisson, sin horizonte, y escala la tasa según la hora.
    """
    import json

    sur, oeste, norte, este = C.BBOX
    pares = _pares_peatones({"Toda el área": (oeste, sur, este, norte, periodo_s)}, "ciudad",
                            semilla, 600, dist_max_m=1200.0)
    pares += _pares_peatones(ZONAS_PASEO, "paseo", semilla + 1, 80)
    C.PEATONES_OD.write_text(json.dumps({"pares": pares}, ensure_ascii=False), encoding="utf-8")
    por_grupo = {}
    for p in pares:
        por_grupo[p["grupo"]] = por_grupo.get(p["grupo"], 0.0) + p["tasa"] * 3600
    return {g: round(v) for g, v in por_grupo.items()}


def generar_demanda(duracion_s: int = HORIZONTE_S, periodo_veh: float = 1.4,
                    periodo_peaton: float = 0.9, semilla: int = 42) -> None:
    C.DIR_SUMO.mkdir(parents=True, exist_ok=True)
    flujos = generar_corredores(duracion_s)
    print(f"{len(flujos)} flujos de corredor:", sorted({f['via'] for f in flujos}))
    print("personas por hora:", generar_peatones(periodo_peaton, semilla + 1))
    # --flows: cientos de pares origen-destino que se repiten durante todo el horizonte,
    # con llegadas de Poisson (--poisson) para que no salgan todos a la vez
    _random_trips(C.RUTAS_FONDO, [
        "-b", "0", "-e", str(duracion_s), "-p", str(periodo_veh), "--flows", "450", "--poisson",
        "--fringe-factor", "8", "--min-distance", "700",
        "--edge-permission", "passenger", "--prefix", "f",
        "--trip-attributes", 'type="mezcla" departLane="best" departSpeed="max"',
        "--additional-files", str(C.TIPOS_VEH),
    ], semilla)
    escribir_sumocfg()


def escribir_sumocfg() -> None:
    C.CONFIG_SUMO.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{C.RED_SUMO.name}"/>
        <route-files value="{C.RUTAS_CORREDORES.name},{C.RUTAS_FONDO.name}"/>
        <additional-files value="{C.TIPOS_VEH.name}"/>
    </input>
    <time>
        <begin value="0"/>
        <step-length value="{C.PASO_SIM_S}"/>
    </time>
    <processing>
        <collision.action value="warn"/>
        <collision.check-junctions value="true"/>
        <collision.mingap-factor value="0"/>
        <time-to-teleport value="240"/>
        <ignore-route-errors value="true"/>
        <pedestrian.model value="striping"/>
    </processing>
    <report>
        <no-step-log value="true"/>
        <no-warnings value="true"/>
    </report>
    <gui_only>
        <start value="true"/>
    </gui_only>
</configuration>
""", encoding="utf-8")
