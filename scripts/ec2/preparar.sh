#!/usr/bin/env bash
# Prepara una instancia EC2 nueva (Ubuntu 24.04) para entrenar. Se corre UNA vez:
#   bash preparar.sh [URL_DEL_REPO] [RAMA]
# SUMO viene en pip (eclipse-sumo/libsumo): no hace falta compilar ni usar GPU.
set -euo pipefail
REPO=${1:-https://github.com/vcalderonc/Traffic-on-Barranquilla-Simulation.git}
RAMA=${2:-main}

sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git tmux htop unzip
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
echo "Listo. Siguiente: tmux new -s fase2 'bash scripts/ec2/entrenar_fase2.sh'"
