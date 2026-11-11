"""Agente de Velocidad: el único que aprende (Double DQN).

Observación (28 valores, todos normalizados y SIN unidades del vehículo):
las distancias se expresan como tiempo para colisión o como la fracción de la
capacidad de frenado propia que haría falta. Por eso el mismo conocimiento sirve
para un automóvil y para un bus (idea de normalización de la propuesta original).

Acciones: 7 niveles longitudinales como fracción de la capacidad del vehículo
(ver ``perfiles.ACCIONES``).
"""
from __future__ import annotations

import math

import numpy as np

from ..aprendizaje.perfiles import ACCIONES, PerfilVehiculo, accion_a_aceleracion
from .especialistas import MARGEN_CLASE, Propuesta, decel_para_detenerse
from .percepcion import ModeloMundo, Objeto

CLASES = ("vehiculo", "peaton", "animal", "obra")
ESTADOS_SENAL = ("verde", "amarillo", "rojo", "pare")
N_OBS = 28
N_ACC = len(ACCIONES)
NOMBRES_OBS = (
    "v/v_lim", "v/20", "a_prev/b_max", "v_lim/20",
    "riesgo_ttc_1", "gap_1/60", "v_rel_1/15", "es_vehiculo_1", "es_peaton_1", "es_animal_1", "es_obra_1",
    "confianza_1", "decel_req_1/b_max",
    "riesgo_ttc_2", "gap_2/60",
    "vulnerable_cerca", "vulnerable_lateral/4",
    "dist_senal/120", "senal_verde", "senal_amarillo", "senal_rojo", "senal_pare", "decel_req_senal/b_max",
    "decel_req_limite/b_max", "mu/0.8", "alcance/90", "carril_bloqueado",
    "sugerencia_obstaculos",
)


def riesgo_ttc(ttc: float) -> float:
    return 1.0 - min(ttc, 8.0) / 8.0


def construir_observacion(mm: ModeloMundo, amenazas: list[Objeto], vulnerables: list[Objeto],
                          perfil: PerfilVehiculo, perfil_ref: PerfilVehiculo | None = None,
                          carril_bloqueado: bool = False, sugerencia: float | None = None) -> np.ndarray:
    """``perfil_ref`` distinto de ``perfil`` = conocimiento copiado sin normalizar
    (las magnitudes se expresan con la capacidad de frenado de OTRO vehículo)."""
    ref = perfil_ref or perfil
    b_ref = ref.frenado_max(mm.clima.mu)
    o = np.zeros(N_OBS, np.float32)
    v = mm.v
    o[0] = min(1.5, v / max(mm.v_lim, 1.0))
    o[1] = v / 20.0
    o[2] = np.clip(mm.a_prev / b_ref, -1.5, 1.0)
    o[3] = mm.v_lim / 20.0
    o[5] = 1.0
    o[14] = 1.0
    if amenazas:
        a1 = amenazas[0]
        gap = a1.s - MARGEN_CLASE[a1.clase]
        o[4] = riesgo_ttc(a1.ttc)
        o[5] = np.clip(a1.s / 60.0, -0.1, 1.0)
        o[6] = np.clip(a1.v_rel / 15.0, -1.0, 1.0)
        o[7 + CLASES.index(a1.clase)] = 1.0
        o[11] = a1.confianza
        if a1.v_rel > 0:
            o[12] = min(2.0, decel_para_detenerse(a1.v_rel, gap) / b_ref)
        if len(amenazas) > 1:
            o[13] = riesgo_ttc(amenazas[1].ttc)
            o[14] = np.clip(amenazas[1].s / 60.0, -0.1, 1.0)
    if vulnerables:
        vu = vulnerables[0]
        o[15] = 1.0 - min(vu.s, 50.0) / 50.0
        o[16] = min(abs(vu.lateral), 6.0) / 4.0
    o[17] = 1.0
    sen = mm.senal
    if sen is not None:
        o[17] = min(sen.dist, 120.0) / 120.0
        o[18 + ESTADOS_SENAL.index(sen.estado)] = 1.0
        if sen.estado in ("rojo", "amarillo", "pare"):
            o[22] = min(2.0, decel_para_detenerse(v, sen.dist - 1.5) / b_ref)
    req_lim = 0.0
    for s, vmax in mm.limites_proximos:
        if v > vmax:
            req_lim = max(req_lim, (v * v - vmax * vmax) / (2.0 * max(s, 1.0)))
    o[23] = min(2.0, req_lim / b_ref)
    o[24] = mm.clima.mu / 0.8
    o[25] = mm.clima.alcance_m / 90.0
    o[26] = 1.0 if carril_bloqueado else 0.0
    # lo que sugiere el agente de Obstáculos (modelo de seguimiento tipo IDM), normalizado
    if sugerencia is not None:
        o[27] = np.clip(sugerencia / (b_ref if sugerencia < 0 else ref.acel_max), -1.5, 1.0)
    return o


def accion_mas_cercana(acel: float, perfil: PerfilVehiculo, mu: float) -> int:
    """Acción discreta que mejor representa una aceleración ejecutada (para la memoria)."""
    mejores = [abs(accion_a_aceleracion(k, perfil, mu) - acel) for k in range(N_ACC)]
    return int(np.argmin(mejores))


class AgenteVelocidad:
    """Envuelve la política: DQN (aprendida) o regla IDM (agente reactivo de referencia)."""

    nombre = "velocidad"

    def __init__(self, perfil: PerfilVehiculo, politica=None, explorar: bool = False,
                 normalizado: bool = True, perfil_origen: PerfilVehiculo | None = None):
        self.perfil = perfil
        self.politica = politica      # AgenteDQN o None (regla)
        self.explorar = explorar
        self.normalizado = normalizado
        self.perfil_origen = perfil_origen
        self.ultima_obs: np.ndarray | None = None
        self.ultima_accion: int = 4

    def proponer(self, mm: ModeloMundo, obs: np.ndarray, sugerida_obstaculos: float | None) -> Propuesta:
        self.ultima_obs = obs
        if self.politica is None:
            # regla: seguir la sugerencia de Obstáculos y acelerar hacia el límite
            a = sugerida_obstaculos if sugerida_obstaculos is not None else self.perfil.acel_max
            self.ultima_accion = accion_mas_cercana(a, self.perfil, mm.clima.mu)
            return Propuesta(self.nombre, acel=a, motivo="regla IDM")
        k = self.politica.actuar(obs, explorar=self.explorar)
        self.ultima_accion = k
        a = accion_a_aceleracion(k, self.perfil, mm.clima.mu, self.normalizado, self.perfil_origen)
        return Propuesta(self.nombre, acel=a, motivo=f"política DQN: acción {k}")


def sin_nan(x: float) -> float:
    return 0.0 if (x is None or math.isnan(x)) else x
