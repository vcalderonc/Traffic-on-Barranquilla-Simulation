"""Simulación en vivo: servidor local que corre SUMO + agentes y transmite al visor 3D.

    python -m bq_sim vivo            ->  abrir http://localhost:8000

El usuario elige en el visor la vía, la hora del día (o el ciclo día-noche), la
lluvia y quién conduce (el instructor DQN o el conductor de reglas). El servidor
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
    salida: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=400))
    cancelado: bool = False


class Motor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.trabajos: queue.Queue = queue.Queue()
        self.listo = threading.Event()
        self.actual: Trabajo | None = None
        self.error: str | None = None

    def run(self) -> None:
        from .aprendizaje.dqn import AgenteDQN
        from .entorno.gym_env import ConduccionBarranquillaEnv
        from .experimentos import MODELO_INSTRUCTOR

        try:
            self.maestro, _ = AgenteDQN.cargar(MODELO_INSTRUCTOR)
            self.env = ConduccionBarranquillaEnv(semilla=11, guardrail=True, multiplicador_eventos=1.6,
                                                 t_max_s=900.0)
            ciudad = json.loads((C.DIR_VISOR / "datos" / "ciudad.json").read_text(encoding="utf-8"))
            self.origen = ciudad["origen"]
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
            obs, info = env.reset(options={"via": t.via, "hora": t.hora, "lluvia": t.lluvia,
                                           "ciclo_min_por_s": t.ciclo, "t_max_s": t.duracion})
            t.salida.put(("inicio", {**info, "agente": t.agente, "guardrail": t.guardrail}))
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


def _vias_disponibles() -> list[dict]:
    from .entorno.mundo import VIAS_SELECCIONABLES

    return [{"id": k, "nombre": v} for k, v in VIAS_SELECCIONABLES.items()]


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
    print(f"Arrancando SUMO (calentamiento de 240 s simulados)... abre http://localhost:{puerto}", flush=True)
    threading.Thread(target=lambda: (motor.listo.wait(), print(
        "Simulación lista." if not motor.error else f"Error: {motor.error}", flush=True)), daemon=True).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
