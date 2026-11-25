"""Fase 2 (E8): reentrenar al instructor para no atropellar peatones ni animales (D-36).

El instructor guardado (28 entradas) se amplía a 31 con ceros: empieza conduciendo igual
que antes y aprende a usar las entradas nuevas (peatón o animal que se mete en la vía).
Se entrena con más peatones, perros, iguanas y vendedores, y con más noche y lluvia.
Cada ``evaluar_cada`` episodios se evalúa sin exploración en escenarios fijos y se
guarda el mejor punto de control.

Pensado para correr varias semillas en paralelo (un proceso por núcleo, ver docs/EC2.md):

    python -m bq_sim fase2 entrenar --semilla 1 --episodios 300
    python -m bq_sim fase2 validar --episodios 40       # todos los candidatos, mismo mundo
    python -m bq_sim fase2 elegir --instalar            # copia el mejor al instructor
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np

from . import config as C
from .agentes.velocidad import N_ACC, N_OBS
from .aprendizaje.dqn import AgenteDQN, HiperDQN
from .aprendizaje.entrenamiento import Registro, correr_episodio, evaluar
from .entorno.gym_env import ConduccionBarranquillaEnv
from .entorno.mundo import ZONAS

DIR_MODELOS = C.DIR_MODELOS / "fase2"
DIR_SALIDAS = C.DIR_SALIDAS / "fase2"
# más imprevistos de los que ponen en riesgo a peatones y animales
REFUERZO = {"peaton": 2.0, "animal": 2.5, "vendedor": 1.5}
CLIMAS_ENTRENAR = ["despejado", "despejado", "noche", "noche", "lluvia"]
CLIMAS_EVALUAR = ["noche", "lluvia", "despejado", "noche"]


def _opciones(semilla: int, n: int, climas: list[str]):
    rng = np.random.default_rng(semilla)
    ops = [{"zona": str(rng.choice(list(ZONAS))), "clima": str(rng.choice(climas))} for _ in range(n)]
    return lambda i: ops[i % len(ops)]


def _entorno(semilla: int) -> ConduccionBarranquillaEnv:
    env = ConduccionBarranquillaEnv(semilla=semilla, guardrail=False, multiplicador_eventos=1.2)
    env.eventos.refuerzo = dict(REFUERZO)
    return env


def resumir(filas: list[dict]) -> dict:
    n = max(1, len(filas))
    return {
        "episodios": len(filas),
        "choques": int(sum(f["choques"] for f in filas)),
        "choques_vulnerables": int(sum(f.get("choques_vulnerables", 0) for f in filas)),
        "casi_vulnerables_por_ep": round(sum(f.get("casi_choques_vulnerables", 0) for f in filas) / n, 3),
        "acelera_ante_conflicto_por_ep": round(sum(f.get("pasos_acelerando_ante_conflicto", 0) for f in filas) / n, 2),
        "frenadas_bruscas_por_ep": round(sum(f["frenadas_bruscas"] for f in filas) / n, 2),
        "vel_media_kmh": round(sum(f["vel_media_kmh"] for f in filas) / n, 2),
        "recompensa": round(sum(f["recompensa"] for f in filas) / n, 2),
    }


def _clave(r: dict) -> tuple:
    """Orden: menos atropellos, menos choques, menos casi-atropellos, más velocidad."""
    return (r["choques_vulnerables"], r["choques"], r["casi_vulnerables_por_ep"], -r["vel_media_kmh"])


def entrenar_semilla(semilla: int, episodios: int = 300, evaluar_cada: int = 50, episodios_eval: int = 8,
                     desde: Path | None = None, demostraciones: int = 60) -> dict:
    from .experimentos import MODELO_INSTRUCTOR

    desde = Path(desde or MODELO_INSTRUCTOR)
    DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    DIR_SALIDAS.mkdir(parents=True, exist_ok=True)
    maestro, meta = AgenteDQN.cargar(desde)
    ag = AgenteDQN(N_OBS, N_ACC, HiperDQN(eps_inicial=0.15, eps_final=0.02, eps_pasos=40_000), semilla=semilla)
    ag.fijar_parametros(maestro.obtener_parametros())  # 28 -> 31 entradas, con ceros
    env = _entorno(semilla)
    reg = Registro(DIR_SALIDAS / f"s{semilla}.csv")
    op_train = _opciones(semilla, episodios, CLIMAS_ENTRENAR)
    op_eval = _opciones(999, episodios_eval, CLIMAS_EVALUAR)
    historial, mejor = [], None
    t0 = time.time()
    try:
        base = resumir(evaluar(env, ag, episodios_eval, reg, "fase2/evaluacion", opciones=op_eval))
        base["tras_episodios"] = 0
        historial.append(base)
        mejor = base
        ag.guardar(DIR_MODELOS / f"instructor_s{semilla}.npz", {"perfil": "automovil", "fase2": base})
        print(f"[s{semilla}] antes de entrenar: {base}", flush=True)
        hechos = 0
        while hechos < episodios:
            n = min(evaluar_cada, episodios - hechos)
            ult = []
            for k in range(hechos, hechos + n):
                # imitación del conductor de reglas (que ya frena ante peatones que se meten):
                # empieza en 0.6 (el instructor ya sabe conducir) y decae hasta un ancla de 0.25
                lam = max(0.25, 0.6 * (1.0 - k / max(1, demostraciones)))
                m = correr_episodio(env, ag, True, True, None, op_train(k), lambda_reglas=lam)
                m.update(episodio=k + 1, fase="fase2")
                reg.escribir(m)
                ult.append(m)
                if len(ult) == 10:
                    r10 = resumir(ult)
                    print(f"[s{semilla}] ep {k + 1:4d} | atropellos {r10['choques_vulnerables']}/10 | "
                          f"choques {r10['choques']}/10 | casi-atr {r10['casi_vulnerables_por_ep']:.2f} | "
                          f"v {r10['vel_media_kmh']:.1f} km/h | eps {ag.epsilon():.2f} | "
                          f"{sum(f['segundos_reloj'] for f in ult):.0f}s", flush=True)
                    ult = []
            hechos += n
            r = resumir(evaluar(env, ag, episodios_eval, reg, "fase2/evaluacion", opciones=op_eval, inicio=hechos))
            r["tras_episodios"] = hechos
            historial.append(r)
            print(f"[s{semilla}] evaluación tras {hechos}: {r}", flush=True)
            if _clave(r) < _clave(mejor):
                mejor = r
                ag.guardar(DIR_MODELOS / f"instructor_s{semilla}.npz",
                           {"perfil": "automovil", "episodios": int(meta.get("episodios", 0)) + hechos,
                            "fase2": r, "semilla": semilla})
    finally:
        reg.cerrar()
        ag.guardar(DIR_MODELOS / f"instructor_s{semilla}_ultimo.npz", {"perfil": "automovil", "semilla": semilla})
        env.close()
    out = {"semilla": semilla, "desde": str(desde), "mejor": mejor, "historial": historial,
           "minutos": round((time.time() - t0) / 60, 1)}
    (DIR_SALIDAS / f"s{semilla}_resumen.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def validar(episodios: int = 40, semilla_mundo: int = 4242, modelos: list[Path] | None = None) -> list[dict]:
    """Evalúa cada candidato (y el instructor actual) en el MISMO mundo y los mismos escenarios."""
    from .experimentos import MODELO_INSTRUCTOR

    modelos = modelos or ([MODELO_INSTRUCTOR] + sorted(p for p in DIR_MODELOS.glob("instructor_s*.npz")
                                                        if not p.stem.endswith("_ultimo")))
    op = _opciones(semilla_mundo, episodios, CLIMAS_EVALUAR)
    filas = []
    for ruta in modelos:
        ag, _ = AgenteDQN.cargar(ruta)
        env = _entorno(semilla_mundo)
        try:
            r = resumir(evaluar(env, ag, episodios, None, "validacion", opciones=op))
        finally:
            env.close()
        r["modelo"] = str(Path(ruta).relative_to(C.RAIZ)) if Path(ruta).is_relative_to(C.RAIZ) else str(ruta)
        filas.append(r)
        print(r, flush=True)
    DIR_SALIDAS.mkdir(parents=True, exist_ok=True)
    (DIR_SALIDAS / "validacion.json").write_text(json.dumps(filas, indent=1), encoding="utf-8")
    return filas


def elegir(instalar: bool = False) -> dict | None:
    from .experimentos import MODELO_INSTRUCTOR

    ruta = DIR_SALIDAS / "validacion.json"
    if not ruta.exists():
        print("Primero: python -m bq_sim fase2 validar")
        return None
    filas = json.loads(ruta.read_text(encoding="utf-8"))
    for f in sorted(filas, key=_clave):
        print(f"{f['modelo']:55s} atropellos {f['choques_vulnerables']:2d} | choques {f['choques']:2d} | "
              f"casi-atropellos/ep {f['casi_vulnerables_por_ep']:.2f} | {f['vel_media_kmh']:.1f} km/h")
    mejor = min(filas, key=_clave)
    actual = str(MODELO_INSTRUCTOR.relative_to(C.RAIZ))
    if instalar and mejor["modelo"] != actual:
        respaldo = C.DIR_MODELOS / "respaldo"
        respaldo.mkdir(parents=True, exist_ok=True)
        shutil.copy(MODELO_INSTRUCTOR, respaldo / "instructor_antes_fase2.npz")
        shutil.copy(C.RAIZ / mejor["modelo"], MODELO_INSTRUCTOR)
        print(f"Instalado {mejor['modelo']} como instructor (respaldo en {respaldo}).")
    elif instalar:
        print("El instructor actual sigue siendo el mejor: no se cambió.")
    return mejor
