"""Experimentos del proyecto (ver docs/EXPERIMENTOS.md).

E1  instructor        el vehículo instructor aprende desde cero (curva de aprendizaje)
E2/E3 aprendices      taxi aprendiz: desde cero vs. con instructor (doble comando) vs. copia + instructor
E4  bus               transferir al bus: conocimiento normalizado vs. copiado tal cual
E5  federado          flota en 3 zonas: aprendizaje solo local vs. FedAvg (Non-IID)
E6  comparacion       agente de reglas vs. DQN vs. DQN + guardrail, por clima
"""
from __future__ import annotations

import json
import time

import numpy as np

from . import config as C
from .agentes.velocidad import N_ACC, N_OBS
from .aprendizaje.dqn import AgenteDQN, HiperDQN
from .aprendizaje.entrenamiento import Registro, entrenar, evaluar
from .aprendizaje.fedavg import Aporte, BaseConocimiento
from .aprendizaje.instructor import InstructorDobleComando
from .entorno.gym_env import ConduccionBarranquillaEnv
from .entorno.mundo import ZONAS

MODELO_INSTRUCTOR = C.DIR_MODELOS / "instructor_automovil.npz"


def _opciones_fijas(semilla: int, n: int, zonas=None, climas=None, perfil=None):
    """Secuencia reproducible de (zona, clima): todas las variantes ven los mismos escenarios."""
    rng = np.random.default_rng(semilla)
    zonas = zonas or list(ZONAS)
    climas = climas or ["despejado", "despejado", "despejado", "lluvia", "noche"]
    ops = []
    for _ in range(n):
        o = {"zona": str(rng.choice(zonas)), "clima": str(rng.choice(climas))}
        if perfil:
            o["perfil"] = perfil
        ops.append(o)
    return lambda i: ops[i]


# ------------------------------------------------------------------- E1
def e1_instructor(episodios: int = 400, semilla: int = 7) -> None:
    env = ConduccionBarranquillaEnv(semilla=semilla, guardrail=False, multiplicador_eventos=1.2)
    ag = AgenteDQN(N_OBS, N_ACC, HiperDQN(eps_pasos=60_000), semilla=semilla)
    reg = Registro(C.DIR_SALIDAS / "e1_instructor.csv")
    t0 = time.time()
    try:
        entrenar(env, ag, episodios, reg, "instructor")
    finally:
        reg.cerrar()
        ag.guardar(MODELO_INSTRUCTOR, {"perfil": "automovil", "episodios": episodios,
                                       "minutos": round((time.time() - t0) / 60, 1)})
        env.close()


# ---------------------------------------------------------------- E2/E3
def e23_aprendices(episodios: int = 60, semillas=(21, 22), perfil: str = "taxi") -> None:
    maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR)
    reg = Registro(C.DIR_SALIDAS / "e23_aprendices.csv")
    for s in semillas:
        for variante in ("desde_cero", "con_instructor", "copia_mas_instructor"):
            env = ConduccionBarranquillaEnv(semilla=s, guardrail=False, perfil=perfil, multiplicador_eventos=1.2)
            hp = HiperDQN(eps_pasos=15_000)
            if variante == "copia_mas_instructor":
                hp.eps_inicial = 0.15
            alumno = AgenteDQN(N_OBS, N_ACC, hp, semilla=s)
            instructor = None
            if variante != "desde_cero":
                instructor = InstructorDobleComando(maestro, episodios_tutela=int(episodios * 0.7))
            if variante == "copia_mas_instructor":
                alumno.fijar_parametros(maestro.obtener_parametros())
            try:
                entrenar(env, alumno, episodios, reg, f"{variante}/s{s}", instructor,
                         opciones=_opciones_fijas(s, episodios))
            finally:
                env.close()
    reg.cerrar()


# ------------------------------------------------------------------- E4
def e4_bus(episodios: int = 25, semilla: int = 31) -> None:
    maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR)
    reg = Registro(C.DIR_SALIDAS / "e4_bus_normalizacion.csv")
    casos = [("automovil_referencia", "automovil", True), ("bus_normalizado", "bus", True),
             ("bus_copia_tal_cual", "bus", False)]
    for nombre, perfil, normalizado in casos:
        env = ConduccionBarranquillaEnv(semilla=semilla, guardrail=False, perfil=perfil,
                                        normalizado=normalizado, perfil_origen="automovil",
                                        multiplicador_eventos=1.2)
        try:
            evaluar(env, maestro, episodios, reg, nombre, opciones=_opciones_fijas(semilla, episodios))
        finally:
            env.close()
    reg.cerrar()


# ------------------------------------------------------------------- E5
FLOTA = (("taxi", "malecon_via40"), ("automovil", "corredor_calle72"), ("bus", "calles79_85"))


def e5_federado(modo: str = "fedavg", rondas: int = 4, episodios_locales: int = 15, semilla: int = 41) -> None:
    """``modo`` = 'fedavg' (comparten por la nube) o 'local' (cada uno aprende solo)."""
    reg = Registro(C.DIR_SALIDAS / f"e5_federado_{modo}.csv")
    hp = lambda: HiperDQN(eps_pasos=12_000)  # noqa: E731
    flota = {f"{p}@{z}": AgenteDQN(N_OBS, N_ACC, hp(), semilla=semilla + i) for i, (p, z) in enumerate(FLOTA)}
    base = BaseConocimiento(next(iter(flota.values())).obtener_parametros(), C.DIR_MODELOS / f"nube_{modo}")
    # libsumo admite una sola simulación por proceso: los tres vehículos comparten el
    # mismo SUMO y cada uno conduce en su zona y con su perfil (opciones de reset).
    env = ConduccionBarranquillaEnv(semilla=semilla, guardrail=False, multiplicador_eventos=1.2)
    envs = {"todos": env}
    try:
        for r in range(rondas):
            aportes = []
            for vid, ag in flota.items():
                if modo == "fedavg" and r > 0:
                    ag.fijar_parametros(base.descargar())
                perfil, zona = vid.split("@")
                filas = entrenar(env, ag, episodios_locales, reg, f"{vid}/ronda{r + 1}",
                                 opciones={"perfil": perfil, "zona": zona},
                                 inicio=r * episodios_locales, imprimir_cada=episodios_locales)
                n = len(filas)
                metricas = {"tasa_choques": sum(f["choques"] for f in filas) / n,
                            "recompensa_media": sum(f["recompensa"] for f in filas) / n}
                aportes.append(Aporte(vid, vid.split("@")[1], vid.split("@")[0], sum(f["pasos"] for f in filas),
                                      metricas, ag.obtener_parametros()))
            if modo == "fedavg":
                info = base.ronda(aportes)
                print(f"[nube] ronda {r + 1}: versión {info['version']} aceptados={info['aceptados']} "
                      f"rechazados={info['rechazados']}", flush=True)
        # modelos finales
        if modo == "fedavg":
            global_ = AgenteDQN(N_OBS, N_ACC, hp())
            global_.fijar_parametros(base.descargar())
            global_.guardar(C.DIR_MODELOS / "flota_fedavg_global.npz", {"rondas": rondas})
        for vid, ag in flota.items():
            ag.guardar(C.DIR_MODELOS / f"flota_{modo}_{vid.replace('@', '_')}.npz")
    finally:
        for e in envs.values():
            e.close()
        reg.cerrar()


def e5_evaluacion_cruzada(episodios: int = 8, semilla: int = 51) -> None:
    """Cada modelo final se evalúa en TODAS las zonas (generalización)."""
    reg = Registro(C.DIR_SALIDAS / "e5_evaluacion_cruzada.csv")
    modelos = {"fedavg_global": C.DIR_MODELOS / "flota_fedavg_global.npz"}
    for perfil, zona in FLOTA:
        modelos[f"local_{perfil}_{zona}"] = C.DIR_MODELOS / f"flota_local_{perfil}_{zona}.npz"
    for i, zona in enumerate(ZONAS):
        env = ConduccionBarranquillaEnv(semilla=semilla + i, guardrail=False, perfil="automovil", zonas=[zona])
        try:
            for nombre, ruta in modelos.items():
                if not ruta.exists():
                    continue
                ag, _ = AgenteDQN.cargar(ruta)
                evaluar(env, ag, episodios, reg, f"{nombre}|{zona}",
                        opciones=_opciones_fijas(semilla + i, episodios, zonas=[zona]))
        finally:
            env.close()
    reg.cerrar()


# ------------------------------------------------------------------- E6
def e6_comparacion(episodios: int = 12, semilla: int = 61) -> None:
    maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR)
    reg = Registro(C.DIR_SALIDAS / "e6_comparacion.csv")
    variantes = (("reactivo_reglas", None, True), ("dqn_sin_guardrail", maestro, False),
                 ("dqn_con_guardrail", maestro, True))
    for clima in ("despejado", "lluvia", "noche"):
        for nombre, politica, guard in variantes:
            env = ConduccionBarranquillaEnv(semilla=semilla, guardrail=guard, climas=[clima],
                                            multiplicador_eventos=1.2)
            try:
                evaluar(env, politica, episodios, reg, f"{nombre}|{clima}",
                        opciones=_opciones_fijas(semilla, episodios, climas=[clima]))
            finally:
                env.close()
    reg.cerrar()


def guardar_json(ruta, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
