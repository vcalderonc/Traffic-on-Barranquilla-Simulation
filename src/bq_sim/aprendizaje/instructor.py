"""Vehículo instructor: el carro ya entrenado que enseña a conducir a los demás.

Funciona como el instructor de una escuela de conducción con "doble comando":

1. **Transferencia directa**: el aprendiz arranca con una copia (normalizada) del
   conocimiento del instructor en vez de una red aleatoria.
2. **Doble comando**: el instructor observa lo mismo que el aprendiz y, si este
   elige una acción claramente menos prudente que la suya en una situación de
   riesgo, la reemplaza (pisa el freno). El aprendiz recibe una penalización por
   intervención y guarda la corrección en su memoria.
3. **Demostración (imitación)**: en cada paso el instructor anota qué habría hecho;
   el aprendiz suma a su pérdida un término de imitación (margen DQfD, Hester et
   al., 2018) cuyo peso ``lambda`` decae con los episodios.

Con el tiempo el instructor "suelta el volante": la tolerancia sube y ``lambda``
baja, hasta que el aprendiz conduce solo. La tasa de intervenciones por episodio
es una medida directa de cuánto ha aprendido el aprendiz.
"""
from __future__ import annotations

import numpy as np

from .dqn import AgenteDQN
from .perfiles import ACCIONES, NOMBRES_ACCIONES


class InstructorDobleComando:
    def __init__(self, maestro: AgenteDQN, tolerancia_q: float = 0.6, riesgo_minimo: float = 0.25,
                 episodios_tutela: int = 50, lambda_inicial: float = 1.0, piso_lambda: float = 0.25):
        self.maestro = maestro
        self.tol0 = tolerancia_q
        self.riesgo_min = riesgo_minimo
        self.tutela = episodios_tutela
        self.lam0 = lambda_inicial
        self.piso = piso_lambda
        self.ep = 0
        self.ultima_guia = -1
        self.intervenciones_ep = 0

    def nuevo_episodio(self) -> None:
        self.ep += 1
        self.intervenciones_ep = 0

    @property
    def fraccion(self) -> float:
        return min(1.0, self.ep / max(1, self.tutela))

    @property
    def lam(self) -> float:
        """Peso de la pérdida de imitación: decae durante la tutela hasta un piso (el consejo queda)."""
        return self.lam0 * max(self.piso, 1.0 - self.fraccion)

    @property
    def tolerancia(self) -> float:
        """Diferencia de valor Q tolerada antes de intervenir (crece: interviene menos)."""
        return self.tol0 * (1.0 + 4.0 * self.fraccion)

    @staticmethod
    def riesgo(obs: np.ndarray) -> float:
        # riesgo TTC del objeto más cercano, frenado requerido (objeto / señal / límite), peatón cerca
        return float(max(obs[4], min(1.0, obs[12]), min(1.0, obs[22]), min(1.0, obs[23]), 0.6 * obs[15]))

    def supervisar(self, obs: np.ndarray, accion_alumno: int) -> tuple[int, bool, str]:
        q = self.maestro.valores_q(obs)
        guia = int(np.argmax(q))
        self.ultima_guia = guia
        if self.ep > self.tutela or guia == accion_alumno:
            return accion_alumno, False, ""
        menos_prudente = ACCIONES[accion_alumno] > ACCIONES[guia]
        diferencia = float(q[guia] - q[accion_alumno])
        if menos_prudente and self.riesgo(obs) >= self.riesgo_min and diferencia > self.tolerancia:
            self.intervenciones_ep += 1
            return guia, True, f"{NOMBRES_ACCIONES[guia]} en vez de {NOMBRES_ACCIONES[accion_alumno]}"
        return accion_alumno, False, ""
