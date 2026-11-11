"""Aprendizaje federado distribuido con Flower (flwr) sobre gRPC.

Es la versión "de despliegue" del mismo FedAvg que usa ``experimentos.e5_federado``:
cada vehículo es un proceso (o contenedor) con su propio SUMO, entrena en su zona
y solo envía los pesos de su red al servidor, que los promedia con
``flwr.server.strategy.FedAvg`` ponderando por pasos de simulación.

Uso local (una terminal por proceso):

    python -m bq_sim.aprendizaje.flower_app servidor --rondas 3 --clientes 3
    python -m bq_sim.aprendizaje.flower_app vehiculo --perfil taxi --zona malecon_via40
    python -m bq_sim.aprendizaje.flower_app vehiculo --perfil automovil --zona corredor_calle72
    python -m bq_sim.aprendizaje.flower_app vehiculo --perfil bus --zona calles79_85

Con Docker Compose: ``docker compose up`` (ver ``docker-compose.yml``).

Se usa la API gRPC clásica de Flower (``start_server`` / ``start_client``), que la
versión 1.43 marca como obsoleta pero conserva; es la más directa para mostrar el
intercambio cliente-servidor sin el motor de simulación de Ray.
"""
from __future__ import annotations

import argparse
import sys
import warnings

import numpy as np

from .. import config as C
from ..agentes.velocidad import N_ACC, N_OBS
from .dqn import AgenteDQN, HiperDQN
from .entrenamiento import entrenar, evaluar, Registro

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _cliente(perfil: str, zona: str, episodios: int, semilla: int, inicial: str | None):
    import flwr as fl

    from ..entorno.gym_env import ConduccionBarranquillaEnv

    class VehiculoFlower(fl.client.NumPyClient):
        def __init__(self):
            self.env = ConduccionBarranquillaEnv(semilla=semilla, guardrail=False, perfil=perfil, zonas=[zona],
                                                 multiplicador_eventos=1.2)
            self.agente = AgenteDQN(N_OBS, N_ACC, HiperDQN(eps_pasos=12_000), semilla=semilla)
            if inicial:
                maestro, _ = AgenteDQN.cargar(inicial)
                self.agente.fijar_parametros(maestro.obtener_parametros())
            self.reg = Registro(C.DIR_SALIDAS / f"flower_{perfil}_{zona}.csv")
            self.ronda = 0

        def get_parameters(self, config):
            return self.agente.obtener_parametros()

        def fit(self, parameters, config):
            self.agente.fijar_parametros(parameters)
            filas = entrenar(self.env, self.agente, int(config.get("episodios", episodios)), self.reg,
                             f"flower/{perfil}@{zona}/r{self.ronda}", inicio=self.ronda * episodios,
                             imprimir_cada=0)
            self.ronda += 1
            n = len(filas)
            pasos = int(sum(f["pasos"] for f in filas))
            return self.agente.obtener_parametros(), pasos, {
                "tasa_choques": float(sum(f["choques"] for f in filas) / n),
                "recompensa": float(sum(f["recompensa"] for f in filas) / n),
            }

        def evaluate(self, parameters, config):
            self.agente.fijar_parametros(parameters)
            filas = evaluar(self.env, self.agente, 2, None, "flower_eval")
            r = float(np.mean([f["recompensa"] for f in filas]))
            return -r, len(filas), {"recompensa": r, "tasa_choques": float(np.mean([f["choques"] for f in filas]))}

    return VehiculoFlower()


def servidor(rondas: int, clientes: int, direccion: str, inicial: str | None) -> None:
    import flwr as fl
    from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays

    def promedio(metricas):
        total = sum(n for n, _ in metricas) or 1
        claves = metricas[0][1].keys() if metricas else []
        return {k: sum(n * m[k] for n, m in metricas) / total for k in claves}

    params0 = None
    if inicial:
        maestro, _ = AgenteDQN.cargar(inicial)
        params0 = ndarrays_to_parameters(maestro.obtener_parametros())

    class FedAvgConGuardado(fl.server.strategy.FedAvg):
        def aggregate_fit(self, server_round, results, failures):
            agregado, metricas = super().aggregate_fit(server_round, results, failures)
            if agregado is not None:
                ag = AgenteDQN(N_OBS, N_ACC)
                ag.fijar_parametros(parameters_to_ndarrays(agregado))
                ag.guardar(C.DIR_MODELOS / "flower_global.npz", {"ronda": server_round})
                print(f"[servidor] ronda {server_round}: modelo global guardado | {metricas}", flush=True)
            return agregado, metricas

    estrategia = FedAvgConGuardado(
        fraction_fit=1.0, fraction_evaluate=1.0, min_fit_clients=clientes, min_evaluate_clients=clientes,
        min_available_clients=clientes, initial_parameters=params0,
        fit_metrics_aggregation_fn=promedio, evaluate_metrics_aggregation_fn=promedio)
    fl.server.start_server(server_address=direccion, config=fl.server.ServerConfig(num_rounds=rondas),
                           strategy=estrategia)


def main(argv=None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Aprendizaje federado con Flower")
    sub = p.add_subparsers(dest="rol", required=True)
    s = sub.add_parser("servidor")
    s.add_argument("--rondas", type=int, default=3)
    s.add_argument("--clientes", type=int, default=3)
    s.add_argument("--direccion", default="0.0.0.0:8080")
    s.add_argument("--inicial", default=None, help="modelo .npz con el que arranca (p. ej. el instructor)")
    v = sub.add_parser("vehiculo")
    v.add_argument("--perfil", default="automovil")
    v.add_argument("--zona", default="malecon_via40")
    v.add_argument("--episodios", type=int, default=10)
    v.add_argument("--semilla", type=int, default=0)
    v.add_argument("--servidor", default="127.0.0.1:8080")
    v.add_argument("--inicial", default=None)
    a = p.parse_args(argv)
    if a.rol == "servidor":
        servidor(a.rondas, a.clientes, a.direccion, a.inicial)
    else:
        from flwr.compat.client.app import start_client

        cliente = _cliente(a.perfil, a.zona, a.episodios, a.semilla, a.inicial)
        start_client(server_address=a.servidor, client=cliente.to_client())


if __name__ == "__main__":
    main()
