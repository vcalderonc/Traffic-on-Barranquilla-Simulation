"""Pruebas de la geometría de la medición de solapes (Fase 0; no necesitan SUMO).

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bq_sim.solapes import Caja, Lugares, cajas_se_solapan, interp_ang  # noqa: E402


class PruebaCaja(unittest.TestCase):
    def test_frente_en_la_posicion_y_cuerpo_hacia_atras(self):
        # rumbo 0 = norte: el carro de 4 m ocupa y en [-4, 0]
        c = Caja(0.0, 0.0, 0.0, 4.0, 2.0)
        self.assertEqual(c.distancia(0.0, -2.0), 0.0)
        self.assertAlmostEqual(c.distancia(0.0, 1.0), 1.0)    # 1 m delante del frente
        self.assertAlmostEqual(c.distancia(0.0, -5.0), 1.0)   # 1 m detrás
        self.assertAlmostEqual(c.distancia(2.0, -2.0), 1.0)   # 1 m al lado

    def test_rumbo_este(self):
        c = Caja(10.0, 0.0, 90.0, 4.0, 2.0)  # rumbo 90 = este: ocupa x en [6, 10]
        self.assertEqual(c.distancia(8.0, 0.5), 0.0)
        self.assertAlmostEqual(c.distancia(11.0, 0.0), 1.0)

    def test_solape_de_cajas(self):
        a = Caja(0.0, 0.0, 0.0, 4.0, 2.0)
        self.assertTrue(cajas_se_solapan(a, Caja(0.5, -1.0, 0.0, 4.0, 2.0)))
        self.assertFalse(cajas_se_solapan(a, Caja(2.5, 0.0, 0.0, 4.0, 2.0)))   # carril vecino
        self.assertFalse(cajas_se_solapan(a, Caja(0.0, -4.5, 0.0, 4.0, 2.0)))  # en fila, 0.5 m de hueco
        self.assertTrue(cajas_se_solapan(a, Caja(0.0, -2.0, 90.0, 4.0, 2.0)))  # cruzado encima

    def test_interpolacion_de_angulo_por_el_camino_corto(self):
        self.assertAlmostEqual(interp_ang(350.0, 10.0, 0.5) % 360.0, 0.0)
        self.assertAlmostEqual(interp_ang(10.0, 350.0, 0.5) % 360.0, 0.0)


class PruebaLugares(unittest.TestCase):
    def test_prioridad_cebra_anden_calzada(self):
        ciudad = {"carriles": [{"interno": False, "l": [[3.2, [0.0, 0.0, 100.0, 0.0]]]}],
                  "andenes": [[2.0, [0.0, 3.0, 100.0, 3.0]]],
                  "cebras": [[4.0, [50.0, -2.0, 50.0, 2.0]]],
                  "cruces": [[90.0, -5.0, 110.0, -5.0, 110.0, 5.0, 90.0, 5.0]]}
        L = Lugares(ciudad)
        self.assertEqual(L.clase(20.0, 0.5), "calzada")
        self.assertEqual(L.clase(20.0, 3.2), "anden")
        self.assertEqual(L.clase(50.5, 0.0), "cebra")
        self.assertEqual(L.clase(105.0, 4.0), "cruce")
        self.assertEqual(L.clase(20.0, 30.0), "otro")


if __name__ == "__main__":
    unittest.main()
