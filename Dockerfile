# Imagen ligera para el servidor Flower y los vehículos (workers) federados.
# SUMO se instala desde PyPI (eclipse-sumo), así que no hace falta apt ni compilar.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY sumo ./sumo
COPY modelos ./modelos

# SUMO_HOME lo resuelve config.sumo_home() a partir del paquete eclipse-sumo
CMD ["python", "-m", "bq_sim.aprendizaje.flower_app", "servidor", "--rondas", "3", "--clientes", "3"]
