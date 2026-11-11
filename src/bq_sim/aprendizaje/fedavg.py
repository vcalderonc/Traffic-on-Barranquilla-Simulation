"""Agregación federada (FedAvg) y base de conocimiento compartida ("la nube").

FedAvg (McMahan et al., 2017): el modelo global es el promedio de los modelos
locales ponderado por la cantidad de experiencia (pasos de simulación) de cada
vehículo. Los vehículos nunca envían sus datos crudos, solo parámetros.

Este módulo es la referencia que se usa en los experimentos. ``flower_app.py``
implementa lo mismo con Flower (``flwr``) para el despliegue distribuido.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


def fedavg(modelos: list[list[np.ndarray]], pesos: list[float]) -> list[np.ndarray]:
    """Promedio ponderado capa por capa."""
    if not modelos:
        raise ValueError("FedAvg necesita al menos un modelo")
    w = np.asarray(pesos, dtype=np.float64)
    w = w / w.sum()
    return [
        sum(wi * m[k].astype(np.float64) for wi, m in zip(w, modelos)).astype(np.float32)
        for k in range(len(modelos[0]))
    ]


@dataclass
class Aporte:
    vehiculo: str
    zona: str
    tipo: str
    pasos: int
    metricas: dict
    params: list = field(repr=False, default_factory=list)


class BaseConocimiento:
    """Servidor de conocimiento que valida, combina y distribuye modelos.

    Validación: un aporte se rechaza si su tasa de choques en evaluación local es
    peor que la del modelo global vigente por más de ``tolerancia`` (evita que un
    vehículo que aprendió mal contamine a los demás).
    """

    def __init__(self, params_iniciales: list[np.ndarray], directorio: Path, tolerancia=0.10):
        self.global_ = [p.copy() for p in params_iniciales]
        self.version = 0
        self.dir = Path(directorio)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.tolerancia = tolerancia
        self.ref_choques: float | None = None
        self.historial: list[dict] = []

    def descargar(self) -> list[np.ndarray]:
        return [p.copy() for p in self.global_]

    def ronda(self, aportes: list[Aporte]) -> dict:
        aceptados, rechazados = [], []
        for ap in aportes:
            tasa = ap.metricas.get("tasa_choques", 0.0)
            if self.ref_choques is not None and tasa > self.ref_choques + self.tolerancia:
                rechazados.append(ap.vehiculo)
            else:
                aceptados.append(ap)
        if aceptados:
            self.global_ = fedavg([a.params for a in aceptados], [a.pasos for a in aceptados])
            self.version += 1
            tasas = [a.metricas.get("tasa_choques", 0.0) for a in aceptados]
            self.ref_choques = float(np.average(tasas, weights=[a.pasos for a in aceptados]))
        registro = {
            "version": self.version,
            "hora": time.strftime("%Y-%m-%d %H:%M:%S"),
            "aceptados": [a.vehiculo for a in aceptados],
            "rechazados": rechazados,
            "pasos_por_vehiculo": {a.vehiculo: a.pasos for a in aportes},
            "metricas": {a.vehiculo: a.metricas for a in aportes},
        }
        self.historial.append(registro)
        np.savez_compressed(self.dir / f"global_v{self.version:02d}.npz", *self.global_)
        (self.dir / "historial.json").write_text(json.dumps(self.historial, indent=2, ensure_ascii=False),
                                                 encoding="utf-8")
        return registro
