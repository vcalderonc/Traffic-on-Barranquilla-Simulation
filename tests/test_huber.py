"""D-37: el delta de Huber decide cuánto pesa en el gradiente un error TD grande (un
atropello) frente a los errores pequeños del mismo lote."""
import unittest

import numpy as np

from bq_sim.aprendizaje.dqn import AgenteDQN, HiperDQN


def _pesos_en_gradiente(delta: float) -> tuple[float, float]:
    """Lote = 1 atropello (r = -150) + 1 transición con error pequeño (r = -3). Devuelve el peso que
    cada una recibe en el gradiente de la salida."""
    hp = HiperDQN(lote=2, inicio_aprendizaje=1, memoria=4, memoria_incidentes=4, frac_incidentes=0.0,
                  n_pasos=1, huber_delta=delta)
    ag = AgenteDQN(4, 3, hp, semilla=0)
    s1, s2 = np.array([1, 0, 0, 1], np.float32), np.array([0, 1, 1, 0], np.float32)
    ag.recordar(s1, 1, -150.0, s1, 1.0)
    ag.recordar(s2, 0, -3.0, s2, 1.0)
    ag.mem.indices = lambda n: np.arange(2)
    capturado = {}
    original = ag.red.backward

    def espiar(cache, g):
        capturado["g"] = g.copy()
        return original(cache, g)

    ag.red.backward = espiar
    ag.entrenar()
    g = capturado["g"]
    return abs(float(g[0, 1])), abs(float(g[1, 0]))


class TestHuber(unittest.TestCase):
    def test_delta_1_iguala_atropello_y_error_pequeno(self):
        atr, normal = _pesos_en_gradiente(1.0)
        self.assertAlmostEqual(atr, normal, places=6)

    def test_delta_10_da_mas_peso_al_atropello(self):
        atr, normal = _pesos_en_gradiente(10.0)
        self.assertGreater(atr, 2.0 * normal)

    def test_modelo_viejo_carga_con_delta_1(self):
        self.assertEqual(HiperDQN().huber_delta, 1.0)


if __name__ == "__main__":
    unittest.main()
