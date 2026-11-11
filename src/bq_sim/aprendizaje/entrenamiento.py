"""Bucle de entrenamiento y evaluación (agente que aprende: crítico + elemento de aprendizaje)."""
from __future__ import annotations

import csv
import time
from pathlib import Path

from .dqn import AgenteDQN
from .instructor import InstructorDobleComando

COLUMNAS = ["episodio", "fase", "zona", "clima", "perfil", "ruta", "largo_ruta_m", "pasos", "tiempo_s",
            "distancia_m", "vel_media_kmh", "choques", "choque_con", "casi_choques", "pare_violados",
            "pare_respetados", "rojos_violados", "frenadas_bruscas", "pasos_exceso_vel",
            "intervenciones_seguridad", "intervenciones_instructor", "llego", "ttc_min", "recompensa",
            "epsilon", "perdida", "lambda_imitacion", "segundos_reloj"]


def correr_episodio(env, agente: AgenteDQN | None, entrenar: bool = True, explorar: bool = True,
                    instructor: InstructorDobleComando | None = None, opciones: dict | None = None,
                    lambda_reglas: float = 0.0) -> dict:
    """Un episodio. ``lambda_reglas`` > 0 activa las demostraciones del conductor de reglas
    (escuela de reglas, DQfD) con ese peso en la pérdida de imitación."""
    t_reloj = time.time()
    obs, _info = env.reset(options=opciones)
    env.instructor = instructor
    if instructor is not None:
        instructor.nuevo_episodio()
        if agente is not None:
            agente.hp.peso_imitacion = instructor.lam
    elif agente is not None and entrenar:
        agente.hp.peso_imitacion = lambda_reglas
    fin = False
    info = {}
    while not fin:
        a = agente.actuar(obs, explorar) if agente is not None else None
        obs2, r, term, trunc, info = env.step(a)
        if agente is not None and entrenar:
            if instructor is not None:
                guia = instructor.ultima_guia
            elif lambda_reglas > 0:
                guia = info["decision"].accion_regla
            else:
                guia = -1
            # se guarda la acción EJECUTADA (tras Señales/Seguridad/instructor): DQN es off-policy
            agente.recordar(obs, info["accion_ejecutada"], r, obs2, float(term), guia, truncado=trunc)
            agente.entrenar()
        obs = obs2
        fin = term or trunc
    env.instructor = None
    m = dict(info["metricas"])
    m["epsilon"] = round(agente.epsilon(), 3) if agente is not None else 0.0
    m["perdida"] = round(agente.ultima_perdida, 4) if agente is not None else 0.0
    m["lambda_imitacion"] = round(instructor.lam if instructor is not None else lambda_reglas, 3)
    m["segundos_reloj"] = round(time.time() - t_reloj, 2)
    return m


class Registro:
    """CSV de métricas por episodio (una fila por episodio)."""

    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.ruta, "w", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=COLUMNAS, extrasaction="ignore")
        self.w.writeheader()

    def escribir(self, fila: dict) -> None:
        self.w.writerow(fila)
        self.f.flush()

    def cerrar(self) -> None:
        self.f.close()


def entrenar(env, agente: AgenteDQN, episodios: int, registro: Registro, fase: str,
             instructor: InstructorDobleComando | None = None, opciones=None, inicio: int = 0,
             imprimir_cada: int = 10, demostraciones_reglas: int = 0, piso_reglas: float = 0.25,
             evaluar_cada: int = 0, opciones_eval=None, episodios_eval: int = 5) -> list[dict]:
    """``demostraciones_reglas`` = episodios durante los cuales el peso de imitación del
    conductor de reglas decae de 1 a ``piso_reglas`` (y ahí se queda: ancla a las reglas). ``evaluar_cada`` > 0 intercala evaluaciones sin
    exploración (fase "<fase>/evaluacion") para medir la política real."""
    filas = []
    for ep in range(episodios):
        ops = opciones(ep) if callable(opciones) else opciones
        lam = max(piso_reglas, 1.0 - ep / demostraciones_reglas) if demostraciones_reglas else 0.0
        m = correr_episodio(env, agente, True, True, instructor, ops, lambda_reglas=lam)
        m.update(episodio=inicio + ep + 1, fase=fase)
        registro.escribir(m)
        filas.append(m)
        if evaluar_cada and (ep + 1) % evaluar_cada == 0:
            ev = evaluar(env, agente, episodios_eval, registro, f"{fase}/evaluacion",
                         opciones=opciones_eval, inicio=inicio + ep)
            n = len(ev)
            print(f"[{fase}] evaluación tras {inicio + ep + 1} episodios | choques {sum(f['choques'] for f in ev)}/{n}"
                  f" | casi {sum(f['casi_choques'] for f in ev) / n:.2f}"
                  f" | brusc {sum(f['frenadas_bruscas'] for f in ev) / n:.1f}"
                  f" | v {sum(f['vel_media_kmh'] for f in ev) / n:.1f} km/h"
                  f" | R {sum(f['recompensa'] for f in ev) / n:.1f}", flush=True)
        if imprimir_cada and (ep + 1) % imprimir_cada == 0:
            ult = filas[-imprimir_cada:]
            n = len(ult)
            print(f"[{fase}] ep {inicio + ep + 1:4d} | choques {sum(f['choques'] for f in ult)}/{n}"
                  f" | casi {sum(f['casi_choques'] for f in ult) / n:.2f}"
                  f" | brusc {sum(f['frenadas_bruscas'] for f in ult) / n:.1f}"
                  f" | interv {sum(f['intervenciones_instructor'] + f['intervenciones_seguridad'] for f in ult) / n:.1f}"
                  f" | R {sum(f['recompensa'] for f in ult) / n:7.2f} | v {sum(f['vel_media_kmh'] for f in ult) / n:4.1f} km/h"
                  f" | eps {m['epsilon']:.2f} | {sum(f['segundos_reloj'] for f in ult):.0f}s", flush=True)
    return filas


def evaluar(env, agente: AgenteDQN | None, episodios: int, registro: Registro | None, fase: str,
            opciones=None, inicio: int = 0) -> list[dict]:
    filas = []
    for ep in range(episodios):
        ops = opciones(ep) if callable(opciones) else opciones
        m = correr_episodio(env, agente, entrenar=False, explorar=False, opciones=ops)
        m.update(episodio=inicio + ep + 1, fase=fase)
        if registro is not None:
            registro.escribir(m)
        filas.append(m)
    return filas
