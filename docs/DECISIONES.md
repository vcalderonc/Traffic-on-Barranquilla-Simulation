# Registro de decisiones del proyecto

Cada decisión tiene el formato: **qué se decidió**, **alternativas** y **por qué**.
Sirve para la sustentación: si preguntan "¿por qué no X?", la respuesta está aquí.

---

### D-01 · Base del proyecto: el Stack Tech, con ajustes (contrapropuesta)

* **Decisión:** usar como columna vertebral la propuesta nueva (*Stack Tech*: OSM +
  SUMO + TraCI + RL con recompensas + FedAvg/Flower + Docker) y fusionarle tres ideas de
  la propuesta original del grupo: normalización del conocimiento por tiempo para
  colisión y por capacidad de frenado propia, transferencia automóvil → vehículo pesado,
  y la validación de aportes en la nube.
* **Alternativas:** quedarse con la propuesta original (lógica difusa en una vía recta);
  usar el Stack Tech tal cual.
* **Por qué:** la original no cumple el mínimo del profesor (varios agentes conduciendo
  un mismo vehículo) ni el escenario de Barranquilla. El Stack Tech sí da el escenario,
  pero no dice cómo se reparten las decisiones dentro del vehículo ni cómo "enseña" un
  carro a otro; eso es lo que se añade.

### D-02 · AWS EKS queda fuera del alcance; se entrega Docker Compose

* **Decisión:** el despliegue distribuido se demuestra con Flower sobre gRPC y
  `docker-compose.yml` (1 servidor + 3 vehículos en una red *bridge*). EKS, Spot,
  Karpenter y S3 quedan documentados como trabajo futuro.
* **Por qué:** EKS cuesta dinero, exige una cuenta de AWS y no cambia ningún resultado
  del modelo de simulación. El aprendizaje federado y el intercambio gRPC ya se pueden
  mostrar en un portátil.

### D-03 · Zona: el Gran Malecón y sus vías principales reales

* **Decisión:** recuadro 10.998–11.030 N, 74.776–74.812 O, descargado de OpenStreetMap
  con Overpass y convertido con `netconvert`.
* **Por qué:** contiene el Malecón (para el visor), la Vía 40 y la Avenida del Río
  (vías rápidas), la Av. Calle 72 y las Calles 76–85 (semáforos y tráfico denso) y
  barrios con PARE. Toda la ciudad haría la simulación demasiado lenta para el equipo.

### D-04 · Varios agentes en un mismo vehículo, con Coordinador por prioridades

* **Decisión:** Percepción, Señales, Obstáculos, Navegación, Velocidad y Seguridad,
  combinados por un árbitro con orden fijo Seguridad > Señales > Velocidad > Navegación.
* **Alternativas:** un único agente RL que lo haga todo; un coordinador aprendido.
* **Por qué:** es el caso 1 de la tabla del profesor. El orden fijo hace el sistema
  explicable y verificable (cada paso dice quién decidió y por qué) y garantiza que el
  aprendizaje nunca pueda saltarse una norma ni un veto de seguridad.

### D-05 · Solo aprende el agente de Velocidad

* **Decisión:** reglas para Señales, Seguridad y Navegación; DQN para Velocidad.
* **Por qué:** principio de parsimonia de la guía ("no se incorpora aprendizaje donde
  bastan reglas"). Las normas de tránsito y la física se conocen; lo difícil es el
  compromiso progreso/riesgo/confort con sensores ruidosos.

### D-06 · Double DQN implementado en NumPy

* **Alternativas:** PyTorch o TensorFlow + Stable-Baselines3.
* **Por qué:** la red es pequeña (27-64-64-7) y corre sin GPU en el portátil del equipo
  (Ryzen 3, 6 GB); evita más de 2 GB de dependencias; cada línea es explicable en la
  sustentación; los pesos son una lista de arreglos NumPy, el formato exacto que
  intercambian FedAvg y `flwr.client.NumPyClient`.

### D-07 · Acciones y observaciones normalizadas por la capacidad del vehículo

* **Decisión:** acciones = fracción del frenado/aceleración máximos propios; distancias
  expresadas como TTC o como fracción del frenado propio necesario.
* **Por qué:** heredado de la propuesta original. Permite que un bus use lo que aprendió
  un automóvil. El experimento E4 mide qué pasa si NO se normaliza.

### D-08 · El instructor enseña con "doble comando" + demostraciones

* **Decisión:** transferencia de pesos, intervención del instructor cuando el aprendiz
  es menos prudente en una situación de riesgo, y pérdida de imitación (DQfD) con peso
  que decae.
* **Alternativas:** solo copiar pesos; solo imitación (clonación de comportamiento).
* **Por qué:** es la forma más fiel de "un carro entrenado que entrena a los otros": el
  aprendiz conduce de verdad, el instructor corrige solo cuando hace falta y se va
  retirando. La tasa de intervenciones mide el aprendizaje.

### D-09 · Imprevistos como vehículos fantasma en SUMO

* **Alternativas:** manejarlos solo en Python; usar peatones de SUMO.
* **Por qué:** los peatones de SUMO no cruzan a mitad de cuadra y SUMO no tiene perros,
  iguanas ni conos. Como vehículos detenidos, todo el tráfico los respeta y SUMO detecta
  los choques; el visor los dibuja con su forma.

### D-10 · `libsumo` para entrenar, TraCI por socket para `sumo-gui`

* **Por qué:** `libsumo` corre SUMO dentro del proceso de Python y es varias veces más
  rápido (≈ 150–400 pasos/s en el portátil); `sumo-gui` exige TraCI por socket.

### D-11 · Peatones imprudentes "pero no suicidas" (corrección tras la versión 1)

* **Problema detectado:** en la primera corrida del instructor (220 episodios,
  `salidas/v1_peatones_suicidas/`) casi todos los choques eran con peatones imprudentes
  que se lanzaban cuando el vehículo ya estaba a menos de su distancia física de
  frenado. Esos choques eran inevitables: castigaban al agente sin enseñarle nada.
* **Decisión:** el imprudente se lanza aunque obligue a frenar fuerte, pero no si el
  vehículo ya no puede detenerse ni con frenado máximo (v²/(2·7) + 0.3·v + 1 m).
* **Por qué:** el modelo debe premiar la anticipación; un choque inevitable no aporta
  señal de aprendizaje y distorsiona la comparación entre variantes.

### D-12 · Episodios truncados por bloqueo

* **Decisión:** si el vehículo pasa 45 s detenido, el episodio se trunca.
* **Por qué:** en las primeras corridas había episodios completos de un carro atascado
  detrás de un trancón o en un PARE sin hueco: tiempo de cómputo sin información.

### D-13 · Se guarda la acción ejecutada, no la propuesta

* **Por qué:** DQN es *off-policy*: puede aprender de las acciones que realmente se
  ejecutaron (incluidas las correcciones de Señales, Seguridad o el instructor). Así el
  agente aprende a anticiparse y evita que lo corrijan.

### D-14 · Entrenar sin guardrail, desplegar con guardrail

* **Por qué:** si Seguridad siempre frena por el aprendiz, este nunca experimenta las
  consecuencias y la curva de aprendizaje no muestra nada. En simulación un choque no
  cuesta nada (es para lo que sirve simular). En la evaluación final se comparan ambas
  configuraciones (E6).

### D-15 · Visor 3D propio en el navegador (Three.js) además de `sumo-gui`

* **Por qué:** `sumo-gui` es 2D y no muestra el Malecón. El visor reproduce un recorrido
  grabado con edificios, río, palmeras, semáforos, imprevistos y el razonamiento de los
  agentes en tiempo real. Funciona en cualquier navegador sin instalar nada.

### D-16 · Datos de OSM y modelos entrenados se versionan en el repositorio

* **Por qué:** reproducibilidad sin internet y sin reentrenar. El OSM comprimido pesa
  ~1 MB y los modelos ~30 KB. La red SUMO también se versiona (1.5 MB) para que
  `python -m bq_sim gui` funcione al clonar.

### D-17 · Consejo de Obstáculos en la observación y recompensa rebalanceada (corrección tras la versión 2)

* **Problema detectado:** en la segunda corrida del instructor
  (`salidas/v2_colapso_lento/`) la política aprendió bien hasta el episodio ~140 y luego
  **colapsó a casi no moverse** (3–10 km/h, cero choques, recompensa ≈ −5). Es un óptimo
  local típico (*reward hacking*): la penalización por choque pesaba más que el premio
  por avanzar, y solo se castigaba estar detenido (< 0.5 m/s), no arrastrarse.
* **Decisiones:**
  1. El agente de Velocidad recibe como entrada la **aceleración que sugiere el agente de
     Obstáculos** (modelo de seguimiento tipo IDM). Es la forma concreta en que, en la
     arquitectura, Obstáculos *informa* a Velocidad: el aprendiz puede seguir el consejo
     o apartarse de él cuando aprende que conviene (p. ej. frenar antes ante un peatón
     en el andén). Observación: 27 → 28 valores.
  2. Progreso de +0.05 a **+0.10** por paso a la velocidad límite.
  3. Se penaliza **ir lento sin motivo** (< 40 % del límite sin obstáculo cercano, señal
     que obligue a parar ni curva o calle más lenta adelante): −0.03 por paso.
  4. Aprendizaje más estable: tasa 5·10⁻⁴ → 3·10⁻⁴ y red objetivo τ 0.01 → 0.005.
* **Por qué:** sin estos cambios el "mejor" agente para la recompensa no era un buen
  conductor. Las métricas de seguridad se reportan aparte de la recompensa justamente
  para detectar este tipo de desalineación (guía, sección 15.3).

### D-18 · Retornos de n pasos, memoria de incidentes y "escuela de reglas" (corrección tras la versión 3)

* **Problema detectado:** la versión 3 del instructor (`salidas/v3_greedy_inseguro/`)
  parecía buena durante el entrenamiento (≈13 % de choques), pero al evaluarla **sin
  exploración** chocaba en el 42 % de los episodios con cielo despejado, frente al 8 %
  del conductor de reglas. Parte de su aparente seguridad venía de las acciones
  aleatorias de exploración (que muchas veces son frenar). Causa de fondo: los choques
  son rarísimos en la memoria (≈ 1 de cada 5 000 transiciones) y con retornos de un
  paso el castigo tarda en llegar a las decisiones que lo provocaron.
* **Decisiones:**
  1. **Retornos de 3 pasos** (Sutton y Barto, 2018, cap. 7): el castigo de un choque
     alcanza en una sola actualización a las decisiones de 0.75 s antes.
  2. **Memoria de incidentes:** las transiciones de los ~2 s previos a cada choque o
     casi-choque se copian a una memoria aparte y forman el 25 % de cada lote (idea
     afín a la repetición priorizada de Schaul et al., 2016).
  3. **Escuela de reglas (DQfD, Hester et al., 2018):** durante los primeros 150
     episodios, el instructor suma a su pérdida un término de imitación del conductor
     de reglas (IDM + Señales + veto de Seguridad) con peso que decae de 1 a 0. Después
     aprende solo por refuerzo. Es como sacar el pase: primero se aprenden las reglas
     y luego la experiencia afina.
  4. **Evaluación sin exploración cada 50 episodios** (5 escenarios fijos), para que la
     curva reportada sea la de la política real y no la de la política con ruido.
  5. ε final 0.05 → 0.02.
* **Por qué:** un instructor que solo es seguro "por suerte" no puede enseñar. La
  comparación con el conductor de reglas en E6 dice si el aprendizaje aporta algo por
  encima de las reglas que imitó al comienzo.

### D-19 · Ancla a las reglas y memoria de incidentes moderada (corrección tras la versión 4)

* **Problema detectado:** con D-18 tal cual (`salidas/v4_colapso_quieto/`), las
  evaluaciones sin exploración mostraron un buen conductor a los 50 episodios
  (0/5 choques, 29 km/h) pero, justo cuando el peso de imitación llegó a cero (episodio
  150), la política pasó a **quedarse quieta** (0 km/h), aunque conducir le daba +34 de
  recompensa frente a −3 de quedarse. La memoria de incidentes al 25 % del lote, sin
  corrección del sesgo de muestreo, le hacía "ver" choques mucho más seguido de lo real
  y sobrestimar el peligro de moverse.
* **Decisiones:**
  1. Memoria de incidentes al **10 %** del lote.
  2. El peso de imitación de las reglas baja de 1 a **0.25** y se queda ahí (no llega a
     cero). El refuerzo puede apartar la política de las reglas solo cuando la ventaja
     en valor Q supera el margen: es una mejora **conservadora** de la política, como en
     DQfD, donde la pérdida de demostración nunca se apaga.
  3. Lo mismo para los aprendices con instructor: el consejo del instructor queda con
     peso 0.25 después de la tutela (el doble comando sí se retira por completo).
  4. En el experimento federado (E5) la flota arranca con el conocimiento del
     instructor y lo afina en su zona, en vez de arrancar de cero.
* **Lección para el informe:** el aprendizaje por refuerzo puro fue frágil en este
  problema (4 versiones con fallas distintas: choques inevitables, *reward hacking*,
  seguridad aparente por exploración y colapso por sesgo de muestreo). Cada falla se
  detectó con una métrica o una evaluación concreta y se corrigió con una técnica
  documentada. Esto respalda el principio de la guía: el aprendizaje se usa donde
  aporta y se combina con reglas y guardrails que garantizan lo que no se puede dejar
  al azar.
