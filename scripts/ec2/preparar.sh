#!/usr/bin/env bash
# Prepara una instancia EC2 nueva (Ubuntu 24.04) para entrenar. Se corre UNA vez:
#   bash preparar.sh [URL_DEL_REPO] [RAMA]
# SUMO viene en pip (eclipse-sumo/libsumo): no hace falta compilar ni usar GPU.
set -euo pipefail
REPO=${1:-https://github.com/vcalderonc/Traffic-on-Barranquilla-Simulation.git}
RAMA=${2:-main}

sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git tmux htop unzip
# libsumo (wheel manylinux) trae casi todo, pero enlaza contra libGL y X11 del sistema,
# que Ubuntu Server no trae. Sin ellas `import libsumo` falla y todo corre por TraCI.
sudo apt-get install -y libgl1 libx11-6 libxext6 libxrender1
if ! command -v aws >/dev/null; then  # AWS CLI, para subir resultados a S3 (opcional)
  curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscli.zip
  unzip -q /tmp/awscli.zip -d /tmp && sudo /tmp/aws/install
fi

cd ~
[ -d Traffic-on-Barranquilla-Simulation ] || git clone "$REPO"
cd Traffic-on-Barranquilla-Simulation
git fetch origin && git checkout "$RAMA" && git pull --ff-only
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
PYTHONPATH=src ./.venv/bin/python -m unittest discover -s tests
# prueba real antes de entrenar: libsumo carga y SUMO corre unos pasos
PYTHONPATH=src ./.venv/bin/python - <<'PY'
import libsumo  # noqa: F401  (falla aquí si faltan librerías del sistema)
from bq_sim.entorno.gym_env import ConduccionBarranquillaEnv
env = ConduccionBarranquillaEnv(semilla=1)
env.reset(seed=1)
for _ in range(20):
    env.step(env.action_space.sample())
env.close()
print("SUMO + libsumo OK")
PY
echo "Listo. Siguiente: tmux new -s fase2 'bash scripts/ec2/entrenar_fase2.sh'"
