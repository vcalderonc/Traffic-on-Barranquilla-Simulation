#!/usr/bin/env bash
# Fase 2 (E8) en paralelo: una semilla por núcleo, luego valida y elige el mejor.
#   SEMILLAS=12 EPISODIOS=400 BUCKET=s3://mi-bucket/bq bash scripts/ec2/entrenar_fase2.sh
# Variables (todas opcionales):
#   SEMILLAS         cuántas semillas (por defecto: núcleos - 1)
#   SEMILLA_INICIAL  número de la primera semilla (1); usar otro rango para no pisar
#                    los candidatos que ya están en modelos/fase2 (s1..s6)
#   EPISODIOS        episodios por semilla (300)
#   EVALUAR_CADA     episodios entre evaluaciones (50)
#   VALIDAR          episodios de validación por candidato (40)
#   INSTALAR         1 = copia el mejor a modelos/instructor_automovil.npz (0)
#   BUCKET           ruta S3 donde subir modelos/fase2 y salidas/fase2 (cada 10 min y al terminar)
#   APAGAR           1 = apaga la instancia al terminar (para no pagar horas sin uso)
set -uo pipefail
cd "$(dirname "$0")/../.."
PY=./.venv/bin/python
export PYTHONPATH=src PYTHONIOENCODING=utf-8
NUCLEOS=$(nproc 2>/dev/null || sysctl -n hw.ncpu)
SEMILLAS=${SEMILLAS:-$(( NUCLEOS > 1 ? NUCLEOS - 1 : 1 ))}
SEMILLA_INICIAL=${SEMILLA_INICIAL:-1}
EPISODIOS=${EPISODIOS:-300}
EVALUAR_CADA=${EVALUAR_CADA:-50}
VALIDAR=${VALIDAR:-40}
mkdir -p salidas/fase2
ULTIMA=$(( SEMILLA_INICIAL + SEMILLAS - 1 ))
echo "$(date) | semillas $SEMILLA_INICIAL..$ULTIMA x $EPISODIOS episodios en $NUCLEOS núcleos"

subir() {
  if [ -n "${BUCKET:-}" ]; then
    aws s3 sync modelos/fase2 "$BUCKET/modelos/fase2" --only-show-errors
    aws s3 sync salidas/fase2 "$BUCKET/salidas/fase2" --only-show-errors
  fi
}

# Aviso de interrupción spot: AWS avisa ~2 minutos antes por el servicio de metadatos.
# Al verlo, se sube lo que haya para no perder los mejores puntos de control.
vigilar_spot() {
  while sleep 5; do
    tok=$(curl -s -m 2 -X PUT http://169.254.169.254/latest/api/token \
          -H "X-aws-ec2-metadata-token-ttl-seconds: 60") || continue
    code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' -H "X-aws-ec2-metadata-token: $tok" \
           http://169.254.169.254/latest/meta-data/spot/instance-action) || continue
    if [ "$code" = "200" ]; then
      echo "$(date) | aviso de interrupción spot: subiendo resultados"
      subir
      return
    fi
  done
}

pids=()
for s in $(seq "$SEMILLA_INICIAL" "$ULTIMA"); do
  $PY -m bq_sim fase2 entrenar --semilla "$s" --episodios "$EPISODIOS" --evaluar-cada "$EVALUAR_CADA" \
    > "salidas/fase2/log_s$s.txt" 2>&1 &
  pids+=($!)
done
# respaldo a S3 cada 10 minutos mientras entrena
( while sleep 600; do subir; done ) & RESPALDO=$!
VIGIA=""
if [ -n "${BUCKET:-}" ] && curl -s -m 1 -o /dev/null http://169.254.169.254/; then
  vigilar_spot & VIGIA=$!
fi
fallos=0
for p in "${pids[@]}"; do wait "$p" || fallos=$((fallos + 1)); done
kill "$RESPALDO" 2>/dev/null
echo "$(date) | entrenamiento terminado ($fallos semillas con error)"
subir

$PY -m bq_sim fase2 validar --episodios "$VALIDAR" --procesos "$NUCLEOS" > salidas/fase2/log_validacion.txt 2>&1
if [ "${INSTALAR:-0}" = "1" ]; then
  $PY -m bq_sim fase2 elegir --instalar | tee salidas/fase2/eleccion.txt
  [ -n "${BUCKET:-}" ] && aws s3 cp modelos/instructor_automovil.npz "$BUCKET/modelos/instructor_automovil.npz" --only-show-errors
else
  $PY -m bq_sim fase2 elegir | tee salidas/fase2/eleccion.txt
fi
[ -n "$VIGIA" ] && kill "$VIGIA" 2>/dev/null
subir
echo "$(date) | listo"
[ "${APAGAR:-0}" = "1" ] && sudo shutdown -h now
exit 0
