"""Perfiles físicos de vehículos y normalización del conocimiento.

Idea heredada de la propuesta original del grupo: el conocimiento se expresa en
magnitudes que no dependen del vehículo (tiempo para colisión, fracción de la
desaceleración máxima propia). Así lo aprendido por un automóvil le sirve a un bus:
cada vehículo traduce las acciones a su propia física.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerfilVehiculo:
    nombre: str
    tipo_sumo: str          # vType en SUMO
    largo_m: float
    ancho_m: float
    acel_max: float         # m/s^2
    frenado_max_seco: float  # m/s^2 con mu = 0.8
    tiempo_reaccion_s: float
    color: tuple = (255, 200, 0)

    def frenado_max(self, mu: float) -> float:
        """Desaceleración máxima disponible con la fricción ``mu`` de la vía."""
        return self.frenado_max_seco * min(1.0, mu / 0.8)


PERFILES = {
    "automovil": PerfilVehiculo("automovil", "ego_auto", 4.5, 1.8, 2.8, 7.5, 0.25, (255, 200, 0)),
    "taxi": PerfilVehiculo("taxi", "ego_taxi", 4.3, 1.7, 2.6, 7.0, 0.25, (255, 230, 0)),
    "bus": PerfilVehiculo("bus", "ego_bus", 12.0, 2.5, 1.2, 4.5, 0.35, (0, 140, 70)),
    "camion": PerfilVehiculo("camion", "ego_camion", 9.0, 2.5, 1.0, 4.0, 0.40, (200, 60, 40)),
}

# Acciones longitudinales: fracción de la capacidad del vehículo (normalizadas).
# Negativo = frenar (fracción del frenado máximo), positivo = acelerar (fracción de acel_max).
ACCIONES = (-1.00, -0.60, -0.30, -0.12, 0.0, 0.40, 1.00)
NOMBRES_ACCIONES = (
    "frenado de emergencia", "frenado fuerte", "frenado moderado", "frenado suave",
    "mantener", "acelerar suave", "acelerar",
)


def accion_a_aceleracion(accion: int, perfil: PerfilVehiculo, mu: float,
                         normalizado: bool = True,
                         perfil_origen: PerfilVehiculo | None = None) -> float:
    """Convierte una acción discreta en aceleración (m/s^2).

    ``normalizado=False`` simula copiar el conocimiento "tal cual": la acción se
    interpreta en m/s^2 del vehículo de origen y luego la física del vehículo real la
    recorta. Es el caso peligroso del experimento automóvil -> bus.
    """
    f = ACCIONES[accion]
    if normalizado or perfil_origen is None:
        ref = perfil
    else:
        ref = perfil_origen
    a = f * (ref.frenado_max(mu) if f < 0 else ref.acel_max)
    # la física del vehículo real manda
    return max(-perfil.frenado_max(mu), min(perfil.acel_max, a))
