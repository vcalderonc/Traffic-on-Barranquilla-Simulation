"""Agentes especialistas que conducen un mismo vehículo.

Corresponde al caso "1. Conducción urbana inteligente" de la tabla del profesor:
agentes de Navegación, Velocidad, Obstáculos, Señales y Seguridad que deben
decidir juntos cómo conducir respetando prioridades.

Cada agente recibe el ``ModeloMundo`` que construye Percepción y devuelve una
``Propuesta``. El Coordinador (``coordinador.py``) las combina.

Principio de parsimonia de la guía (sección 0): solo el agente de Velocidad
aprende, porque es donde hay un compromiso difícil (progreso vs. riesgo vs.
confort con sensores ruidosos). Señales, Navegación y Seguridad son reglas,
porque las normas de tránsito y los límites físicos ya se conocen.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import config as C
from ..aprendizaje.perfiles import PerfilVehiculo
from .percepcion import ModeloMundo, Objeto

INF = float("inf")


@dataclass
class Propuesta:
    agente: str
    acel_max: float = INF          # cota superior de aceleración (m/s^2)
    acel: float | None = None      # aceleración sugerida
    carril: int | None = None      # carril solicitado
    veto: bool = False             # solo Seguridad: anula a los demás
    motivo: str = ""
    datos: dict = field(default_factory=dict)


def decel_para_detenerse(v: float, d: float) -> float:
    """Desaceleración (positiva) para pasar de v a 0 en d metros."""
    return v * v / (2.0 * max(d, 0.3))


# ---------------------------------------------------------------- Señales
class AgenteSenales:
    """Semáforos, PARE y límites de velocidad (reglas de tránsito, Ley 769 de 2002)."""

    nombre = "senales"
    MARGEN_LINEA = 1.5

    def __init__(self, perfil: PerfilVehiculo):
        self.perfil = perfil
        self.pare_cumplido: set[str] = set()
        self.t_detenido = 0.0
        self.pare_actual: str | None = None

    def proponer(self, mm: ModeloMundo) -> Propuesta:
        v = mm.v
        b_max = self.perfil.frenado_max(mm.clima.mu)
        cota, motivo = INF, ""
        # 1) límite de velocidad actual y próximos (curvas, giros, calles lentas)
        exceso = v - mm.v_lim
        if exceso > 0:
            cota, motivo = -min(b_max * 0.5, exceso / 0.5), f"límite {mm.v_lim * 3.6:.0f} km/h"
        for s, vmax in mm.limites_proximos:
            if v > vmax:
                a = (vmax * vmax - v * v) / (2.0 * max(s, 1.0))
                if a < cota:
                    cota, motivo = a, f"límite {vmax * 3.6:.0f} km/h en {s:.0f} m"
        # 2) semáforo o PARE
        sen = mm.senal
        if sen is not None:
            d = sen.dist - self.MARGEN_LINEA
            req = decel_para_detenerse(v, d)
            if sen.tipo == "semaforo" and sen.estado in ("rojo", "amarillo"):
                # zona de dilema: con amarillo, si no alcanza a frenar cómodo, sigue
                if sen.estado == "rojo" or req < 0.6 * b_max:
                    if d < 0.5:
                        a = -b_max if v > 0.1 else 0.0
                    else:
                        a = -req
                    if a < cota:
                        cota, motivo = a, f"semáforo en {sen.estado} a {sen.dist:.0f} m"
            elif sen.tipo == "pare":
                if self.pare_actual != sen.id:
                    self.pare_actual, self.t_detenido = sen.id, 0.0
                if sen.id not in self.pare_cumplido:
                    if v < 0.3 and sen.dist < 6.0:
                        self.t_detenido += C.PASO_SIM_S
                    if self.t_detenido >= 1.0 and not sen.conflicto:
                        self.pare_cumplido.add(sen.id)  # ya paró y la vía está libre
                    else:
                        a = -req if d > 0.5 else (-b_max if v > 0.1 else 0.0)
                        if a < cota:
                            espera = " (esperando vía libre)" if self.t_detenido >= 1.0 else ""
                            cota, motivo = a, f"PARE a {sen.dist:.0f} m{espera}"
        return Propuesta(self.nombre, acel_max=cota, motivo=motivo)


# -------------------------------------------------------------- Obstáculos
MARGEN_CLASE = {"vehiculo": 2.5, "peaton": 4.0, "animal": 3.5, "obra": 3.0}


class AgenteObstaculos:
    """Evalúa el riesgo de cada objeto detectado (TTC por clase) y sugiere una aceleración."""

    nombre = "obstaculos"

    def __init__(self, perfil: PerfilVehiculo):
        self.perfil = perfil

    def amenazas(self, mm: ModeloMundo) -> list[Objeto]:
        return sorted((o for o in mm.detectados if o.en_trayectoria and o.s > -1.0),
                      key=lambda o: o.s - MARGEN_CLASE[o.clase])

    def proponer(self, mm: ModeloMundo) -> Propuesta:
        am = self.amenazas(mm)
        vulnerables = sorted((o for o in mm.detectados if o.cerca_via and not o.en_trayectoria),
                             key=lambda o: o.s)
        b_max = self.perfil.frenado_max(mm.clima.mu)
        a_sug = self.perfil.acel_max
        motivo = ""
        if am:
            o = am[0]
            gap = o.s - MARGEN_CLASE[o.clase]
            v_obj = max(0.0, mm.v - o.v_rel)
            # modelo de seguimiento tipo IDM: brecha deseada con 1.5 s de ventaja
            deseada = MARGEN_CLASE[o.clase] + mm.v * 1.5 + mm.v * o.v_rel / (2 * math.sqrt(self.perfil.acel_max * 3.0))
            a_sug = self.perfil.acel_max * (1 - (mm.v / max(mm.v_lim, 1)) ** 4 - (deseada / max(o.s, 0.5)) ** 2)
            if o.v_rel > 0:
                a_sug = min(a_sug, -decel_para_detenerse(o.v_rel, gap) if gap > 0 else -b_max)
            a_sug = max(-b_max, a_sug)
            motivo = f"{o.subtipo} a {o.s:.0f} m (TTC {o.ttc:.1f} s)" if o.ttc < 99 else f"{o.subtipo} a {o.s:.0f} m"
            if v_obj < 0.5 and o.clase in ("obra", "vehiculo"):
                motivo += ", bloquea el carril"
        elif vulnerables:
            o = vulnerables[0]
            motivo = f"{o.subtipo} junto a la vía a {o.s:.0f} m"
        return Propuesta(self.nombre, acel=a_sug, motivo=motivo,
                         datos={"amenazas": am, "vulnerables": vulnerables})


# -------------------------------------------------------------- Navegación
class AgenteNavegacion:
    """Ruta sobre la red real y cambios de carril tácticos.

    1. Esquivar: obras o vehículos detenidos que bloquean el carril.
    2. Adelantar: si el vehículo de adelante va lento (bus, camión, moto despacio) se
       pasa por la izquierda, como manda el Código Nacional de Tránsito (Ley 769 de
       2002, art. 73: se adelanta por la izquierda; art. 60: se transita por la
       derecha). No se adelanta cerca de un cruce, semáforo o PARE, ni a quien está
       detenido en una fila (eso no es "lento", es un trancón o un rojo).
    3. Volver a la derecha cuando ya pasó y el carril derecho está libre.
    Seguridad da (o niega) el visto bueno a cada cambio con los sensores laterales y
    el radar trasero.
    """

    nombre = "navegacion"

    def __init__(self, mundo, ego: str):
        self.m = mundo
        self.ego = ego
        self.cambio_pedido_t = -99.0
        self.lento_desde: float | None = None
        self.objetivo_adelantar: int | None = None
        self.adelantando_desde: float | None = None
        self.adelantamientos = 0

    def carriles_validos(self) -> list[int]:
        """Carriles del tramo actual desde los que se puede seguir la ruta."""
        try:
            mejores = self.m.traci.vehicle.getBestLanes(self.ego)
        except Exception:
            return []
        validos = []
        for (carril, _largo, _ocup, _offset, permite_continuar, _sig) in mejores:
            if permite_continuar and self.m.permite_autos(carril):
                validos.append(int(carril.rsplit("_", 1)[1]))
        return validos

    def proponer(self, mm: ModeloMundo, amenazas: list[Objeto]) -> Propuesta:
        # ¿se completó el cambio al carril de adelantamiento?
        if self.objetivo_adelantar is not None and mm.carril_idx == self.objetivo_adelantar:
            self.adelantamientos += 1
            self.adelantando_desde = mm.t
            self.objetivo_adelantar = None
        p = self._esquivar(mm, amenazas)
        if p.carril is not None or p.motivo or mm.n_carriles_auto < 2:
            self.lento_desde = None
            return p
        return self._adelantar(mm, amenazas) or p

    def _esquivar(self, mm: ModeloMundo, amenazas: list[Objeto]) -> Propuesta:
        bloqueo = next((o for o in amenazas if o.s < 70 and (o.clase == "obra" or
                        (o.clase == "vehiculo" and mm.v - o.v_rel < 0.3 and o.s < 35))), None)
        if bloqueo is None or mm.n_carriles_auto < 2:
            return Propuesta(self.nombre)
        validos = [k for k in self.carriles_validos() if k != mm.carril_idx]
        if not validos:
            return Propuesta(self.nombre, motivo=f"{bloqueo.subtipo} bloquea y no hay carril alterno")
        destino = min(validos, key=lambda k: abs(k - mm.carril_idx))
        paso = destino - mm.carril_idx
        destino = mm.carril_idx + (1 if paso > 0 else -1)
        return Propuesta(self.nombre, carril=destino,
                         motivo=f"cambiar al carril {destino} por {bloqueo.subtipo} a {bloqueo.s:.0f} m",
                         datos={"tipo": "esquivar"})

    @staticmethod
    def _cruce_cerca(mm: ModeloMundo, dist: float) -> bool:
        if mm.senal is not None and mm.senal.dist < dist:
            return True
        return any(s < dist and (conflicto or estado in "rRyYsSwm=")
                   for (s, estado, conflicto, _via) in mm.camino.enlaces)

    @staticmethod
    def _carril_libre(mm: ModeloMundo, lado: int, adelante: float, v_min: float = 0.0) -> bool:
        """¿El carril vecino (lado=-1 izquierda, +1 derecha) está libre hasta ``adelante`` m?

        Se ignoran los vehículos de ese carril que van al menos a ``v_min`` m/s.
        """
        ancho = 3.2
        for o in mm.detectados:
            if o.clase != "vehiculo" or o.en_trayectoria:
                continue
            if 0.6 * ancho < lado * o.lateral < 1.6 * ancho and -3.0 < o.s < adelante:
                if max(0.0, mm.v - o.v_rel) < v_min:
                    return False
        return True

    def _adelantar(self, mm: ModeloMundo, amenazas: list[Objeto]) -> Propuesta | None:
        validos = self.carriles_validos()
        izquierda, derecha = mm.carril_idx + 1, mm.carril_idx - 1
        # 3) ya adelantó: volver a la derecha cuando haya espacio
        if self.adelantando_desde is not None:
            if derecha not in validos:
                self.adelantando_desde = None
            elif mm.t - self.adelantando_desde > 3.0 and self._carril_libre(mm, 1, 25.0) \
                    and not self._cruce_cerca(mm, 25.0):
                return Propuesta(self.nombre, carril=derecha, motivo="volver al carril derecho tras adelantar",
                                 datos={"tipo": "volver"})
        # 2) ¿hay un vehículo lento adelante?
        lider = next((o for o in amenazas if o.clase == "vehiculo"), None)
        if lider is None or lider.s > 55.0:
            self.lento_desde = None
            return None
        v_lider = max(0.0, mm.v - lider.v_rel)
        lento = 1.5 < v_lider < 0.75 * mm.v_lim and (mm.v_lim - v_lider) > 2.5
        if not lento or self._cruce_cerca(mm, 45.0) or izquierda not in validos:
            self.lento_desde = None
            return None
        if self.lento_desde is None:
            self.lento_desde = mm.t
        if mm.t - self.lento_desde < 2.0:  # que no sea un frenazo pasajero
            return None
        if not self._carril_libre(mm, -1, lider.s + 25.0, v_min=v_lider + 2.0):
            return Propuesta(self.nombre, motivo=f"{lider.subtipo} lento, pero el carril izquierdo va ocupado")
        self.objetivo_adelantar = izquierda
        return Propuesta(self.nombre, carril=izquierda,
                         motivo=f"adelantar a {lider.subtipo} lento ({v_lider * 3.6:.0f} km/h) por la izquierda",
                         datos={"tipo": "adelantar"})


# --------------------------------------------------------------- Seguridad
class AgenteSeguridad:
    """Guardrail: veta lo que lleve a un choque inminente (TTC crítico) o a un cambio de carril inseguro."""

    nombre = "seguridad"

    def __init__(self, perfil: PerfilVehiculo, ttc_critico: float = 1.3, activo: bool = True):
        self.perfil = perfil
        self.ttc_critico = ttc_critico
        self.activo = activo
        self.veto_teorico = False

    def carril_seguro(self, mm: ModeloMundo, destino: int) -> bool:
        lado = 1 if destino < mm.carril_idx else -1  # carril de índice menor = a la derecha
        ancho = 3.2
        for o in mm.detectados:
            if o.clase != "vehiculo" or o.en_trayectoria:
                continue
            if 0.6 * ancho < lado * o.lateral < 1.6 * ancho and -12.0 < o.s < 8.0 + max(0.0, o.v_rel) * 1.5:
                return False
        # radar trasero: alguien que viene por ese carril y llegaría en menos de 3 s
        for o in mm.extras.get("traseros", ()):
            if 0.6 * ancho < lado * o.lateral < 1.6 * ancho:
                distancia = -o.s
                if distancia < 8.0 or (o.v_rel < -0.5 and distancia / -o.v_rel < 3.0):
                    return False
        return True

    def proponer(self, mm: ModeloMundo, amenazas: list[Objeto], carril_pedido: int | None) -> Propuesta:
        """Si está desactivada (entrenamiento) no impone nada, pero igual calcula su
        veto en ``veto_teorico`` para que el conductor de reglas pueda dar demostraciones."""
        p = self._evaluar(mm, amenazas, carril_pedido)
        self.veto_teorico = p.veto
        return p if self.activo else Propuesta(self.nombre)

    def _evaluar(self, mm: ModeloMundo, amenazas: list[Objeto], carril_pedido: int | None) -> Propuesta:
        b_max = self.perfil.frenado_max(mm.clima.mu)
        veto, motivo, a = False, "", INF
        for o in amenazas:
            gap = o.s - 1.0
            if (o.ttc < self.ttc_critico or gap < 1.0) and o.v_rel > -0.5:
                veto, a = True, -b_max
                motivo = f"frenado de emergencia: {o.subtipo} TTC {o.ttc:.1f} s"
                break
            # aunque el TTC no sea crítico, ¿alcanza a frenar con la física real?
            if o.v_rel > 0 and decel_para_detenerse(o.v_rel, gap) > 0.9 * b_max:
                veto, a = True, -b_max
                motivo = f"distancia de frenado insuficiente: {o.subtipo} a {o.s:.0f} m"
                break
        carril = None
        if carril_pedido is not None and not self.carril_seguro(mm, carril_pedido):
            carril = -1  # -1 = cambio de carril vetado
            motivo = motivo or "cambio de carril vetado: vehículo en el carril destino"
        return Propuesta(self.nombre, acel_max=a, veto=veto, carril=carril, motivo=motivo)
