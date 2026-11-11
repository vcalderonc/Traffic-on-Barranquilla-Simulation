"""Exportación de datos para el visor 3D del Gran Malecón y grabación de recorridos.

* ``exportar_ciudad``: vías y cruces (de la red SUMO), edificios, río, parques,
  palmeras y nombres de calles (de OpenStreetMap) -> ``visor/datos/ciudad.json``.
* ``grabar_recorrido``: corre el vehículo instructor por el Malecón y guarda, a
  2 Hz, posiciones de todo el tráfico, imprevistos, semáforos y el "razonamiento"
  de los agentes (quién decidió y por qué) -> ``visor/datos/recorrido_*.json``.
* ``abrir_gui``: lo mismo, pero en la interfaz nativa de SUMO (sumo-gui).

Las alturas de los edificios no existen en OSM para esta zona (solo 221 de 11 869
tienen pisos): se usan los pisos de OSM cuando existen y, si no, una altura
sintética determinista según el área de la huella. Es un supuesto visual que no
afecta la simulación.
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
            ciudad["carriles"].append({"interno": fn == "internal", "l": carriles})
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

    for wid, (refs, tags) in vias.items():
        if "building" in tags and len(refs) >= 4:
            p = xy(refs[:-1] if refs[0] == refs[-1] else refs)
            if len(p) < 3 or not all(caja[0] < x < caja[2] and caja[1] < y < caja[3] for x, y in p):
                continue
            area = _area(p)
            if "building:levels" in tags:
                try:
                    pisos = float(tags["building:levels"].split(";")[0])
                except ValueError:
                    pisos = 2
            else:
                h = int(hashlib.md5(wid.encode()).hexdigest()[:6], 16) / 0xFFFFFF
                if area < 120:
                    pisos = 1 + round(h)
                elif area < 400:
                    pisos = 2 + round(2 * h)
                elif area < 1500:
                    pisos = 3 + round(7 * h ** 2)
                else:
                    pisos = 2 + round(14 * h ** 3)
            altura = float(tags.get("height", "0").split()[0] or 0) if tags.get("height") else pisos * 3.2
            tipo = tags.get("building", "yes")
            ciudad["edificios"].append([round(altura, 1), tipo[:12], _plano(loc(p))])
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
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    (DIR_DATOS / "ciudad.json").write_text(json.dumps(ciudad, separators=(",", ":"), ensure_ascii=False),
                                           encoding="utf-8")
    print({k: len(v) for k, v in ciudad.items() if isinstance(v, list)})
    return ciudad


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
TIPOS_VISOR = {"auto": 0, "taxi": 1, "moto": 2, "bus": 3, "camion": 4}


class Grabadora:
    """Captura cuadros a 2 Hz durante un episodio para reproducirlos en el visor."""

    def __init__(self, origen, radio_m: float = 650.0, cada_pasos: int = 2):
        self.ox, self.oy = origen
        self.radio = radio_m
        self.cada = cada_pasos
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

    def paso(self, env, d, recompensa) -> None:
        self._n += 1
        if self._n % self.cada:
            return
        tr = env.mundo.traci
        mm = env.veh.mm
        if mm is None:
            return
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
            if abs(x - ex) < 350 and abs(y - ey) < 350:
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
        self.cuadros.append({
            "t": round(env.mundo.t - env.t0, 2),
            "v": vehs, "p": personas, "o": objetos, "s": semaforos,
            "ego": {
                "id": self._id(env.ego), "kmh": round(mm.v * 3.6, 1), "lim": round(mm.v_lim * 3.6),
                "a": round(d.acel, 2), "acc": d.accion_ejecutada, "dom": d.dominante, "motivo": d.motivo,
                "prop": d.propuestas, "interv": d.intervencion, "det": det,
                "senal": [sen.tipo, sen.estado, round(sen.dist, 1)] if sen else None,
                "r": round(met.recompensa, 2), "choques": met.choques, "casi": met.casi_choques,
                "bruscas": met.frenadas_bruscas, "pare": met.pare_respetados, "pare_mal": met.pare_violados,
                "rojos": met.rojos_violados, "dist": round(met.distancia_m), "carril": mm.carril_idx,
            },
        })

    def fin_episodio(self, env) -> None:
        self.episodios[-1]["fin"] = len(self.cuadros)
        self.episodios[-1]["metricas"] = env.eval.met.resumen()
        self.episodios[-1]["eventos"] = env.eval.met.eventos + env.eventos.registro


def _ruta_malecon(env, preferida="Avenida del Río"):
    rutas = env.mundo.rutas_zona("malecon_via40")
    tr = env.mundo.traci

    def en_pref(r):
        return sum(env.mundo.largo_carril(f"{e}_0") for e in r.aristas if tr.edge.getStreetName(e) == preferida)
    return max(rutas, key=en_pref)


def grabar_recorrido(duracion_s: float = 150.0, climas=("despejado", "lluvia", "noche")) -> None:
    """Graba recorridos del instructor (con guardrail) por el Malecón, uno por clima."""
    from .aprendizaje.dqn import AgenteDQN
    from .entorno.gym_env import ConduccionBarranquillaEnv
    from .experimentos import MODELO_INSTRUCTOR

    ciudad = json.loads((DIR_DATOS / "ciudad.json").read_text(encoding="utf-8"))
    maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR) if MODELO_INSTRUCTOR.exists() else (None, None)
    indice = []
    for i, clima in enumerate(climas):
        grab = Grabadora(ciudad["origen"])
        env = ConduccionBarranquillaEnv(semilla=101 + i, guardrail=True, zonas=["malecon_via40"],
                                        multiplicador_eventos=2.2, t_max_s=duracion_s, grabadora=grab)
        ruta = _ruta_malecon(env, "Avenida del Río" if i != 1 else "Vía 40")
        env.mundo._rutas["malecon_via40/ego_auto"] = [ruta]
        try:
            obs, _ = env.reset(options={"zona": "malecon_via40", "clima": clima})
            fin = False
            while not fin:
                a = maestro.actuar(obs, explorar=False) if maestro else None
                obs, _r, term, trunc, _info = env.step(a)
                fin = term or trunc
        finally:
            env.close()
        nombre = f"recorrido_{i + 1}_{clima}.json"
        datos = {"clima": clima, "ids": len(grab._ids), "episodios": grab.episodios, "cuadros": grab.cuadros,
                 "dt": C.PASO_SIM_S * grab.cada}
        (DIR_DATOS / nombre).write_text(json.dumps(datos, separators=(",", ":"), ensure_ascii=False),
                                        encoding="utf-8")
        m = grab.episodios[0].get("metricas", {})
        indice.append({"archivo": nombre, "clima": clima, "ruta": grab.episodios[0].get("ruta", ""),
                       "duracion_s": round(len(grab.cuadros) * datos["dt"], 1),
                       "choques": m.get("choques"), "casi_choques": m.get("casi_choques"),
                       "eventos": len(grab.episodios[0].get("eventos", []))})
        print(nombre, len(grab.cuadros), "cuadros", m)
    (DIR_DATOS / "recorridos.json").write_text(json.dumps(indice, indent=1, ensure_ascii=False), encoding="utf-8")


def abrir_gui(zona: str = "malecon_via40", clima: str = "despejado") -> None:
    """Abre sumo-gui y deja al instructor conduciendo episodio tras episodio."""
    from .aprendizaje.dqn import AgenteDQN
    from .entorno.gym_env import ConduccionBarranquillaEnv
    from .experimentos import MODELO_INSTRUCTOR

    maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR)
    env = ConduccionBarranquillaEnv(semilla=5, gui=True, zonas=[zona], climas=[clima],
                                    multiplicador_eventos=2.0)
    tr = env.mundo.traci
    try:
        while True:
            obs, info = env.reset()
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
    except Exception as ex:  # cerrar la ventana termina la conexión
        print("Fin:", ex)
    finally:
        env.close()
