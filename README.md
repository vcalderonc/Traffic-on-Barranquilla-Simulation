# Traffic on Barranquilla Simulation

**Simulación multiagente de conducción autónoma en el norte de Barranquilla (Gran
Malecón, Vía 40, Buenavista), con un vehículo instructor que enseña a conducir a los
demás.**

Modelo de simulación hecho en Python sobre SUMO con la red vial real de
OpenStreetMap: Vía 40, Avenida del Río, Av. Calle 72, Calles 76–99, Carrera 53, Carrera
51B y Av. Carrera 46, con sus semáforos y señales de PARE. Cada vehículo autónomo lo conducen seis agentes
(Percepción, Señales, Obstáculos, Navegación, Velocidad y Seguridad) coordinados por
prioridades. El agente de Velocidad aprende con Double DQN; un vehículo ya entrenado
(el **instructor**) enseña a taxis, autos y buses aprendices, y la flota comparte lo
aprendido con aprendizaje federado (FedAvg / Flower). Incluye un **visor 3D** en el
navegador con el Malecón, La Luna del Río, las estatuas de Shakira y Sofía Vergara, el
Caimán del Río, los Buenavista con pantallas tipo Times Square, la Ventana al Mundo, la
Aleta del Tiburón y la Puerta de Oro iluminadas, ciclo día-noche con el atardecer rosado
de la ciudad y una **simulación en vivo** donde el usuario elige la vía o arma su propio
recorrido (partida, monumentos sobre glorietas y llegada), la hora (con horas pico), la
lluvia y quién conduce. El instructor es un Porsche 911 GT color cherry blossom.

| | |
|---|---|
| Escenario | Red real OSM → SUMO: 6 754 tramos, 146 semáforos, 22 PARE, aceras, cebras y 23 543 edificios |
| Tráfico | compactos, sedanes, camionetas, pick-ups, taxis, motos, busetas y camiones + peatones y paseantes; flujos en los grandes corredores; **horas pico** (≈ 1 100 a 1 900 vehículos y ~1 100 personas a la vez) |
| Imprevistos | peatones que cruzan a mitad de cuadra, perros, iguanas, carriles con conos, frenadas súbitas y **vendedores ambulantes en los semáforos** |
| Clima y hora | hora del día con ciclo día-noche (la luz cambia el alcance de los sensores) y lluvia (menos fricción y alcance) |
| Vías para manejar | Malecón (Av. del Río), Vía 40, Av. Calle 72, Calles 76, 79, 84 y 98 (Buenavista), Carreras 53 y 51B, Av. Carrera 46, o un recorrido a la medida desde cualquier punto pasando por la Ventana al Mundo, la Aleta del Tiburón, la Puerta de Oro, el Caimán del Río o La Luna del Río |
| Conducción | seguir el carril, semáforos, PARE, esquivar obstáculos y **adelantar por la izquierda** con verificación del radar trasero |
| Agentes por vehículo | 6 + Coordinador (caso "Conducción urbana inteligente" de la tabla del profesor) |
| Aprendizaje | Double DQN en NumPy, interfaz Gymnasium, recompensas del Stack Tech |
| Enseñanza | instructor con *doble comando* + demostraciones + transferencia normalizada |
| Federado | FedAvg con validación, 3 zonas no-IID; versión distribuida con Flower + Docker Compose |

![Zona simulada](salidas/figuras/mapa_zonas.png)

## Resultados principales

Detalle, figuras e intervalos de confianza en [docs/EXPERIMENTOS.md](docs/EXPERIMENTOS.md).

| Experimento | Resultado |
|---|---|
| E1 · El instructor aprende | De 7 km/h y 66 frenadas bruscas por episodio a ~30 km/h y 3–5; **0 choques en 40 evaluaciones** sin exploración; ningún rojo ni PARE cruzado |
| E2/E3 · El instructor enseña a un taxi | Con la copia normalizada + instructor, el taxi llega al nivel objetivo en **5 episodios** (18–34 aprendiendo solo); con solo doble comando termina más suave y rápido que solo |
| E4 · Automóvil → bus | Normalizado: el bus conduce igual que el automóvil. Copiado tal cual: **el bus no arranca** (1.8 km/h) |
| E5 · Flota federada en 3 zonas | El modelo FedAvg **no choca en ninguna zona** (0/18) y supera a los modelos locales, que fallan fuera de su zona; la nube rechazó un aporte dañino del bus |
| E6 · Reglas vs. DQN vs. híbrido | Seguridad estadísticamente equivalente: el aprendizaje alcanza a las reglas pero no las supera; su valor está en la transferencia |
| E7 · Red ampliada y más tráfico | El instructor se transfiere a vías y horas que no vio: 1 choque en 12 episodios, igual que las reglas, y más rápido (32 vs 28 km/h) |

> **Limitación encontrada (D-26):** en E1–E7 los viajes de fondo solo se generaban hasta
> t = 4 000 s y los episodios se encadenan en la misma corrida de SUMO, así que después de
> los primeros ~30 episodios de cada experimento casi no había tráfico de fondo. Ya está
> corregido (flujos sin horizonte); los resultados de la tabla valen para esa condición.

La historia completa del entrenamiento (cuatro versiones fallidas, cómo se detectó cada
falla y cómo se corrigió) está en [docs/DECISIONES.md](docs/DECISIONES.md), D-11 a D-19.
E1–E6 se corrieron con la primera versión de la red (commit `985cee7`); la red ampliada
se valida con E7 (ver [docs/EXPERIMENTOS.md](docs/EXPERIMENTOS.md)).

## Documentación

| Documento | Contenido |
|---|---|
| [docs/PROPUESTA.md](docs/PROPUESTA.md) | Propuesta final (contrapropuesta sobre el Stack Tech), objetivos, alcance y cobertura de la tabla del profesor |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | PEAS, entorno, agentes, Coordinador, DQN, instructor, nube y contratos de cada agente |
| [docs/MODELO_SIMULACION.md](docs/MODELO_SIMULACION.md) | Entidades, reloj, distribuciones, supuestos, verificación y validación |
| [docs/DECISIONES.md](docs/DECISIONES.md) | Registro de decisiones del proyecto (qué, alternativas y por qué) |
| [docs/EXPERIMENTOS.md](docs/EXPERIMENTOS.md) | Diseño y resultados de los experimentos E1–E7 |
| [salidas/RESUMEN.md](salidas/RESUMEN.md) | Tablas numéricas con intervalos de confianza |

## Cómo ejecutarlo (Windows, PowerShell)

Requisitos: Python 3.11 o superior. SUMO se instala solo con `pip`.

```powershell
git clone https://github.com/vcalderonc/Traffic-on-Barranquilla-Simulation.git
cd Traffic-on-Barranquilla-Simulation
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "src"
```

La red, la demanda y los modelos entrenados ya vienen en el repositorio, así que se
puede ir directo a ver resultados.

**Simulación en vivo** (recomendado): abre http://localhost:8000, pestaña *Simulación en
vivo*. En *Recorrido* elige "Por una vía" o "A la medida": partida (un lugar o
*Elegir en el mapa* y clic sobre una vía), los monumentos por los que quieres pasar (en
el orden en que los marques) y la llegada. Ajusta la hora (las horas pico traen más
tráfico), el ciclo día-noche, la lluvia y quién conduce, y pulsa *Conducir*. Al arrancar,
SUMO llena la ciudad de tráfico (~1 min); con un cambio grande de hora, el recorrido tarda
unos segundos más en empezar.

```powershell
python -m bq_sim vivo
```

**Solo los recorridos grabados** (no corre SUMO; también sirve para GitHub Pages):

```powershell
python -m http.server 8000 -d visor
```

**En la interfaz nativa de SUMO** (`sumo-gui`), eligiendo vía, hora y lluvia:

```powershell
python -m bq_sim gui --via "Calle 98" --hora 18 --lluvia
```

**Seguir entrenando al instructor** (acumulativo; guarda respaldo del anterior):

```powershell
python -m bq_sim instructor --continuar --episodios 100
```

En el visor: **H** oculta los paneles para presentar, **C** pone la cámara en la cabina del
Porsche, la barra de *Hora* cambia la luz, los botones *Malecón*, *Buenavista*, *Ventana
al Mundo* y *Aleta del Tiburón* llevan la cámara a esos lugares y *Mapa* muestra toda la
zona. *Gráficos* elige la calidad (Alta: sombras y reflejos; se baja sola si el equipo va
lento).

Para regenerar todo desde cero (o `bash scripts/correr_experimentos.sh` para E2–E6 + visor + gráficas, ~1 h):

```powershell
python -m bq_sim red --descargar      # OSM -> red SUMO con PARE (necesita internet)
python -m bq_sim demanda              # tráfico de fondo, peatones y paseantes (flujos sin horizonte)
python -m bq_sim instructor           # E1: entrena el vehículo instructor (~25 min en un portátil de 2 núcleos)
python -m bq_sim aprendices           # E2/E3
python -m bq_sim bus                  # E4
python -m bq_sim federado --modo local
python -m bq_sim federado --modo fedavg
python -m bq_sim cruzada              # E5: evaluación cruzada
python -m bq_sim comparacion          # E6
python -m bq_sim graficas             # figuras y salidas/RESUMEN.md
python -m bq_sim visor                # ciudad + recorridos para el visor 3D (varios minutos cada uno)
```

Aprendizaje federado distribuido con Flower (una terminal por proceso):

```powershell
python -m bq_sim.aprendizaje.flower_app servidor --rondas 3 --clientes 3 --inicial modelos/instructor_automovil.npz
python -m bq_sim.aprendizaje.flower_app vehiculo --perfil taxi --zona malecon_via40 --semilla 1
python -m bq_sim.aprendizaje.flower_app vehiculo --perfil automovil --zona corredor_calle72 --semilla 2
python -m bq_sim.aprendizaje.flower_app vehiculo --perfil bus --zona calles79_85 --semilla 3
```

O con Docker: `docker compose up --build` (los archivos están listos, pero Docker no se probó en el equipo de desarrollo; la versión con procesos sí se verificó).

## Estructura

```
src/bq_sim/
  config.py              parámetros del modelo (recompensas, climas, tasas de imprevistos)
  red.py                 OSM -> SUMO (netconvert) y PARE
  demanda.py             tráfico de fondo (flujos de Poisson) y pares a pie de peatones y paseantes
  ciudad.py              lugares, horas pico y estrato aproximado por barrio
  entorno/
    mundo.py             conexión con SUMO, horas pico, peatones, rutas por zona y a la medida
    eventos.py           imprevistos estocásticos (peatón, perro, iguana, conos, frenada, vendedor)
    evaluador.py         recompensa y métricas (crítico)
    gym_env.py           entorno Gymnasium
  agentes/
    percepcion.py        sensores virtuales + rastreador
    especialistas.py     Señales, Obstáculos, Navegación (esquivar y adelantar), Seguridad
    velocidad.py         observación normalizada y agente de Velocidad
    vehiculo.py          Coordinador y vehículo autónomo
  aprendizaje/
    dqn.py               Double DQN en NumPy
    perfiles.py          perfiles físicos y normalización
    instructor.py        doble comando + demostraciones
    fedavg.py            FedAvg y base de conocimiento
    flower_app.py        versión distribuida con Flower (gRPC)
    entrenamiento.py     bucles de entrenamiento y evaluación
  experimentos.py        E1-E7
  graficas.py            figuras y tablas
  visor.py               exportación para el visor 3D (ciudad, hitos, alumbrado) y sumo-gui
  servidor.py            simulación en vivo para el navegador (Server-Sent Events)
data/osm/                extracto de OpenStreetMap (comprimido)
data/hitos.json          lugares emblemáticos con su ubicación en OSM
data/estratos.json       estrato aproximado de 51 barrios
sumo/                    red, tipos de vehículo, demanda y configuración de SUMO
modelos/                 redes entrenadas (.npz)
salidas/                 CSV por episodio, figuras y RESUMEN.md
visor/                   visor 3D (index.html, app.js, modelos.js: carros y personas, hitos.js: monumentos, datos/)
```

## Créditos y licencias de datos

Datos del mapa © colaboradores de OpenStreetMap, disponibles bajo la licencia
[ODbL](https://www.openstreetmap.org/copyright). Simulación con
[Eclipse SUMO](https://eclipse.dev/sumo/).
