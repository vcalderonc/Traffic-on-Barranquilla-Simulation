"""Vehículo autónomo = sistema multiagente + Coordinador (árbitro por prioridades).

Arquitectura (caso "Conducción urbana inteligente"):

    ENTORNO VIRTUAL (SUMO + red real de Barranquilla + imprevistos)
            │ percepciones (TraCI)
       [Percepción]  ── sensores virtuales con ruido, rastreador ──> ModeloMundo
            │
     ┌──────┼───────────┬────────────┬────────────┬───────────┐
  Señales  Obstáculos  Navegación   Velocidad    Seguridad
  (reglas) (riesgo TTC) (ruta/carril) (DQN)      (guardrail)
     └──────┴───────────┴─────┬──────┴────────────┴───────────┘
                         Coordinador
                              │ aceleración + carril
                        Actuadores (TraCI)

Prioridades del Coordinador (de mayor a menor):
  1. Seguridad: si veta, se frena al máximo (nadie la puede anular).
  2. Señales: sus cotas son obligatorias (normas de tránsito).
  3. Velocidad: elige libremente dentro de lo permitido.
  4. Navegación: decide el carril, sujeto al visto bueno de Seguridad.
Obstáculos no impone: informa el riesgo a Velocidad y a Seguridad.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config as C
from ..aprendizaje.perfiles import PerfilVehiculo, accion_a_aceleracion
from .especialistas import (AgenteNavegacion, AgenteObstaculos, AgenteSenales,
                            AgenteSeguridad, Propuesta)
from .percepcion import AgentePercepcion, ModeloMundo
from .velocidad import AgenteVelocidad, accion_mas_cercana, construir_observacion

PRIORIDAD = ("seguridad", "senales", "velocidad", "navegacion")


@dataclass
class Decision:
    acel: float
    carril: int | None
    dominante: str
    motivo: str
    accion_politica: int
    accion_ejecutada: int
    intervencion: str | None          # "seguridad" | "instructor" | None
    propuestas: dict = field(default_factory=dict)
    accion_regla: int = -1            # lo que habría hecho el conductor de reglas (demostración)


class Coordinador:
    nombre = "coordinador"

    def combinar(self, perfil: PerfilVehiculo, mm: ModeloMundo, p_vel: Propuesta, p_sen: Propuesta,
                 p_nav: Propuesta, p_seg: Propuesta) -> tuple[float, int | None, str, str]:
        b_max = perfil.frenado_max(mm.clima.mu)
        a, dominante, motivo = p_vel.acel, "velocidad", p_vel.motivo
        if p_sen.acel_max < a:
            a, dominante, motivo = p_sen.acel_max, "senales", p_sen.motivo
        if p_seg.veto and p_seg.acel_max < a:
            a, dominante, motivo = p_seg.acel_max, "seguridad", p_seg.motivo
        a = max(-b_max, min(perfil.acel_max, a))
        if mm.v <= 0.05 and a < 0:
            a = 0.0
        carril = None
        if p_nav.carril is not None:
            if p_seg.carril == -1:
                motivo = motivo if dominante != "velocidad" else p_seg.motivo
            else:
                carril = p_nav.carril
                if dominante == "velocidad":
                    dominante, motivo = "navegacion", p_nav.motivo
        return a, carril, dominante, motivo


class VehiculoAutonomo:
    def __init__(self, mundo, ego_id: str, perfil: PerfilVehiculo, clima: C.Clima,
                 politica=None, explorar: bool = False, guardrail: bool = True,
                 normalizado: bool = True, perfil_origen: PerfilVehiculo | None = None,
                 semilla: int = 0, ruido_sensores: bool = True):
        self.m = mundo
        self.id = ego_id
        self.perfil = perfil
        self.clima = clima
        self.normalizado = normalizado
        self.perfil_ref = perfil if normalizado else (perfil_origen or perfil)
        self.percepcion = AgentePercepcion(mundo, ego_id, perfil.ancho_m, clima, semilla, ruido_sensores)
        self.senales = AgenteSenales(perfil)
        self.obstaculos = AgenteObstaculos(perfil)
        self.navegacion = AgenteNavegacion(mundo, ego_id)
        self.velocidad = AgenteVelocidad(perfil, politica, explorar, normalizado, perfil_origen)
        self.seguridad = AgenteSeguridad(perfil, activo=guardrail)
        self.coordinador = Coordinador()
        self.a_prev = 0.0
        self.mm: ModeloMundo | None = None
        self.obs = None
        self._carril_pedido_t = -99.0

    # ---------------------------------------------------- percepción
    def observar(self):
        mm = self.percepcion.percibir(self.a_prev)
        p_obs = self.obstaculos.proponer(mm)
        p_nav = self.navegacion.proponer(mm, p_obs.datos["amenazas"])
        bloqueado = p_nav.carril is not None or "bloquea" in p_nav.motivo
        obs = construir_observacion(mm, p_obs.datos["amenazas"], p_obs.datos["vulnerables"],
                                    self.perfil, self.perfil_ref, bloqueado, p_obs.acel)
        self.mm, self.obs = mm, obs
        self._p_obs, self._p_nav = p_obs, p_nav
        return obs

    # ---------------------------------------------------- decisión
    def decidir(self, accion_externa: int | None = None, instructor=None) -> Decision:
        mm, obs = self.mm, self.obs
        p_obs, p_nav = self._p_obs, self._p_nav
        p_sen = self.senales.proponer(mm)
        if accion_externa is not None:
            self.velocidad.ultima_accion = accion_externa
            a_ext = accion_a_aceleracion(accion_externa, self.perfil, mm.clima.mu, self.normalizado,
                                         None if self.normalizado else self.perfil_ref)
            p_vel = Propuesta("velocidad", acel=a_ext, motivo=f"política: acción {accion_externa}")
        else:
            p_vel = self.velocidad.proponer(mm, obs, p_obs.acel)
        accion_politica = self.velocidad.ultima_accion
        intervencion = None
        if instructor is not None:
            k_inst, intervino, motivo_i = instructor.supervisar(obs, accion_politica)
            if intervino:
                intervencion = "instructor"
                p_vel = Propuesta("velocidad", acel=accion_a_aceleracion(k_inst, self.perfil, mm.clima.mu),
                                  motivo=f"instructor (doble comando): {motivo_i}")
        p_seg = self.seguridad.proponer(mm, p_obs.datos["amenazas"], p_nav.carril)
        a, carril, dominante, motivo = self.coordinador.combinar(self.perfil, mm, p_vel, p_sen, p_nav, p_seg)
        if dominante == "seguridad":
            intervencion = "seguridad"
        if dominante == "velocidad" and p_obs.motivo:
            motivo = f"{motivo} | {p_obs.motivo}"
        ejecutada = accion_mas_cercana(a, self.perfil, mm.clima.mu)
        # demostración del conductor de reglas: IDM de Obstáculos, cotas de Señales y veto de Seguridad
        b_max = self.perfil.frenado_max(mm.clima.mu)
        a_regla = -b_max if self.seguridad.veto_teorico else min(p_obs.acel, p_sen.acel_max)
        regla = accion_mas_cercana(max(-b_max, min(self.perfil.acel_max, a_regla)), self.perfil, mm.clima.mu)
        return Decision(a, carril, dominante, motivo, accion_politica, ejecutada, intervencion,
                        {"senales": p_sen.motivo, "obstaculos": p_obs.motivo, "navegacion": p_nav.motivo,
                         "seguridad": p_seg.motivo, "velocidad": p_vel.motivo}, regla)

    # ---------------------------------------------------- actuadores
    def actuar(self, d: Decision) -> None:
        tr = self.m.traci
        v_nueva = max(0.0, self.mm.v + d.acel * self.m.dt)
        tr.vehicle.setSpeed(self.id, v_nueva)
        if d.carril is not None and self.m.t - self._carril_pedido_t > 2.0:
            try:
                tr.vehicle.changeLane(self.id, d.carril, 3.0)
                self._carril_pedido_t = self.m.t
            except Exception:
                pass
        self.a_prev = d.acel
