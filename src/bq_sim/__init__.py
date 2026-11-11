"""Simulación multiagente de conducción autónoma en Barranquilla (zona del Gran Malecón).

Paquetes:
    red          construcción de la red vial real (OpenStreetMap -> SUMO)
    demanda      tráfico de fondo, peatones y rutas del vehículo autónomo
    entorno      entorno Gymnasium sobre SUMO/TraCI y eventos estocásticos
    agentes      agentes especializados que conducen un mismo vehículo
    aprendizaje  DQN en NumPy, instructor con doble comando y FedAvg
    experimentos escenarios de evaluación y gráficas
    visor        exportación de datos para el visor 3D del Malecón
"""

__version__ = "1.0.0"
