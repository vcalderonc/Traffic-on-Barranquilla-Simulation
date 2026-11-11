"""Conexión con SUMO: arranque, vehículo autónomo, consultas de verdad-terreno.

``MundoSUMO`` mantiene una sola corrida de SUMO por proceso. Los episodios del
vehículo autónomo se encadenan sobre el mismo tráfico (no se reinicia SUMO en cada
episodio), lo que ahorra el costo de cargar la red y deja el tráfico ya "caliente".
"""
from __future__ import annotations

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
        self._formas: dict[str, list] = {}
        self._largos: dict[str, float] = {}
        self._anchos: dict[str, float] = {}
        self._vmax: dict[str, float] = {}
        self._permite_auto: dict[str, bool] = {}
        self.avanzar(int(calentamiento_s / self.dt))
        self._rutas: dict[str, list[RutaEgo]] = {}

    # ------------------------------------------------------------------ tiempo
    def avanzar(self, pasos: int = 1) -> None:
        for _ in range(pasos):
            self.traci.simulationStep()

    @property
    def t(self) -> float:
        return self.traci.simulation.getTime()

    def cerrar(self) -> None:
        try:
            self.traci.close()
        except Exception:
            pass

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
                self.traci.vehicle.setColor(ego_id, (255, 170, 0, 255))
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


@dataclass
class Camino:
    poli: list
    enlaces: list      # (s, estado_enlace, hay_conflicto, carril_interno)
    tramos: list       # (s_inicio, carril)
    carril: str
    pos: float


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
