"""D-36: anticipar al peatón o animal que se mete en la vía (no necesitan SUMO).

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bq_sim.agentes.percepcion import AgentePercepcion, Objeto  # noqa: E402
from bq_sim.agentes.velocidad import N_ACC, N_OBS  # noqa: E402
from bq_sim.aprendizaje.dqn import AgenteDQN  # noqa: E402


class PruebaRedAmpliada(unittest.TestCase):
    def test_modelo_de_28_entradas_sirve_en_31_y_conduce_igual(self):
        viejo = AgenteDQN(28, N_ACC, semilla=3)
        nuevo = AgenteDQN(N_OBS, N_ACC, semilla=9)
        nuevo.fijar_parametros(viejo.obtener_parametros())
        rng = np.random.default_rng(0)
        for _ in range(20):
            obs = rng.uniform(-1, 1, N_OBS).astype(np.float32)
            np.testing.assert_allclose(viejo.valores_q(obs), nuevo.valores_q(obs), rtol=1e-5, atol=1e-6)
            self.assertEqual(viejo.actuar(obs, explorar=False), nuevo.actuar(obs, explorar=False))

    def test_modelo_viejo_puede_recordar_observaciones_nuevas(self):
        viejo = AgenteDQN(28, N_ACC, semilla=3)
        obs = np.zeros(N_OBS, np.float32)
        for _ in range(5):
            viejo.recordar(obs, 1, 0.1, obs, 0.0)
        self.assertEqual(viejo.mem.s.shape[1], 28)
        self.assertGreater(viejo.mem.n, 0)  # guardó transiciones, recortadas a sus 28 entradas


class PruebaConflicto(unittest.TestCase):
    def _percepcion(self):
        p = AgentePercepcion.__new__(AgentePercepcion)
        p.m = SimpleNamespace(t=0.0)
        p.ancho_ego = 1.85
        p._lat_prev = {}
        return p

    def _seguir(self, p, lateral_por_paso, s=25.0, v_ego=12.0, dt=0.25):
        o = None
        for lat in lateral_por_paso:
            p.m.t += dt
            o = Objeto("obs_perro_1", "animal", "perro", s, lat, v_ego, 0.4, False, True)
            umbral = p.ancho_ego / 2 + 0.4 / 2 + 0.25
            o.en_trayectoria = abs(lat) < umbral
            p._predecir_cruce(o, umbral, v_ego)
        return o

    def test_animal_que_se_acerca_es_conflicto(self):
        p = self._percepcion()
        o = self._seguir(p, [4.0, 3.5, 3.0, 2.5])  # 2 m/s hacia la trayectoria
        self.assertGreater(o.v_lat, 1.0)
        self.assertTrue(o.conflicto)
        self.assertLess(o.t_entra, 1.0)

    def test_animal_quieto_o_que_se_aleja_no_es_conflicto(self):
        p = self._percepcion()
        self.assertFalse(self._seguir(p, [3.0, 3.0, 3.0, 3.0]).conflicto)
        p = self._percepcion()
        self.assertFalse(self._seguir(p, [2.0, 2.5, 3.0, 3.5]).conflicto)

    def test_si_el_ego_pasa_mucho_antes_no_es_conflicto(self):
        # muy lejos lateralmente y despacio: entra en ~10 s; el ego llega en ~0.5 s
        p = self._percepcion()
        self.assertFalse(self._seguir(p, [6.0, 5.95, 5.9, 5.85], s=6.0, v_ego=12.0).conflicto)


class PruebaSeparacionLateral(unittest.TestCase):
    """El ego detenido no arranca rozando a un peatón que espera sobre la línea del carril."""

    def _evaluar(self, lateral, s=3.0, v=0.0):
        from bq_sim.agentes.especialistas import AgenteSeguridad
        from bq_sim.aprendizaje.perfiles import PERFILES

        perfil = PERFILES["automovil"]
        ped = Objeto("obs_peaton_1", "peaton", "peaton", s, lateral, 0.0, 0.6, False, True)
        mm = SimpleNamespace(v=v, clima=SimpleNamespace(mu=0.8), detectados=[ped], extras={})
        return AgenteSeguridad(perfil)._evaluar(mm, [], None)

    def test_peaton_a_1_6_m_del_centro_bloquea_el_arranque(self):
        p = self._evaluar(1.6)
        self.assertTrue(p.veto)
        self.assertLessEqual(p.acel_max, 0.0)

    def test_peaton_en_el_anden_no_bloquea(self):
        self.assertFalse(self._evaluar(2.6).veto)


if __name__ == "__main__":
    unittest.main()
