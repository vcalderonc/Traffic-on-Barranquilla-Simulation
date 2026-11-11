"""Gráficas y tablas de resultados a partir de los CSV de ``salidas/``.

Convenciones visuales: superficie clara, una sola escala Y por gráfica, colores
categóricos en orden fijo (azul, naranja, aqua, amarillo) asignados a cada
variante y nunca reciclados, líneas de 2 px, rejilla tenue y leyenda siempre que
haya dos o más series. Los intervalos son de confianza al 95 % (t de Student).
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import config as C  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SUPERFICIE, TINTA, TINTA2, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23,
       11: 2.20, 12: 2.18, 14: 2.14, 16: 2.12, 19: 2.09, 24: 2.06, 29: 2.05}


def t95(n: int) -> float:
    gl = n - 1
    if gl <= 0:
        return float("nan")
    claves = [k for k in T95 if k <= gl]
    return T95[max(claves)] if gl < 30 else 1.96


def media_ic(s: pd.Series) -> tuple[float, float]:
    s = s.dropna().astype(float)
    n = len(s)
    if n < 2:
        return (float(s.mean()) if n else float("nan")), float("nan")
    return float(s.mean()), t95(n) * float(s.std(ddof=1)) / math.sqrt(n)


def _estilo(ax, titulo: str, xlabel: str = "", ylabel: str = ""):
    ax.set_facecolor(SUPERFICIE)
    ax.set_title(titulo, loc="left", fontsize=11, color=TINTA, pad=8)
    ax.set_xlabel(xlabel, color=TINTA2, fontsize=9)
    ax.set_ylabel(ylabel, color=TINTA2, fontsize=9)
    ax.tick_params(colors=TINTA2, labelsize=8, length=0)
    ax.grid(True, color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)


def _figura(filas: int, cols: int, ancho=11, alto=7):
    fig, axs = plt.subplots(filas, cols, figsize=(ancho, alto), squeeze=False)
    fig.patch.set_facecolor(SUPERFICIE)
    return fig, axs


def _guardar(fig, nombre: str) -> Path:
    ruta = C.DIR_SALIDAS / "figuras" / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(ruta, dpi=130, facecolor=SUPERFICIE)
    plt.close(fig)
    return ruta


def _leer(nombre: str) -> pd.DataFrame | None:
    ruta = C.DIR_SALIDAS / nombre
    if not ruta.exists():
        return None
    d = pd.read_csv(ruta)
    d["llego"] = d["llego"].astype(str).str.lower().eq("true").astype(int)
    d["choque"] = (d["choques"] > 0).astype(int)
    return d


# ------------------------------------------------------------------ E1
def fig_e1(ventana: int = 25) -> list[str]:
    d = _leer("e1_instructor.csv")
    if d is None:
        return []
    fig, axs = _figura(2, 2)
    paneles = [("recompensa", "Recompensa por episodio", "recompensa"),
               ("choque", "Tasa de choques (media móvil)", "fracción de episodios"),
               ("casi_choques", "Casi-choques (TTC < 1 s) por episodio", "eventos"),
               ("frenadas_bruscas", "Frenadas bruscas por episodio", "eventos")]
    for ax, (col, titulo, ylab) in zip(axs.flat, paneles):
        _estilo(ax, titulo, "episodio", ylab)
        ax.plot(d["episodio"], d[col], color=SERIES[0], alpha=0.18, linewidth=1)
        ax.plot(d["episodio"], d[col].rolling(ventana, min_periods=5).mean(), color=SERIES[0], linewidth=2)
    fig.suptitle("E1 · El vehículo instructor aprende desde cero (Double DQN, sin guardrail)",
                 x=0.01, ha="left", fontsize=12, color=TINTA)
    return [str(_guardar(fig, "e1_curva_instructor.png"))]


# ---------------------------------------------------------------- E2/E3
NOMBRES_VAR = {"desde_cero": "desde cero", "con_instructor": "con instructor (doble comando)",
               "copia_mas_instructor": "copia normalizada + instructor"}


def fig_e23(ventana: int = 10) -> list[str]:
    d = _leer("e23_aprendices.csv")
    if d is None:
        return []
    d["variante"] = d["fase"].str.split("/").str[0]
    fig, axs = _figura(1, 3, ancho=14, alto=4.4)
    for ax, (col, titulo) in zip(axs.flat, [("recompensa", "Recompensa"), ("choque", "Tasa de choques"),
                                            ("intervenciones_instructor", "Intervenciones del instructor")]):
        _estilo(ax, titulo, "episodio del aprendiz", "")
        for i, (var, nombre) in enumerate(NOMBRES_VAR.items()):
            sub = d[d["variante"] == var]
            if sub.empty:
                continue
            curva = sub.groupby("episodio")[col].mean().rolling(ventana, min_periods=3).mean()
            ax.plot(curva.index, curva.values, color=SERIES[i], linewidth=2, label=nombre)
    axs[0, 0].legend(frameon=False, fontsize=8, labelcolor=TINTA2)
    fig.suptitle("E2/E3 · Taxi aprendiz: ¿enseña el vehículo instructor? (media de semillas, ventana móvil)",
                 x=0.01, ha="left", fontsize=12, color=TINTA)
    return [str(_guardar(fig, "e23_aprendices.png"))]


def _barras_ic(ax, etiquetas, medias, ics, colores):
    xs = range(len(etiquetas))
    ax.bar(xs, medias, color=colores, width=0.6, edgecolor=SUPERFICIE, linewidth=2)
    ax.errorbar(xs, medias, yerr=ics, fmt="none", ecolor=TINTA2, elinewidth=1.2, capsize=4)
    ax.set_xticks(list(xs), etiquetas, fontsize=8)
    for x, m in zip(xs, medias):
        ax.annotate(f"{m:.2f}", (x, m), textcoords="offset points", xytext=(0, 4), ha="center",
                    fontsize=8, color=TINTA)


# ------------------------------------------------------------------- E4
def fig_e4() -> list[str]:
    d = _leer("e4_bus_normalizacion.csv")
    if d is None:
        return []
    orden = ["automovil_referencia", "bus_normalizado", "bus_copia_tal_cual"]
    nombres = ["automóvil\n(referencia)", "bus\nnormalizado", "bus\ncopia tal cual"]
    fig, axs = _figura(1, 3, ancho=13, alto=4.2)
    for ax, (col, titulo) in zip(axs.flat, [("choque", "Tasa de choques"), ("casi_choques", "Casi-choques / episodio"),
                                            ("frenadas_bruscas", "Frenadas bruscas / episodio")]):
        _estilo(ax, titulo)
        mi = [media_ic(d[d["fase"] == f][col]) for f in orden]
        _barras_ic(ax, nombres, [m for m, _ in mi], [i for _, i in mi], SERIES[:3])
    fig.suptitle("E4 · Transferir lo aprendido por un automóvil a un bus (IC 95 %)",
                 x=0.01, ha="left", fontsize=12, color=TINTA)
    return [str(_guardar(fig, "e4_bus_normalizacion.png"))]


# ------------------------------------------------------------------- E5
def fig_e5(ventana: int = 8) -> list[str]:
    salidas = []
    curvas = {m: _leer(f"e5_federado_{m}.csv") for m in ("local", "fedavg")}
    if all(v is not None for v in curvas.values()):
        fig, axs = _figura(1, 2, ancho=12, alto=4.2)
        for ax, (col, titulo) in zip(axs.flat, [("recompensa", "Recompensa media de la flota"),
                                                ("choque", "Tasa de choques de la flota")]):
            _estilo(ax, titulo, "episodio local acumulado", "")
            for i, (modo, nombre) in enumerate([("local", "cada vehículo aprende solo"),
                                                ("fedavg", "FedAvg (comparten por la nube)")]):
                sub = curvas[modo]
                curva = sub.groupby("episodio")[col].mean().rolling(ventana, min_periods=3).mean()
                ax.plot(curva.index, curva.values, color=SERIES[i], linewidth=2, label=nombre)
        axs[0, 0].legend(frameon=False, fontsize=8, labelcolor=TINTA2)
        fig.suptitle("E5 · Flota de 3 vehículos en 3 zonas de Barranquilla (datos no-IID)",
                     x=0.01, ha="left", fontsize=12, color=TINTA)
        salidas.append(str(_guardar(fig, "e5_federado_curvas.png")))
    cz = _leer("e5_evaluacion_cruzada.csv")
    if cz is not None:
        cz["modelo"] = cz["fase"].str.split("|").str[0]
        cz["zona_eval"] = cz["fase"].str.split("|").str[1]
        tabla = cz.pivot_table(index="modelo", columns="zona_eval", values="recompensa", aggfunc="mean")
        fig, axs = _figura(1, 1, ancho=9, alto=3.6)
        ax = axs[0, 0]
        im = ax.imshow(tabla.values, cmap="Blues", aspect="auto")
        ax.set_xticks(range(len(tabla.columns)), tabla.columns, fontsize=8, color=TINTA2)
        ax.set_yticks(range(len(tabla.index)), tabla.index, fontsize=8, color=TINTA2)
        for i in range(tabla.shape[0]):
            for j in range(tabla.shape[1]):
                v = tabla.values[i, j]
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=9,
                        color="white" if v > tabla.values.mean() else TINTA)
        ax.set_title("Recompensa media al evaluar cada modelo en cada zona", loc="left", fontsize=11, color=TINTA)
        fig.colorbar(im, ax=ax, fraction=0.03)
        salidas.append(str(_guardar(fig, "e5_evaluacion_cruzada.png")))
    return salidas


# ------------------------------------------------------------------- E6
def fig_e6() -> list[str]:
    d = _leer("e6_comparacion.csv")
    if d is None:
        return []
    d["variante"] = d["fase"].str.split("|").str[0]
    d["clima"] = d["fase"].str.split("|").str[1]
    variantes = [("reactivo_reglas", "reglas (reactivo)"), ("dqn_sin_guardrail", "DQN sin guardrail"),
                 ("dqn_con_guardrail", "DQN + guardrail (híbrido)")]
    climas = ["despejado", "lluvia", "noche"]
    fig, axs = _figura(1, 4, ancho=16, alto=4.2)
    for ax, (col, titulo) in zip(axs.flat, [("choque", "Tasa de choques"), ("casi_choques", "Casi-choques / ep."),
                                            ("frenadas_bruscas", "Frenadas bruscas / ep."),
                                            ("vel_media_kmh", "Velocidad media (km/h)")]):
        _estilo(ax, titulo)
        ancho = 0.26
        for i, (var, nombre) in enumerate(variantes):
            mi = [media_ic(d[(d["variante"] == var) & (d["clima"] == c)][col]) for c in climas]
            xs = [k + (i - 1) * ancho for k in range(len(climas))]
            ax.bar(xs, [m for m, _ in mi], width=ancho, color=SERIES[i], edgecolor=SUPERFICIE, linewidth=2,
                   label=nombre)
            ax.errorbar(xs, [m for m, _ in mi], yerr=[e for _, e in mi], fmt="none", ecolor=TINTA2,
                        elinewidth=1, capsize=3)
        ax.set_xticks(range(len(climas)), climas, fontsize=8)
    axs[0, 0].legend(frameon=False, fontsize=8, labelcolor=TINTA2)
    fig.suptitle("E6 · Reglas vs. aprendizaje vs. híbrido, por clima (IC 95 %)", x=0.01, ha="left",
                 fontsize=12, color=TINTA)
    return [str(_guardar(fig, "e6_comparacion.png"))]


# ---------------------------------------------------------- tabla resumen
METRICAS_TABLA = [("choque", "choques"), ("casi_choques", "casi-choques"), ("frenadas_bruscas", "frenadas bruscas"),
                  ("pare_violados", "PARE violados"), ("rojos_violados", "rojos violados"),
                  ("vel_media_kmh", "vel. media km/h"), ("recompensa", "recompensa")]


def tabla_resumen() -> str:
    lineas = ["# Resumen numérico de los experimentos", "",
              "Media ± semiancho del intervalo de confianza al 95 % (t de Student). "
              "`n` = episodios. Generado por `python -m bq_sim graficas`.", ""]
    for archivo, titulo, agrupar in [
        ("e4_bus_normalizacion.csv", "E4 · Normalización automóvil → bus", "fase"),
        ("e6_comparacion.csv", "E6 · Reglas vs DQN vs híbrido por clima", "fase"),
        ("e5_evaluacion_cruzada.csv", "E5 · Evaluación cruzada de la flota", "fase"),
    ]:
        d = _leer(archivo)
        if d is None:
            continue
        lineas += [f"## {titulo}", "", "| variante | n | " + " | ".join(n for _, n in METRICAS_TABLA) + " |",
                   "|---|---|" + "---|" * len(METRICAS_TABLA)]
        for g, sub in d.groupby(agrupar, sort=False):
            celdas = []
            for col, _ in METRICAS_TABLA:
                m, ic = media_ic(sub[col])
                celdas.append(f"{m:.2f} ± {ic:.2f}" if not math.isnan(ic) else f"{m:.2f}")
            lineas.append(f"| {g} | {len(sub)} | " + " | ".join(celdas) + " |")
        lineas.append("")
    for archivo, titulo, col_var in [("e23_aprendices.csv", "E2/E3 · Aprendices (últimos 20 episodios de cada corrida)", "fase"),
                                     ("e1_instructor.csv", "E1 · Instructor (por bloques de 50 episodios)", None)]:
        d = _leer(archivo)
        if d is None:
            continue
        if col_var is None:
            d["grupo"] = "episodios " + ((d["episodio"] - 1) // 50 * 50 + 1).astype(str) + "–" + \
                         ((d["episodio"] - 1) // 50 * 50 + 50).astype(str)
        else:
            d["grupo"] = d[col_var].str.split("/").str[0]
            maximo = d.groupby(col_var)["episodio"].transform("max")
            d = d[d["episodio"] > maximo - 20]
        lineas += [f"## {titulo}", "", "| grupo | n | " + " | ".join(n for _, n in METRICAS_TABLA) +
                   " | intervenciones instructor |", "|---|---|" + "---|" * (len(METRICAS_TABLA) + 1)]
        for g, sub in d.groupby("grupo", sort=False):
            celdas = []
            for col, _ in METRICAS_TABLA + [("intervenciones_instructor", "")]:
                m, ic = media_ic(sub[col])
                celdas.append(f"{m:.2f} ± {ic:.2f}" if not math.isnan(ic) else f"{m:.2f}")
            lineas.append(f"| {g} | {len(sub)} | " + " | ".join(celdas) + " |")
        lineas.append("")
    texto = "\n".join(lineas)
    (C.DIR_SALIDAS / "RESUMEN.md").write_text(texto, encoding="utf-8")
    return texto


def todas() -> None:
    hechas = fig_e1() + fig_e23() + fig_e4() + fig_e5() + fig_e6()
    tabla_resumen()
    for h in hechas:
        print("figura:", h)
    print("tabla: salidas/RESUMEN.md")
