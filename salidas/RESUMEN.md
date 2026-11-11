# Resumen numérico de los experimentos

Media ± semiancho del intervalo de confianza al 95 % (t de Student). `n` = episodios. Generado por `python -m bq_sim graficas`.

## E4 · Normalización automóvil → bus

| variante | n | choques | casi-choques | frenadas bruscas | PARE violados | rojos violados | vel. media km/h | recompensa |
|---|---|---|---|---|---|---|---|---|
| automovil_referencia | 20 | 0.10 ± 0.14 | 0.10 ± 0.14 | 4.75 ± 2.90 | 0.00 ± 0.00 | 0.00 ± 0.00 | 22.55 ± 5.12 | 19.81 ± 18.42 |
| bus_normalizado | 20 | 0.15 ± 0.17 | 0.15 ± 0.17 | 4.40 ± 1.51 | 0.00 ± 0.00 | 0.00 ± 0.00 | 26.92 ± 3.16 | 18.47 ± 23.64 |
| bus_copia_tal_cual | 20 | 0.00 ± 0.00 | 0.05 ± 0.10 | 0.10 ± 0.21 | 0.00 ± 0.00 | 0.00 ± 0.00 | 1.79 ± 1.91 | -3.70 ± 2.52 |

## E6 · Reglas vs DQN vs híbrido por clima

| variante | n | choques | casi-choques | frenadas bruscas | PARE violados | rojos violados | vel. media km/h | recompensa |
|---|---|---|---|---|---|---|---|---|
| reactivo_reglas|despejado | 10 | 0.10 ± 0.23 | 0.50 ± 0.91 | 2.10 ± 1.83 | 0.00 ± 0.00 | 0.00 ± 0.00 | 27.12 ± 5.36 | 25.80 ± 33.18 |
| dqn_sin_guardrail|despejado | 10 | 0.20 ± 0.30 | 0.80 ± 0.88 | 3.60 ± 2.29 | 0.00 ± 0.00 | 0.00 ± 0.00 | 29.22 ± 5.09 | 8.87 ± 40.83 |
| dqn_con_guardrail|despejado | 10 | 0.20 ± 0.30 | 0.80 ± 0.88 | 3.20 ± 2.49 | 0.00 ± 0.00 | 0.00 ± 0.00 | 29.31 ± 5.12 | 5.07 ± 42.98 |
| reactivo_reglas|lluvia | 10 | 0.10 ± 0.23 | 0.70 ± 0.89 | 4.60 ± 1.72 | 0.00 ± 0.00 | 0.00 ± 0.00 | 27.14 ± 5.61 | 23.91 ± 27.92 |
| dqn_sin_guardrail|lluvia | 10 | 0.10 ± 0.23 | 0.10 ± 0.23 | 6.80 ± 4.70 | 0.00 ± 0.00 | 0.00 ± 0.00 | 26.12 ± 5.11 | 25.95 ± 33.56 |
| dqn_con_guardrail|lluvia | 10 | 0.20 ± 0.30 | 0.30 ± 0.35 | 6.40 ± 5.19 | 0.00 ± 0.00 | 0.00 ± 0.00 | 28.01 ± 5.68 | 13.60 ± 40.87 |
| reactivo_reglas|noche | 10 | 0.00 ± 0.00 | 0.60 ± 0.90 | 3.50 ± 1.97 | 0.00 ± 0.00 | 0.00 ± 0.00 | 27.82 ± 4.72 | 38.77 ± 10.50 |
| dqn_sin_guardrail|noche | 10 | 0.00 ± 0.00 | 0.80 ± 0.94 | 7.80 ± 4.99 | 0.00 ± 0.00 | 0.00 ± 0.00 | 26.85 ± 4.34 | 33.62 ± 9.73 |
| dqn_con_guardrail|noche | 10 | 0.00 ± 0.00 | 0.60 ± 0.90 | 6.00 ± 2.13 | 0.00 ± 0.00 | 0.00 ± 0.00 | 27.54 ± 3.70 | 36.03 ± 10.82 |

## E5 · Evaluación cruzada de la flota

| variante | n | choques | casi-choques | frenadas bruscas | PARE violados | rojos violados | vel. media km/h | recompensa |
|---|---|---|---|---|---|---|---|---|
| fedavg_global|malecon_via40 | 6 | 0.00 ± 0.00 | 0.17 ± 0.43 | 3.67 ± 2.87 | 0.00 ± 0.00 | 0.00 ± 0.00 | 32.14 ± 7.01 | 40.59 ± 5.84 |
| local_taxi_malecon_via40|malecon_via40 | 6 | 0.00 ± 0.00 | 0.17 ± 0.43 | 4.67 ± 3.36 | 0.00 ± 0.00 | 0.00 ± 0.00 | 38.38 ± 11.26 | 42.16 ± 7.84 |
| local_automovil_corredor_calle72|malecon_via40 | 6 | 0.17 ± 0.43 | 0.00 ± 0.00 | 2.67 ± 4.86 | 0.00 ± 0.00 | 0.00 ± 0.00 | 37.52 ± 9.10 | 27.46 ± 60.59 |
| local_bus_calles79_85|malecon_via40 | 6 | 0.00 ± 0.00 | 0.17 ± 0.43 | 4.00 ± 3.04 | 0.00 ± 0.00 | 0.00 ± 0.00 | 28.59 ± 18.06 | 29.70 ± 22.12 |
| fedavg_global|corredor_calle72 | 6 | 0.00 ± 0.00 | 0.00 ± 0.00 | 3.50 ± 2.95 | 0.00 ± 0.00 | 0.00 ± 0.00 | 24.48 ± 10.75 | 32.42 ± 12.11 |
| local_taxi_malecon_via40|corredor_calle72 | 6 | 0.00 ± 0.00 | 0.00 ± 0.00 | 3.33 ± 2.45 | 0.00 ± 0.00 | 0.00 ± 0.00 | 26.62 ± 6.24 | 35.22 ± 5.67 |
| local_automovil_corredor_calle72|corredor_calle72 | 6 | 0.17 ± 0.43 | 0.33 ± 0.54 | 2.67 ± 2.27 | 0.00 ± 0.00 | 0.00 ± 0.00 | 20.70 ± 13.17 | 6.32 ± 62.34 |
| local_bus_calles79_85|corredor_calle72 | 6 | 0.17 ± 0.43 | 0.17 ± 0.43 | 5.83 ± 5.37 | 0.00 ± 0.00 | 0.00 ± 0.00 | 28.99 ± 6.78 | 10.10 ± 58.06 |
| fedavg_global|calles79_85 | 6 | 0.00 ± 0.00 | 0.00 ± 0.00 | 2.67 ± 2.27 | 0.00 ± 0.00 | 0.00 ± 0.00 | 23.54 ± 12.84 | 33.87 ± 20.92 |
| local_taxi_malecon_via40|calles79_85 | 6 | 0.33 ± 0.54 | 0.33 ± 0.54 | 2.33 ± 4.48 | 0.00 ± 0.00 | 0.00 ± 0.00 | 23.78 ± 12.86 | -14.84 ± 70.28 |
| local_automovil_corredor_calle72|calles79_85 | 6 | 0.17 ± 0.43 | 0.17 ± 0.43 | 10.50 ± 9.63 | 0.00 ± 0.00 | 0.00 ± 0.00 | 28.69 ± 5.98 | 25.28 ± 56.93 |
| local_bus_calles79_85|calles79_85 | 6 | 0.00 ± 0.00 | 0.17 ± 0.43 | 5.00 ± 2.65 | 0.00 ± 0.00 | 0.00 ± 0.00 | 26.61 ± 9.48 | 35.84 ± 19.53 |

## E2/E3 · Aprendices (últimos 20 episodios de cada corrida)

| grupo | n | choques | casi-choques | frenadas bruscas | PARE violados | rojos violados | vel. media km/h | recompensa | intervenciones instructor |
|---|---|---|---|---|---|---|---|---|---|
| desde_cero | 40 | 0.03 ± 0.05 | 0.07 ± 0.08 | 18.38 ± 4.57 | 0.00 ± 0.00 | 0.00 ± 0.00 | 20.82 ± 3.31 | 21.23 ± 8.00 | 0.00 ± 0.00 |
| con_instructor | 40 | 0.05 ± 0.07 | 0.07 ± 0.08 | 8.03 ± 1.24 | 0.00 ± 0.00 | 0.00 ± 0.00 | 32.69 ± 3.73 | 30.39 ± 10.22 | 1.88 ± 1.71 |
| copia_mas_instructor | 40 | 0.07 ± 0.08 | 0.17 ± 0.14 | 8.15 ± 1.29 | 0.00 ± 0.00 | 0.00 ± 0.00 | 32.01 ± 3.86 | 26.88 ± 11.06 | 0.35 ± 0.33 |

## E1 · Instructor (por bloques de 50 episodios)

| grupo | n | choques | casi-choques | frenadas bruscas | PARE violados | rojos violados | vel. media km/h | recompensa | intervenciones instructor |
|---|---|---|---|---|---|---|---|---|---|
| entrenamiento, episodios 1–50 | 50 | 0.02 ± 0.04 | 0.06 ± 0.07 | 66.20 ± 8.96 | 0.00 ± 0.00 | 0.00 ± 0.00 | 6.75 ± 1.75 | -11.26 ± 5.15 | 0.00 ± 0.00 |
| entrenamiento, episodios 51–100 | 50 | 0.04 ± 0.05 | 0.06 ± 0.09 | 41.04 ± 5.30 | 0.00 ± 0.00 | 0.00 ± 0.00 | 24.51 ± 2.78 | 22.08 ± 8.25 | 0.00 ± 0.00 |
| entrenamiento, episodios 101–150 | 50 | 0.00 ± 0.00 | 0.12 ± 0.09 | 7.86 ± 2.27 | 0.00 ± 0.00 | 0.00 ± 0.00 | 28.72 ± 3.11 | 33.14 ± 3.77 | 0.00 ± 0.00 |
| entrenamiento, episodios 151–200 | 50 | 0.00 ± 0.00 | 0.14 ± 0.11 | 5.36 ± 0.92 | 0.00 ± 0.00 | 0.00 ± 0.00 | 27.64 ± 2.64 | 32.87 ± 3.96 | 0.00 ± 0.00 |
| entrenamiento, episodios 201–250 | 50 | 0.02 ± 0.04 | 0.02 ± 0.04 | 5.32 ± 1.23 | 0.00 ± 0.00 | 0.00 ± 0.00 | 31.28 ± 2.19 | 37.18 ± 5.83 | 0.00 ± 0.00 |
| entrenamiento, episodios 251–300 | 50 | 0.08 ± 0.08 | 0.16 ± 0.10 | 4.74 ± 0.95 | 0.00 ± 0.00 | 0.00 ± 0.00 | 27.67 ± 2.72 | 25.91 ± 10.98 | 0.00 ± 0.00 |
| entrenamiento, episodios 301–350 | 50 | 0.02 ± 0.04 | 0.08 ± 0.08 | 4.94 ± 0.74 | 0.00 ± 0.00 | 0.00 ± 0.00 | 30.77 ± 2.81 | 34.86 ± 6.30 | 0.00 ± 0.00 |
| entrenamiento, episodios 351–400 | 50 | 0.00 ± 0.00 | 0.10 ± 0.10 | 4.58 ± 0.68 | 0.00 ± 0.00 | 0.00 ± 0.00 | 28.13 ± 2.76 | 37.10 ± 4.44 | 0.00 ± 0.00 |
| evaluación sin exploración tras 50 episodios | 5 | 0.00 ± 0.00 | 0.20 ± 0.56 | 2.60 ± 3.36 | 0.00 ± 0.00 | 0.00 ± 0.00 | 28.90 ± 20.58 | 34.64 ± 27.29 | 0.00 ± 0.00 |
| evaluación sin exploración tras 100 episodios | 5 | 0.00 ± 0.00 | 0.00 ± 0.00 | 8.40 ± 13.00 | 0.00 ± 0.00 | 0.00 ± 0.00 | 34.51 ± 9.62 | 32.66 ± 12.86 | 0.00 ± 0.00 |
| evaluación sin exploración tras 150 episodios | 5 | 0.00 ± 0.00 | 0.20 ± 0.56 | 2.20 ± 2.70 | 0.00 ± 0.00 | 0.00 ± 0.00 | 35.38 ± 9.55 | 42.17 ± 16.04 | 0.00 ± 0.00 |
| evaluación sin exploración tras 200 episodios | 5 | 0.00 ± 0.00 | 0.20 ± 0.56 | 2.60 ± 3.36 | 0.00 ± 0.00 | 0.00 ± 0.00 | 33.52 ± 11.60 | 40.38 ± 18.65 | 0.00 ± 0.00 |
| evaluación sin exploración tras 250 episodios | 5 | 0.00 ± 0.00 | 0.00 ± 0.00 | 1.40 ± 1.42 | 0.00 ± 0.00 | 0.00 ± 0.00 | 40.49 ± 28.70 | 34.87 ± 17.24 | 0.00 ± 0.00 |
| evaluación sin exploración tras 300 episodios | 5 | 0.00 ± 0.00 | 0.40 ± 1.11 | 3.00 ± 2.64 | 0.00 ± 0.00 | 0.00 ± 0.00 | 34.58 ± 17.85 | 37.73 ± 12.62 | 0.00 ± 0.00 |
| evaluación sin exploración tras 350 episodios | 5 | 0.00 ± 0.00 | 0.40 ± 1.11 | 0.60 ± 1.11 | 0.00 ± 0.00 | 0.00 ± 0.00 | 19.44 ± 14.65 | 17.83 ± 22.02 | 0.00 ± 0.00 |
| evaluación sin exploración tras 400 episodios | 5 | 0.00 ± 0.00 | 0.00 ± 0.00 | 3.80 ± 4.07 | 0.00 ± 0.00 | 0.00 ± 0.00 | 39.52 ± 11.59 | 35.75 ± 14.85 | 0.00 ± 0.00 |
