"""Double DQN implementado solo con NumPy.

Por qué NumPy y no PyTorch: la red es pequeña (2 capas de 64), corre en cualquier
portátil sin GPU, no agrega 2 GB de dependencias y cada línea se puede explicar en
la sustentación. Los parámetros son una lista de arreglos NumPy, que es justo el
formato que intercambian FedAvg y ``flwr.client.NumPyClient``.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


# --------------------------------------------------------------------------- red
class MLP:
    """Perceptrón multicapa con ReLU y salida lineal (un valor Q por acción)."""

    def __init__(self, n_entrada: int, n_salida: int, ocultas=(64, 64), semilla: int = 0):
        rng = np.random.default_rng(semilla)
        dims = [n_entrada, *ocultas, n_salida]
        self.params: list[np.ndarray] = []
        for a, b in zip(dims[:-1], dims[1:]):
            self.params.append((rng.standard_normal((a, b)) * np.sqrt(2.0 / a)).astype(np.float32))
            self.params.append(np.zeros(b, dtype=np.float32))

    # forward con caché para el backward
    def forward(self, x: np.ndarray):
        cache = [x]
        h = x
        n_capas = len(self.params) // 2
        for i in range(n_capas):
            W, b = self.params[2 * i], self.params[2 * i + 1]
            z = h @ W + b
            h = np.maximum(z, 0.0) if i < n_capas - 1 else z
            cache.append(h)
        return h, cache

    def predecir(self, x: np.ndarray) -> np.ndarray:
        return self.forward(np.atleast_2d(x).astype(np.float32))[0]

    def backward(self, cache, grad_salida: np.ndarray) -> list[np.ndarray]:
        grads = [None] * len(self.params)
        g = grad_salida
        n_capas = len(self.params) // 2
        for i in reversed(range(n_capas)):
            h_prev = cache[i]
            grads[2 * i] = h_prev.T @ g
            grads[2 * i + 1] = g.sum(axis=0)
            if i > 0:
                g = (g @ self.params[2 * i].T) * (cache[i] > 0)
        return grads

    def copiar_de(self, otra: "MLP") -> None:
        self.params = [p.copy() for p in otra.params]


class Adam:
    def __init__(self, params, lr=5e-4, b1=0.9, b2=0.999, eps=1e-8):
        self.lr, self.b1, self.b2, self.eps = lr, b1, b2, eps
        self.m = [np.zeros_like(p) for p in params]
        self.v = [np.zeros_like(p) for p in params]
        self.t = 0

    def paso(self, params, grads, clip=10.0):
        norma = np.sqrt(sum(float((g ** 2).sum()) for g in grads))
        escala = min(1.0, clip / (norma + 1e-8))
        self.t += 1
        for i, (p, g) in enumerate(zip(params, grads)):
            g = g * escala
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * g * g
            mh = self.m[i] / (1 - self.b1 ** self.t)
            vh = self.v[i] / (1 - self.b2 ** self.t)
            p -= (self.lr * mh / (np.sqrt(vh) + self.eps)).astype(p.dtype)


# --------------------------------------------------------------- memoria replay
class MemoriaReplay:
    def __init__(self, capacidad: int, n_obs: int, semilla: int = 0):
        self.cap = capacidad
        self.s = np.zeros((capacidad, n_obs), np.float32)
        self.a = np.zeros(capacidad, np.int64)
        self.r = np.zeros(capacidad, np.float32)
        self.s2 = np.zeros((capacidad, n_obs), np.float32)
        self.fin = np.zeros(capacidad, np.float32)
        self.a_guia = np.full(capacidad, -1, np.int64)  # acción del instructor (-1 = sin dato)
        self.i = 0
        self.n = 0
        self.rng = np.random.default_rng(semilla)

    def agregar(self, s, a, r, s2, fin, a_guia=-1):
        k = self.i
        self.s[k], self.a[k], self.r[k], self.s2[k], self.fin[k] = s, a, r, s2, fin
        self.a_guia[k] = a_guia
        self.i = (self.i + 1) % self.cap
        self.n = min(self.n + 1, self.cap)

    def muestra(self, lote: int):
        idx = self.rng.integers(0, self.n, size=lote)
        return self.s[idx], self.a[idx], self.r[idx], self.s2[idx], self.fin[idx], self.a_guia[idx]


# ------------------------------------------------------------------- agente DQN
@dataclass
class HiperDQN:
    gamma: float = 0.97          # horizonte efectivo ~ 33 pasos de 0.25 s = 8 s
    lr: float = 3e-4
    lote: int = 64
    memoria: int = 60_000
    inicio_aprendizaje: int = 1_000
    tau: float = 0.005           # actualización suave de la red objetivo
    eps_inicial: float = 1.0
    eps_final: float = 0.05
    eps_pasos: int = 40_000
    ocultas: tuple = (64, 64)
    peso_imitacion: float = 0.0  # lambda de la pérdida de imitación (la fija el instructor)
    margen_imitacion: float = 0.8


class AgenteDQN:
    """Double DQN con red objetivo suave, pérdida Huber y pérdida de imitación opcional.

    La pérdida de imitación (margen al estilo DQfD) es la forma en que el vehículo
    instructor "enseña": empuja a que la acción que él habría tomado tenga el valor
    Q más alto por al menos un margen.
    """

    def __init__(self, n_obs: int, n_acc: int, hp: HiperDQN | None = None, semilla: int = 0):
        self.hp = hp or HiperDQN()
        self.n_obs, self.n_acc = n_obs, n_acc
        self.red = MLP(n_obs, n_acc, self.hp.ocultas, semilla)
        self.objetivo = MLP(n_obs, n_acc, self.hp.ocultas, semilla)
        self.objetivo.copiar_de(self.red)
        self.opt = Adam(self.red.params, self.hp.lr)
        self.mem = MemoriaReplay(self.hp.memoria, n_obs, semilla)
        self.rng = np.random.default_rng(semilla + 1)
        self.pasos = 0
        self.ultima_perdida = 0.0

    # --- política
    def epsilon(self) -> float:
        f = min(1.0, self.pasos / max(1, self.hp.eps_pasos))
        return self.hp.eps_inicial + f * (self.hp.eps_final - self.hp.eps_inicial)

    def valores_q(self, obs) -> np.ndarray:
        return self.red.predecir(obs)[0]

    def actuar(self, obs, explorar: bool = True) -> int:
        if explorar and self.rng.random() < self.epsilon():
            return int(self.rng.integers(self.n_acc))
        return int(np.argmax(self.valores_q(obs)))

    # --- aprendizaje
    def recordar(self, s, a, r, s2, fin, a_guia=-1):
        self.mem.agregar(s, a, r, s2, fin, a_guia)
        self.pasos += 1

    def entrenar(self) -> float:
        if self.mem.n < self.hp.inicio_aprendizaje:
            return 0.0
        s, a, r, s2, fin, a_guia = self.mem.muestra(self.hp.lote)
        q, cache = self.red.forward(s)
        # Double DQN: la red en línea elige, la red objetivo evalúa
        a2 = np.argmax(self.red.forward(s2)[0], axis=1)
        q2 = self.objetivo.forward(s2)[0][np.arange(len(a2)), a2]
        y = r + self.hp.gamma * (1.0 - fin) * q2
        filas = np.arange(len(a))
        td = q[filas, a] - y
        # gradiente de Huber (delta = 1)
        g = np.zeros_like(q)
        g[filas, a] = np.clip(td, -1.0, 1.0) / len(a)
        perdida = float(np.mean(np.where(np.abs(td) < 1, 0.5 * td ** 2, np.abs(td) - 0.5)))

        # pérdida de imitación (DQfD): max_a [Q(s,a) + m*(a != a_guia)] - Q(s, a_guia)
        lam = self.hp.peso_imitacion
        con_guia = a_guia >= 0
        if lam > 0 and con_guia.any():
            idx = np.where(con_guia)[0]
            qg = q[idx]
            margen = np.full_like(qg, self.hp.margen_imitacion)
            margen[np.arange(len(idx)), a_guia[idx]] = 0.0
            a_max = np.argmax(qg + margen, axis=1)
            difiere = a_max != a_guia[idx]
            if difiere.any():
                k = idx[difiere]
                g[k, a_max[difiere]] += lam / len(a)
                g[k, a_guia[k]] -= lam / len(a)
                perdida += lam * float(np.mean(difiere))

        grads = self.red.backward(cache, g.astype(np.float32))
        self.opt.paso(self.red.params, grads)
        tau = self.hp.tau
        for po, pr in zip(self.objetivo.params, self.red.params):
            po *= (1 - tau)
            po += tau * pr
        self.ultima_perdida = perdida
        return perdida

    # --- intercambio de conocimiento (FedAvg / instructor)
    def obtener_parametros(self) -> list[np.ndarray]:
        return [p.copy() for p in self.red.params]

    def fijar_parametros(self, params: list[np.ndarray]) -> None:
        self.red.params = [np.asarray(p, np.float32).copy() for p in params]
        self.objetivo.copiar_de(self.red)
        self.opt = Adam(self.red.params, self.hp.lr)

    def guardar(self, ruta: Path, meta: dict | None = None) -> None:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        meta = dict(meta or {})
        meta.update(n_obs=self.n_obs, n_acc=self.n_acc, hp=asdict(self.hp), pasos=self.pasos)
        np.savez_compressed(ruta, *self.red.params, meta=json.dumps(meta))

    @classmethod
    def cargar(cls, ruta: Path, semilla: int = 0) -> tuple["AgenteDQN", dict]:
        datos = np.load(ruta, allow_pickle=False)
        meta = json.loads(str(datos["meta"]))
        hp = HiperDQN(**{k: (tuple(v) if k == "ocultas" else v) for k, v in meta["hp"].items()})
        ag = cls(meta["n_obs"], meta["n_acc"], hp, semilla)
        params = [datos[f"arr_{i}"] for i in range(len(ag.red.params))]
        ag.fijar_parametros(params)
        return ag, meta
