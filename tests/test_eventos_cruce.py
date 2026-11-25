"""El imprevisto que cruza tiene una sola posición: SUMO, percepción y visor coinciden (D-35).

Usa un mundo falso (sin SUMO): tres carriles rectos hacia el este, de 3.2 m, centros en
y = 0, 3.2 y 6.4.

    python -m unittest discover -s tests -v
"""
import random
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bq_sim.entorno.eventos import GestorEventos, ObjetoEvento  # noqa: E402

ANCHO = 3.2


class TraciFalso:
    def __init__(self):
        self.carril = {}       # id -> carril en SUMO
        self.ocupados = set()  # carriles con un carro encima del objeto
        self.vehicle = SimpleNamespace(moveTo=self._mover, setSpeed=lambda *a: None,
                                       getIDList=lambda: list(self.carril), remove=self.carril.pop)
        self.lane = SimpleNamespace(getLastStepVehicleIDs=self._en_carril)

    def _mover(self, vid, carril, pos):
        self.carril[vid] = carril

    def _en_carril(self, carril):
        return ["auto_1"] if carril in self.ocupados else []


class MundoFalso:
    dt = 0.25

    def __init__(self):
        self.t = 0.0
        self.rng = random.Random(1)
        self.traci = TraciFalso()

    def forma_carril(self, carril):
        k = int(carril.rsplit("_", 1)[1])
        return [(0.0, k * ANCHO), (100.0, k * ANCHO)]

    def ancho_carril(self, carril):
        return ANCHO

    def quitar(self, vid):
        self.traci.carril.pop(vid, None)


def nuevo_peaton(m):
    g = GestorEventos(m, params=SimpleNamespace(tasa_por_km={}))
    g._libre = lambda ob, k: f"{ob.arista}_{k}" not in m.traci.ocupados
    ob = ObjetoEvento("obs_peaton_1", "peaton", "e", 50.0, [0, 1, 2], t_carril=2.0,
                      espera_inicial=0.0, imprudente=False, en_sumo=True)
    m.traci.carril[ob.id] = "e_0"
    g.objetos[ob.id] = ob
    return g, ob


def correr(g, m, segundos):
    for _ in range(int(segundos / m.dt)):
        m.t += m.dt
        g._actualizar()


class PruebaCruceContinuo(unittest.TestCase):
    def test_sumo_cambia_de_carril_al_cruzar_la_linea(self):
        m = MundoFalso()
        g, ob = nuevo_peaton(m)
        for _ in range(40):
            m.t += m.dt
            g._actualizar()
            if not ob.vivo:
                break
            _x, y, _r = g.posicion(ob)
            carril_sumo = int(m.traci.carril[ob.id].rsplit("_", 1)[1])
            # el centro del peatón está siempre dentro del carril que SUMO le asigna
            self.assertLessEqual(abs(y - carril_sumo * ANCHO), ANCHO / 2 + 1e-6, (m.t, y, carril_sumo))
        self.assertFalse(ob.vivo, "termina de cruzar y sale por el último carril")

    def test_espera_sobre_la_linea_si_el_carril_siguiente_esta_ocupado(self):
        m = MundoFalso()
        g, ob = nuevo_peaton(m)
        m.traci.ocupados.add("e_1")
        correr(g, m, 3.0)
        _x, y, _r = g.posicion(ob)
        self.assertEqual(m.traci.carril[ob.id], "e_0")
        self.assertAlmostEqual(y, 0.499 * ANCHO, places=3)  # en la línea, no dibujado dentro del carril 1
        m.traci.ocupados.clear()
        correr(g, m, 0.5)
        self.assertEqual(m.traci.carril[ob.id], "e_1")

    def test_visor_y_percepcion_usan_la_misma_posicion(self):
        m = MundoFalso()
        g, ob = nuevo_peaton(m)
        correr(g, m, 1.3)
        m.posiciones_eventos = {ob.id: g.posicion(ob)}
        r = g.posiciones_render()[0]
        x, y, _ = m.posiciones_eventos[ob.id]
        self.assertAlmostEqual(r["x"], round(x, 2))
        self.assertAlmostEqual(r["y"], round(y, 2))


if __name__ == "__main__":
    unittest.main()
