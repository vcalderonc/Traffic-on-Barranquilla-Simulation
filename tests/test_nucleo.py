"""Pruebas de verificación del núcleo (no necesitan SUMO).

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bq_sim.aprendizaje.dqn import MLP, AgenteDQN, HiperDQN  # noqa: E402
from bq_sim.aprendizaje.fedavg import fedavg  # noqa: E402
from bq_sim.aprendizaje.perfiles import PERFILES, accion_a_aceleracion  # noqa: E402
from bq_sim.entorno.mundo import proyectar, punto_en  # noqa: E402


class PruebaRed(unittest.TestCase):
    def test_gradiente_numerico(self):
        """El backward de la red coincide con diferencias finitas."""
        rng = np.random.default_rng(0)
        red = MLP(5, 3, (4,), semilla=1)
        red.params = [p.astype(np.float64) for p in red.params]
        x = rng.standard_normal((2, 5))
        g_sal = rng.standard_normal((2, 3))
        _, cache = red.forward(x)
        grads = red.backward(cache, g_sal)
        eps = 1e-6
        for k, p in enumerate(red.params):
            i = tuple(rng.integers(0, s) for s in p.shape)
            orig = p[i]
            p[i] = orig + eps
            f1 = float((red.forward(x)[0] * g_sal).sum())
            p[i] = orig - eps
            f2 = float((red.forward(x)[0] * g_sal).sum())
            p[i] = orig
            self.assertAlmostEqual(grads[k][i], (f1 - f2) / (2 * eps), places=5)

    def test_dqn_aprende_problema_trivial(self):
        """En un bandido de un estado, el DQN termina prefiriendo la acción con más recompensa."""
        ag = AgenteDQN(2, 3, HiperDQN(inicio_aprendizaje=64, lote=32, eps_pasos=1, gamma=0.0, lr=5e-3), semilla=0)
        s = np.array([1.0, 0.0], np.float32)
        for _ in range(600):
            a = int(ag.rng.integers(3))
            ag.recordar(s, a, [0.0, 1.0, 0.2][a], s, 1.0)
            ag.entrenar()
        self.assertEqual(ag.actuar(s, explorar=False), 1)


class PruebaFederado(unittest.TestCase):
    def test_fedavg_pondera_por_experiencia(self):
        a = [np.array([0.0, 0.0])]
        b = [np.array([4.0, 8.0])]
        g = fedavg([a, b], [3, 1])
        np.testing.assert_allclose(g[0], [1.0, 2.0])


class PruebaNormalizacion(unittest.TestCase):
    def test_bus_normalizado_usa_su_propia_capacidad(self):
        bus, auto = PERFILES["bus"], PERFILES["automovil"]
        # frenado fuerte (60 %) normalizado: 60 % del frenado del bus
        self.assertAlmostEqual(accion_a_aceleracion(1, bus, 0.8), -0.6 * bus.frenado_max_seco)

    def test_copia_tal_cual_se_recorta_por_la_fisica(self):
        bus, auto = PERFILES["bus"], PERFILES["automovil"]
        # emergencia del automóvil (-7.5) en un bus: la física lo deja en -4.5
        a = accion_a_aceleracion(0, bus, 0.8, normalizado=False, perfil_origen=auto)
        self.assertAlmostEqual(a, -bus.frenado_max_seco)
        # frenado suave copiado tal cual pide más de lo que el bus "cree" pedir
        a_suave = accion_a_aceleracion(3, bus, 0.8, normalizado=False, perfil_origen=auto)
        self.assertLess(a_suave, accion_a_aceleracion(3, bus, 0.8))

    def test_lluvia_reduce_frenado(self):
        auto = PERFILES["automovil"]
        self.assertLess(auto.frenado_max(0.45), auto.frenado_max(0.8))


class PruebaGeometria(unittest.TestCase):
    def test_proyeccion_sobre_camino(self):
        camino = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        s, lat, _ = proyectar(camino, 5.0, -1.0)  # a la derecha del primer tramo
        self.assertAlmostEqual(s, 5.0)
        self.assertAlmostEqual(lat, 1.0)
        s2, _, _ = proyectar(camino, 10.0, 5.0)
        self.assertAlmostEqual(s2, 15.0)
        s3, _, _ = proyectar(camino, -3.0, 0.0)  # detrás del ego
        self.assertAlmostEqual(s3, -3.0)

    def test_punto_en(self):
        x, y, _ = punto_en([(0, 0), (10, 0), (10, 10)], 12.0)
        self.assertAlmostEqual(x, 10.0)
        self.assertAlmostEqual(y, 2.0)


if __name__ == "__main__":
    unittest.main()
