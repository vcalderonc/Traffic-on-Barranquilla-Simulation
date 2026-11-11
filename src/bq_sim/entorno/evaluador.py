"""Crítico / evaluador: calcula la recompensa y las métricas con la verdad del simulador.

Usa la información real (sin ruido de sensores), como un juez externo. Implementa
la función de recompensa del documento Stack Tech:
choque -100, casi-choque (TTC < 1 s) -10, PARE -20, frenada brusca -0.1, más
progreso, llegada, rojo, exceso de velocidad e intervenciones.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config as C


@dataclass
class Metricas:
    pasos: int = 0
    distancia_m: float = 0.0
    tiempo_s: float = 0.0
    choques: int = 0
    choque_con: str = ""
    casi_choques: int = 0
    pare_violados: int = 0
    pare_respetados: int = 0
    rojos_violados: int = 0
    frenadas_bruscas: int = 0
    pasos_exceso_vel: int = 0
    intervenciones_seguridad: int = 0
    intervenciones_instructor: int = 0
    llego: bool = False
    recompensa: float = 0.0
    ttc_min: float = 99.0
    eventos: list = field(default_factory=list)

    def resumen(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "eventos"}
        d["vel_media_kmh"] = round(3.6 * self.distancia_m / self.tiempo_s, 2) if self.tiempo_s else 0.0
        d["ttc_min"] = round(min(self.ttc_min, 99.0), 2)
        d["recompensa"] = round(self.recompensa, 3)
        d["distancia_m"] = round(self.distancia_m, 1)
        return d


class Evaluador:
    def __init__(self, ego: str, b_max: float, rec: C.Recompensas | None = None):
        self.ego = ego
        self.b_max = b_max
        self.r = rec or C.Recompensas()
        self.met = Metricas()
        self._casi_contados: set[str] = set()
        self._senal_prev = None
        self._v_min_senal: dict[str, float] = {}
        self._frenando = False

    def paso(self, mundo, mm_antes, mm_despues, decision, colisiones: list, llego: bool) -> tuple[float, bool]:
        r = self.r
        dt = mundo.dt
        rec = 0.0
        m = self.met
        m.pasos += 1
        m.tiempo_s += dt
        v = mm_despues.v if mm_despues is not None else mm_antes.v
        m.distancia_m += v * dt
        v_lim = max(mm_antes.v_lim, 1.0)
        rec += r.progreso * min(v / v_lim, 1.0)
        terminado = False
        # choques (vehículos, fantasmas y peatones de SUMO)
        if colisiones:
            m.choques += 1
            m.choque_con = colisiones[0]
            rec += r.choque
            terminado = True
            m.eventos.append({"t": round(mundo.t, 2), "tipo": "choque", "con": colisiones[0]})
        # casi-choques: TTC real < 1 s con algo en la trayectoria
        if mm_despues is not None:
            for o in mm_despues.verdad:
                if not o.en_trayectoria:
                    continue
                m.ttc_min = min(m.ttc_min, o.ttc)
                if o.ttc < 1.0 and o.id not in self._casi_contados and not terminado:
                    self._casi_contados.add(o.id)
                    m.casi_choques += 1
                    rec += r.casi_choque
                    m.eventos.append({"t": round(mundo.t, 2), "tipo": "casi_choque", "con": o.subtipo,
                                      "ttc": round(o.ttc, 2)})
        # señales: ¿cruzó un PARE sin detenerse o un semáforo en rojo?
        sen_prev = mm_antes.senal
        sen_ahora = mm_despues.senal if mm_despues is not None else None
        if sen_prev is not None:
            clave = sen_prev.id
            if sen_prev.dist < 8.0:
                self._v_min_senal[clave] = min(self._v_min_senal.get(clave, 99.0), mm_antes.v)
            cruzo = (sen_ahora is None or sen_ahora.id != clave) and sen_prev.dist < mm_antes.v * dt + 3.0
            if cruzo:
                if sen_prev.tipo == "pare":
                    if self._v_min_senal.get(clave, 99.0) > 0.5:
                        m.pare_violados += 1
                        rec += r.pare
                        m.eventos.append({"t": round(mundo.t, 2), "tipo": "pare_violado"})
                    else:
                        m.pare_respetados += 1
                elif sen_prev.estado == "rojo":
                    m.rojos_violados += 1
                    rec += r.semaforo_rojo
                    m.eventos.append({"t": round(mundo.t, 2), "tipo": "semaforo_rojo"})
        # confort y normas
        if decision.acel < -0.5 * self.b_max:
            rec += r.frenada_brusca
            if not self._frenando:
                m.frenadas_bruscas += 1
            self._frenando = True
        else:
            self._frenando = False
        if v > mm_antes.v_lim * 1.05 + 0.5:
            m.pasos_exceso_vel += 1
            rec += r.exceso_velocidad
        if decision.intervencion == "seguridad":
            m.intervenciones_seguridad += 1
            rec += r.intervencion
        elif decision.intervencion == "instructor":
            m.intervenciones_instructor += 1
            rec += r.intervencion
        # lento sin motivo: evita el óptimo local "casi no moverse para no chocar nunca"
        if v < 0.4 * v_lim and not colisiones:
            hay_motivo = (
                any(o.en_trayectoria and o.s < 35 for o in mm_antes.detectados)
                or any(o.cerca_via and o.s < 25 for o in mm_antes.detectados)
                or (sen_prev is not None and sen_prev.estado in ("rojo", "amarillo", "pare") and sen_prev.dist < 50)
                or any(vmax < 0.6 * v_lim and s < 40 for s, vmax in mm_antes.limites_proximos))
            if not hay_motivo:
                rec += r.lento_sin_motivo
        if llego:
            m.llego = True
            rec += r.llegada
            terminado = True
        m.recompensa += rec
        return rec, terminado
