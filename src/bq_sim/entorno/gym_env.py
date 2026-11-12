"""Entorno estándar Gymnasium sobre SUMO/TraCI (reset / step / observation / reward).

Desde el punto de vista del agente de Velocidad (el que aprende), "el entorno" es
todo lo demás: la ciudad, el tráfico, los imprevistos y también los otros agentes
del vehículo (Señales, Seguridad, Navegación). Es la convención usual en
aprendizaje por refuerzo multiagente.
"""
from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .. import config as C
from ..ciudad import es_hora_pico, factor_demanda
from ..agentes.vehiculo import VehiculoAutonomo
from ..agentes.velocidad import N_ACC, N_OBS
from ..aprendizaje.perfiles import PERFILES
from .evaluador import Evaluador
from .eventos import GestorEventos
from .mundo import ZONAS, MundoSUMO

PESOS_CLIMA = {"despejado": 0.6, "lluvia": 0.25, "noche": 0.15}


class ConduccionBarranquillaEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, semilla: int = 0, zonas: list[str] | None = None, climas: list[str] | None = None,
                 perfil: str = "automovil", guardrail: bool = True, normalizado: bool = True,
                 perfil_origen: str | None = None, gui: bool = False, escala_demanda: float = 0.75,
                 multiplicador_eventos: float = 1.0, t_max_s: float = 150.0, ruido_sensores: bool = True,
                 grabadora=None, demanda_por_hora: bool = False, calentamiento_s: float = 240.0):
        super().__init__()
        self.mundo = MundoSUMO(semilla, gui, escala_demanda, calentamiento_s=calentamiento_s)
        self.eventos = GestorEventos(self.mundo, multiplicador=multiplicador_eventos)
        self.zonas = zonas or list(ZONAS)
        self.climas = climas or list(PESOS_CLIMA)
        self.perfil_nombre = perfil
        self.guardrail = guardrail
        self.normalizado = normalizado
        self.perfil_origen = PERFILES[perfil_origen] if perfil_origen else None
        self.t_max_s = t_max_s
        self.ruido = ruido_sensores
        self.grabadora = grabadora
        self.demanda_por_hora = demanda_por_hora  # horas pico: más tráfico según la hora del día
        self.max_quieto_s = 45.0  # el episodio se corta si el vehículo pasa este tiempo detenido
        self.instructor = None
        self.hora, self.lluvia, self.ciclo, self.t_max_ep = 15.0, False, 0.0, t_max_s
        self.observation_space = spaces.Box(-2.0, 2.0, (N_OBS,), np.float32)
        self.action_space = spaces.Discrete(N_ACC)
        self.rng = np.random.default_rng(semilla)
        self._n_ep = 0
        self.ego = None
        self.veh: VehiculoAutonomo | None = None
        self.eval: Evaluador | None = None
        self.info_ep: dict = {}

    # ----------------------------------------------------------------- reset
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        options = options or {}
        if self.ego:
            self.mundo.quitar(self.ego)
        self.eventos.reiniciar()
        via = options.get("via")
        zona = options.get("zona") or self.rng.choice(self.zonas)
        if "clima" in options:
            clima = options["clima"]
        else:
            p = np.array([PESOS_CLIMA[c] for c in self.climas])
            clima = self.rng.choice(self.climas, p=p / p.sum())
        # hora del día y lluvia: si se piden explícitamente, el clima es dinámico
        if options.get("hora") is not None:
            self.hora = float(options["hora"]) % 24.0
            self.lluvia = bool(options.get("lluvia", False))
            clima_obj = C.clima_dinamico(self.hora, self.lluvia)
            clima = clima_obj.nombre
        else:
            self.hora = C.HORA_CLIMA[clima]
            self.lluvia = clima == "lluvia"
            clima_obj = C.CLIMAS[clima]
        self.ciclo = float(options.get("ciclo_min_por_s", 0.0))  # minutos de día por segundo simulado
        if options.get("demanda_por_hora", self.demanda_por_hora):
            self.mundo.ajustar_demanda(factor_demanda(self.hora), hora=self.hora)
        self.t_max_ep = float(options.get("t_max_s", self.t_max_s))
        perfil = PERFILES[options.get("perfil", self.perfil_nombre)]
        if options.get("partida") is not None:
            # recorrido a la medida: desde donde el usuario quiera, pasando por monumentos
            ruta_p = self.mundo.ruta_personalizada(options["partida"], options.get("pasar_por") or (),
                                                   options.get("destino"), perfil.tipo_sumo,
                                                   semilla=int(self.rng.integers(1 << 20)))
            zona = "recorrido a la medida"
            x, y = self.mundo.forma_carril(f"{ruta_p.aristas[0]}_0")[0]
            lon, lat = self.mundo.lonlat(x, y)
            self.eventos.mult_clase = next((z["eventos"] for z in ZONAS.values()
                                            if self.mundo.traci.edge.getStreetName(ruta_p.aristas[0]) in z["calles"]), {})
            rutas = [ruta_p]
            # que alcance a llegar (6 m/s de promedio, con semáforos y trancones)
            self.t_max_ep = max(self.t_max_ep, ruta_p.largo_m / 6.0 + 120.0)
        elif via:
            zona = f"vía: {via}"
            self.eventos.mult_clase = next((z["eventos"] for z in ZONAS.values() if via in z["calles"]), {})
            rutas = self.mundo.rutas_por_via(via, tipo=perfil.tipo_sumo)
            if not rutas:
                raise ValueError(f"No hay rutas disponibles sobre {via}")
        else:
            self.eventos.mult_clase = ZONAS[zona]["eventos"]
            rutas = self.mundo.rutas_zona(zona, tipo=perfil.tipo_sumo)
        for intento in range(8):
            self._n_ep += 1
            self.ego = f"ego{self._n_ep}"
            ruta = rutas[int(self.rng.integers(len(rutas)))]
            if self.mundo.insertar_ego(self.ego, ruta, perfil.tipo_sumo):
                break
        else:
            raise RuntimeError(f"No se pudo insertar el vehículo autónomo en la zona {zona}")
        self.veh = VehiculoAutonomo(
            self.mundo, self.ego, perfil, clima_obj, politica=None, guardrail=self.guardrail,
            normalizado=self.normalizado, perfil_origen=self.perfil_origen,
            semilla=int(self.rng.integers(1 << 30)), ruido_sensores=self.ruido)
        self.eval = Evaluador(self.ego, perfil.frenado_max(clima_obj.mu))
        self.t0 = self.mundo.t
        self._quieto = 0
        obs = self.veh.observar()
        self.info_ep = {"zona": zona, "clima": clima, "perfil": perfil.nombre, "ruta": ruta.desc,
                        "largo_ruta_m": round(ruta.largo_m, 1), "ego": self.ego,
                        "hora": round(self.hora, 2), "lluvia": self.lluvia,
                        "hora_pico": es_hora_pico(self.hora), "factor_demanda": round(self.mundo.factor_hora, 2)}
        if self.grabadora is not None:
            self.grabadora.inicio_episodio(self, self.info_ep)
        return obs, dict(self.info_ep)

    # ------------------------------------------------------------------ step
    def step(self, action):
        tr = self.mundo.traci
        veh = self.veh
        d = veh.decidir(None if action is None else int(action), self.instructor)
        mm_antes = veh.mm
        veh.actuar(d)
        self.eventos.paso(self.ego, mm_antes.v)
        self.mundo.avanzar()
        if self.ciclo > 0:  # ciclo día-noche: la luz (y con ella los sensores) cambia con la hora
            self.hora = (self.hora + self.ciclo * self.mundo.dt / 60.0) % 24.0
            if self.eval.met.pasos % 8 == 0:
                nuevo = C.clima_dinamico(self.hora, self.lluvia)
                veh.clima = veh.percepcion.clima = nuevo
            if self.demanda_por_hora and self.eval.met.pasos % 120 == 0:
                self.mundo.ajustar_demanda(factor_demanda(self.hora), recalentar=False, hora=self.hora)
        colisiones = []
        for c in tr.simulation.getCollisions():
            if c.collider == self.ego:
                colisiones.append(c.victim)
            elif c.victim == self.ego:
                colisiones.append(c.collider)
        llego = self.ego in tr.simulation.getArrivedIDList()
        en_red = self.ego in tr.vehicle.getIDList()
        mm_despues = None
        obs = np.zeros(N_OBS, np.float32)
        if en_red:
            obs = veh.observar()
            mm_despues = veh.mm
            # atropello de peatones de SUMO: verificación geométrica, solo si el peatón está
            # donde circulan carros (cebra o calzada sin andén). En las esquinas, la curva de
            # giro de la red pasa a menos de 1.5 m del andén y un peatón quieto en el andén
            # contaba como atropellado aunque el carro no lo tocara (D-34)
            if not colisiones:
                for o in mm_despues.verdad:
                    if o.clase == "peaton" and o.en_trayectoria and not o.id.startswith("obs_") and o.s < 0.3 \
                            and self._peaton_en_calzada(o.id):
                        colisiones.append(o.id)
                        break
        rec, terminado = self.eval.paso(self.mundo, mm_antes, mm_despues, d, colisiones, llego)
        self._quieto = self._quieto + 1 if (mm_despues is not None and mm_despues.v < 0.1) else 0
        atascado = self._quieto * self.mundo.dt > self.max_quieto_s  # bloqueado (trancón o PARE sin hueco)
        truncado = (not terminado) and ((self.mundo.t - self.t0) >= self.t_max_ep or not en_red or atascado)
        if self.grabadora is not None:
            self.grabadora.paso(self, d, rec)
        if terminado or truncado:
            self.eval.met.eventos.extend(self.eventos.registro)
            if en_red:
                self.mundo.quitar(self.ego)
            self.eventos.reiniciar()
            if self.grabadora is not None:
                self.grabadora.fin_episodio(self)
        info = {"decision": d, "accion_ejecutada": d.accion_ejecutada}
        if terminado or truncado:
            info["metricas"] = {**self.info_ep, **self.eval.met.resumen(),
                                "adelantamientos": veh.navegacion.adelantamientos}
            self.ego = None
        return obs, float(rec), bool(terminado), bool(truncado), info

    def _peaton_en_calzada(self, pid: str) -> bool:
        """¿El peatón está en una cebra o en una calzada sin andén (no en un andén o esquina)?"""
        try:
            tramo = self.mundo.traci.person.getRoadID(pid)
        except Exception:
            return True
        if not tramo:
            return True
        if tramo.startswith(":"):  # dentro del cruce: ":<nodo>_c<k>" es cebra, ":<nodo>_w<k>" es esquina
            return tramo.rsplit("_", 1)[-1].startswith("c")
        cache = self.__dict__.setdefault("_tramo_con_anden", {})
        if tramo not in cache:
            tr = self.mundo.traci
            carriles = [f"{tramo}_{k}" for k in range(tr.edge.getLaneNumber(tramo))]
            cache[tramo] = any(not self.mundo.permite_autos(c) and "pedestrian" in tr.lane.getAllowed(c)
                               for c in carriles)
        return not cache[tramo]

    def close(self):
        self.mundo.cerrar()
