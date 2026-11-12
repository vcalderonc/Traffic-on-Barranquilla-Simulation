"""Conexión con SUMO: arranque, vehículo autónomo, consultas de verdad-terreno.

``MundoSUMO`` mantiene una sola corrida de SUMO por proceso. Los episodios del
vehículo autónomo se encadenan sobre el mismo tráfico (no se reinicia SUMO en cada
episodio), lo que ahorra el costo de cargar la red y deja el tráfico ya "caliente".
"""
from __future__ import annotations

import bisect
import json
import math
import random
from dataclasses import dataclass

from .. import config as C

# Modo de velocidad del ego (bits de TraCI):
#   bit 3 = respetar prioridad de paso frente a vehículos que llegan a la intersección.
# Se APAGAN a propósito: distancia segura al líder (bit 0) y frenar ante el rojo (bit 4).
# Así, evitar choques y respetar semáforos y PARE es responsabilidad de los agentes.
MODO_VELOCIDAD_EGO = 0b001000
# Cambio de carril: SUMO solo hace los cambios estratégicos para seguir la ruta;
# los cambios tácticos (esquivar conos) los decide el agente de Navegación.
MODO_CARRIL_EGO = 0b1000000001


def _traci(gui: bool):
    if gui:
        import traci  # el GUI necesita TraCI por socket
        return traci
    try:
        import libsumo  # mucho más rápido: SUMO corre dentro del mismo proceso
        return libsumo
    except ImportError:  # pragma: no cover
        import traci
        return traci


# Zonas para el aprendizaje federado (datos no-IID): cada vehículo aprende en una.
# Se definen por las vías principales REALES que recorren (nombres de OpenStreetMap)
# y cada una tiene su propio perfil de imprevistos (multiplicadores de la tasa base).
ZONAS = {
    "malecon_via40": {
        "nombre": "Gran Malecón: Vía 40 y Avenida del Río",
        "calles": ("Vía 40", "Avenida del Río", "Rotonda Malecón 72"),
        "eventos": {"peaton": 1.4, "animal": 1.6, "obra": 0.6, "frenada_lider": 0.8},
    },
    "corredor_calle72": {
        "nombre": "Corredor Av. Calle 72 – Calles 70 a 76 – Carreras 58 a 65",
        "calles": ("Avenida Calle 72", "Calle 70", "Calle 74", "Calle 75", "Calle 76",
                   "Carrera 58", "Carrera 64", "Carrera 65"),
        "eventos": {"peaton": 1.0, "animal": 0.6, "obra": 1.0, "frenada_lider": 1.5},
    },
    "calles79_85": {
        "nombre": "Calles 79 a 85 y Carreras 53 a 59B",
        "calles": ("Calle 79", "Calle 80", "Calle 81", "Calle 82", "Calle 84", "Calle 85",
                   "Carrera 53", "Carrera 55", "Carrera 56", "Carrera 59B"),
        "eventos": {"peaton": 1.0, "animal": 0.8, "obra": 1.6, "frenada_lider": 1.0},
    },
}


# Vías que el usuario puede elegir para manejar (nombre en OSM -> descripción)
VIAS_SELECCIONABLES = {
    "Avenida del Río": "Gran Malecón del Río (Avenida del Río)",
    "Vía 40": "Vía 40 (paralela al Malecón)",
    "Avenida Calle 72": "Avenida Calle 72",
    "Calle 84": "Calle 84",
    "Calle 79": "Calle 79",
    "Calle 76": "Calle 76",
    "Calle 98": "Calle 98 (Buenavista y Plaza del Parque)",
    "Carrera 53": "Carrera 53 (Buenavista)",
    "Carrera 51B": "Carrera 51B",
    "Avenida Carrera 46": "Avenida Carrera 46 (Olaya Herrera)",
}

# Si una vía tiene un lugar emblemático, se prefieren las rutas que pasan frente a él
# (lon, lat): la Calle 98 frente a los Buenavista, el Malecón frente a La Luna del Río.
PASAR_FRENTE_A = {
    "Calle 98": (-74.82767, 11.01315),          # C.C. Buenavista
    "Carrera 53": (-74.82767, 11.01315),
    "Avenida del Río": (-74.78816, 11.01513),   # La Luna del Río
}


@dataclass
class RutaEgo:
    aristas: tuple
    largo_m: float
    zona: str
    desc: str


class MundoSUMO:
    def __init__(self, semilla: int = 0, gui: bool = False, escala_demanda: float = 0.75,
                 calentamiento_s: float = 240.0, extra: list[str] | None = None):
        self.traci = _traci(gui)
        self.tc = self.traci.constants
        self.rng = random.Random(semilla)
        self.semilla = semilla
        binario = C.binario("sumo-gui" if gui else "sumo")
        args = [binario, "-c", str(C.CONFIG_SUMO), "--seed", str(semilla),
                "--scale", str(escala_demanda), "--pedestrian.model", "nonInteracting",
                "--no-step-log", "true", "--duration-log.disable", "true"]
        if gui:
            args += ["--delay", "60", "--gui-settings-file", str(C.DIR_SUMO / "vista.xml")] \
                if (C.DIR_SUMO / "vista.xml").exists() else ["--delay", "60"]
        args += extra or []
        self.traci.start(args)
        self.dt = self.traci.simulation.getDeltaT()
        self.escala_base = escala_demanda
        self.factor_hora = 1.0
        self._formas: dict[str, list] = {}
        self._largos: dict[str, float] = {}
        self._anchos: dict[str, float] = {}
        self._vmax: dict[str, float] = {}
        self._permite_auto: dict[str, bool] = {}
        self.peatones = PeatonesDinamicos(self, semilla)
        self.avanzar(int(calentamiento_s / self.dt))
        self._rutas: dict[str, list[RutaEgo]] = {}

    # ------------------------------------------------------------------ tiempo
    def avanzar(self, pasos: int = 1) -> None:
        for _ in range(pasos):
            self.peatones.paso()
            self.traci.simulationStep()

    @property
    def t(self) -> float:
        return self.traci.simulation.getTime()

    def cerrar(self) -> None:
        try:
            self.traci.close()
        except Exception:
            pass

    def ajustar_demanda(self, factor: float, recalentar: bool = True, hora: float | None = None) -> None:
        """Horas pico: multiplica la demanda base por ``factor`` (``ciudad.factor_demanda``).

        SUMO aplica la escala a los vehículos que entran desde ese momento; si el cambio
        es grande se avanza un rato la simulación para que la red se llene (o se
        desocupe) antes de que salga el vehículo autónomo. Con ``hora`` también se
        ajusta la gente a pie (``ciudad.factor_peatones``).
        """
        anterior, self.factor_hora = self.factor_hora, factor
        self.traci.simulation.setScale(self.escala_base * factor)
        if hora is not None:
            from ..ciudad import factor_peatones

            self.peatones.factor = {g: factor_peatones(hora, g) for g in ("ciudad", "paseo")}
        cambio = abs(factor - anterior)
        if recalentar and cambio > 0.25:
            self.avanzar(int(min(60.0, 60.0 * cambio) / self.dt))

    # ------------------------------------------------------------ geometría
    def forma_carril(self, carril: str) -> list:
        f = self._formas.get(carril)
        if f is None:
            f = list(self.traci.lane.getShape(carril))
            self._formas[carril] = f
        return f

    def largo_carril(self, carril: str) -> float:
        v = self._largos.get(carril)
        if v is None:
            v = self.traci.lane.getLength(carril)
            self._largos[carril] = v
        return v

    def ancho_carril(self, carril: str) -> float:
        v = self._anchos.get(carril)
        if v is None:
            v = self.traci.lane.getWidth(carril)
            self._anchos[carril] = v
        return v

    def vmax_carril(self, carril: str) -> float:
        v = self._vmax.get(carril)
        if v is None:
            v = self.traci.lane.getMaxSpeed(carril)
            self._vmax[carril] = v
        return v

    def permite_autos(self, carril: str) -> bool:
        v = self._permite_auto.get(carril)
        if v is None:
            permitidos = self.traci.lane.getAllowed(carril)
            v = (not permitidos) or ("passenger" in permitidos)
            self._permite_auto[carril] = v
        return v

    def lonlat(self, x: float, y: float) -> tuple[float, float]:
        return self.traci.simulation.convertGeo(x, y)

    # ------------------------------------------------------------- rutas ego
    def _aristas_calles(self, calles: tuple) -> list[str]:
        out = []
        for e in self.traci.edge.getIDList():
            if e.startswith(":") or self.traci.edge.getStreetName(e) not in calles:
                continue
            n = self.traci.edge.getLaneNumber(e)
            carriles = [f"{e}_{i}" for i in range(n)]
            if any(self.permite_autos(c) for c in carriles):
                out.append(e)
        return out

    def rutas_zona(self, zona: str, n: int = 60, tipo: str = "ego_auto") -> list[RutaEgo]:
        """Rutas origen-destino que recorren sobre todo las vías ancla de la zona.

        Condiciones: el origen está sobre una vía ancla, la ruta mide 600-1500 m y al
        menos el 45 % de su longitud va por vías ancla de la zona.
        """
        clave = f"{zona}/{tipo}"
        if clave in self._rutas:
            return self._rutas[clave]
        calles = ZONAS[zona]["calles"]
        anclas = self._aristas_calles(calles)
        todas = [e for e in self.traci.edge.getIDList() if not e.startswith(":")]
        rng = random.Random(1000 + sum(map(ord, zona)))
        rutas: list[RutaEgo] = []
        intentos = 0
        while len(rutas) < n and intentos < n * 60 and anclas:
            intentos += 1
            a = rng.choice(anclas)
            b = rng.choice(anclas if rng.random() < 0.7 else todas)
            if a == b:
                continue
            r = self.traci.simulation.findRoute(a, b, tipo)
            if not r.edges or not 600 <= r.length <= 1500:
                continue
            en_ancla = sum(self.largo_carril(f"{e}_0") for e in r.edges
                           if self.traci.edge.getStreetName(e) in calles)
            if en_ancla < 0.45 * r.length:
                continue
            nombres = []
            for e in r.edges:
                nom = self.traci.edge.getStreetName(e)
                if nom and nom not in nombres:
                    nombres.append(nom)
            rutas.append(RutaEgo(tuple(r.edges), r.length, zona, " → ".join(nombres[:4])))
        self._rutas[clave] = rutas
        return rutas

    def rutas_por_via(self, via: str, tipo: str = "ego_auto", n: int = 12) -> list[RutaEgo]:
        """Rutas que recorren sobre todo la vía pedida (≥ 60 % de su longitud), de 0.7 a 4.5 km.

        Se prefieren las que más metros hacen sobre la vía: así el usuario "maneja" por
        la Vía 40, el Malecón o la Calle 98 de punta a punta y no solo la cruza.
        """
        clave = f"via:{via}/{tipo}"
        if clave in self._rutas:
            return self._rutas[clave]
        anclas = self._aristas_calles((via,))
        rng = random.Random(7 + sum(map(ord, via)))
        candidatas: dict[tuple, RutaEgo] = {}
        for _ in range(500):
            if len(anclas) < 2:
                break
            a, b = rng.sample(anclas, 2)
            r = self.traci.simulation.findRoute(a, b, tipo)
            if not r.edges or not 700 <= r.length <= 4500:
                continue
            en_via = sum(self.largo_carril(f"{e}_0") for e in r.edges if self.traci.edge.getStreetName(e) == via)
            if en_via < 0.6 * r.length:
                continue
            nombres = []
            for e in r.edges:
                nom = self.traci.edge.getStreetName(e)
                if nom and nom not in nombres:
                    nombres.append(nom)
            candidatas[tuple(r.edges)] = RutaEgo(tuple(r.edges), r.length, f"vía: {via}",
                                                 " → ".join(nombres[:4]))
        rutas = sorted(candidatas.values(), key=lambda r: -r.largo_m)
        if via in PASAR_FRENTE_A:  # preferir las que pasan a menos de 200 m del lugar emblemático
            px, py = self.traci.simulation.convertGeo(*PASAR_FRENTE_A[via], fromGeo=True)

            def distancia(r):
                return min(math.hypot(x - px, y - py) for e in r.aristas
                           for x, y in self.forma_carril(f"{e}_0"))
            cerca = [r for r in rutas if distancia(r) < 200.0]
            rutas = cerca + [r for r in rutas if r not in cerca]
        rutas = rutas[:n]
        self._rutas[clave] = rutas
        return rutas

    # ------------------------------------------------- recorridos a la medida
    def punto_xy(self, lugar) -> tuple[float, float]:
        """Lugar de ``ciudad.LUGARES`` (id) o punto (x, y) de la red -> coordenadas de SUMO."""
        if isinstance(lugar, str):
            from ..ciudad import LUGARES

            if lugar not in LUGARES:
                raise ValueError(f"Lugar desconocido: {lugar}")
            _nombre, lon, lat = LUGARES[lugar]
            return self.traci.simulation.convertGeo(lon, lat, fromGeo=True)
        x, y = lugar
        return float(x), float(y)

    def _red(self):
        """Red de SUMO leída con sumolib (geometría y glorietas), solo cuando se necesita."""
        if getattr(self, "_red_sumolib", None) is None:
            import warnings

            import sumolib

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._red_sumolib = sumolib.net.readNet(str(C.RED_SUMO), withInternal=False)
                self._glorietas = [tuple(r.getEdges()) for r in self._red_sumolib.getRoundabouts()]
        return self._red_sumolib

    def arista_cercana(self, x: float, y: float, tipo: str = "ego_auto", radio_glorieta: float = 75.0) -> str:
        """Tramo más cercano a (x, y) por donde puede andar el vehículo.

        Si hay una glorieta a menos de ``radio_glorieta`` m (los monumentos sobre
        rotondas), se elige un tramo de la glorieta para que la ruta pase por ella.
        """
        import warnings

        red = self._red()
        clase = self.traci.vehicletype.getVehicleClass(tipo)

        def dist(e):
            forma = e.getShape()
            return min(_dist_segmento(x, y, forma[i], forma[i + 1]) for i in range(len(forma) - 1))

        mejor = None
        for glorieta in self._glorietas:
            for eid in glorieta:
                e = red.getEdge(eid)
                if e.allows(clase):
                    d = dist(e)
                    if d < radio_glorieta and (mejor is None or d < mejor[0]):
                        mejor = (d, eid)
        if mejor:
            return mejor[1]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            vecinas = [(d, e.getID()) for e, d in red.getNeighboringEdges(x, y, 250.0) if e.allows(clase)]
        if not vecinas:
            raise ValueError("No hay una vía para carros cerca de ese punto")
        return min(vecinas)[1]

    def ruta_personalizada(self, partida, pasar_por=(), destino=None, tipo: str = "ego_auto",
                           semilla: int = 0) -> RutaEgo:
        """Ruta que sale de ``partida``, pasa por cada lugar de ``pasar_por`` (en orden) y
        termina en ``destino``.

        Los monumentos de la Vía 40 (Ventana al Mundo, Aleta del Tiburón) están sobre
        rotondas: su punto cae en la glorieta, así que la ruta le da la vuelta. Sin
        destino, el recorrido sigue 0.8 a 2 km más por una vía principal.
        """
        tr = self.traci
        puntos = [self.punto_xy(partida)] + [self.punto_xy(p) for p in pasar_por]
        if destino:
            puntos.append(self.punto_xy(destino))
        aristas_obj = [self.arista_cercana(x, y, tipo) for x, y in puntos]
        if not destino:
            aristas_obj.append(self._salida_principal(puntos[-1], aristas_obj[-1], tipo, semilla))
        ruta: list[str] = []
        for a, b in zip(aristas_obj[:-1], aristas_obj[1:]):
            if a == b:
                continue
            r = tr.simulation.findRoute(a, b, tipo)
            if not r.edges:
                raise ValueError(f"No hay ruta en carro de {tr.edge.getStreetName(a) or a} a "
                                 f"{tr.edge.getStreetName(b) or b}")
            tramo = list(r.edges)
            ruta += tramo[1:] if ruta and ruta[-1] == tramo[0] else tramo
        if len(ruta) < 2:
            raise ValueError("El recorrido es demasiado corto")
        largo = sum(self.largo_carril(f"{e}_0") for e in ruta)
        nombres = []
        for e in ruta:
            nom = tr.edge.getStreetName(e)
            if nom and nom not in nombres:
                nombres.append(nom)
        return RutaEgo(tuple(ruta), largo, "recorrido a la medida", " → ".join(nombres[:6]))

    def _salida_principal(self, punto, arista: str, tipo: str, semilla: int) -> str:
        """Un tramo de una vía principal a 0.8-2 km del último punto para seguir el viaje."""
        rng = random.Random(semilla + 31)
        x0, y0 = punto
        candidatas = []
        for via in VIAS_SELECCIONABLES:
            for e in self._aristas_calles((via,)):
                x, y = self.forma_carril(f"{e}_0")[-1]
                if 800.0 <= math.hypot(x - x0, y - y0) <= 2000.0:
                    candidatas.append(e)
        rng.shuffle(candidatas)
        for e in candidatas[:40]:
            r = self.traci.simulation.findRoute(arista, e, tipo)
            if r.edges and r.length < 3500:
                return e
        raise ValueError("No se encontró cómo seguir el viaje desde ese punto")

    # ------------------------------------------------------------ ego
    def insertar_ego(self, ego_id: str, ruta: RutaEgo, tipo: str, max_espera_pasos: int = 40) -> bool:
        rid = f"r_{ego_id}_{int(self.t * 100)}"
        self.traci.route.add(rid, list(ruta.aristas))
        self.traci.vehicle.add(ego_id, rid, tipo, depart="now", departLane="best",
                               departPos="base", departSpeed="0")
        for _ in range(max_espera_pasos):
            self.avanzar()
            if ego_id in self.traci.vehicle.getIDList():
                self.traci.vehicle.setSpeedMode(ego_id, MODO_VELOCIDAD_EGO)
                self.traci.vehicle.setLaneChangeMode(ego_id, MODO_CARRIL_EGO)
                self.traci.vehicle.setColor(ego_id, (244, 167, 185, 255))  # cherry blossom
                return True
        try:
            self.traci.vehicle.remove(ego_id)
        except Exception:
            pass
        return False

    def quitar(self, veh_id: str) -> None:
        try:
            if veh_id in self.traci.vehicle.getIDList():
                if veh_id.startswith("ego"):
                    self.traci.vehicle.unsubscribeContext(veh_id, self.tc.CMD_GET_VEHICLE_VARIABLE, 110.0)
                self.traci.vehicle.remove(veh_id)
        except Exception:
            pass

    def ruta_por_delante(self, ego: str, horizonte_m: float = 140.0) -> "Camino":
        """Camino que seguirá el ego: polilínea, tramos (carriles) y enlaces próximos.

        Las distancias ``s`` se miden desde el frente del ego a lo largo del camino.
        """
        tr = self.traci
        carril = tr.vehicle.getLaneID(ego)
        pos = tr.vehicle.getLanePosition(ego)
        forma = self.forma_carril(carril)
        poli = _recortar_desde(forma, pos)
        tramos = [(0.0, carril)]
        s = self.largo_carril(carril) - pos
        enlaces = []
        for (sig, _prio, _abierto, conflicto, via, estado, _dir, _l) in tr.vehicle.getNextLinks(ego):
            if s > horizonte_m:
                break
            enlaces.append((s, estado, conflicto, via))
            if via:
                tramos.append((s, via))
                poli += self.forma_carril(via)[1:]
                s += self.largo_carril(via)
            if sig:
                tramos.append((s, sig))
                poli += self.forma_carril(sig)[1:]
                s += self.largo_carril(sig)
        return Camino(poli, enlaces, tramos, carril, pos)


class PeatonesDinamicos:
    """Gente a pie lanzada por TraCI con llegadas de Poisson (sin horizonte de tiempo).

    Lee los pares origen-destino de ``sumo/peatones_od.json`` (``demanda.generar_peatones``):
    peatones de toda el área (grupo "ciudad") y paseantes del Malecón, Buenavista y la
    Calle 72 (grupo "paseo"). La ruta a pie de cada par se calcula una vez y se reutiliza.
    """

    def __init__(self, mundo: "MundoSUMO", semilla: int = 0, siembra_s: float = 420.0):
        self.m = mundo
        self.rng = random.Random(semilla + 77)
        self.factor = {"ciudad": 1.0, "paseo": 1.0}
        self.rutas: dict[tuple, tuple | None] = {}
        self.n = 0
        self.grupos: dict[str, tuple] = {}
        try:
            pares = json.loads(C.PEATONES_OD.read_text(encoding="utf-8"))["pares"]
        except (OSError, KeyError, ValueError):
            pares = []
        for grupo in sorted({p["grupo"] for p in pares}):
            lista = [p for p in pares if p["grupo"] == grupo]
            acum, total = [], 0.0
            for p in lista:
                total += p["tasa"]
                acum.append(total)
            self.grupos[grupo] = (lista, acum, total)
        # siembra: la gente que ya venía caminando cuando arranca la simulación
        for grupo, (lista, acum, total) in self.grupos.items():
            for _ in range(int(total * siembra_s * self.m.escala_base)):
                self._lanzar(lista[bisect.bisect_left(acum, self.rng.random() * total)], sembrado=True)

    def _poisson(self, lam: float) -> int:
        k, p, limite = 0, 1.0, math.exp(-lam)
        while True:
            p *= self.rng.random()
            if p <= limite:
                return k
            k += 1

    def paso(self) -> None:
        dt = self.m.dt
        for grupo, (lista, acum, total) in self.grupos.items():
            for _ in range(self._poisson(total * self.factor.get(grupo, 1.0) * self.m.escala_base * dt)):
                self._lanzar(lista[bisect.bisect_left(acum, self.rng.random() * total)])

    def _lanzar(self, par: dict, sembrado: bool = False) -> None:
        tr = self.m.traci
        clave = (par["de"], par["a"])
        if clave not in self.rutas:
            try:
                etapas = tr.simulation.findIntermodalRoute(par["de"], par["a"], modes="")
                aristas = tuple(e for st in etapas for e in st.edges)
                self.rutas[clave] = aristas if len(aristas) >= 1 else None
            except Exception:
                self.rutas[clave] = None
        aristas = self.rutas[clave]
        if not aristas:
            return
        try:
            largo = self.m.largo_carril(f"{aristas[0]}_0")
            pos = self.rng.uniform(0.0, largo) if sembrado else self.rng.uniform(0.0, min(largo, 8.0))
            # nunca aparece encima de un vehículo (por si el tramo no tiene andén propio)
            for vid in tr.edge.getLastStepVehicleIDs(aristas[0]):
                if abs(tr.vehicle.getLanePosition(vid) - pos) < 15.0:
                    return
            self.n += 1
            pid = f"pd{self.n}"
            tr.person.add(pid, aristas[0], pos)
            tr.person.appendWalkingStage(pid, list(aristas), -1)
        except Exception:
            pass


@dataclass
class Camino:
    poli: list
    enlaces: list      # (s, estado_enlace, hay_conflicto, carril_interno)
    tramos: list       # (s_inicio, carril)
    carril: str
    pos: float


def _dist_segmento(x: float, y: float, p1, p2) -> float:
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    f = 0.0 if l2 <= 1e-9 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / l2))
    return math.hypot(x - (x1 + f * dx), y - (y1 + f * dy))


def _recortar_desde(forma: list, pos: float) -> list:
    """Polilínea desde la distancia ``pos`` medida sobre ``forma``."""
    acumulado = 0.0
    for i in range(len(forma) - 1):
        (x1, y1), (x2, y2) = forma[i], forma[i + 1]
        seg = math.hypot(x2 - x1, y2 - y1)
        if acumulado + seg >= pos:
            f = (pos - acumulado) / seg if seg > 0 else 0.0
            inicio = (x1 + f * (x2 - x1), y1 + f * (y2 - y1))
            return [inicio] + list(forma[i + 1:])
        acumulado += seg
    return [tuple(forma[-1]), tuple(forma[-1])]


def punto_en(forma: list, pos: float) -> tuple[float, float, float]:
    """Punto (x, y) y rumbo (rad) a la distancia ``pos`` sobre una polilínea."""
    acumulado = 0.0
    for i in range(len(forma) - 1):
        (x1, y1), (x2, y2) = forma[i], forma[i + 1]
        seg = math.hypot(x2 - x1, y2 - y1)
        if acumulado + seg >= pos or i == len(forma) - 2:
            f = max(0.0, min(1.0, (pos - acumulado) / seg)) if seg > 0 else 0.0
            return x1 + f * (x2 - x1), y1 + f * (y2 - y1), math.atan2(y2 - y1, x2 - x1)
        acumulado += seg
    x, y = forma[-1]
    return x, y, 0.0


def proyectar(poli: list, x: float, y: float) -> tuple[float, float, float]:
    """Proyecta (x, y) sobre la polilínea.

    Devuelve (s a lo largo del camino, desplazamiento lateral con signo [>0 derecha],
    rumbo del camino en ese punto [rad]). Los puntos detrás del ego dan s negativa.
    """
    mejor = (float("inf"), 0.0, 0.0, 0.0)
    acumulado = 0.0
    for i in range(len(poli) - 1):
        (x1, y1), (x2, y2) = poli[i], poli[i + 1]
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-9:
            continue
        seg = math.sqrt(seg2)
        f_libre = ((x - x1) * dx + (y - y1) * dy) / seg2
        f = max(0.0, min(1.0, f_libre))
        if i == 0 and f_libre < 0:
            f = f_libre  # extrapola hacia atrás en el primer segmento
        px, py = x1 + f * dx, y1 + f * dy
        d2 = (x - px) ** 2 + (y - py) ** 2
        if d2 < mejor[0]:
            lateral = ((x - x1) * dy - (y - y1) * dx) / seg
            mejor = (d2, acumulado + f * seg, lateral, math.atan2(dy, dx))
        acumulado += seg
    return mejor[1], mejor[2], mejor[3]
