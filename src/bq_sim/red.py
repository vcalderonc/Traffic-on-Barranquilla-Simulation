"""Construcción de la red vial real de Barranquilla (OpenStreetMap -> SUMO).

Pasos (equivalentes a lo que pide el Stack Tech con OSM + netconvert + Netedit):

1. ``descargar_osm``: polígono del Gran Malecón y vías principales desde Overpass.
2. ``construir_red``: ``netconvert`` con semáforos de OSM, glorietas, aceras y cebras.
3. ``aplicar_pares``: convierte en intersecciones con PARE (``priority_stop``) los
   nodos que OSM marca como ``highway=stop``. Es la edición que se haría a mano en
   Netedit, pero programada para que sea reproducible.

Las velocidades máximas son las etiquetas ``maxspeed`` de OSM (p. ej. Vía 40 a 60 km/h).
Donde OSM no trae etiqueta se usa el límite urbano colombiano de 50 km/h.
"""
from __future__ import annotations

import gzip
import shutil
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from . import config as C

TIPOS_CONSERVADOS = [
    "highway.trunk", "highway.trunk_link", "highway.primary", "highway.primary_link",
    "highway.secondary", "highway.secondary_link", "highway.tertiary", "highway.tertiary_link",
    "highway.unclassified", "highway.residential", "highway.living_street",
]

CONSULTA_OVERPASS = """[out:xml][timeout:150][bbox:{s},{w},{n},{e}];
(way["highway"];way["building"];way["natural"="water"];way["waterway"];
 relation["natural"="water"];way["leisure"="park"];way["landuse"="grass"];
 node["highway"~"traffic_signals|stop|give_way|crossing"];node["traffic_sign"];);
(._;>;);out body;"""


def descargar_osm(destino: Path = C.OSM_CRUDO) -> Path:
    s, w, n, e = C.BBOX
    datos = urllib.parse.urlencode({"data": CONSULTA_OVERPASS.format(s=s, w=w, n=n, e=e)}).encode()
    req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=datos,
                                 headers={"User-Agent": "academic-traffic-sim/1.0"})
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=200) as r, open(destino, "wb") as f:
        shutil.copyfileobj(r, f)
    return destino


def comprimir_osm() -> Path:
    with open(C.OSM_CRUDO, "rb") as fi, gzip.open(C.OSM_RED, "wb", compresslevel=9) as fo:
        shutil.copyfileobj(fi, fo)
    return C.OSM_RED


def _mapa_tipos() -> Path:
    """Typemap de SUMO con 50 km/h por defecto para las vías urbanas sin etiqueta."""
    base = C.sumo_home() / "data" / "typemap" / "osmNetconvert.typ.xml"
    arbol = ET.parse(base)
    for t in arbol.getroot().iter("type"):
        if t.get("id") in TIPOS_CONSERVADOS:
            t.set("speed", f"{C.VEL_URBANA_MS:.2f}")
    salida = C.DIR_SUMO / "tipos_barranquilla.typ.xml"
    salida.parent.mkdir(parents=True, exist_ok=True)
    arbol.write(salida, encoding="utf-8", xml_declaration=True)
    return salida


def construir_red() -> Path:
    if not C.OSM_RED.exists():
        comprimir_osm()
    peatones = C.sumo_home() / "data" / "typemap" / "osmNetconvertPedestrians.typ.xml"
    cmd = [
        C.binario("netconvert"),
        "--osm-files", str(C.OSM_RED),
        "--type-files", f"{_mapa_tipos()},{peatones}",
        "--keep-edges.by-type", ",".join(TIPOS_CONSERVADOS + ["highway.footway", "highway.pedestrian"]),
        "--remove-edges.by-vclass", "rail,rail_urban,tram",
        "--output-file", str(C.RED_SUMO),
        "--geometry.remove", "--ramps.guess", "--roundabouts.guess",
        "--junctions.join", "--junctions.join-dist", "10",
        "--junctions.corner-detail", "5",
        "--tls.guess-signals", "--tls.discard-simple", "--tls.join",
        "--tls.default-type", "static",
        "--sidewalks.guess", "--crossings.guess",
        "--keep-edges.components", "1",
        "--output.street-names", "--output.original-names",
        "--osm.all-attributes", "false",
        "--no-warnings", "true",
    ]
    subprocess.run(cmd, check=True)
    return C.RED_SUMO


def _nodos_pare_osm() -> list[tuple[float, float]]:
    with gzip.open(C.OSM_RED, "rb") as f:
        raiz = ET.parse(f).getroot()
    pares = []
    for nodo in raiz.iter("node"):
        etiquetas = {t.get("k"): t.get("v") for t in nodo.iter("tag")}
        if etiquetas.get("highway") == "stop" or etiquetas.get("traffic_sign", "").upper() in ("CO:SR-01", "STOP", "PARE"):
            pares.append((float(nodo.get("lon")), float(nodo.get("lat"))))
    return pares


def aplicar_pares(radio_m: float = 18.0) -> list[str]:
    """Marca como ``priority_stop`` las intersecciones con señal de PARE de OSM."""
    import sumolib

    red = sumolib.net.readNet(str(C.RED_SUMO), withInternal=False)
    elegidos: list[str] = []
    for lon, lat in _nodos_pare_osm():
        x, y = red.convertLonLat2XY(lon, lat)
        cerca = red.getNeighboringNodes(x, y, radio_m) if hasattr(red, "getNeighboringNodes") else []
        candidatos = [n for n in (cerca or red.getNodes())
                      if n.getType() in ("priority", "right_before_left")]
        if not candidatos:
            continue
        nodo = min(candidatos, key=lambda n: (n.getCoord()[0] - x) ** 2 + (n.getCoord()[1] - y) ** 2)
        dx, dy = nodo.getCoord()[0] - x, nodo.getCoord()[1] - y
        if dx * dx + dy * dy <= radio_m ** 2 and nodo.getID() not in elegidos:
            elegidos.append(nodo.getID())
    if not elegidos:
        return []
    parche = C.DIR_SUMO / "pares.nod.xml"
    with open(parche, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<nodes>\n')
        for nid in elegidos:
            f.write(f'    <node id="{nid}" type="priority_stop"/>\n')
        f.write("</nodes>\n")
    temporal = C.DIR_SUMO / "tmp.net.xml.gz"
    subprocess.run([
        C.binario("netconvert"), "--sumo-net-file", str(C.RED_SUMO), "--node-files", str(parche),
        "--output-file", str(temporal), "--no-warnings", "true",
    ], check=True)
    temporal.replace(C.RED_SUMO)
    return elegidos


def resumen() -> dict:
    import sumolib

    red = sumolib.net.readNet(str(C.RED_SUMO))
    nombres: dict[str, float] = {}
    for e in red.getEdges():
        if e.allows("passenger") and e.getName():
            nombres[e.getName()] = nombres.get(e.getName(), 0.0) + e.getLength()
    tipos: dict[str, int] = {}
    for n in red.getNodes():
        tipos[n.getType()] = tipos.get(n.getType(), 0) + 1
    return {
        "aristas": len(red.getEdges()),
        "nodos": len(red.getNodes()),
        "semaforos": len(red.getTrafficLights()),
        "tipos_nodo": tipos,
        "vias_principales_km": {k: round(v / 1000, 2) for k, v in
                                sorted(nombres.items(), key=lambda kv: -kv[1])[:20]},
    }
