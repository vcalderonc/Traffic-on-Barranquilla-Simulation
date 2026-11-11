"""Agente de Percepción: sensores virtuales (cámara + LiDAR simulados).

No hay visión por computador: la verdad del simulador se degrada con un modelo de
sensor explícito, que es la práctica estándar en simulación de vehículos
autónomos. El modelo tiene:

* alcance que depende del clima (despejado 90 m, lluvia 55 m, noche 45 m);
* probabilidad de detección por clase y distancia (una iguana se ve peor que un bus);
* ruido gaussiano en distancia y velocidad que crece con la distancia y el clima;
* confusión de clase peatón <-> animal de noche o con lluvia;
* un rastreador con memoria corta (0.75 s) que sostiene objetos que se dejan de
  ver por un ciclo: es el "estado interno" del agente reactivo basado en modelo.

Clases que reconoce: vehículo (auto, taxi, moto, bus, camión), peatón, animal
(perro, iguana) y obra (conos). Señales: semáforo, PARE y límite de velocidad.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .. import config as C
from ..entorno.mundo import Camino, MundoSUMO, proyectar

PROB_CLASE = {"vehiculo": 0.99, "peaton": 0.95, "animal": 0.85, "obra": 0.97}
FACTOR_TAMANO = {"iguana": 0.55, "perro": 0.85}


def clase_de_tipo(tipo: str) -> tuple[str, str]:
    if tipo.startswith("obs_"):
        sub = tipo[4:]
        return {"peaton": ("peaton", "peaton"), "perro": ("animal", "perro"),
                "iguana": ("animal", "iguana"), "obra": ("obra", "conos")}.get(sub, ("obra", sub))
    for clave in ("moto", "bus", "camion", "taxi"):
        if clave in tipo:
            return "vehiculo", clave
    return "vehiculo", "auto"


@dataclass
class Objeto:
    id: str
    clase: str
    subtipo: str
    s: float              # distancia libre a lo largo del camino (m)
    lateral: float        # desplazamiento lateral del centro (m)
    v_rel: float          # velocidad de acercamiento (m/s, >0 se acerca)
    ancho: float
    en_trayectoria: bool
    cerca_via: bool
    confianza: float = 1.0
    x: float = 0.0
    y: float = 0.0

    @property
    def ttc(self) -> float:
        if self.v_rel <= 0.05:
            return float("inf")
        return max(0.0, self.s) / self.v_rel


@dataclass
class Senal:
    tipo: str      # "semaforo" | "pare"
    estado: str    # verde | amarillo | rojo | pare
    dist: float
    conflicto: bool = False
    id: str = ""


@dataclass
class ModeloMundo:
    t: float
    v: float
    a_prev: float
    v_lim: float
    limites_proximos: list           # [(s, vmax)]
    detectados: list                 # objetos percibidos (con ruido)
    verdad: list                     # objetos reales (para el evaluador)
    senal: Senal | None
    camino: Camino
    carril_idx: int
    n_carriles_auto: int
    clima: C.Clima
    x: float = 0.0
    y: float = 0.0
    angulo: float = 0.0
    extras: dict = field(default_factory=dict)


class AgentePercepcion:
    nombre = "percepcion"

    def __init__(self, mundo: MundoSUMO, ego: str, ancho_ego: float, clima: C.Clima,
                 semilla: int = 0, ruido_activo: bool = True):
        self.m = mundo
        self.ego = ego
        self.ancho_ego = ancho_ego
        self.clima = clima
        self.rng = random.Random(semilla)
        self.ruido_activo = ruido_activo
        self.memoria: dict[str, tuple[Objeto, float]] = {}
        self._confusion: dict[str, bool] = {}
        tc = mundo.tc
        mundo.traci.vehicle.subscribeContext(
            ego, tc.CMD_GET_VEHICLE_VARIABLE, 110.0,
            [tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_ANGLE, tc.VAR_TYPE, tc.VAR_LENGTH, tc.VAR_WIDTH])

    # ---------------------------------------------------------- verdad
    def _objetos_reales(self, camino: Camino, v_ego: float, x0: float, y0: float) -> list[Objeto]:
        tr = self.m.traci
        tc = self.m.tc
        out: list[Objeto] = []
        ctx = tr.vehicle.getContextSubscriptionResults(self.ego) or {}
        for vid, var in ctx.items():
            if vid == self.ego:
                continue
            x, y = var[tc.VAR_POSITION]
            ang = math.radians(var[tc.VAR_ANGLE])
            largo, ancho = var[tc.VAR_LENGTH], var[tc.VAR_WIDTH]
            hx, hy = math.sin(ang), math.cos(ang)  # SUMO: 0 = norte, horario
            clase, sub = clase_de_tipo(var[tc.VAR_TYPE])
            s1, lat1, rumbo = proyectar(camino.poli, x, y)
            s2, lat2, _ = proyectar(camino.poli, x - largo * hx, y - largo * hy)
            s = min(s1, s2)
            if s < -3.0 or s > 120.0:
                continue
            lateral = 0.5 * (lat1 + lat2)
            v_obj = var[tc.VAR_SPEED] * (hx * math.cos(rumbo) + hy * math.sin(rumbo))
            out.append(self._clasificar(vid, clase, sub, s, lateral, v_ego - v_obj, ancho, x, y))
        # peatones de SUMO (andenes y cebras)
        for pid in tr.person.getIDList():
            x, y = tr.person.getPosition(pid)
            if abs(x - x0) > 60 or abs(y - y0) > 60:
                continue
            s, lateral, rumbo = proyectar(camino.poli, x, y)
            if s < -2.0 or s > 60.0:
                continue
            ang = math.radians(tr.person.getAngle(pid))
            v_obj = tr.person.getSpeed(pid) * (math.sin(ang) * math.cos(rumbo) + math.cos(ang) * math.sin(rumbo))
            out.append(self._clasificar(pid, "peaton", "peaton", s, lateral, v_ego - v_obj, 0.6, x, y))
        return out

    def _clasificar(self, oid, clase, sub, s, lateral, v_rel, ancho, x, y) -> Objeto:
        umbral = self.ancho_ego / 2 + ancho / 2 + 0.25
        en_tray = abs(lateral) < umbral and s > -1.0
        cerca = (clase in ("peaton", "animal")) and abs(lateral) < umbral + 4.0 and 0 < s < 50
        return Objeto(oid, clase, sub, s, lateral, v_rel, ancho, en_tray, cerca, 1.0, x, y)

    # ------------------------------------------------------- sensor
    def _sensar(self, reales: list[Objeto], t: float) -> list[Objeto]:
        if not self.ruido_activo:
            return [o for o in reales if o.s <= self.clima.alcance_m]
        vistos: list[Objeto] = []
        k_ruido = self.clima.ruido
        for o in reales:
            if o.s > self.clima.alcance_m:
                continue
            frac = max(0.0, o.s) / self.clima.alcance_m
            p = PROB_CLASE[o.clase] * FACTOR_TAMANO.get(o.subtipo, 1.0)
            p *= (1.0 - self.clima.p_omision) * (1.0 - 0.45 * frac ** 3)
            if self.rng.random() > p:
                continue
            sigma_s = (0.15 + 0.02 * max(0.0, o.s)) * k_ruido
            sigma_v = 0.25 * k_ruido
            clase, sub = o.clase, o.subtipo
            if self.clima.nombre != "despejado" and clase in ("peaton", "animal"):
                if o.id not in self._confusion:
                    self._confusion[o.id] = self.rng.random() < 0.05
                if self._confusion[o.id]:
                    clase = "animal" if clase == "peaton" else "peaton"
            vistos.append(Objeto(o.id, clase, sub, o.s + self.rng.gauss(0, sigma_s),
                                 o.lateral + self.rng.gauss(0, 0.1 * k_ruido),
                                 o.v_rel + self.rng.gauss(0, sigma_v), o.ancho,
                                 o.en_trayectoria, o.cerca_via, round(p, 2), o.x, o.y))
        # rastreador: sostiene lo visto hace poco
        ids = {o.id for o in vistos}
        for oid, (prev, t_prev) in list(self.memoria.items()):
            if oid in ids:
                continue
            dt = t - t_prev
            if dt <= 0.75:
                vistos.append(Objeto(prev.id, prev.clase, prev.subtipo, prev.s - prev.v_rel * dt,
                                     prev.lateral, prev.v_rel, prev.ancho, prev.en_trayectoria,
                                     prev.cerca_via, prev.confianza * 0.6, prev.x, prev.y))
            else:
                del self.memoria[oid]
        for o in vistos:
            if o.id in ids:
                self.memoria[o.id] = (o, t)
        return vistos

    # ------------------------------------------------------- señales
    def _senal(self, camino: Camino) -> Senal | None:
        tr = self.m.traci
        mejor: Senal | None = None
        for (tls, _idx, dist, estado) in tr.vehicle.getNextTLS(self.ego):
            if dist > 150:
                break
            e = estado.lower()
            nombre = "verde" if e == "g" else "amarillo" if e == "y" else "rojo" if e in ("r", "u") else None
            if nombre:
                mejor = Senal("semaforo", nombre, dist, id=tls)
            break
        for (s, estado, conflicto, via) in camino.enlaces:
            if s > 150:
                break
            if estado == "s":
                if mejor is None or s < mejor.dist:
                    mejor = Senal("pare", "pare", s, conflicto, id=via or f"pare@{round(s)}")
                break
        return mejor

    def _limites(self, camino: Camino) -> list:
        return [(s, self.m.vmax_carril(c)) for s, c in camino.tramos[1:] if s < 120]

    # ------------------------------------------------------- ciclo
    def percibir(self, a_prev: float) -> ModeloMundo:
        tr = self.m.traci
        camino = self.m.ruta_por_delante(self.ego)
        v = tr.vehicle.getSpeed(self.ego)
        x, y = tr.vehicle.getPosition(self.ego)
        t = self.m.t
        reales = self._objetos_reales(camino, v, x, y)
        detectados = self._sensar(reales, t)
        arista = tr.vehicle.getRoadID(self.ego)
        n_autos = 1
        if not arista.startswith(":"):
            n = tr.edge.getLaneNumber(arista)
            n_autos = sum(1 for k in range(n) if self.m.permite_autos(f"{arista}_{k}"))
        return ModeloMundo(
            t=t, v=v, a_prev=a_prev, v_lim=tr.vehicle.getAllowedSpeed(self.ego),
            limites_proximos=self._limites(camino), detectados=detectados, verdad=reales,
            senal=self._senal(camino), camino=camino, carril_idx=tr.vehicle.getLaneIndex(self.ego),
            n_carriles_auto=n_autos, clima=self.clima, x=x, y=y, angulo=tr.vehicle.getAngle(self.ego),
        )
