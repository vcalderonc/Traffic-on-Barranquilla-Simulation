#!/usr/bin/env bash
# Corre E2-E6, el visor y las gráficas después de entrenar el instructor (E1).
# Usa dos procesos en paralelo (el equipo de referencia tiene 2 núcleos).
#   bash scripts/correr_experimentos.sh
set -u
cd "$(dirname "$0")/.."
PY=./.venv/Scripts/python.exe
[ -x "$PY" ] || PY=./.venv/bin/python
export PYTHONPATH=src PYTHONIOENCODING=utf-8
mkdir -p salidas

(
  $PY -m bq_sim comparacion > salidas/log_e6_comparacion.txt 2>&1
  $PY -m bq_sim bus > salidas/log_e4_bus.txt 2>&1
  $PY -m bq_sim federado --modo local > salidas/log_e5_local.txt 2>&1
  $PY -m bq_sim visor > salidas/log_visor.txt 2>&1
) &
A=$!
(
  $PY -m bq_sim aprendices > salidas/log_e23_aprendices.txt 2>&1
  $PY -m bq_sim federado --modo fedavg > salidas/log_e5_fedavg.txt 2>&1
) &
B=$!
wait $A $B
$PY -m bq_sim cruzada > salidas/log_e5_cruzada.txt 2>&1
$PY -m bq_sim graficas > salidas/log_graficas.txt 2>&1
echo "listo"
