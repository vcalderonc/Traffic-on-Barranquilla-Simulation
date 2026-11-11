"""Punto de entrada:  python -m bq_sim <comando>

Comandos
  red            descarga OSM (opcional --descargar) y construye la red SUMO con PARE
  demanda        genera tráfico de fondo y peatones
  instructor     E1: entrena el vehículo instructor
  aprendices     E2/E3: aprendices con y sin instructor
  bus            E4: normalización del conocimiento automóvil -> bus
  federado       E5: flota federada (FedAvg) y solo local
  cruzada        E5: evaluación cruzada de los modelos de la flota
  comparacion    E6: reglas vs DQN vs DQN+guardrail por clima
  graficas       genera las figuras de salidas/ a partir de los CSV
  visor          exporta la ciudad y graba un recorrido para el visor 3D del Malecón
  gui            abre sumo-gui con el vehículo instructor conduciendo
"""
from __future__ import annotations

import argparse
import sys


def main(argv=None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="bq_sim", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("red")
    r.add_argument("--descargar", action="store_true", help="vuelve a descargar OSM con Overpass")
    sub.add_parser("demanda")
    e1 = sub.add_parser("instructor")
    e1.add_argument("--episodios", type=int, default=400)
    e23 = sub.add_parser("aprendices")
    e23.add_argument("--episodios", type=int, default=50)
    e4 = sub.add_parser("bus")
    e4.add_argument("--episodios", type=int, default=20)
    e5 = sub.add_parser("federado")
    e5.add_argument("--modo", choices=["fedavg", "local"], default="fedavg")
    e5.add_argument("--rondas", type=int, default=4)
    e5.add_argument("--episodios-locales", type=int, default=12)
    cz = sub.add_parser("cruzada")
    cz.add_argument("--episodios", type=int, default=6)
    e6 = sub.add_parser("comparacion")
    e6.add_argument("--episodios", type=int, default=10)
    sub.add_parser("graficas")
    v = sub.add_parser("visor")
    v.add_argument("--solo-ciudad", action="store_true")
    v.add_argument("--duracion", type=float, default=150.0)
    g = sub.add_parser("gui")
    g.add_argument("--zona", default="malecon_via40")
    g.add_argument("--clima", default="despejado")
    a = p.parse_args(argv)

    if a.cmd == "red":
        from . import red
        if a.descargar:
            red.descargar_osm()
        red.comprimir_osm() if (a.descargar or not red.C.OSM_RED.exists()) else None
        red.construir_red()
        print("PARE aplicados:", len(red.aplicar_pares()))
        print(red.resumen())
    elif a.cmd == "demanda":
        from . import demanda
        demanda.generar_demanda()
    elif a.cmd == "instructor":
        from . import experimentos as X
        X.e1_instructor(a.episodios)
    elif a.cmd == "aprendices":
        from . import experimentos as X
        X.e23_aprendices(a.episodios)
    elif a.cmd == "bus":
        from . import experimentos as X
        X.e4_bus(a.episodios)
    elif a.cmd == "federado":
        from . import experimentos as X
        X.e5_federado(a.modo, a.rondas, a.episodios_locales)
    elif a.cmd == "cruzada":
        from . import experimentos as X
        X.e5_evaluacion_cruzada(a.episodios)
    elif a.cmd == "comparacion":
        from . import experimentos as X
        X.e6_comparacion(a.episodios)
    elif a.cmd == "graficas":
        from . import graficas
        graficas.todas()
    elif a.cmd == "visor":
        from . import visor
        visor.exportar_ciudad()
        if not a.solo_ciudad:
            visor.grabar_recorrido(duracion_s=a.duracion)
    elif a.cmd == "gui":
        from . import visor
        visor.abrir_gui(a.zona, a.clima)


if __name__ == "__main__":
    main()
