"""Exportación de datos para el visor 3D del Gran Malecón y grabación de recorridos.

* ``exportar_ciudad``: vías y cruces (de la red SUMO), edificios, río, parques,
  palmeras y nombres de calles (de OpenStreetMap) -> ``visor/datos/ciudad.json``.
* ``grabar_recorrido``: corre el vehículo instructor por el Malecón y guarda, a
  2 Hz, posiciones de todo el tráfico, imprevistos, semáforos y el "razonamiento"
  de los agentes (quién decidió y por qué) -> ``visor/datos/recorrido_*.json``.
* ``abrir_gui``: lo mismo, pero en la interfaz nativa de SUMO (sumo-gui).

Las alturas de los edificios no existen en OSM para esta zona (solo 221 de 11 869
tienen pisos): se usan los pisos de OSM cuando existen y, si no, una altura
sintética determinista según el área de la huella y el estrato del barrio
(``ciudad.estrato``): torres de 8 a 26 pisos en Alto Prado, Riomar, Villa Country o
Buenavista; casas de uno o dos pisos y colores vivos en los barrios populares;
bodegas en la zona industrial. También según el estrato se siembran árboles de calle
(más y con más robles morados y guayacanes en el norte) y se ubican puestos de
vendedores ambulantes (más en los corredores populares y en el Malecón). Es un
supuesto visual que no afecta la simulación.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import xml.etree.ElementTree as ET

from . import config as C

DIR_DATOS = C.DIR_VISOR / "datos"
R = lambda v: round(v, 1)  # noqa: E731


# =============================================================== ciudad
def _osm():
    with gzip.open(C.OSM_RED, "rb") as f:
        raiz = ET.parse(f).getroot()
    nodos = {n.get("id"): (float(n.get("lon")), float(n.get("lat"))) for n in raiz.iter("node")}
    vias = {}
    for w in raiz.iter("way"):
        refs = [nd.get("ref") for nd in w.iter("nd")]
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        vias[w.get("id")] = (refs, tags)
    relaciones = []
    for r in raiz.iter("relation"):
        tags = {t.get("k"): t.get("v") for t in r.iter("tag")}
        miembros = [(m.get("ref"), m.get("role")) for m in r.iter("member") if m.get("type") == "way"]
        relaciones.append((tags, miembros))
    return nodos, vias, relaciones


def _anillos(segmentos: list[list[str]]) -> list[list[str]]:
    """Une tramos de vías (listas de ids de nodos) en anillos cerrados."""
    pend = [list(s) for s in segmentos if len(s) > 1]
    anillos = []
    while pend:
        actual = pend.pop(0)
        cambio = True
        while actual[0] != actual[-1] and cambio:
            cambio = False
            for i, s in enumerate(pend):
                if s[0] == actual[-1]:
                    actual += s[1:]
                elif s[-1] == actual[-1]:
                    actual += s[::-1][1:]
                elif s[-1] == actual[0]:
                    actual = s + actual[1:]
                elif s[0] == actual[0]:
                    actual = s[::-1] + actual[1:]
                else:
                    continue
                pend.pop(i)
                cambio = True
                break
        anillos.append(actual)
    return anillos


def _recortar(poli: list, xmin, ymin, xmax, ymax) -> list:
    """Sutherland-Hodgman contra un rectángulo."""
    def corte(pts, dentro, interseca):
        out = []
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            if dentro(b):
                if not dentro(a):
                    out.append(interseca(a, b))
                out.append(b)
            elif dentro(a):
                out.append(interseca(a, b))
        return out

    def ix(a, b, x):
        t = (x - a[0]) / (b[0] - a[0])
        return (x, a[1] + t * (b[1] - a[1]))

    def iy(a, b, y):
        t = (y - a[1]) / (b[1] - a[1])
        return (a[0] + t * (b[0] - a[0]), y)

    pts = poli
    for dentro, inter in (
        (lambda p: p[0] >= xmin, lambda a, b: ix(a, b, xmin)),
        (lambda p: p[0] <= xmax, lambda a, b: ix(a, b, xmax)),
        (lambda p: p[1] >= ymin, lambda a, b: iy(a, b, ymin)),
        (lambda p: p[1] <= ymax, lambda a, b: iy(a, b, ymax)),
    ):
        if not pts:
            break
        pts = corte(pts, dentro, inter)
    return pts


def _area(p) -> float:
    return 0.5 * abs(sum(p[i - 1][0] * p[i][1] - p[i][0] * p[i - 1][1] for i in range(len(p))))


def _dentro(p, x, y) -> bool:
    c = False
    for i in range(len(p)):
        (x1, y1), (x2, y2) = p[i - 1], p[i]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


def _plano(p) -> list:
    return [R(v) for xy in p for v in xy]


def exportar_ciudad() -> dict:
    import sumolib

    red = sumolib.net.readNet(str(C.RED_SUMO), withInternal=True)
    (xmin, ymin), (xmax, ymax) = red.getBoundary()[:2], red.getBoundary()[2:]
    ox, oy = (xmin + xmax) / 2, (ymin + ymax) / 2
    margen = 150
    caja = (xmin - margen, ymin - margen, xmax + margen, ymax + margen)

    def loc(p):
        return [(x - ox, y - oy) for x, y in p]

    ciudad = {"origen": [ox, oy], "limites": [R(xmin - ox), R(ymin - oy), R(xmax - ox), R(ymax - oy)],
              "carriles": [], "andenes": [], "cruces": [], "cebras": [], "edificios": [],
              "agua": [], "parques": [], "palmeras": [], "etiquetas": [], "semaforos": []}
    # --- vías: carriles por arista, andenes, cebras
    for e in red.getEdges(withInternal=True):
        fn = e.getFunction()
        if fn == "crossing":
            for ln in e.getLanes():
                ciudad["cebras"].append([R(ln.getWidth()), _plano(loc(ln.getShape()))])
            continue
        if fn == "walkingarea":
            continue
        carriles = []
        for ln in e.getLanes():
            peatonal = ln.allows("pedestrian") and not ln.allows("passenger")
            item = [R(ln.getWidth()), _plano(loc(ln.getShape()))]
            (ciudad["andenes"] if peatonal else carriles).append(item)
        if carriles:
            item = {"interno": fn == "internal", "l": carriles}
            if fn != "internal":  # ¿doble sentido? (para pintar la línea central amarilla)
                ida = (e.getFromNode().getID(), e.getToNode().getID())
                if any(o.getToNode().getID() == ida[0] for o in e.getToNode().getOutgoing()):
                    item["o"] = 1
            ciudad["carriles"].append(item)
    for n in red.getNodes():
        forma = n.getShape()
        if len(forma) >= 3:
            ciudad["cruces"].append(_plano(loc(forma)))
    # --- semáforos: una cabeza por enlace controlado, al final del carril de llegada
    for tls in red.getTrafficLights():
        vistos = set()
        for (entrada, _salida, idx) in tls.getConnections():
            if idx in vistos:
                continue
            vistos.add(idx)
            forma = entrada.getShape()
            (x1, y1), (x2, y2) = forma[-2], forma[-1]
            ang = math.atan2(y2 - y1, x2 - x1)
            # a la derecha del carril, sobre la línea de pare
            dx, dy = math.sin(ang), -math.cos(ang)
            w = entrada.getWidth() / 2 + 0.6
            ciudad["semaforos"].append([tls.getID(), idx, R(x2 + dx * w - ox), R(y2 + dy * w - oy), round(ang, 3)])
    # --- nombres de vías principales
    longitudes: dict[str, list] = {}
    for e in red.getEdges():
        if e.getName() and e.allows("passenger"):
            longitudes.setdefault(e.getName(), []).append(e)
    for nombre, aristas in longitudes.items():
        total = sum(a.getLength() for a in aristas)
        if total < 1200 and nombre not in ("Rotonda Malecón 72",):
            continue
        for a in sorted(aristas, key=lambda a: -a.getLength())[:3]:
            forma = a.getShape()
            x, y = forma[len(forma) // 2]
            ciudad["etiquetas"].append(["via", nombre, R(x - ox), R(y - oy)])

    # --- OSM: edificios, agua, parques
    nodos, vias, relaciones = _osm()

    def xy(ids):
        pts = []
        for i in ids:
            if i in nodos:
                x, y = red.convertLonLat2XY(*nodos[i])
                pts.append((x, y))
        return pts

    from .ciudad import _barrios, barrio

    def estrato_xy(x, y):
        return barrio(*red.convertXY2LonLat(x, y))[1]

    hitos = json.loads((C.RAIZ / "data" / "hitos.json").read_text(encoding="utf-8"))["hitos"]
    ids_hitos = {str(h["osm"]["id"]) for h in hitos if h["osm"]["tipo"] == "way"} | {"685753639", "744671556"}
    for wid, (refs, tags) in vias.items():
        if wid in ids_hitos:
            continue  # los lugares emblemáticos se modelan aparte
        if "building" in tags and len(refs) >= 4:
            p = xy(refs[:-1] if refs[0] == refs[-1] else refs)
            if len(p) < 3 or not all(caja[0] < x < caja[2] and caja[1] < y < caja[3] for x, y in p):
                continue
            area = _area(p)
            cx, cy = sum(x for x, _ in p) / len(p), sum(y for _, y in p) / len(p)
            est = estrato_xy(cx, cy)
            tipo = tags.get("building", "yes")
            h = int(hashlib.md5(wid.encode()).hexdigest()[:6], 16) / 0xFFFFFF
            h2 = int(hashlib.md5((wid + "e").encode()).hexdigest()[:6], 16) / 0xFFFFFF
            pisos, estilo = _pisos_y_estilo(area, est, tipo, h, h2)
            if "building:levels" in tags:
                try:
                    pisos = float(tags["building:levels"].split(";")[0])
                except ValueError:
                    pass
            alto_piso = 4.5 if estilo == 4 else 3.1
            altura = float(tags.get("height", "0").split()[0] or 0) if tags.get("height") else pisos * alto_piso
            if estilo in (0, 1) and altura < 15:
                estilo = 5 if est >= 5 else 2
            ciudad["edificios"].append([round(min(altura, 140.0), 1), tipo[:12], _plano(loc(p)), est, estilo])
        elif tags.get("leisure") == "park" or tags.get("landuse") == "grass":
            p = xy(refs)
            p = _recortar(p, *caja)
            if len(p) >= 3:
                ciudad["parques"].append([tags.get("name", ""), _plano(loc(p))])
                if tags.get("name") and _area(p) > 4000:
                    cx = sum(x for x, _ in p) / len(p)
                    cy = sum(y for _, y in p) / len(p)
                    ciudad["etiquetas"].append(["lugar", tags["name"], R(cx - ox), R(cy - oy)])
                _sembrar_palmeras(p, ciudad, ox, oy, wid, malecon="Malec" in tags.get("name", ""))
        elif tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
            p = _recortar(xy(refs), *caja)
            if len(p) >= 3:
                ciudad["agua"].append(_plano(loc(p)))
    for tags, miembros in relaciones:
        if tags.get("natural") != "water" and tags.get("waterway") != "riverbank":
            continue
        externos = [vias[r][0] for r, rol in miembros if r in vias and rol in ("outer", "")]
        for anillo in _anillos(externos):
            p = _recortar(xy(anillo), *caja)
            if len(p) >= 3 and _area(p) > 500:
                ciudad["agua"].append(_plano(loc(p)))
                if tags.get("name") and _area(p) > 200_000:
                    cx = sum(x for x, _ in p) / len(p)
                    cy = sum(y for _, y in p) / len(p)
                    ciudad["etiquetas"].append(["agua", tags["name"], R(cx - ox), R(cy - oy)])
    ciudad["hitos"] = _exportar_hitos(red, hitos, ox, oy)
    ciudad["faroles"] = _faroles(red, ox, oy)
    ciudad["barrios"] = []
    for lon, lat, est, nombre in _barrios():
        x, y = red.convertLonLat2XY(lon, lat)
        ciudad["barrios"].append([R(x - ox), R(y - oy), est, nombre])
    ciudad["arboles"] = _arboles(red, ciudad, ox, oy, estrato_xy)
    ciudad["puestos"] = _puestos(red, ciudad, ox, oy, estrato_xy)
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    (DIR_DATOS / "ciudad.json").write_text(json.dumps(ciudad, separators=(",", ":"), ensure_ascii=False),
                                           encoding="utf-8")
    print({k: len(v) for k, v in ciudad.items() if isinstance(v, list)})
    return ciudad


def _pisos_y_estilo(area: float, est: int, tipo: str, h: float, h2: float) -> tuple[float, int]:
    """Pisos sintéticos y estilo visual según huella, estrato y uso de OSM.

    Estilos: 0 torre de vidrio, 1 torre residencial de concreto con balcones,
    2 edificio medio en tonos pastel, 3 casa popular de colores vivos, 4 bodega,
    5 casa o edificio bajo elegante (estratos 5-6).
    """
    if tipo in ("industrial", "warehouse", "hangar", "manufacture") or est == 0:
        return (1 + round(h), 4) if area > 300 else (1 + round(h), 3 if est <= 3 else 2)
    if tipo in ("house", "detached", "terrace", "hut", "shed", "garage"):
        return (1 + round(h * (1.6 if est >= 4 else 1.0)), 5 if est >= 5 else 3 if est <= 3 else 2)
    if est >= 5:
        if area < 250:
            return 2 + round(h), 5
        if 350 <= area <= 2500 and h2 < 0.36:
            return 8 + round(18 * h ** 1.3), 0 if h2 < 0.13 else 1
        return (3 + round(5 * h), 5) if area <= 2500 else (3 + round(5 * h), 0 if h2 < 0.4 else 2)
    if est == 4:
        if 300 <= area <= 2000 and h2 < 0.16:
            return 6 + round(8 * h), 1
        return (2 + round(2 * h), 2) if area >= 120 else (1 + round(h), 2)
    if est == 3:
        if area > 400 and h2 < 0.08:
            return 5 + round(5 * h), 1
        return (2 + round(3 * h), 2) if area > 400 else (1 + round(2 * h ** 2), 3)
    return (2 + round(h), 2) if area > 400 else (1 + round(h ** 2), 3)


def _rejilla_edificios(ciudad, celda: float = 40.0) -> tuple[dict, float]:
    rejilla: dict = {}
    for i, b in enumerate(ciudad["edificios"]):
        pl = b[2]
        xs, ys = pl[0::2], pl[1::2]
        for gx in range(int(min(xs) // celda), int(max(xs) // celda) + 1):
            for gy in range(int(min(ys) // celda), int(max(ys) // celda) + 1):
                rejilla.setdefault((gx, gy), []).append(i)
    return rejilla, celda


def _libre_de_edificios(ciudad, rejilla, celda, x, y) -> bool:
    for i in rejilla.get((int(x // celda), int(y // celda)), ()):
        pl = ciudad["edificios"][i][2]
        if _dentro(list(zip(pl[0::2], pl[1::2])), x, y):
            return False
    return True


# separación (m) entre árboles de calle según el estrato: el norte es mucho más arborizado
PASO_ARBOLES = {0: 90, 1: 55, 2: 45, 3: 30, 4: 22, 5: 15, 6: 12}


def _arboles(red, ciudad, ox, oy, estrato_xy) -> list:
    """Árboles de calle [x, y, altura, especie]: 0 mango/campano, 1 almendro, 2 roble morado,
    3 guayacán amarillo, 4 palma, 5 matarratón."""
    import random

    rejilla, celda = _rejilla_edificios(ciudad)
    out = []
    for e in red.getEdges():
        if e.getFunction() == "internal" or not e.allows("passenger") or e.getName() in VIAS_ILUMINADAS:
            continue
        forma = e.getShape()
        if len(forma) < 2:
            continue
        rng = random.Random(e.getID())
        mx, my = forma[len(forma) // 2]
        est = estrato_xy(mx, my)
        paso = PASO_ARBOLES.get(est, 35)
        ancho = sum(ln.getWidth() for ln in e.getLanes()) / 2 + 1.9
        acumulado, siguiente = 0.0, rng.uniform(0, paso)
        for (x1, y1), (x2, y2) in zip(forma[:-1], forma[1:]):
            seg = math.hypot(x2 - x1, y2 - y1)
            if seg < 1e-6:
                continue
            nx, ny = (y2 - y1) / seg, -(x2 - x1) / seg
            while siguiente <= acumulado + seg:
                f = (siguiente - acumulado) / seg
                x, y = x1 + f * (x2 - x1) + nx * ancho, y1 + f * (y2 - y1) + ny * ancho
                siguiente += paso * rng.uniform(0.75, 1.3)
                if rng.random() < 0.2 or not _libre_de_edificios(ciudad, rejilla, celda, x - ox, y - oy):
                    continue
                r = rng.random()
                flor = 0.28 if est >= 5 else 0.12 if est >= 3 else 0.05
                if r < flor * 0.6:
                    especie = 2
                elif r < flor:
                    especie = 3
                elif r < flor + 0.08:
                    especie = 4
                elif r < flor + 0.2:
                    especie = 1
                elif r < flor + 0.3:
                    especie = 5
                else:
                    especie = 0
                alto = rng.uniform(5.5, 9.0) if est <= 2 else rng.uniform(7.0, 14.0)
                out.append([R(x - ox), R(y - oy), round(alto, 1), especie])
            acumulado += seg
    return out


# puestos de vendedores: probabilidad por semáforo según el estrato
PROB_PUESTO_SEMAFORO = {0: 0.25, 1: 0.75, 2: 0.75, 3: 0.6, 4: 0.4, 5: 0.2, 6: 0.12}
CORREDORES_COMERCIALES = ("Avenida Calle 72", "Avenida Carrera 46", "Calle 84", "Carrera 53", "Calle 76",
                          "Calle 79", "Carrera 51B", "Calle 98", "Carrera 54", "Calle 70", "Carrera 43",
                          "Carrera 44", "Calle 74")


def _puestos(red, ciudad, ox, oy, estrato_xy) -> list:
    """Puestos de vendedores ambulantes [x, y, rumbo, tipo, estrato].

    Tipos: 0 carrito con sombrilla (frutas, raspao), 1 toldo con mesa, 2 carrito de
    tinto y termos, 3 kiosco de comida (Malecón). Van en las esquinas con semáforo, a lo
    largo de los corredores comerciales y en las plazoletas del Malecón.
    """
    import random

    rng = random.Random(98)
    rejilla, celda = _rejilla_edificios(ciudad)
    out = []

    def poner(x, y, rumbo, tipo, est):
        if _libre_de_edificios(ciudad, rejilla, celda, x - ox, y - oy):
            out.append([R(x - ox), R(y - oy), round(rumbo, 2), tipo, est])

    # esquinas con semáforo
    for tls in red.getTrafficLights():
        vistos = set()
        for (entrada, _salida, _idx) in tls.getConnections():
            arista = entrada.getEdge()
            if arista.getID() in vistos:
                continue
            vistos.add(arista.getID())
            forma = entrada.getShape()
            (x1, y1), (x2, y2) = forma[-2], forma[-1]
            ang = math.atan2(y2 - y1, x2 - x1)
            est = estrato_xy(x2, y2)
            if rng.random() > PROB_PUESTO_SEMAFORO.get(est, 0.4) * 0.6:
                continue
            ancho = sum(ln.getWidth() for ln in arista.getLanes()) / 2 + 2.6
            atras = rng.uniform(6, 14)
            x = x2 - math.cos(ang) * atras + math.sin(ang) * ancho
            y = y2 - math.sin(ang) * atras - math.cos(ang) * ancho
            poner(x, y, ang + math.pi / 2, rng.choice((0, 0, 1, 2)) if est <= 4 else 2, est)
    # corredores comerciales
    for e in red.getEdges():
        if e.getName() not in CORREDORES_COMERCIALES or not e.allows("passenger"):
            continue
        forma = e.getShape()
        mx, my = forma[len(forma) // 2]
        est = estrato_xy(mx, my)
        if est >= 5 and rng.random() < 0.7:
            continue
        ancho = sum(ln.getWidth() for ln in e.getLanes()) / 2 + 2.8
        acumulado, siguiente = 0.0, rng.uniform(20, 120)
        for (x1, y1), (x2, y2) in zip(forma[:-1], forma[1:]):
            seg = math.hypot(x2 - x1, y2 - y1)
            if seg < 1e-6:
                continue
            nx, ny = (y2 - y1) / seg, -(x2 - x1) / seg
            while siguiente <= acumulado + seg:
                f = (siguiente - acumulado) / seg
                x, y = x1 + f * (x2 - x1) + nx * ancho, y1 + f * (y2 - y1) + ny * ancho
                poner(x, y, math.atan2(y2 - y1, x2 - x1) + math.pi / 2, rng.choice((0, 1, 1, 2)), est)
                siguiente += rng.uniform(70, 160) * (1.8 if est >= 4 else 1.0)
            acumulado += seg
    # kioscos y carritos del Malecón (dentro del parque lineal)
    for nombre, plano in ciudad["parques"]:
        if "Malec" not in nombre:
            continue
        pts = [(plano[i] + ox, plano[i + 1] + oy) for i in range(0, len(plano), 2)]
        n = min(60, int(_area(pts) / 3000))
        xs, ys = [x for x, _ in pts], [y for _, y in pts]
        puestos = 0
        for _ in range(n * 30):
            if puestos >= n:
                break
            x, y = rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))
            if _dentro(pts, x, y):
                poner(x, y, rng.uniform(0, 6.28), rng.choice((3, 3, 0, 2)), estrato_xy(x, y))
                puestos += 1
    return out


VIAS_ILUMINADAS = ("Avenida del Río", "Vía 40", "Avenida Calle 72", "Calle 98", "Calle 99", "Carrera 53",
                   "Calle 84", "Avenida Carrera 46", "Carrera 51B", "Calle 79", "Calle 76", "Rotonda Malecón 72")


def _faroles(red, ox, oy, cada_m: float = 32.0) -> list:
    """Postes de alumbrado a la derecha de cada sentido de las vías principales."""
    out = []
    for e in red.getEdges():
        if e.getName() not in VIAS_ILUMINADAS or not e.allows("passenger"):
            continue
        forma = e.getShape()
        ancho = sum(ln.getWidth() for ln in e.getLanes()) / 2 + 1.2
        acumulado, siguiente = 0.0, cada_m / 2
        for (x1, y1), (x2, y2) in zip(forma[:-1], forma[1:]):
            seg = math.hypot(x2 - x1, y2 - y1)
            if seg < 1e-6:
                continue
            nx, ny = (y2 - y1) / seg, -(x2 - x1) / seg  # normal a la derecha
            while siguiente <= acumulado + seg:
                f = (siguiente - acumulado) / seg
                x, y = x1 + f * (x2 - x1) + nx * ancho, y1 + f * (y2 - y1) + ny * ancho
                out.append([R(x - ox), R(y - oy), round(math.atan2(-ny, -nx), 2)])  # el brazo mira a la vía
                siguiente += cada_m
            acumulado += seg
    return out


def _exportar_hitos(red, hitos: list, ox, oy) -> list:
    """Lugares emblemáticos en coordenadas locales, con orientación y fachada de pantalla."""
    def rumbo_via(x, y, nombres=("Avenida del Río", "Vía 40")):
        mejor = (1e18, 0.0)
        for e in red.getEdges():
            if e.getName() not in nombres:
                continue
            for (x1, y1), (x2, y2) in zip(e.getShape()[:-1], e.getShape()[1:]):
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                d = (mx - x) ** 2 + (my - y) ** 2
                if d < mejor[0]:
                    mejor = (d, math.atan2(y2 - y1, x2 - x1))
        return mejor[1]

    def punto_via_cercano(x, y, nombres):
        mejor = (1e18, (x, y))
        for e in red.getEdges():
            if e.getName() not in nombres:
                continue
            for px, py in e.getShape():
                d = (px - x) ** 2 + (py - y) ** 2
                if d < mejor[0]:
                    mejor = (d, (px, py))
        return mejor[1]

    out = []
    for h in hitos:
        item = {"id": h["id"], "tipo": h["tipo"], "nombre": h["nombre"], "altura": h.get("altura_m", 10.0)}
        if "punto" in h:
            x, y = red.convertLonLat2XY(*h["punto"])
            item["x"], item["y"] = R(x - ox), R(y - oy)
            item["rumbo"] = round(rumbo_via(x, y), 3)
        if "poligono" in h:
            pts = [red.convertLonLat2XY(lon, lat) for lon, lat in h["poligono"]]
            if pts[0] == pts[-1]:
                pts = pts[:-1]
            item["poligono"] = _plano([(x - ox, y - oy) for x, y in pts])
            cx = sum(x for x, _ in pts) / len(pts)
            cy = sum(y for _, y in pts) / len(pts)
            item["x"], item["y"] = R(cx - ox), R(cy - oy)
            item["rumbo"] = round(rumbo_via(cx, cy, ("Vía 40", "Avenida del Río", "Avenida Circunvalar")), 3)
            if h["tipo"] == "puerta_oro":  # el portal dorado mira a la Vía 40
                vx, vy = punto_via_cercano(cx, cy, ("Vía 40",))
                lados = []
                for i in range(len(pts)):
                    (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    lados.append((math.hypot(mx - vx, my - vy) - 0.2 * math.hypot(x2 - x1, y2 - y1), (x1, y1, x2, y2)))
                x1, y1, x2, y2 = min(lados)[1]
                item["fachada"] = [R(x1 - ox), R(y1 - oy), R(x2 - ox), R(y2 - oy)]
            if h["tipo"] == "mall":
                # fachada más cercana a la vía principal: ahí va la pantalla gigante y el letrero
                vx, vy = punto_via_cercano(cx, cy, ("Calle 98", "Carrera 53", "Calle 99", "Carrera 54"))
                lados = []
                for i in range(len(pts)):
                    (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
                    largo = math.hypot(x2 - x1, y2 - y1)
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    lados.append((math.hypot(mx - vx, my - vy) - 0.3 * largo, (x1, y1, x2, y2)))
                x1, y1, x2, y2 = min(lados)[1]
                item["fachada"] = [R(x1 - ox), R(y1 - oy), R(x2 - ox), R(y2 - oy)]
        out.append(item)
    return out


def _sembrar_palmeras(p, ciudad, ox, oy, semilla: str, malecon: bool) -> None:
    import random

    rng = random.Random(semilla)
    area = _area(p)
    n = int(area / (90 if malecon else 260))
    xs, ys = [x for x, _ in p], [y for _, y in p]
    puestas = 0
    for _ in range(n * 4):
        if puestas >= min(n, 600):
            break
        x, y = rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys))
        if _dentro(p, x, y):
            ciudad["palmeras"].append([R(x - ox), R(y - oy), round(rng.uniform(7, 13), 1)])
            puestas += 1


# ============================================================ recorrido
# Código de clase para el visor: 0 compacto, 1 taxi, 2 moto, 3 bus, 4 camión, 5 sedán,
# 6 camioneta SUV, 7 pick-up, 8 Cybertruck, 9 vehículo autónomo. El modelo exacto dentro
# de la clase (p. ej. Model Y o Prado TXL entre las SUV) lo elige el visor según el estrato.
TIPOS_VISOR = {"auto_compacto": 0, "taxi": 1, "moto": 2, "bus": 3, "camion": 4, "auto_sedan": 5,
               "auto_suv": 6, "auto_pickup": 7, "auto_cybertruck": 8, "auto": 5}


class Grabadora:
    """Arma cuadros (2 Hz) del episodio: los guarda para el visor o se los pasa a quien
    los transmite en vivo (``al_cuadro``)."""

    def __init__(self, origen, radio_m: float = 650.0, cada_pasos: int = 2, guardar: bool = True,
                 al_cuadro=None):
        self.ox, self.oy = origen
        self.radio = radio_m
        self.cada = cada_pasos
        self.guardar = guardar
        self.al_cuadro = al_cuadro
        self.cuadros: list = []
        self.episodios: list = []
        self._n = 0
        self._ids: dict[str, int] = {}

    def _id(self, s: str) -> int:
        if s not in self._ids:
            self._ids[s] = len(self._ids)
        return self._ids[s]

    def inicio_episodio(self, env, info) -> None:
        self.episodios.append({"inicio": len(self.cuadros), "t0": round(env.t0, 2), **info})

    def cuadro(self, env, d) -> dict | None:
        tr = env.mundo.traci
        mm = env.veh.mm
        if mm is None:
            return None
        ex, ey = mm.x, mm.y
        vehs = []
        for vid in tr.vehicle.getIDList():
            if vid.startswith("obs_"):
                continue
            x, y = tr.vehicle.getPosition(vid)
            if abs(x - ex) > self.radio or abs(y - ey) > self.radio:
                continue
            tipo = tr.vehicle.getTypeID(vid)
            if vid == env.ego:
                cod = 9
            else:
                cod = next((v for k, v in TIPOS_VISOR.items() if tipo.startswith(k)), 0)
            vehs.append([self._id(vid), cod, R(x - self.ox), R(y - self.oy), round(tr.vehicle.getAngle(vid), 1)])
        personas = []
        for pid in tr.person.getIDList():
            x, y = tr.person.getPosition(pid)
            if abs(x - ex) < 300 and abs(y - ey) < 300:
                personas.append([self._id(pid), R(x - self.ox), R(y - self.oy), round(tr.person.getAngle(pid), 1)])
        objetos = [[self._id(o["id"]), o["tipo"], R(o["x"] - self.ox), R(o["y"] - self.oy), o["rumbo"]]
                   for o in env.eventos.posiciones_render()]
        semaforos = {t: tr.trafficlight.getRedYellowGreenState(t) for t in tr.trafficlight.getIDList()}
        met = env.eval.met
        det = []
        for o in sorted(mm.detectados, key=lambda o: o.s)[:8]:
            det.append([o.subtipo, round(o.s, 1), round(min(o.ttc, 99), 1), int(o.en_trayectoria),
                        R(o.x - self.ox), R(o.y - self.oy)])
        sen = mm.senal
        return {
            "t": round(env.mundo.t - env.t0, 2), "h": round(env.hora, 3), "ll": int(env.lluvia),
            "v": vehs, "p": personas, "o": objetos, "s": semaforos,
            "ego": {
                "id": self._id(env.ego), "kmh": round(mm.v * 3.6, 1), "lim": round(mm.v_lim * 3.6),
                "a": round(d.acel, 2), "acc": d.accion_ejecutada, "dom": d.dominante, "motivo": d.motivo,
                "prop": d.propuestas, "interv": d.intervencion, "det": det,
                "senal": [sen.tipo, sen.estado, round(sen.dist, 1)] if sen else None,
                "r": round(met.recompensa, 2), "choques": met.choques, "casi": met.casi_choques,
                "bruscas": met.frenadas_bruscas, "pare": met.pare_respetados, "pare_mal": met.pare_violados,
                "rojos": met.rojos_violados, "dist": round(met.distancia_m), "carril": mm.carril_idx,
                "clima": mm.clima.nombre, "alcance": mm.clima.alcance_m,
                "adel": env.veh.navegacion.adelantamientos,
            },
        }

    def paso(self, env, d, recompensa) -> None:
        self._n += 1
        if self._n % self.cada:
            return
        c = self.cuadro(env, d)
        if c is None:
            return
        if self.guardar:
            self.cuadros.append(c)
        if self.al_cuadro is not None:
            self.al_cuadro(c)

    def fin_episodio(self, env) -> None:
        self.episodios[-1]["fin"] = len(self.cuadros)
        self.episodios[-1]["metricas"] = {**env.eval.met.resumen(),
                                          "adelantamientos": env.veh.navegacion.adelantamientos}
        self.episodios[-1]["eventos"] = env.eval.met.eventos + env.eventos.registro


# Recorridos grabados para el visor: (archivo, vía, hora inicial, lluvia, minutos de día por s, semilla)
# El 7.º campo (opcional) pide un recorrido a la medida: partida, monumentos y duración.
RECORRIDOS = (
    ("recorrido_1_malecon_atardecer", "Avenida del Río", 17.2, False, 0.6, 201),
    ("recorrido_2_malecon_dia", "Avenida del Río", 10.0, False, 0.0, 202),
    ("recorrido_3_calle84_lluvia", "Calle 84", 15.0, True, 0.0, 207),
    ("recorrido_4_malecon_noche", "Avenida del Río", 21.0, False, 0.0, 204),
    ("recorrido_5_buenavista_noche", "Calle 98", 19.6, False, 0.0, 205),
    ("recorrido_7_via40_hora_pico", "Vía 40", 7.4, False, 0.0, 211),
    ("recorrido_8_buenavista_ventana_al_mundo", None, 17.7, False, 0.35, 212,
     {"partida": "buenavista", "pasar_por": ["ventana_mundo"], "duracion": 420.0}),
    ("recorrido_9_malecon_aleta_tiburon_noche", None, 19.4, False, 0.0, 213,
     {"partida": "malecon_72", "pasar_por": ["aleta_tiburon"], "duracion": 360.0}),
)


def _ruta_para_grabar(mundo, via: str, avance_ideal_m: float = 1000.0):
    """La ruta más larga, salvo que la vía tenga un lugar emblemático: entonces la ruta que
    pasa frente a él a ~1 km del inicio, para que se vea dentro de los 4 minutos grabados."""
    from .entorno.mundo import PASAR_FRENTE_A

    rutas = mundo.rutas_por_via(via)
    if via not in PASAR_FRENTE_A:
        return rutas[0]
    px, py = mundo.traci.simulation.convertGeo(*PASAR_FRENTE_A[via], fromGeo=True)

    def acercamiento(r):
        acumulado, mejor = 0.0, (1e18, 0.0)
        for e in r.aristas:
            d = min(math.hypot(x - px, y - py) for x, y in mundo.forma_carril(f"{e}_0"))
            if d < mejor[0]:
                mejor = (d, acumulado)
            acumulado += mundo.largo_carril(f"{e}_0")
        return mejor

    medidas = [(acercamiento(r), r) for r in rutas]
    cerca = [(abs(avance - avance_ideal_m), r) for (d, avance), r in medidas if d < 200.0]
    return min(cerca, key=lambda t: t[0])[1] if cerca else rutas[0]


def grabar_recorrido(duracion_s: float = 240.0, recorridos=RECORRIDOS, solo: list[str] | None = None) -> None:
    """Graba recorridos del instructor (con guardrail) por vías reales a distintas horas.

    ``solo`` = nombres a regrabar; los demás archivos y su entrada en el índice se conservan.
    """
    from .aprendizaje.dqn import AgenteDQN
    from .entorno.gym_env import ConduccionBarranquillaEnv
    from .experimentos import MODELO_INSTRUCTOR

    ciudad = json.loads((DIR_DATOS / "ciudad.json").read_text(encoding="utf-8"))
    maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR) if MODELO_INSTRUCTOR.exists() else (None, None)
    ruta_indice = DIR_DATOS / "recorridos.json"
    previos = json.loads(ruta_indice.read_text(encoding="utf-8")) if ruta_indice.exists() else []
    indice = {r["archivo"]: r for r in previos if (DIR_DATOS / r["archivo"]).exists()}
    for (nombre, via, hora, lluvia, ciclo, semilla, *resto) in recorridos:
        if solo and nombre not in solo:
            continue
        extra = resto[0] if resto else {}
        grab = Grabadora(ciudad["origen"])
        # misma demanda que el modo en vivo: tráfico según la hora (horas pico) y ciudad ya llena
        env = ConduccionBarranquillaEnv(semilla=semilla, guardrail=True, multiplicador_eventos=2.0,
                                        t_max_s=extra.get("duracion", duracion_s), grabadora=grab,
                                        escala_demanda=0.9, demanda_por_hora=True, calentamiento_s=600.0)
        env.max_quieto_s = 150.0
        try:
            opciones = {"hora": hora, "lluvia": lluvia, "ciclo_min_por_s": ciclo,
                        "t_max_s": extra.get("duracion", duracion_s)}
            if extra.get("partida"):
                opciones.update(partida=extra["partida"], pasar_por=extra.get("pasar_por", []),
                                destino=extra.get("destino"))
            else:
                env.mundo._rutas[f"via:{via}/ego_auto"] = [_ruta_para_grabar(env.mundo, via)]
                opciones["via"] = via
            obs, _ = env.reset(options=opciones)
            fin = False
            while not fin:
                a = maestro.actuar(obs, explorar=False) if maestro else None
                obs, _r, term, trunc, _info = env.step(a)
                fin = term or trunc
        finally:
            env.close()
        # comprimido (el visor lo descomprime con DecompressionStream): ~5 veces más liviano
        archivo = f"{nombre}.json.gz"
        via = via or grab.episodios[0].get("ruta", "recorrido a la medida")
        datos = {"via": via, "hora": hora, "lluvia": lluvia, "ids": len(grab._ids),
                 "episodios": grab.episodios, "cuadros": grab.cuadros, "dt": C.PASO_SIM_S * grab.cada}
        with gzip.open(DIR_DATOS / archivo, "wt", encoding="utf-8") as f:
            f.write(json.dumps(datos, separators=(",", ":"), ensure_ascii=False))
        (DIR_DATOS / f"{nombre}.json").unlink(missing_ok=True)
        indice.pop(f"{nombre}.json", None)
        m = grab.episodios[0].get("metricas", {})
        indice[archivo] = {"archivo": archivo, "via": via, "hora": hora, "lluvia": lluvia,
                           "ruta": grab.episodios[0].get("ruta", ""),
                           "duracion_s": round(len(grab.cuadros) * datos["dt"], 1),
                           "choques": m.get("choques"), "casi_choques": m.get("casi_choques"),
                           "eventos": len(grab.episodios[0].get("eventos", [])),
                           "adelantamientos": m.get("adelantamientos", 0)}
        print(archivo, len(grab.cuadros), "cuadros", m, flush=True)
    ruta_indice.write_text(json.dumps(sorted(indice.values(), key=lambda r: r["archivo"]), indent=1,
                                      ensure_ascii=False), encoding="utf-8")


def abrir_gui(via: str = "Avenida del Río", hora: float = 17.5, lluvia: bool = False, ciclo: float = 0.0) -> None:
    """Abre sumo-gui y deja al instructor conduciendo por la vía elegida, episodio tras episodio."""
    from .aprendizaje.dqn import AgenteDQN
    from .entorno.gym_env import ConduccionBarranquillaEnv
    from .experimentos import MODELO_INSTRUCTOR

    maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR)
    env = ConduccionBarranquillaEnv(semilla=5, gui=True, multiplicador_eventos=2.0, t_max_s=300.0)
    tr = env.mundo.traci
    try:
        while True:
            obs, info = env.reset(options={"via": via, "hora": hora, "lluvia": lluvia, "ciclo_min_por_s": ciclo})
            print("Episodio:", info)
            try:
                tr.gui.trackVehicle("View #0", env.ego)
                tr.gui.setZoom("View #0", 900)
            except Exception:
                pass
            fin = False
            while not fin:
                obs, _r, term, trunc, inf = env.step(maestro.actuar(obs, explorar=False))
                fin = term or trunc
            print("Resultado:", {k: inf["metricas"][k] for k in ("choques", "casi_choques", "llego", "recompensa")})
            hora = env.hora
    except Exception as ex:  # cerrar la ventana termina la conexión
        print("Fin:", ex)
    finally:
        env.close()
