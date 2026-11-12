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

---

## Segunda etapa: ciudad ampliada, hora del día y simulación en vivo

### D-20 · Red ampliada hasta Buenavista, la Ventana al Mundo y la Ventana de Campeones

* **Decisión:** el recuadro pasa de 10.998–11.030 N / 74.776–74.812 O a
  **10.995–11.036 N / 74.770–74.838 O**. La red tiene ahora 6 754 tramos, 146 semáforos,
  22 PARE y 23 543 edificios.
* **Por qué:** se pidió incluir la zona de los centros comerciales Buenavista y Plaza del
  Parque (sobre la **Calle 98/99 con Carrera 53**; no la 93, como se verificó en OSM) y
  modelar la ciudad lo más parecido posible. De paso entran la Ventana al Mundo y la
  Ventana de Campeones.
* **Consecuencia:** los experimentos E1–E6 se corrieron con la red anterior (commit
  `985cee7`) y sus resultados siguen siendo válidos para esa red. La red nueva se valida
  con E7. Repetir E1–E6 sobre la red nueva es posible con los mismos comandos (~2–3 h).

### D-21 · Flujos de corredor además de los viajes aleatorios

* **Problema detectado:** con viajes de origen y destino aleatorios, casi ningún carro
  usaba la Avenida del Río; en los recorridos del Malecón el instructor iba solo
  (0.1 vehículos a menos de 80 m en promedio).
* **Decisión:** 16 flujos `<flow>` de SUMO entre los extremos de los grandes corredores
  (Vía 40 600 veh/h por sentido, Av. Calle 72 y Av. Carrera 46 400, Calle 98 y Carrera 53
  350, Calle 84 y Carrera 51B 300, Avenida del Río 260, Calles 79 y 76 250), más los
  viajes aleatorios. Ahora hay ~490 vehículos en la red, 74 en la Vía 40 y 28 en la
  Avenida del Río en un instante típico.
* **Supuesto declarado:** los volúmenes son estimaciones razonables, no aforos oficiales.

### D-22 · Hora del día, ciclo día-noche y clima dinámico

* **Decisión:** el clima deja de ser solo una etiqueta fija. `config.clima_dinamico(hora,
  lluvia)` interpola el alcance, el ruido, las omisiones y la fricción entre "día" y
  "noche" según la luz natural de Barranquilla (amanece ~5:50, oscurece ~18:20) y le suma
  la lluvia, de modo que **lluvia de noche** es el peor caso. Con `ciclo_min_por_s` la hora
  avanza durante el episodio y los sensores del vehículo pierden alcance al oscurecer.
* **Compatibilidad:** con la hora en los extremos coincide exactamente con los climas
  fijos usados en E1–E6 (verificado con pruebas unitarias).
* **Visor:** cielo por hora con el atardecer rosado-lila característico de la ciudad, sol
  que sale por el río y se pone tras la ciudad, luna, estrellas, ventanas y alumbrado que
  se encienden al oscurecer.

### D-23 · Simulación en vivo en el navegador (Server-Sent Events)

* **Decisión:** `python -m bq_sim vivo` levanta un servidor local (solo biblioteca
  estándar) que corre SUMO + agentes y transmite cuadros al visor. El usuario elige la vía
  (10 vías reales), la hora, la lluvia, el ciclo, quién conduce (instructor DQN o reglas),
  el guardrail y la velocidad.
* **Por qué SSE y un único hilo dueño de SUMO:** `libsumo` admite una sola simulación por
  proceso y no debe usarse desde varios hilos; los pedidos HTTP le llegan por una cola. SSE
  es unidireccional y basta para transmitir cuadros, sin dependencias nuevas.

### D-24 · Lugares emblemáticos: ubicación real, forma estilizada

* **Decisión:** posiciones y huellas tomadas de OpenStreetMap (`data/hitos.json`): Estatua
  de Sofía Vergara, La Luna del Río, el carrusel, la Plaza de las Luces, el Edificio
  Gastronómico Caimán del Río, C.C. Buenavista, Buenavista II, Mall Plaza Buenavista,
  C.C. Plaza del Parque, Ventana al Mundo (47 m) y Ventana de Campeones (33 m).
* **Estatua de Shakira:** OSM no la tiene con nombre. La prensa la ubica en la Unidad
  Funcional 3 del Gran Malecón; se usó la escultura sin nombre que OSM registra en ese
  tramo, junto al Caimán del Río. **Posición aproximada.**
* **Estatuas estilizadas:** figuras de bronce simplificadas (bailarina con los brazos en
  alto; figura con vestido saludando), sin intentar el parecido de las personas. La
  rueda, el Caimán y las Ventanas son modelos simplificados con medidas aproximadas.
* **Pantallas tipo Times Square** en la fachada de Buenavista que da a la vía: textos
  genéricos de la ciudad, sin marcas comerciales.

### D-25 · Entrenamiento acumulativo opcional

* **Decisión:** `python -m bq_sim instructor --continuar` carga el instructor guardado,
  lo sigue entrenando (100 episodios por defecto, exploración baja, ancla 0.25 a las
  reglas), guarda una copia del anterior en `modelos/respaldo/` y anota las métricas en
  `salidas/e1_continuacion_<n>.csv`.
* **Por qué no es el comportamiento por defecto:** entrenar desde cero hace que los
  resultados del informe se puedan repetir exactamente; el modo acumulativo es para quien
  quiera que el instructor "siga aprendiendo" entre sesiones.

---

## Tercera etapa: horas pico, recorridos a la medida y gráficos realistas

### D-26 · La demanda ya no se acaba (hallazgo sobre los experimentos anteriores)

* **Problema detectado:** los viajes de fondo y los peatones se generaban con
  `randomTrips.py` hasta t = 4 000 s. Como los episodios se encadenan sobre la misma
  corrida de SUMO (D-07), pasada la primera hora simulada ya no entraba tráfico nuevo y la
  ciudad se vaciaba. En E1 (440 episodios, 52 387 s simulados) eso ocurrió desde el
  episodio ~29; en E2/E3, E6, E7 y en la continuación del entrenamiento, desde el episodio
  ~30. Es decir, la mayor parte del entrenamiento se hizo con **poco o ningún tráfico de
  fondo**: el instructor aprendió sobre todo semáforos, PARE, límites e imprevistos
  (peatones, animales, conos), y muy poco de seguir carros en tráfico denso.
* **Decisión:** toda la demanda se genera como flujos sin horizonte práctico
  (`HORIZONTE_S = 400 000 s`, más de cuatro días): los corredores son `<flow>` con
  llegadas de Poisson (`period="exp(λ)"`) y el tráfico aleatorio son 450 pares
  origen-destino con `--flows --poisson`. Se verificó que a t = 5 000 s sigue habiendo
  cientos de vehículos (antes, cero).
* **Consecuencia para el informe:** los resultados de E1–E7 siguen siendo válidos, pero
  para la condición en la que se obtuvieron (tráfico que se desvanece); hay que decirlo
  como limitación. En una prueba sin reentrenar, con tráfico de hora pico (1 300–2 200
  vehículos en la red), el instructor hizo 3 recorridos sin choques, con 3 casi-choques y
  5 adelantamientos. Se recomienda continuar el entrenamiento (`instructor --continuar`) y
  repetir E7 con la demanda corregida.

### D-27 · Horas pico y gente a pie según la hora

* **Decisión:** `ciudad.factor_demanda(hora)` multiplica la demanda base con un perfil de
  Barranquilla: picos de 6:30–8:30 (×1.6), 11:30–13:30 (×1.4, mucha gente almuerza en
  casa) y 17:00–19:30 (×1.65); de madrugada ×0.3. En vivo y en las grabaciones se aplica
  con `traci.simulation.setScale` al iniciar (con hasta 60 s de recalentamiento si el
  cambio es grande) y cada 30 s cuando corre el ciclo día-noche.
* **Por qué el pico no es ×2:** con ×2 las glorietas se trancan y la red pasa de 1 300 a
  más de 2 200 vehículos sin estabilizarse (trancón permanente).
* **Gente a pie:** los `personFlow` de SUMO se expanden completos al cargar (con días de
  horizonte eran cientos de miles de personas y la carga tomaba ~90 s), así que
  `PeatonesDinamicos` lanza a cada persona por TraCI con llegadas de Poisson desde
  `sumo/peatones_od.json`: 600 pares en toda el área (≈ 4 000 personas/h) y 240 pares de
  **paseantes** en el Gran Malecón, Buenavista y la Calle 72 (≈ 3 600 personas/h). El
  perfil de paseo llena el Malecón al atardecer y lo vacía al mediodía. En estado estable
  hay ~1 100 personas caminando y ~1 200 vehículos a escala 1.0.

### D-28 · Adelantamientos por la izquierda

* **Decisión:** el agente de Navegación ahora también adelanta: si el vehículo de adelante
  va lento (más de 2 s por debajo del 75 % del límite y moviéndose), no hay cruce,
  semáforo ni PARE a menos de 45 m y el carril izquierdo está libre hasta 25 m después del
  lento, pide pasarse a la izquierda; cuando ya pasó y la derecha está libre, vuelve.
  Sigue el Código Nacional de Tránsito (Ley 769 de 2002: se adelanta por la izquierda y
  se circula por la derecha) y no adelanta a quien está detenido en una fila.
* **Seguridad:** el guardrail aprueba o niega cada cambio de carril. Se le agregó un
  **radar trasero** (vehículos hasta 45 m detrás): niega el cambio si alguien viene por ese
  carril y llegaría en menos de 3 s.
* **Compatibilidad con el DQN:** la entrada "carril bloqueado" de la red solo se activa al
  esquivar obstáculos, no al adelantar, así que el modelo entrenado no cambia de
  significado. Los adelantamientos se cuentan en las métricas y en el visor.

### D-29 · Vendedores ambulantes en los semáforos y puestos por estrato

* **Decisión:** cuando el vehículo autónomo frena o espera en un rojo (a 10–45 m del
  semáforo), puede aparecer un **vendedor** que se mete entre los carros, se queda en el
  carril mientras está en rojo y se devuelve 0.6–2.2 s después de que cambia a verde: el
  caso de "arrancar en verde sin mirar". Probabilidad por semáforo según el estrato: 55 %
  en estratos 1–2, 45 % en 3, 30 % en 4, 18 % en 5 y 12 % en 6. Para la percepción es un
  peatón (subtipo "vendedor").
* **Puestos (decorado):** 398 puestos fijos (carritos con sombrilla, toldos con fruta,
  carritos de tinto y kioscos de comida) en las esquinas con semáforo, a lo largo de los
  corredores comerciales y en las plazoletas del Malecón, con su vendedor y clientes.

### D-30 · Partida elegible y paso por monumentos sobre glorietas

* **Decisión:** además de "manejar por una vía", el usuario arma un recorrido a la medida:
  punto de partida (un lugar o **un clic en el mapa**), monumentos por los que pasar, en
  el orden elegido, y llegada opcional (si no hay, sigue 0.8–2 km por una vía principal).
  `MundoSUMO.ruta_personalizada` encadena rutas más rápidas de SUMO entre esos puntos.
* **Glorietas:** la Ventana al Mundo (Vía 40 con Circunvalar), la Aleta del Tiburón
  (Ventana de Campeones, "Rotonda Aleta del Tiburón" en OSM) y la Rotonda Malecón 72
  están sobre glorietas; si hay una glorieta a menos de 75 m del monumento, el punto de
  paso se toma sobre ella, de modo que el vehículo le da la vuelta.
* **Puerta de Oro:** en OSM "La Puerta de Oro" es un bar; se usó el **Centro de Eventos
  Puerta de Oro** sobre la Vía 40. No está sobre una glorieta (la más cercana queda a
  ~540 m): el recorrido pasa por su frente. Su polígono en OSM es el predio completo, así
  que se dibuja como plazoleta y los edificios que están dentro llevan la fachada dorada.
* **Tecnoglass azul:** se confirmó con el usuario que se refería a la torre azul de la
  Ventana al Mundo.

### D-31 · Estrato por zona (aproximado)

* **Decisión:** `data/estratos.json` asigna un estrato aproximado a 51 barrios de OSM (p.
  ej. Alto Prado, El Golf, Riomar, Barrio Buenavista y Villa Santos 6; Villa Country y El
  Prado 5; Barrio Abajo y Montecristo 3; Siape, San Salvador, La Loma y Ciudad Mallorquín
  2; zona industrial 0). Cada punto toma el estrato del barrio más cercano.
* **Para qué se usa:** alturas y estilo de los edificios (torres de 8 a 26 pisos y casas
  elegantes en el norte, casas de uno o dos pisos de colores vivos en los barrios
  populares, bodegas en la zona industrial), densidad y especies de árboles de calle (más
  robles morados y guayacanes en el norte), qué carros circulan (más Model Y, Prado TXL y
  Mustang donde el estrato es alto) y cuántos vendedores hay.
* **Supuesto declarado:** no es la estratificación oficial de la Alcaldía; es una
  aproximación por barrio para que el poder adquisitivo de cada zona se note.

### D-32 · Gráficos: fachadas procedurales, modelos de carros y luz realista

* **Render:** tonemapping ACES, bloom para las luces de noche, sombras del sol (calidad
  alta), mapa de entorno generado con el mismo cielo (los vidrios y la pintura reflejan el
  atardecer rosado), nubes procedurales, río Magdalena color café con oleaje y destello
  del sol, asfalto con textura, líneas de carril (amarilla al centro en las vías de doble
  sentido), andenes de baldosa, charcos de luz bajo los postes y haces de los faros. Hay
  calidad Alta/Media/Baja con ajuste automático según los cuadros por segundo.
* **Edificios:** un atlas procedural de fachadas (6 estilos × piso tipo y planta baja)
  con ventanas que reflejan el cielo de día y se encienden al azar de noche (cálidas y
  frías), tanques de agua negros en las terrazas de las casas, techos de teja.
* **Vehículos:** modelos 3D procedurales extruyendo la silueta lateral de cada carro, con
  vidrios, rines, luces y **placas colombianas** (amarillas las particulares, blancas las
  de servicio público). El instructor es un **Porsche 911 GT color cherry blossom**
  (rosado claro, con alerón GT); circulan Cybertruck, Model Y, Mustang, **Toyota Prado
  TXL** y Hilux (se interpretó "Toyota XL" como la Prado TXL y se agregó la Hilux, muy
  común en la ciudad), sedanes, compactos, taxis amarillos con aviso y franja de cuadros,
  busetas de colores, camiones y motos con conductor. Son siluetas inspiradas en cada
  modelo, sin logos ni marcas. La clase física (largo, aceleración) sigue saliendo de
  SUMO; el modelo visual dentro de la clase se elige según el estrato de la zona.
* **Personas:** cuerpo articulado con caminata animada, ropa, piel y pelo variados.
* **Monumentos iluminados:** la Aleta del Tiburón con paneles LED que alternan el rojo y
  blanco del Junior, el tricolor de Colombia y destellos de agua; la Ventana al Mundo con
  su pilar de mosaico de colores y la torre de vidrio azul, iluminados por dentro; el
  Centro de Eventos Puerta de Oro con lamas doradas y un portal dorado frente a la Vía 40.

### D-33 · Grabaciones comprimidas y con la demanda nueva

* **Decisión:** `python -m bq_sim visor` graba los recorridos con la misma demanda del
  modo en vivo (horas pico, gente a pie) y los guarda como `.json.gz`; el visor los
  descomprime en el navegador (`DecompressionStream`) y sigue leyendo los `.json`
  anteriores. Se agregaron tres: Vía 40 en hora pico, Buenavista → Ventana al Mundo al
  atardecer y Malecón → Aleta del Tiburón de noche.
* **Pendiente:** regrabarlos en un equipo con más rendimiento (cada uno toma varios
  minutos con el tráfico nuevo). Mientras tanto el visor muestra las grabaciones de la
  etapa anterior.

### D-34 · La gente a pie solo aparece en andenes

* **Problema detectado:** al regrabar el recorrido del Malecón, el instructor "atropelló"
  a un peatón a los 87 s. SUMO no registró ninguna colisión: el peatón dinámico había
  **aparecido** justo debajo del carro, porque el generador lo hizo empezar a caminar en un
  tramo de la Avenida del Río cuya calzada también admite peatones (no en un andén).
* **Decisión:** los pares origen-destino a pie solo empiezan y terminan en tramos con un
  andén o sendero exclusivo para peatones, y `PeatonesDinamicos` no lanza a nadie a menos
  de 15 m de un vehículo en ese tramo. Las rutas a pie pueden seguir cruzando calles sin
  andén (como en muchos barrios de la ciudad), pero allí el peatón llega caminando y la
  percepción lo ve venir.
* **Segunda causa, en el evaluador:** aun así el choque se repetía en el mismo punto. El
  atropello de peatones de SUMO se verificaba solo por geometría (peatón a menos de 0.3 m
  delante y dentro del ancho del carro). En las esquinas, la curva de giro que dibuja
  `netconvert` pasa a menos de 1.5 m del andén, así que un peatón parado en el andén
  "aparecía" dentro de la trayectoria al girar. Ahora solo cuenta como atropello si el
  peatón está donde circulan carros: en una cebra o en una calzada sin andén.
