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


class PruebaHoraDelDia(unittest.TestCase):
    def test_luminosidad(self):
        from bq_sim.config import luminosidad
        self.assertAlmostEqual(luminosidad(12.0), 1.0)
        self.assertAlmostEqual(luminosidad(2.0), 0.0)
        self.assertAlmostEqual(luminosidad(22.0), 0.0)
        self.assertTrue(0.0 < luminosidad(18.2) < 1.0)   # atardecer
        self.assertTrue(0.0 < luminosidad(6.0) < 1.0)    # amanecer

    def test_clima_dinamico_coincide_con_los_fijos(self):
        from bq_sim.config import CLIMAS, clima_dinamico
        dia, noche = clima_dinamico(12.0, False), clima_dinamico(23.0, False)
        self.assertAlmostEqual(dia.alcance_m, CLIMAS["despejado"].alcance_m)
        self.assertAlmostEqual(noche.alcance_m, CLIMAS["noche"].alcance_m)
        self.assertAlmostEqual(clima_dinamico(12.0, True).alcance_m, CLIMAS["lluvia"].alcance_m)
        self.assertLess(clima_dinamico(23.0, True).alcance_m, noche.alcance_m)  # lluvia de noche: lo peor
        self.assertEqual(clima_dinamico(12.0, True).mu, CLIMAS["lluvia"].mu)


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


class PruebaCiudad(unittest.TestCase):
    def test_horas_pico(self):
        from bq_sim.ciudad import es_hora_pico, factor_demanda, factor_peatones
        self.assertAlmostEqual(factor_demanda(7.5), 1.60)
        self.assertAlmostEqual(factor_demanda(18.0), 1.65)
        self.assertLess(factor_demanda(3.0), 0.5)
        self.assertTrue(es_hora_pico(7.5) and es_hora_pico(18.0) and es_hora_pico(12.5))
        self.assertFalse(es_hora_pico(15.0) or es_hora_pico(23.0))
        self.assertAlmostEqual(factor_demanda(24.0), factor_demanda(0.0))
        # el Malecón se llena al atardecer y casi nadie camina al mediodía
        self.assertGreater(factor_peatones(18.5, "paseo"), 3 * factor_peatones(12.0, "paseo"))

    def test_estrato_por_barrio(self):
        import json
        from bq_sim.ciudad import barrio, estrato
        datos = json.loads((Path(__file__).resolve().parents[1] / "data" / "estratos.json").read_text(encoding="utf-8"))
        for b in datos["barrios"]:
            self.assertEqual(estrato(b["lon"], b["lat"]), b["estrato"])
        nombre, est = barrio(-74.8125, 11.0035)
        self.assertIn(est, range(0, 7))


class _Traci:  # TraCI mínimo para probar a Navegación sin SUMO
    class vehicle:
        @staticmethod
        def getBestLanes(_ego):
            return [("e_0", 100.0, 0.0, 0, True, []), ("e_1", 100.0, 0.0, 0, True, [])]


class _Mundo:
    traci = _Traci

    @staticmethod
    def permite_autos(_carril):
        return True


def _mm(t, carril, detectados, traseros=()):
    from bq_sim import config as C
    from bq_sim.agentes.percepcion import ModeloMundo
    from bq_sim.entorno.mundo import Camino
    return ModeloMundo(t=t, v=10.0, a_prev=0.0, v_lim=13.9, limites_proximos=[], detectados=list(detectados),
                       verdad=[], senal=None, camino=Camino([(0, 0), (200, 0)], [], [(0.0, "e_0")], "e_0", 0.0),
                       carril_idx=carril, n_carriles_auto=2, clima=C.CLIMAS["despejado"],
                       extras={"traseros": list(traseros)})


class PruebaAdelantar(unittest.TestCase):
    def test_adelanta_al_lento_y_cuenta(self):
        from bq_sim.agentes.especialistas import AgenteNavegacion
        from bq_sim.agentes.percepcion import Objeto
        lento = Objeto("bus1", "vehiculo", "bus", 25.0, 0.0, 6.0, 2.5, True, False)  # va a 4 m/s
        nav = AgenteNavegacion(_Mundo, "ego")
        self.assertIsNone(nav.proponer(_mm(0.0, 0, [lento]), [lento]).carril)   # todavía no: espera 2 s
        p = nav.proponer(_mm(2.5, 0, [lento]), [lento])
        self.assertEqual(p.carril, 1)
        self.assertEqual(p.datos.get("tipo"), "adelantar")
        nav.proponer(_mm(3.0, 1, []), [])                                     # ya se pasó a la izquierda
        self.assertEqual(nav.adelantamientos, 1)

    def test_no_adelanta_si_la_izquierda_va_ocupada(self):
        from bq_sim.agentes.especialistas import AgenteNavegacion
        from bq_sim.agentes.percepcion import Objeto
        lento = Objeto("bus1", "vehiculo", "bus", 25.0, 0.0, 6.0, 2.5, True, False)
        vecino = Objeto("a2", "vehiculo", "auto", 12.0, -3.2, 5.0, 1.8, False, False)  # izquierda, también lento
        nav = AgenteNavegacion(_Mundo, "ego")
        nav.proponer(_mm(0.0, 0, [lento, vecino]), [lento])
        self.assertIsNone(nav.proponer(_mm(2.5, 0, [lento, vecino]), [lento]).carril)

    def test_radar_trasero_veta_el_cambio(self):
        from bq_sim.agentes.especialistas import AgenteSeguridad
        from bq_sim.agentes.percepcion import Objeto
        seg = AgenteSeguridad(PERFILES["automovil"])
        rapido = Objeto("m1", "vehiculo", "moto", -20.0, -3.2, -9.0, 0.8, False, False)  # se acerca a 9 m/s más
        self.assertFalse(seg.carril_seguro(_mm(0.0, 0, [], [rapido]), 1))
        lejos = Objeto("m2", "vehiculo", "moto", -40.0, -3.2, -2.0, 0.8, False, False)
        self.assertTrue(seg.carril_seguro(_mm(0.0, 0, [], [lejos]), 1))


if __name__ == "__main__":
    unittest.main()
