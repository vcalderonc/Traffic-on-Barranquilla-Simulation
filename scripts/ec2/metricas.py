#!/usr/bin/env python3
"""Publica en CloudWatch el avance del entrenamiento de la Fase 2 (para el dashboard).

Lee los logs de cada semilla (salidas/fase2/log_s*.txt) y grupos.txt, y cada minuto manda
métricas al espacio "BQSim/Entrenamiento" con las dimensiones Corrida y Grupo:

  Episodios            episodios terminados (promedio de las semillas del grupo)
  Atropellos10         atropellos en los últimos 10 episodios de entrenamiento (promedio)
  Choques10            choques en los últimos 10 episodios (promedio)
  VelocidadKmh         velocidad media en los últimos 10 episodios (promedio)
  EvalAtropellos       atropellos en la última evaluación sin exploración (promedio)
  EvalVelocidadKmh     velocidad en la última evaluación (promedio)
  SemillasVivas        semillas que siguen escribiendo en su log
  SemillasConError     semillas cuyo log terminó en un error

Y, sin dimensión de grupo, MemoriaUsadaPct de la instancia.

Solo usa la biblioteca estándar y el AWS CLI (no hace falta boto3):
    python3 scripts/ec2/metricas.py --corrida fase2-spot-2 [--region us-east-1] [--cada 60]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ESPACIO = "BQSim/Entrenamiento"
DIR = Path(__file__).resolve().parents[2] / "salidas" / "fase2"
RE_EP = re.compile(r"\[s(\d+)\] ep\s+(\d+) \| atropellos (\d+)/10 \| choques (\d+)/10 \| casi-atr [\d.]+ \| v ([\d.]+) km/h")
RE_EVAL = re.compile(r"\[s(\d+)\] evaluación tras (\d+): (\{.*\})")


def region_imds() -> str | None:
    try:
        tok = urllib.request.urlopen(urllib.request.Request(
            "http://169.254.169.254/latest/api/token", method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"}), timeout=2).read().decode()
        return urllib.request.urlopen(urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/placement/region",
            headers={"X-aws-ec2-metadata-token": tok}), timeout=2).read().decode()
    except OSError:
        return None


def grupos() -> dict[int, str]:
    out = {}
    f = DIR / "grupos.txt"
    if f.exists():
        for linea in f.read_text().splitlines():
            partes = linea.split(maxsplit=1)
            if len(partes) == 2 and partes[0].startswith("s"):
                out[int(partes[0][1:])] = partes[1].replace(" ", ",")  # "delta=10,lr=3e-4"
    return out


def leer_semilla(ruta: Path) -> dict:
    texto = ruta.read_text(errors="replace")
    d = {"vivo": time.time() - ruta.stat().st_mtime < 300, "error": "Traceback" in texto}
    eps = RE_EP.findall(texto)
    if eps:
        _, ep, atr, cho, vel = eps[-1]
        d.update(episodios=int(ep), atropellos=int(atr), choques=int(cho), velocidad=float(vel))
    evs = RE_EVAL.findall(texto)
    if evs:
        r = ast.literal_eval(evs[-1][2])
        d.update(eval_atropellos=r["choques_vulnerables"], eval_velocidad=r["vel_media_kmh"])
    return d


def memoria_pct() -> float | None:
    try:
        info = {k: int(v.split()[0]) for k, v in
                (l.split(":", 1) for l in Path("/proc/meminfo").read_text().splitlines())}
        return 100.0 * (1 - info["MemAvailable"] / info["MemTotal"])
    except (OSError, KeyError, ValueError):
        return None


def recolectar(corrida: str) -> list[dict]:
    asignacion = grupos()
    por_grupo: dict[str, list[dict]] = defaultdict(list)
    for log in DIR.glob("log_s*.txt"):
        m = re.fullmatch(r"log_s(\d+)\.txt", log.name)
        if m:
            s = int(m.group(1))
            por_grupo[asignacion.get(s, "sin_grupo")].append(leer_semilla(log))
    datos = []

    def poner(nombre, valor, grupo=None, unidad="None"):
        dims = [{"Name": "Corrida", "Value": corrida}]
        if grupo is not None:
            dims.append({"Name": "Grupo", "Value": grupo})
        datos.append({"MetricName": nombre, "Dimensions": dims, "Value": float(valor), "Unit": unidad})

    for grupo, semillas in por_grupo.items():
        prom = lambda k: [s[k] for s in semillas if k in s]  # noqa: E731
        for clave, nombre in [("episodios", "Episodios"), ("atropellos", "Atropellos10"),
                              ("choques", "Choques10"), ("velocidad", "VelocidadKmh"),
                              ("eval_atropellos", "EvalAtropellos"), ("eval_velocidad", "EvalVelocidadKmh")]:
            v = prom(clave)
            if v:
                poner(nombre, sum(v) / len(v), grupo)
        poner("SemillasVivas", sum(s["vivo"] and not s["error"] for s in semillas), grupo, "Count")
        poner("SemillasConError", sum(s["error"] for s in semillas), grupo, "Count")
    mem = memoria_pct()
    if mem is not None:
        poner("MemoriaUsadaPct", mem, None, "Percent")
    return datos


def publicar(datos: list[dict], region: str) -> None:
    for i in range(0, len(datos), 500):  # límite de put-metric-data
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(datos[i:i + 500], f)
        r = subprocess.run(["aws", "cloudwatch", "put-metric-data", "--region", region, "--namespace", ESPACIO,
                            "--metric-data", f"file://{f.name}"], capture_output=True, text=True)
        Path(f.name).unlink(missing_ok=True)
        if r.returncode:
            print(f"[metricas] put-metric-data falló: {r.stderr.strip()}", file=sys.stderr, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corrida", required=True)
    ap.add_argument("--region", default=None)
    ap.add_argument("--cada", type=int, default=60)
    ap.add_argument("--una-vez", action="store_true", help="imprime las métricas y sale (sin publicar)")
    a = ap.parse_args()
    if a.una_vez:
        print(json.dumps(recolectar(a.corrida), indent=1))
        return
    region = a.region or region_imds() or "us-east-1"
    while True:
        try:
            publicar(recolectar(a.corrida), region)
        except Exception as e:  # noqa: BLE001  (no debe tumbar el entrenamiento)
            print(f"[metricas] {e}", file=sys.stderr, flush=True)
        time.sleep(a.cada)


if __name__ == "__main__":
    main()
