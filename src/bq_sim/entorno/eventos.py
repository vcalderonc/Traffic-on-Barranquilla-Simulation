"""Eventos estocásticos frente al vehículo autónomo.

SUMO modela bien autos, buses, motos y peatones en andenes y cebras, pero no los
imprevistos que más ponen a prueba a un conductor en Barranquilla: el peatón que
cruza por la mitad de la cuadra, el perro callejero, la iguana del Malecón, el
carril cerrado con conos o el carro de adelante que frena en seco.

Cada imprevisto se genera como un proceso de Poisson en el espacio recorrido
(tasa por km en ``config.ParamEventos``). Peatones, animales y conos se insertan
en SUMO como "vehículos fantasma" detenidos (tipos ``obs_*``) para que todo el
tráfico reaccione a ellos y SUMO detecte los choques; el visor los dibuja con su
forma real.

Vendedores de semáforo: cuando el vehículo autónomo se detiene (o se está deteniendo)
ante un rojo, un vendedor ambulante puede meterse entre los carros a ofrecer agua,
minutos o frutas, y se queda en el carril hasta que cambia a verde. La probabilidad
depende del estrato de la zona (``ciudad.estrato``): más en el centro y los corredores
populares, menos en Alto Prado o Villa Country. Es el caso típico de "arrancar en
verde sin mirar".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import config as C
from .mundo import MundoSUMO, punto_en

TIPO_SUMO = {"peaton": "obs_peaton", "perro": "obs_perro", "iguana": "obs_iguana", "conos": "obs_obra",
             "vendedor": "obs_vendedor"}
CLASE = {"peaton": "peaton", "perro": "animal", "iguana": "animal", "conos": "obra", "vendedor": "peaton"}

# Probabilidad de que aparezca un vendedor en un semáforo en rojo, según el estrato.
PROB_VENDEDOR = {0: 0.15, 1: 0.55, 2: 0.55, 3: 0.45, 4: 0.30, 5: 0.18, 6: 0.12}


@dataclass
class ObjetoEvento:
    id: str
    subtipo: str
    arista: str
    pos: float
    carriles: list            # secuencia de índices de carril que recorre
    t_carril: float           # tiempo para cruzar un carril (s)
    espera_inicial: float     # tiempo quieto en el andén antes de cruzar
    imprudente: bool
    k: int = 0                # índice actual dentro de ``carriles``
    t_entrada: float = 0.0
    t_pausa_hasta: float = 0.0
    regresa: bool = False
    espera_en: int | None = None  # vendedor: índice de ``carriles`` donde espera el verde
    t_creado: float = 0.0
    vivo: bool = True
    en_sumo: bool = False
    historial: list = field(default_factory=list)

    @property
    def clase(self) -> str:
        return CLASE[self.subtipo]


class GestorEventos:
    def __init__(self, mundo: MundoSUMO, params: C.ParamEventos | None = None,
                 multiplicador: float = 1.0):
        self.m = mundo
        self.p = params or C.ParamEventos()
        self.mult = multiplicador
        self.mult_clase: dict[str, float] = {}  # perfil de imprevistos de la zona
        self.rng = mundo.rng
        self.objetos: dict[str, ObjetoEvento] = {}
        self.frenadas: list[dict] = []
        self.registro: list[dict] = []  # bitácora de eventos del episodio
        self._n = 0
        self._ego: str | None = None
        self._ultimo_rojo: tuple = ("", -1e9)

    # ------------------------------------------------------------ ciclo
    def reiniciar(self) -> None:
        for ob in list(self.objetos.values()):
            self._retirar(ob)
        self.objetos.clear()
        for f in self.frenadas:
            self._liberar_lider(f)
        self.frenadas.clear()
        self.registro.clear()

    def paso(self, ego: str, v_ego: float) -> None:
        """Genera nuevos eventos según la distancia recorrida y actualiza los vivos."""
        dist = v_ego * self.m.dt / 1000.0  # km recorridos en este paso
        for tipo, tasa in self.p.tasa_por_km.items():
            if self.rng.random() < tasa * self.mult * self.mult_clase.get(tipo, 1.0) * dist:
                if tipo == "frenada_lider":
                    self._frenada_lider(ego)
                elif tipo == "animal":
                    self._crear(ego, "perro" if self.rng.random() < 0.65 else "iguana")
                elif tipo == "obra":
                    self._crear(ego, "conos")
                else:
                    self._crear(ego, "peaton")
        self._ego = ego
        self._vendedor(ego, v_ego)
        self._actualizar()

    # ----------------------------------------------------------- creación
    def _punto_adelante(self, ego: str, d: float):
        tr = self.m.traci
        ruta = tr.vehicle.getRoute(ego)
        i = tr.vehicle.getRouteIndex(ego)
        if i < 0:
            return None
        pos = tr.vehicle.getLanePosition(ego)
        arista = ruta[i]
        if arista.startswith(":"):
            return None
        restante = self.m.largo_carril(f"{arista}_0") - pos
        acumulado = 0.0
        if d < restante:
            return arista, pos + d
        acumulado = restante
        for e in ruta[i + 1:]:
            largo = self.m.largo_carril(f"{e}_0")
            if acumulado + largo > d:
                p = d - acumulado
                if 6.0 < p < largo - 6.0:
                    return e, p
                return None
            acumulado += largo + 8.0  # aproximación del cruce interno
        return None

    def _carriles(self, arista: str):
        n = self.m.traci.edge.getLaneNumber(arista)
        autos = [k for k in range(n) if self.m.permite_autos(f"{arista}_{k}")]
        anden = [k for k in range(n) if k not in autos]
        return autos, anden

    def _crear(self, ego: str, subtipo: str) -> None:
        lo, hi = (70.0, 92.0) if subtipo == "conos" else self.p.dist_aparicion_m
        punto = self._punto_adelante(ego, self.rng.uniform(max(lo, 25.0), hi))
        if punto is None:
            return
        arista, pos = punto
        autos, anden = self._carriles(arista)
        if not autos:
            return
        self._n += 1
        oid = f"obs_{subtipo}_{self._n}"
        if subtipo == "conos":
            if len(autos) < 2:
                return
            carril_ego = self.m.traci.vehicle.getLaneIndex(ego)
            k = carril_ego if carril_ego in autos else self.rng.choice(autos)
            ob = ObjetoEvento(oid, subtipo, arista, pos, [k], t_carril=1e9, espera_inicial=0.0,
                              imprudente=False)
        else:
            desde_derecha = self.rng.random() < 0.6
            seq = (anden[:1] + autos) if desde_derecha else list(reversed(autos))
            if subtipo == "peaton":
                vel = self.rng.uniform(1.0, 1.7)
            elif subtipo == "perro":
                vel = self.rng.uniform(1.6, 3.5)
            else:
                vel = self.rng.uniform(0.35, 0.8)
            ancho = self.m.ancho_carril(f"{arista}_{autos[0]}")
            ob = ObjetoEvento(oid, subtipo, arista, pos, seq, t_carril=ancho / vel,
                              espera_inicial=self.rng.uniform(0.3, 2.5) if seq[0] in anden else 0.0,
                              imprudente=self.rng.random() < 0.5)
        if ob.carriles[0] in autos and not self._libre(ob, ob.carriles[0]):
            return
        if not self._insertar(ob, ob.carriles[0]):
            return
        ob.t_entrada = self.m.t
        self.objetos[oid] = ob
        self.registro.append({"t": round(self.m.t, 2), "evento": subtipo, "id": oid,
                              "calle": self.m.traci.edge.getStreetName(arista)})

    def _estado_semaforo(self, ego: str | None):
        try:
            prox = self.m.traci.vehicle.getNextTLS(ego) if ego else ()
        except Exception:
            return None
        return prox[0] if prox else None

    def _vendedor(self, ego: str, v_ego: float) -> None:
        """Vendedor ambulante que se mete entre los carros detenidos en un rojo."""
        if v_ego > 6.0:
            return
        sem = self._estado_semaforo(ego)
        if sem is None:
            return
        tls, _idx, dist, estado = sem
        if estado.lower() not in ("r", "y", "u") or not 10.0 < dist < 45.0:
            return
        if tls == self._ultimo_rojo[0] and self.m.t - self._ultimo_rojo[1] < 90.0:
            return  # una sola oportunidad por semáforo
        self._ultimo_rojo = (tls, self.m.t)
        tr = self.m.traci
        from ..ciudad import estrato

        x, y = tr.vehicle.getPosition(ego)
        lon, lat = self.m.lonlat(x, y)
        prob = PROB_VENDEDOR.get(estrato(lon, lat), 0.3) * self.mult * self.mult_clase.get("vendedor", 1.0)
        if self.rng.random() >= min(0.9, prob):
            return
        arista = tr.vehicle.getRoadID(ego)
        if arista.startswith(":"):
            return
        autos, anden = self._carriles(arista)
        k_ego = tr.vehicle.getLaneIndex(ego)
        if k_ego not in autos:
            return
        pos = tr.vehicle.getLanePosition(ego) + min(dist - 3.0, self.rng.uniform(6.0, 12.0))
        if pos > self.m.largo_carril(f"{arista}_{k_ego}") - 1.0:
            return
        # entra desde el andén (o desde el borde derecho), llega al carril del ego,
        # ofrece hasta que cambie a verde y se devuelve
        ida = anden[:1] + [k for k in autos if k <= k_ego]
        seq = ida + ida[-2::-1]
        self._n += 1
        vel = self.rng.uniform(0.8, 1.3)
        ancho = self.m.ancho_carril(f"{arista}_{k_ego}")
        ob = ObjetoEvento(f"obs_vendedor_{self._n}", "vendedor", arista, pos, seq, t_carril=ancho / vel,
                          espera_inicial=self.rng.uniform(0.2, 1.0) if seq[0] in anden else 0.0,
                          imprudente=False, espera_en=len(ida) - 1, t_creado=self.m.t)
        if ob.carriles[0] in autos and not self._libre(ob, ob.carriles[0]):
            return
        if not self._insertar(ob, ob.carriles[0]):
            return
        ob.t_entrada = self.m.t
        self.objetos[ob.id] = ob
        self.registro.append({"t": round(self.m.t, 2), "evento": "vendedor", "id": ob.id,
                              "calle": tr.edge.getStreetName(arista), "estrato": estrato(lon, lat)})

    def _insertar(self, ob: ObjetoEvento, k: int) -> bool:
        tr = self.m.traci
        carril = f"{ob.arista}_{k}"
        rid = f"r_{ob.id}"
        try:
            tr.route.add(rid, [ob.arista])
            tr.vehicle.add(ob.id, rid, TIPO_SUMO[ob.subtipo], depart="now",
                           departLane=str(k), departPos=str(ob.pos), departSpeed="0")
            tr.vehicle.moveTo(ob.id, carril, ob.pos)
            tr.vehicle.setSpeedMode(ob.id, 0)
            tr.vehicle.setLaneChangeMode(ob.id, 0)
            tr.vehicle.setSpeed(ob.id, 0.0)
            ob.en_sumo = True
            return True
        except Exception:
            return False

    def _retirar(self, ob: ObjetoEvento) -> None:
        if ob.en_sumo:
            self.m.quitar(ob.id)
        ob.vivo = False
        ob.en_sumo = False

    # --------------------------------------------------------- dinámica
    def _libre(self, ob: ObjetoEvento, k: int) -> bool:
        """¿Puede el objeto entrar al carril k sin que un vehículo de fondo lo arrolle?"""
        tr = self.m.traci
        carril = f"{ob.arista}_{k}"
        for v in tr.lane.getLastStepVehicleIDs(carril):
            if v == ob.id or v.startswith("obs_"):
                continue
            p = tr.vehicle.getLanePosition(v)
            largo = tr.vehicle.getLength(v)
            if p - largo - 1.0 <= ob.pos <= p + 2.0:
                return False  # ocupado físicamente
            vel = tr.vehicle.getSpeed(v)
            if v.startswith("ego") and ob.imprudente:
                # imprudente, pero no suicida: se lanza aunque obligue a frenar fuerte,
                # solo se abstiene si el vehículo ya no podría detenerse ni frenando al máximo
                frenado = vel * vel / (2 * 7.0) + vel * 0.3 + 1.0
            else:
                frenado = vel * vel / (2 * 4.0) + 3.0
            if 0 < ob.pos - p < frenado:
                return False
        return True

    def _actualizar(self) -> None:
        t = self.m.t
        tr = self.m.traci
        vivos = set(tr.vehicle.getIDList())
        for ob in list(self.objetos.values()):
            if not ob.vivo:
                continue
            if ob.en_sumo and ob.id not in vivos:  # SUMO lo quitó (teletransporte)
                ob.vivo = False
                continue
            if ob.subtipo == "conos":
                continue
            if ob.subtipo == "vendedor":
                if t - ob.t_creado > 75.0:  # nunca se queda para siempre
                    self._retirar(ob)
                    continue
                if ob.espera_en is not None and ob.k == ob.espera_en and t - ob.t_entrada >= ob.t_carril:
                    sem = self._estado_semaforo(self._ego)
                    if sem is not None and sem[3].lower() in ("r", "y", "u"):
                        continue  # sigue ofreciendo mientras esté en rojo
                    ob.espera_en = None  # cambió a verde: termina la venta y se devuelve
                    ob.t_pausa_hasta = t + self.rng.uniform(0.6, 2.2)
                    continue
            if t < ob.t_pausa_hasta:
                continue
            espera = ob.espera_inicial if ob.k == 0 else 0.0
            if t - ob.t_entrada < ob.t_carril + espera:
                # perro: puede detenerse a mitad del carril o devolverse
                if ob.subtipo == "perro" and ob.k > 0 and self.rng.random() < 0.01:
                    if self.rng.random() < 0.6:
                        ob.t_pausa_hasta = t + self.rng.uniform(0.5, 2.5)
                    elif not ob.regresa:
                        ob.regresa = True
                        ob.carriles = ob.carriles[:ob.k + 1][::-1]
                        ob.k = 0
                        ob.t_entrada = t
                continue
            # pasar al siguiente carril
            if ob.k + 1 >= len(ob.carriles):
                self._retirar(ob)
                continue
            sig = ob.carriles[ob.k + 1]
            if not self._libre(ob, sig):
                continue
            try:
                tr.vehicle.moveTo(ob.id, f"{ob.arista}_{sig}", ob.pos)
                tr.vehicle.setSpeed(ob.id, 0.0)
                ob.k += 1
                ob.t_entrada = t
            except Exception:
                self._retirar(ob)
        for f in list(self.frenadas):
            if t >= f["hasta"]:
                self._liberar_lider(f)
                self.frenadas.remove(f)

    # ------------------------------------------------------ frenada súbita
    def _frenada_lider(self, ego: str) -> None:
        tr = self.m.traci
        lider = tr.vehicle.getLeader(ego, 45.0)
        if not lider:
            return
        lid, gap = lider
        if lid.startswith("obs_") or any(f["id"] == lid for f in self.frenadas):
            return
        v = tr.vehicle.getSpeed(lid)
        if v < 4.0:
            return
        objetivo = v * self.rng.uniform(0.0, 0.35)
        dur = max(0.5, (v - objetivo) / self.rng.uniform(5.0, 7.0))
        try:
            tr.vehicle.slowDown(lid, objetivo, dur)
        except Exception:
            return
        self.frenadas.append({"id": lid, "hasta": self.m.t + dur + self.rng.uniform(1.0, 3.0)})
        self.registro.append({"t": round(self.m.t, 2), "evento": "frenada_lider", "id": lid,
                              "gap_m": round(gap, 1)})

    def _liberar_lider(self, f: dict) -> None:
        try:
            self.m.traci.vehicle.setSpeed(f["id"], -1)
        except Exception:
            pass

    # ------------------------------------------------------ visor
    def posiciones_render(self) -> list[dict]:
        """Posición suavizada (cruce lateral interpolado) para el visor 3D."""
        out = []
        t = self.m.t
        for ob in self.objetos.values():
            if not ob.vivo:
                continue
            k = ob.carriles[ob.k]
            forma = self.m.forma_carril(f"{ob.arista}_{k}")
            x, y, rumbo = punto_en(forma, ob.pos)
            if ob.subtipo != "conos" and ob.k + 1 < len(ob.carriles) and t >= ob.t_pausa_hasta:
                espera = ob.espera_inicial if ob.k == 0 else 0.0
                f = max(0.0, min(1.0, (t - ob.t_entrada - espera) / ob.t_carril))
                x2, y2, _ = punto_en(self.m.forma_carril(f"{ob.arista}_{ob.carriles[ob.k + 1]}"), ob.pos)
                x, y = x + f * (x2 - x), y + f * (y2 - y)
                rumbo = math.atan2(y2 - y, x2 - x) if (x2, y2) != (x, y) else rumbo
            out.append({"id": ob.id, "tipo": ob.subtipo, "x": round(x, 2), "y": round(y, 2),
                        "rumbo": round(rumbo, 3)})
        return out
