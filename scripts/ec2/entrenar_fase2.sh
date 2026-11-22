#!/usr/bin/env bash
# Fase 2 (E8) en paralelo: una semilla por núcleo, luego valida y elige el mejor.
#   SEMILLAS=12 EPISODIOS=400 BUCKET=s3://mi-bucket/bq bash scripts/ec2/entrenar_fase2.sh
# Variables (todas opcionales):
#   SEMILLAS   cuántas semillas (por defecto: núcleos - 1)
#   EPISODIOS  episodios por semilla (300)
#   VALIDAR    episodios de validación por candidato (40)
#   INSTALAR   1 = copia el mejor a modelos/instructor_automovil.npz (0)
#   BUCKET     ruta S3 donde subir modelos/fase2 y salidas/fase2 al terminar
#   APAGAR     1 = apaga la instancia al terminar (para no pagar horas sin uso)
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=./.venv/bin/python
export PYTHONPATH=src PYTHONIOENCODING=utf-8
NUCLEOS=$(nproc 2>/dev/null || sysctl -n hw.ncpu)
SEMILLAS=${SEMILLAS:-$(( NUCLEOS > 1 ? NUCLEOS - 1 : 1 ))}
EPISODIOS=${EPISODIOS:-300}
VALIDAR=${VALIDAR:-40}
mkdir -p salidas/fase2
echo "$(date) | $SEMILLAS semillas x $EPISODIOS episodios en $NUCLEOS núcleos"

subir() {
  if [ -n "${BUCKET:-}" ]; then
    aws s3 sync modelos/fase2 "$BUCKET/modelos/fase2" --only-show-errors
    aws s3 sync salidas/fase2 "$BUCKET/salidas/fase2" --only-show-errors
  fi
}

pids=()
for s in $(seq 1 "$SEMILLAS"); do
  $PY -m bq_sim fase2 entrenar --semilla "$s" --episodios "$EPISODIOS" > "salidas/fase2/log_s$s.txt" 2>&1 &
  pids+=($!)
done
# respaldo a S3 cada 10 minutos mientras entrena (por si la instancia spot se interrumpe)
( while sleep 600; do subir; done ) & RESPALDO=$!
fallos=0
for p in "${pids[@]}"; do wait "$p" || fallos=$((fallos + 1)); done
kill "$RESPALDO" 2>/dev/null
echo "$(date) | entrenamiento terminado ($fallos semillas con error)"

$PY -m bq_sim fase2 validar --episodios "$VALIDAR" > salidas/fase2/log_validacion.txt 2>&1
if [ "${INSTALAR:-0}" = "1" ]; then
  $PY -m bq_sim fase2 elegir --instalar | tee salidas/fase2/eleccion.txt
else
  $PY -m bq_sim fase2 elegir | tee salidas/fase2/eleccion.txt
fi
subir
echo "$(date) | listo"
[ "${APAGAR:-0}" = "1" ] && sudo shutdown -h now
