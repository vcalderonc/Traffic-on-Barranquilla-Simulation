"""Simulación en vivo: servidor local que corre SUMO + agentes y transmite al visor 3D.

    python -m bq_sim vivo            ->  abrir http://localhost:8000

El usuario elige en el visor la vía (o un recorrido a la medida: punto de partida,
monumentos por los que pasar y llegada), la hora del día (o el ciclo día-noche), la
lluvia y quién conduce (el instructor DQN o el conductor de reglas). El tráfico y la
gente a pie siguen la hora: en horas pico hay más carros. El servidor
corre el episodio en tiempo real y envía un cuadro cada 0.5 s simulados por
Server-Sent Events (``/api/simular``), con el mismo formato de los recorridos
grabados. Solo usa la biblioteca estándar de Python.

``libsumo`` admite una sola simulación por proceso y no se debe usar desde varios
hilos: un único hilo (``Motor``) es el dueño de SUMO y los pedidos HTTP le llegan
por una cola.
"""
from __future__ import annotations

import json
import queue
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from . import config as C


@dataclass
class Trabajo:
    via: str
    hora: float
    lluvia: bool
    ciclo: float
    agente: str
    guardrail: bool
    velocidad: float
    duracion: float
    partida: object = None           # id de lugar o (x, y) de la red
    pasar_por: list = field(default_factory=list)
    destino: str | None = None
    salida: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=400))
    cancelado: bool = False


class Motor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.trabajos: queue.Queue = queue.Queue()
        self.listo = threading.Event()
        self.actual: Trabajo | None = None
        self.error: str | None = None
        self.lugares: list[dict] = []

    def run(self) -> None:
        from .aprendizaje.dqn import AgenteDQN
        from .entorno.gym_env import ConduccionBarranquillaEnv
        from .experimentos import MODELO_INSTRUCTOR

        try:
            self.maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR)
            # demanda completa (escala 1.0) que sigue la hora del día; calentamiento largo
            # para que la ciudad arranque con el tráfico ya formado
            self.env = ConduccionBarranquillaEnv(semilla=11, guardrail=True, multiplicador_eventos=1.6,
                                                 t_max_s=900.0, escala_demanda=0.9, demanda_por_hora=True,
                                                 calentamiento_s=600.0)
            self.env.max_quieto_s = 150.0  # en vivo se espera el trancón (SUMO resuelve los bloqueos)
            ciudad = json.loads((C.DIR_VISOR / "datos" / "ciudad.json").read_text(encoding="utf-8"))
            self.origen = ciudad["origen"]
            self.lugares = _lugares(self.env.mundo, self.origen)
        except Exception as ex:  # pragma: no cover
            self.error = str(ex)
            self.listo.set()
            return
        self.listo.set()
        while True:
            t = self.trabajos.get()
            self.actual = t
            try:
                self._correr(t)
            except Exception as ex:
                t.salida.put(("error", {"mensaje": str(ex)}))
            finally:
                t.salida.put(None)
                self.actual = None

    def _camino(self, env) -> list:
        try:
            return _camino_local(env, self.origen)
        except Exception:
            return []

    def _correr(self, t: Trabajo) -> None:
        from .visor import Grabadora

        env = self.env

        def enviar(cuadro):
            try:
                t.salida.put(("cuadro", cuadro), timeout=5)
            except queue.Full:
                t.cancelado = True

        env.grabadora = Grabadora(self.origen, guardar=False, al_cuadro=enviar)
        env.guardrail = t.guardrail
        politica = self.maestro if t.agente == "instructor" else None
        try:
            opciones = {"via": t.via, "hora": t.hora, "lluvia": t.lluvia,
                        "ciclo_min_por_s": t.ciclo, "t_max_s": t.duracion}
            if t.partida is not None:
                opciones.update(partida=t.partida, pasar_por=t.pasar_por, destino=t.destino)
            obs, info = env.reset(options=opciones)
            t.salida.put(("inicio", {**info, "agente": t.agente, "guardrail": t.guardrail,
                                     "camino": self._camino(env)}))
            t_real0, t_sim0 = time.time(), env.mundo.t
            fin, inf = False, {}
            while not fin and not t.cancelado:
                a = politica.actuar(obs, explorar=False) if politica is not None else None
                obs, _r, term, trunc, inf = env.step(a)
                fin = term or trunc
                espera = (env.mundo.t - t_sim0) / max(t.velocidad, 0.1) - (time.time() - t_real0)
                if espera > 0:
                    time.sleep(espera)
            if fin:
                t.salida.put(("fin", inf.get("metricas", {})))
            else:  # cancelado: retirar el vehículo y los imprevistos
                env.mundo.quitar(env.ego)
                env.eventos.reiniciar()
                env.ego = None
        finally:
            env.grabadora = None


def _camino_local(env, origen, paso_m: float = 6.0) -> list:
    """Polilínea de la ruta del vehículo (coordenadas del visor) para dibujarla como en un GPS."""
    import math

    pts = []
    for e in env.mundo.traci.vehicle.getRoute(env.ego):
        for x, y in env.mundo.forma_carril(f"{e}_0"):
            if not pts or math.hypot(x - pts[-1][0], y - pts[-1][1]) >= paso_m:
                pts.append((x, y))
    return [round(v, 1) for x, y in pts for v in (x - origen[0], y - origen[1])]


def _vias_disponibles() -> list[dict]:
    from .entorno.mundo import VIAS_SELECCIONABLES

    return [{"id": k, "nombre": v} for k, v in VIAS_SELECCIONABLES.items()]


# Lugares de partida / paso; los que están sobre glorietas se marcan como rotonda
ROTONDAS = {"ventana_mundo", "aleta_tiburon", "malecon_72"}
MONUMENTOS = ("ventana_mundo", "puerta_oro", "caiman_rio", "luna_rio", "malecon_72", "aleta_tiburon")


def _lugares(mundo, origen) -> list[dict]:
    """Lo calcula el hilo Motor (libsumo no se puede usar desde otros hilos)."""
    from .ciudad import LUGARES

    out = []
    for k, (nombre, _lon, _lat) in LUGARES.items():
        x, y = mundo.punto_xy(k)
        out.append({"id": k, "nombre": nombre, "x": round(x - origen[0], 1), "y": round(y - origen[1], 1),
                    "rotonda": k in ROTONDAS, "monumento": k in MONUMENTOS})
    return out


class Manejador(SimpleHTTPRequestHandler):
    motor: Motor = None  # se asigna al arrancar

    def log_message(self, formato, *args):  # silencio salvo errores
        if "/api/" in (self.path or "") and args and str(args[1]).startswith(("4", "5")):
            super().log_message(formato, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if u.path == "/api/estado":
            m = self.motor
            return self._json({"vivo": True, "listo": m.listo.is_set() and not m.error, "error": m.error,
                               "ocupado": m.actual is not None, "vias": _vias_disponibles(),
                               "lugares": m.lugares,
                               "agentes": [{"id": "instructor", "nombre": "Vehículo instructor (DQN)"},
                                           {"id": "reglas", "nombre": "Conductor de reglas"}]})
        if u.path == "/api/detener":
            if self.motor.actual is not None:
                self.motor.actual.cancelado = True
            return self._json({"ok": True})
        if u.path == "/api/simular":
            return self._simular(q)
        return super().do_GET()

    def _simular(self, q: dict):
        m = self.motor
        if not m.listo.is_set() or m.error:
            return self._json({"error": m.error or "La simulación todavía está arrancando"}, 503)
        if m.actual is not None:  # un solo episodio a la vez: el nuevo reemplaza al anterior
            m.actual.cancelado = True
        try:
            t = Trabajo(via=q.get("via", "Avenida del Río"), hora=float(q.get("hora", 17.5)),
                        lluvia=q.get("lluvia", "0") in ("1", "true"), ciclo=float(q.get("ciclo", 0)),
                        agente=q.get("agente", "instructor"), guardrail=q.get("guardrail", "1") in ("1", "true"),
                        velocidad=float(q.get("velocidad", 1)), duracion=float(q.get("duracion", 300)))
            # recorrido a la medida: partida=<id> o partida_x/partida_y (coordenadas del visor)
            if q.get("partida_x") and q.get("partida_y"):
                t.partida = (float(q["partida_x"]) + m.origen[0], float(q["partida_y"]) + m.origen[1])
            elif q.get("partida"):
                t.partida = q["partida"]
            t.pasar_por = [p for p in q.get("pasar_por", "").split(",") if p]
            t.destino = q.get("destino") or None
        except ValueError:
            return self._json({"error": "parámetros inválidos"}, 400)
        m.trabajos.put(t)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                item = t.salida.get()
                if item is None:
                    self.wfile.write(b"event: cerrar\ndata: {}\n\n")
                    self.wfile.flush()
                    break
                tipo, datos = item
                self.wfile.write(f"event: {tipo}\ndata: {json.dumps(datos, separators=(',', ':'), ensure_ascii=False)}\n\n"
                                 .encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            t.cancelado = True  # el usuario cerró la pestaña o pidió otro recorrido


def servir(puerto: int = 8000) -> None:
    motor = Motor()
    motor.start()
    Manejador.motor = motor
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), partial(Manejador, directory=str(C.DIR_VISOR)))
    servidor.daemon_threads = True
    print(f"Arrancando SUMO (calentamiento de 600 s simulados, ~1 minuto)... abre http://localhost:{puerto}", flush=True)
    threading.Thread(target=lambda: (motor.listo.wait(), print(
        "Simulación lista." if not motor.error else f"Error: {motor.error}", flush=True)), daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
