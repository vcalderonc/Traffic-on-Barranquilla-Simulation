"""Fase 0: mide los solapes (carro encima de una persona o de otro carro) en las grabaciones del visor.

No necesita SUMO: lee ``visor/datos/recorrido_*.json`` (cuadros a 2 Hz) y la geometría de
``visor/datos/ciudad.json``. Cada vehículo es un rectángulo con el frente en la posición
que da SUMO y el cuerpo hacia atrás (igual que lo dibuja el visor); cada persona es un
círculo. Se mide con dos huellas:

* ``sumo``:   largo y ancho del ``vType`` (lo que de verdad simula SUMO);
* ``visual``: el modelo 3D más grande que el visor puede elegir para esa clase (lo que se ve).

También muestrea los instantes intermedios que el visor interpola entre cuadros, porque la
interpolación lineal puede "cortar" una curva y producir un solape que no existe en
ningún cuadro.

Cada solape se clasifica por responsable (ego / fondo), por tipo de persona (SUMO,
imprevisto, vendedor o cliente de un puesto) y por lugar (cebra, andén, cruce, calzada).
Los cuadros seguidos con el mismo par se agrupan en un solo evento.

    python -m bq_sim solapes                 # todas las grabaciones
    python -m bq_sim solapes --sub 4         # 4 muestras por intervalo de 0.5 s
"""
from __future__ import annotations

import csv
import gzip
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import config as C

# Códigos de clase del visor (visor.TIPOS_VISOR) -> (largo, ancho) en metros
DIM_SUMO = {0: (3.7, 1.65), 1: (3.7, 1.65), 2: (2.1, 0.8), 3: (12.0, 2.5), 4: (9.0, 2.5),
            5: (4.5, 1.8), 6: (4.8, 1.9), 7: (5.3, 1.9), 8: (5.7, 2.0)}
# El mayor modelo de visor/modelos.js que elegirModelo() puede usar para cada código
DIM_VISUAL = {0: (4.5, 1.78), 1: (3.75, 1.66), 2: (2.1, 0.8), 3: (12.0, 2.5), 4: (9.0, 2.45),
              5: (4.92, 1.92), 6: (4.84, 1.92), 7: (5.68, 2.0), 8: (5.68, 2.0)}
# El ego: SUMO usa el vType del perfil; el visor siempre dibuja el Porsche 911 (4.57 x 1.86)
DIM_EGO_SUMO = {"automovil": (4.5, 1.85), "taxi": (4.3, 1.7), "bus": (12.0, 2.5), "camion": (9.0, 2.5)}
DIM_EGO_VISUAL = (4.57, 1.86)
COD_EGO = 9

RADIO = {"persona": 0.25, "imprevisto": 0.3, "vendedor": 0.25, "cliente": 0.25, "animal": 0.25}
TIPOS_OBJ_PERSONA = {"peaton": "imprevisto", "vendedor": "imprevisto", "perro": "animal", "iguana": "animal"}
CELDA = 12.0  # metros, índice espacial


# ------------------------------------------------------------------ geometría
@dataclass
class Caja:
    """Rectángulo orientado de un vehículo: frente en (x, y), rumbo SUMO en grados (0 = norte, horario)."""
    x: float
    y: float
    ang: float
    largo: float
    ancho: float

    def __post_init__(self):
        a = math.radians(self.ang)
        self.ux, self.uy = math.sin(a), math.cos(a)          # hacia adelante
        self.cx = self.x - self.ux * self.largo / 2           # centro
        self.cy = self.y - self.uy * self.largo / 2
        self.hl, self.hw = self.largo / 2, self.ancho / 2

    def distancia(self, px: float, py: float) -> float:
        """Distancia del punto al rectángulo (0 si está adentro)."""
        dx, dy = px - self.cx, py - self.cy
        lon = dx * self.ux + dy * self.uy
        lat = -dx * self.uy + dy * self.ux
        ex, ey = max(abs(lon) - self.hl, 0.0), max(abs(lat) - self.hw, 0.0)
        return math.hypot(ex, ey)

    def esquinas(self):
        vx, vy = self.uy, -self.ux  # a la derecha
        return [(self.cx + sl * self.ux * self.hl + sw * vx * self.hw,
                 self.cy + sl * self.uy * self.hl + sw * vy * self.hw)
                for sl, sw in ((1, 1), (1, -1), (-1, -1), (-1, 1))]

    def ejes(self):
        return [(self.ux, self.uy), (self.uy, -self.ux)]


def cajas_se_solapan(a: Caja, b: Caja, holgura: float = 0.0) -> bool:
    """Teorema del eje separador para dos rectángulos orientados (holgura > 0 exige más penetración)."""
    if math.hypot(a.cx - b.cx, a.cy - b.cy) > a.hl + a.hw + b.hl + b.hw:
        return False
    ca, cb = a.esquinas(), b.esquinas()
    for ex, ey in a.ejes() + b.ejes():
        pa = [x * ex + y * ey for x, y in ca]
        pb = [x * ex + y * ey for x, y in cb]
        if max(pa) - holgura <= min(pb) or max(pb) - holgura <= min(pa):
            return False
    return True


def _dist_segmento(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _dentro(pl, x, y) -> bool:
    c, n = False, len(pl) // 2
    j = n - 1
    for i in range(n):
        xi, yi, xj, yj = pl[2 * i], pl[2 * i + 1], pl[2 * j], pl[2 * j + 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def interp_ang(a: float, b: float, f: float) -> float:
    d = ((b - a + 540.0) % 360.0) - 180.0
    return a + d * f


def _azar(i: float, sal: float) -> float:  # misma función que el visor
    x = math.sin(i * 12.9898 + sal * 78.233) * 43758.5453
    return x - math.floor(x)


# ------------------------------------------------------------------ lugares de la ciudad
class Lugares:
    """Clasifica un punto en cebra / andén / cruce / calzada / otro con la geometría de ciudad.json."""

    def __init__(self, ciudad: dict):
        self.franjas = defaultdict(list)   # celda -> [(clase, ancho/2, ax, ay, bx, by)]
        self.cruces = defaultdict(list)    # celda -> [polígono]
        for w, pl in ciudad.get("cebras", []):
            self._franja("cebra", w, pl)
        for w, pl in ciudad.get("andenes", []):
            self._franja("anden", w, pl)
        for c in ciudad.get("carriles", []):
            for w, pl in c["l"]:
                self._franja("calzada", w, pl)
        for pl in ciudad.get("cruces", []):
            xs, ys = pl[0::2], pl[1::2]
            for k in self._celdas_caja(min(xs), min(ys), max(xs), max(ys)):
                self.cruces[k].append(pl)

    @staticmethod
    def _celdas_caja(x0, y0, x1, y1):
        for i in range(int(math.floor(x0 / CELDA)), int(math.floor(x1 / CELDA)) + 1):
            for j in range(int(math.floor(y0 / CELDA)), int(math.floor(y1 / CELDA)) + 1):
                yield (i, j)

    def _franja(self, clase, w, pl):
        h = w / 2
        for k in range(0, len(pl) - 2, 2):
            ax, ay, bx, by = pl[k], pl[k + 1], pl[k + 2], pl[k + 3]
            for c in self._celdas_caja(min(ax, bx) - h, min(ay, by) - h, max(ax, bx) + h, max(ay, by) + h):
                self.franjas[c].append((clase, h, ax, ay, bx, by))

    def clase(self, x: float, y: float) -> str:
        k = (int(math.floor(x / CELDA)), int(math.floor(y / CELDA)))
        hay = set()
        for clase, h, ax, ay, bx, by in self.franjas.get(k, ()):
            if clase not in hay and _dist_segmento(x, y, ax, ay, bx, by) <= h:
                hay.add(clase)
        for orden in ("cebra", "anden"):
            if orden in hay:
                return orden
        if any(_dentro(pl, x, y) for pl in self.cruces.get(k, ())):
            return "cruce"
        return "calzada" if "calzada" in hay else "otro"


def personas_estaticas(ciudad: dict) -> list[tuple[float, float, str]]:
    """Vendedores y clientes de los puestos, con la misma fórmula que construirPuestos() del visor."""
    out, por_tipo = [], defaultdict(list)
    for p in ciudad.get("puestos", []):
        por_tipo[p[3]].append(p)
    for tipo, lista in por_tipo.items():
        for i, (x, y, r, *_rest) in enumerate(lista):
            fx, fy = math.sin(r), -math.cos(r)
            out.append((x - fx * 1.1, y - fy * 1.1, "vendedor"))
            n_cli = math.floor(_azar(i, tipo + 11) * (4 if tipo == 3 else 3))
            for c in range(n_cli):
                d, lat = 1.5 + c * 0.7, (_azar(i, c) - 0.5) * 2.2
                out.append((x + fx * d + fy * lat, y + fy * d - fx * lat, "cliente"))
    return out


# ------------------------------------------------------------------ medición
@dataclass
class Evento:
    recorrido: str
    huella: str
    tipo: str            # "persona" (vehículo-persona) o "vehiculo" (vehículo-vehículo)
    ego: bool
    a: str
    b: str
    clase_a: int
    clase_b: str
    t_ini: float
    t_fin: float
    x: float
    y: float
    lugar: str
    penetracion_m: float
    cuadros: int = 1


@dataclass
class Resultado:
    recorrido: str
    cuadros: int
    choques_registrados: int
    eventos: list = field(default_factory=list)


def _indice(puntos, celda=CELDA):
    g = defaultdict(list)
    for p in puntos:
        g[(int(math.floor(p[0] / celda)), int(math.floor(p[1] / celda)))].append(p)
    return g


def _vecinos(g, x, y, celda=CELDA):
    i, j = int(math.floor(x / celda)), int(math.floor(y / celda))
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            yield from g.get((i + di, j + dj), ())


def medir_recorrido(ruta: Path, lugares: Lugares, estaticas: list, sub: int = 2,
                    huellas=("sumo", "visual"), con_vehiculos: bool = True) -> Resultado:
    if ruta.suffix == ".gz":
        with gzip.open(ruta, "rt", encoding="utf-8") as fh:
            rec = json.load(fh)
    else:
        rec = json.loads(ruta.read_text(encoding="utf-8"))
    cuadros = rec["cuadros"]
    dt = rec.get("dt", 0.5)
    episodios = rec.get("episodios", [])
    choques = sum((e.get("metricas") or {}).get("choques", 0) for e in episodios)
    res = Resultado(ruta.name.split(".")[0], len(cuadros), choques)

    def perfil_en(k):
        for e in episodios:
            if e.get("inicio", 0) <= k < e.get("fin", 1 << 30):
                return e.get("perfil", "automovil")
        return "automovil"

    abiertos: dict[tuple, Evento] = {}
    idx_est = _indice(estaticas)

    for k, A in enumerate(cuadros):
        B = cuadros[k + 1] if k + 1 < len(cuadros) else A
        bv = {v[0]: v for v in B["v"]}
        bp = {p[0]: p for p in B["p"]}
        bo = {o[0]: o for o in B["o"]}
        perfil = perfil_en(k)
        for s in range(sub):
            f = s / sub
            t = round(A["t"] + f * dt, 3)
            vivos: set[tuple] = set()
            # personas e imprevistos interpolados como los dibuja el visor
            pers = []
            for pid, x, y, _a in A["p"]:
                w = bp.get(pid)
                if w:
                    x, y = x + (w[1] - x) * f, y + (w[2] - y) * f
                pers.append((x, y, "persona", f"p{pid}"))
            for oid, tipo, x, y, _r in A["o"]:
                if tipo not in TIPOS_OBJ_PERSONA:
                    continue
                w = bo.get(oid)
                if w:
                    x, y = x + (w[2] - x) * f, y + (w[3] - y) * f
                pers.append((x, y, TIPOS_OBJ_PERSONA[tipo], f"o{oid}:{tipo}"))
            idx_p = _indice(pers)
            for huella in huellas:
                cajas = []
                for vid, cod, x, y, ang in A["v"]:
                    w = bv.get(vid)
                    if w:
                        x, y, ang = x + (w[2] - x) * f, y + (w[3] - y) * f, interp_ang(ang, w[4], f)
                    if cod == COD_EGO:
                        L, W = DIM_EGO_SUMO.get(perfil, DIM_EGO_SUMO["automovil"]) if huella == "sumo" else DIM_EGO_VISUAL
                    else:
                        L, W = (DIM_SUMO if huella == "sumo" else DIM_VISUAL).get(cod, DIM_SUMO[0])
                    cajas.append((vid, cod, Caja(x, y, ang, L, W)))
                for vid, cod, cj in cajas:
                    cand = list(_vecinos(idx_p, cj.cx, cj.cy))
                    cand += [(x, y, c, f"e{int(x * 10)}_{int(y * 10)}") for x, y, c in _vecinos(idx_est, cj.cx, cj.cy)]
                    for px, py, clase, pid in cand:
                        r = RADIO[clase]
                        d = cj.distancia(px, py)
                        if d < r:
                            clave = (huella, "persona", vid, pid)
                            vivos.add(clave)
                            _abrir(abiertos, clave, res, t, px, py, r - d, lugares, cod, clase)
                if con_vehiculos:
                    idx_v = _indice([(c.cx, c.cy, vid, cod, c) for vid, cod, c in cajas], celda=16.0)
                    for vid, cod, cj in cajas:
                        for _x, _y, vid2, cod2, cj2 in _vecinos(idx_v, cj.cx, cj.cy, celda=16.0):
                            if vid2 <= vid or not cajas_se_solapan(cj, cj2, holgura=0.05):
                                continue
                            ego = cod == COD_EGO or cod2 == COD_EGO
                            a, b = (vid2, vid) if cod2 == COD_EGO else (vid, vid2)
                            ca, cb = (cod2, cod) if cod2 == COD_EGO else (cod, cod2)
                            clave = (huella, "vehiculo", a, b)
                            vivos.add(clave)
                            mx, my = (cj.cx + cj2.cx) / 2, (cj.cy + cj2.cy) / 2
                            _abrir(abiertos, clave, res, t, mx, my, 0.0, lugares, ca, str(cb), ego=ego)
            for clave in [c for c in abiertos if c not in vivos]:
                abiertos.pop(clave)
    return res


def _abrir(abiertos, clave, res, t, x, y, pen, lugares, cod, clase_b, ego=None):
    ev = abiertos.get(clave)
    if ev is None:
        huella, tipo, a, b = clave
        ev = Evento(res.recorrido, huella, tipo, cod == COD_EGO if ego is None else ego, str(a), str(b),
                    cod, clase_b, t, t, round(x, 1), round(y, 1), lugares.clase(x, y), round(pen, 2))
        abiertos[clave] = ev
        res.eventos.append(ev)
    else:
        ev.t_fin = t
        ev.cuadros += 1
        ev.penetracion_m = max(ev.penetracion_m, round(pen, 2))


# ------------------------------------------------------------------ informe
def _tabla(eventos, filtro, por):
    c = Counter(por(e) for e in eventos if filtro(e))
    return ", ".join(f"{k}: {v}" for k, v in c.most_common()) or "—"


def medir_todo(directorio: Path | None = None, sub: int = 2, salida: Path | None = None,
               con_vehiculos: bool = True) -> list[Resultado]:
    directorio = Path(directorio or (C.DIR_VISOR / "datos"))
    salida = Path(salida or (C.DIR_SALIDAS / "fase0_solapes"))
    salida.mkdir(parents=True, exist_ok=True)
    ciudad = json.loads((directorio / "ciudad.json").read_text(encoding="utf-8"))
    print("Indexando la geometría de la ciudad…")
    lugares = Lugares(ciudad)
    estaticas = personas_estaticas(ciudad)
    resultados = []
    rutas = {}
    for ruta in sorted(directorio.glob("recorrido_*.json*")):
        nombre = ruta.name.split(".")[0]
        if nombre not in rutas or ruta.suffix == ".gz":  # si hay las dos, la comprimida es la nueva
            rutas[nombre] = ruta
    for ruta in rutas.values():
        print(f"Midiendo {ruta.name}…")
        resultados.append(medir_recorrido(ruta, lugares, estaticas, sub=sub, con_vehiculos=con_vehiculos))

    campos = list(Evento.__dataclass_fields__)
    with open(salida / "eventos.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for r in resultados:
            for e in r.eventos:
                w.writerow(e.__dict__)

    resumen = []
    lineas = ["# Fase 0 · Solapes en las grabaciones del visor", "",
              f"Muestras por intervalo de {0.5} s: {sub}. Persona = círculo de 0.25 m; "
              "vehículo = rectángulo con el frente en la posición de SUMO.", "",
              "| Recorrido | Choques registrados | Huella | Ego–persona | Fondo–persona | Ego–vehículo | Vehículo–vehículo (fondo) |",
              "|---|---|---|---|---|---|---|"]
    for r in resultados:
        for h in ("sumo", "visual"):
            ev = [e for e in r.eventos if e.huella == h]
            fila = {"recorrido": r.recorrido, "huella": h, "choques_registrados": r.choques_registrados,
                    "ego_persona": sum(e.tipo == "persona" and e.ego for e in ev),
                    "fondo_persona": sum(e.tipo == "persona" and not e.ego for e in ev),
                    "ego_vehiculo": sum(e.tipo == "vehiculo" and e.ego for e in ev),
                    "fondo_vehiculo": sum(e.tipo == "vehiculo" and not e.ego for e in ev)}
            resumen.append(fila)
            lineas.append(f"| {r.recorrido} | {r.choques_registrados} | {h} | {fila['ego_persona']} | "
                          f"{fila['fondo_persona']} | {fila['ego_vehiculo']} | {fila['fondo_vehiculo']} |")
    todos = [e for r in resultados for e in r.eventos]
    for h in ("sumo", "visual"):
        lineas += ["", f"## Huella {h}: vehículo–persona", "",
                   f"* Por lugar (ego): {_tabla(todos, lambda e: e.huella == h and e.tipo == 'persona' and e.ego, lambda e: e.lugar)}",
                   f"* Por lugar (fondo): {_tabla(todos, lambda e: e.huella == h and e.tipo == 'persona' and not e.ego, lambda e: e.lugar)}",
                   f"* Por tipo de persona: {_tabla(todos, lambda e: e.huella == h and e.tipo == 'persona', lambda e: e.clase_b)}",
                   f"* Por clase de vehículo (código visor): {_tabla(todos, lambda e: e.huella == h and e.tipo == 'persona', lambda e: e.clase_a)}"]
    solo_visual = {(e.recorrido, e.tipo, e.a, e.b) for e in todos if e.huella == "visual"} - \
                  {(e.recorrido, e.tipo, e.a, e.b) for e in todos if e.huella == "sumo"}
    lineas += ["", f"Solapes que solo aparecen con la huella visual (modelo 3D más grande que el vType): {len(solo_visual)}"]
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / "RESUMEN.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print(f"\nEventos: {salida / 'eventos.csv'}")
    return resultados
