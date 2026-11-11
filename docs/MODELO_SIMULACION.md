# El modelo de simulación

El proyecto es, ante todo, un **modelo de simulación de eventos en tiempo discreto
con paso fijo**: todo (la ciudad, el tráfico, los peatones, los sensores, la nube) es
software. Este documento lo describe con el vocabulario de modelado y simulación.

## 1. Sistema, frontera y propósito

* **Sistema:** el tránsito en la zona del Gran Malecón del Río de Barranquilla y uno o
  varios vehículos autónomos que circulan por ella.
* **Frontera:** recuadro geográfico 10.998°–11.030° N, 74.776°–74.812° O
  (≈ 3.9 km × 3.5 km). Contiene la Vía 40, la Avenida del Río, la Av. Calle 72, las
  Calles 70–86 y las Carreras 53–75, más el río Magdalena.
* **Propósito:** estimar qué tan seguro, legal y cómodo conduce un vehículo cuya
  política de velocidad se aprende, y si ese conocimiento se puede **transferir** a
  otros vehículos (instructor → aprendiz, automóvil → bus, zona → zona).

## 2. Entidades y atributos

| Entidad | Atributos | Origen |
|---|---|---|
| Red vial | 2 942 tramos, 1 291 nodos, carriles, velocidad máxima, aceras, cebras, 50 semáforos, 11 PARE | OpenStreetMap, convertida con `netconvert` |
| Vehículo de fondo | tipo (auto 52 %, taxi 18 %, moto 18 %, bus 7 %, camión 5 %), ruta, aceleración, frenado, imperfección del conductor σ | `randomTrips.py`, modelo de seguimiento de Krauss |
| Peatón de SUMO | ruta a pie por andenes y cebras | `randomTrips.py --pedestrians` |
| Vehículo autónomo | perfil (automóvil, taxi, bus, camión), ruta, velocidad, 6 agentes, política | este proyecto |
| Imprevisto | clase (peatón imprudente, perro, iguana, conos, frenada del líder), posición, velocidad de cruce, carriles a cruzar, prudencia | `entorno/eventos.py` |
| Clima | fricción μ, alcance de sensores, ruido, probabilidad de omisión | `config.CLIMAS` |
| Base de conocimiento | versión del modelo global, historial de aportes | `aprendizaje/fedavg.py` |

## 3. Reloj y avance del tiempo

* Paso fijo **Δt = 0.25 s** (`--step-length 0.25`). En cada paso: percibir → decidir →
  actuar → generar imprevistos → avanzar SUMO → evaluar.
* **Calentamiento:** 240 s de simulación antes del primer episodio, para que la red
  tenga tráfico estable y no vacía (periodo transitorio descartado).
* Los episodios del vehículo autónomo se encadenan sobre el **mismo tráfico**: no se
  reinicia SUMO en cada episodio (ahorra tiempo y evita repetir el transitorio).
* Un episodio termina por **choque**, **llegada**, **tiempo máximo (150 s)** o
  **bloqueo** (45 s detenido, p. ej. un trancón).

## 4. Variables aleatorias y distribuciones

| Variable | Distribución | Parámetros |
|---|---|---|
| Llegadas de vehículos de fondo | periódica con origen/destino aleatorio (randomTrips) | 1 vehículo cada 1.1 s × escala 0.75 ≈ 2 450 veh/h; 8× más probable entrar por el borde |
| Llegadas de peatones de fondo | periódica, origen/destino aleatorio | 1 cada 2.5 s |
| Imprevistos | **proceso de Poisson en el espacio** recorrido por el ego | tasa base por km: peatón 1.6, animal 0.8, obra 0.6, frenada del líder 0.8; multiplicada por el perfil de la zona |
| Distancia de aparición | uniforme | peatón/animal 25–85 m; conos 70–92 m |
| Velocidad de cruce | uniforme | peatón 1.0–1.7 m/s, perro 1.6–3.5 m/s, iguana 0.35–0.8 m/s |
| Espera en el andén | uniforme | 0.3–2.5 s |
| Peatón imprudente | Bernoulli | p = 0.5 |
| Animal: perro / iguana | Bernoulli | 65 % perro |
| Perro: pausa o devolverse | Bernoulli por paso | 1 % por paso (60 % pausa 0.5–2.5 s, 40 % se devuelve) |
| Frenada del líder | velocidad final uniforme 0–35 % de la actual, desaceleración 5–7 m/s² | solo si hay líder a < 45 m y va a > 4 m/s |
| Ruido de distancia | normal | σ = (0.15 + 0.02·d) × factor de clima |
| Ruido de velocidad relativa | normal | σ = 0.25 × factor de clima |
| Detección | Bernoulli | p = p_clase × p_tamaño × (1 − p_omisión) × (1 − 0.45 (d/alcance)³) |
| Confusión peatón ↔ animal | Bernoulli por objeto | 5 % con lluvia o de noche |
| Clima del episodio | categórica | despejado 60 %, lluvia 25 %, noche 15 % |
| Zona del episodio | uniforme | 3 zonas |

**Perfiles de imprevistos por zona** (lo que hace los datos *no-IID* para el aprendizaje
federado):

| Zona | Vías ancla (nombres reales de OSM) | Peatón | Animal | Obra | Frenada líder |
|---|---|---|---|---|---|
| Gran Malecón | Vía 40, Avenida del Río, Rotonda Malecón 72 | ×1.4 | ×1.6 | ×0.6 | ×0.8 |
| Corredor Calle 72 | Av. Calle 72, Calles 70/74/75/76, Carreras 58/64/65 | ×1.0 | ×0.6 | ×1.0 | ×1.5 |
| Calles 79–85 | Calles 79/80/81/82/84/85, Carreras 53/55/56/59B | ×1.0 | ×0.8 | ×1.6 | ×1.0 |

## 5. Supuestos y simplificaciones (declarados)

1. **Sin visión por computador.** La percepción degrada la verdad del simulador con un
   modelo de sensor explícito (alcance, ruido, omisión, confusión de clase). Es la
   práctica estándar para estudiar decisión y no percepción.
2. **Imprevistos como "vehículos fantasma".** SUMO no deja que un peatón cruce por la
   mitad de la cuadra ni modela animales u obras; se insertan como vehículos detenidos
   (`obs_*`) que el resto del tráfico respeta y con los que SUMO detecta choques. El
   cruce lateral avanza carril por carril.
3. **Imprudente pero no suicida.** El peatón o animal imprudente puede lanzarse aunque
   obligue al vehículo a frenar fuerte, pero no cuando ya es físicamente imposible que
   frene (ver [DECISIONES.md](DECISIONES.md), D-11). Sin este supuesto aparecían choques
   inevitables que solo agregaban ruido.
4. **Velocidades máximas:** las etiquetas `maxspeed` de OSM (p. ej. Vía 40 a 60 km/h,
   Av. Calle 72 a 30–40 km/h). Donde OSM no trae etiqueta, 50 km/h (límite urbano de la
   Ley 2251 de 2022).
5. **Semáforos con planes fijos** inferidos por `netconvert` (OSM no trae los tiempos
   reales de la Secretaría de Movilidad).
6. **PARE:** solo los 11 que están en OSM (`highway=stop`); no se inventaron otros.
7. **Alturas de edificios** (solo para el visor): pisos de OSM cuando existen (221 de
   11 869) y, si no, altura sintética según el área de la huella. No afectan la
   simulación.
8. **Física longitudinal simple:** aceleración y frenado máximos por tipo de vehículo,
   frenado escalado por la fricción μ. Sin dinámica lateral ni derrapes.

## 6. Verificación (¿el modelo hace lo que dice el código?)

* **Pruebas unitarias** (`python -m unittest discover -s tests -v`, 8 pruebas): el
  gradiente de la red coincide con diferencias finitas; el DQN resuelve un problema
  trivial; FedAvg pondera por experiencia; la normalización usa la capacidad propia del
  bus y la copia tal cual queda recortada por su física; la lluvia reduce el frenado;
  la proyección sobre el camino da distancias y laterales correctos.
* Prueba de humo con el agente de reglas: 4 episodios sin choques, con peatones,
  perros, conos y frenadas generados y registrados (`salidas/`).
* Prueba aislada de SUMO: un vehículo con `speedMode` sin distancia segura choca contra
  un obstáculo insertado y SUMO lo reporta (`ego → obs1`); con el control normal frena.
* Las señales se verifican con `getNextTLS` y los enlaces con estado `s` (PARE) de
  `getNextLinks`; el evaluador cuenta PARE respetados y violados por separado.
* **Flower sobre gRPC:** una ronda real con servidor y dos vehículos en procesos
  separados (taxi en el Malecón, bus en las Calles 79–85), cada uno con su propio SUMO;
  el servidor recibió los dos aportes, los combinó con FedAvg y guardó el modelo global
  (`salidas/log_flower_*.txt`, `modelos/flower_global.npz`). Docker Compose no se pudo
  probar porque el equipo no tiene Docker instalado.
* Semillas fijas en SUMO, en la generación de demanda, en los imprevistos y en las
  redes: cada experimento es reproducible.

## 7. Validación (¿el modelo representa razonablemente la realidad?)

* **Geometría:** la red se construye de OpenStreetMap; los nombres de las vías que
  recorre cada ruta del ego son los reales (p. ej. "Avenida del Río → Rotonda Malecón 72").
* **Física:** distancias de detención consistentes con d = v·t_r + v²/(2μg)
  (seco μ = 0.8, mojado μ = 0.45).
* **Comportamiento agregado:** velocidades medias de 25–35 km/h en el corredor y algo
  más en la Vía 40, del orden de las velocidades urbanas de la ciudad.
* **Límite:** no se calibró contra aforos reales de tránsito de Barranquilla; queda
  como trabajo futuro (datos de la Secretaría de Movilidad o de la app Waze for Cities).

## 8. Diseño experimental

* **Réplicas:** cada comparación usa la **misma secuencia de escenarios** (zona y clima
  por episodio, semilla fija) para todas las variantes — *números aleatorios comunes*,
  que reduce la varianza de las diferencias.
* **Medidas de desempeño:** tasa de choques, casi-choques, PARE y rojos violados,
  frenadas bruscas, velocidad media, TTC mínimo, recompensa e intervenciones.
* **Intervalos de confianza al 95 %** con t de Student (`graficas.py`).
* Los experimentos y sus resultados están en [EXPERIMENTOS.md](EXPERIMENTOS.md).
