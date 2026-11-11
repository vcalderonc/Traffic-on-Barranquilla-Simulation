"""Demanda de tráfico: vehículos de fondo, peatones y configuración de SUMO.

Se usa ``randomTrips.py`` (herramienta oficial de SUMO) con semilla fija, así cada
corrida es reproducible. El factor de borde (``--fringe-factor``) hace que buena
parte de los viajes entren y salgan por los extremos del área, como el tráfico
que cruza la zona del Malecón por la Vía 40 y la Av. Calle 72.
"""
from __future__ import annotations

import subprocess
import sys

from . import config as C


def _random_trips(salida, extra: list[str], semilla: int) -> None:
    script = C.sumo_home() / "tools" / "randomTrips.py"
    cmd = [sys.executable, str(script), "-n", str(C.RED_SUMO), "-o", str(salida),
           "--seed", str(semilla), "--validate", "--remove-loops"] + extra
    subprocess.run(cmd, check=True)


def generar_demanda(duracion_s: int = 4000, periodo_veh: float = 1.1,
                    periodo_peaton: float = 2.5, semilla: int = 42) -> None:
    C.DIR_SUMO.mkdir(parents=True, exist_ok=True)
    _random_trips(C.RUTAS_FONDO, [
        "-b", "0", "-e", str(duracion_s), "-p", str(periodo_veh),
        "--fringe-factor", "8", "--min-distance", "700",
        "--edge-permission", "passenger", "--prefix", "f",
        "--trip-attributes", 'type="mezcla" departLane="best" departSpeed="max"',
        "--additional-files", str(C.TIPOS_VEH),
    ], semilla)
    _random_trips(C.PEATONES, [
        "-b", "0", "-e", str(duracion_s), "-p", str(periodo_peaton),
        "--pedestrians", "--max-distance", "1200", "--prefix", "p",
    ], semilla + 1)
    escribir_sumocfg()


def escribir_sumocfg() -> None:
    C.CONFIG_SUMO.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{C.RED_SUMO.name}"/>
        <route-files value="{C.RUTAS_FONDO.name},{C.PEATONES.name}"/>
        <additional-files value="{C.TIPOS_VEH.name}"/>
    </input>
    <time>
        <begin value="0"/>
        <step-length value="{C.PASO_SIM_S}"/>
    </time>
    <processing>
        <collision.action value="warn"/>
        <collision.check-junctions value="true"/>
        <collision.mingap-factor value="0"/>
        <time-to-teleport value="240"/>
        <ignore-route-errors value="true"/>
        <pedestrian.model value="striping"/>
    </processing>
    <report>
        <no-step-log value="true"/>
        <no-warnings value="true"/>
    </report>
    <gui_only>
        <start value="true"/>
    </gui_only>
</configuration>
""", encoding="utf-8")
