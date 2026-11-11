# Propuesta (versión final): conducción autónoma multiagente en Barranquilla con un vehículo instructor

> **Decisión:** se usa el *Stack Tech* (propuesta nueva) como base, con una
> contrapropuesta de ajustes. Ver el porqué de cada ajuste en
> [DECISIONES.md](DECISIONES.md).

## Qué se conserva de cada propuesta

| De la propuesta original (frenado difuso) | Del Stack Tech (propuesta nueva) | Lo que se añade |
|---|---|---|
| Tiempo para colisión (TTC) como variable central | Red real de Barranquilla (OSM → SUMO) | Varios agentes conduciendo un mismo vehículo (mínimo del profesor) |
| Normalizar el conocimiento por la capacidad del vehículo | Control en tiempo real con TraCI | Coordinador por prioridades con trazabilidad |
| Transferencia automóvil → vehículo pesado | Recompensas: choque −100, casi-choque −10, PARE −20, frenada brusca −0.1 | Vehículo instructor con doble comando |
| Validar lo que sube a la nube | Gymnasium (`reset`/`step`) | Peatones, perros, iguanas, conos y frenadas súbitas |
| Evaluar con escenarios comparables | FedAvg con Flower y datos no-IID por zonas | Clima: lluvia y noche |
| | Docker | Visor 3D del Gran Malecón |
| *(se reemplaza la lógica difusa por DQN)* | *(EKS pasa a trabajo futuro)* | |

## Planteamiento del problema

Un vehículo autónomo en Barranquilla tiene que hacer varias cosas a la vez: seguir su
ruta, respetar semáforos, PARE y límites, mantener distancia con autos y motos, y
reaccionar a lo que aparece sin aviso — un peatón que cruza por la mitad de la cuadra
en la Vía 40, un perro en la Calle 79, una iguana en el Malecón, un carril cerrado con
conos o el bus de adelante que frena en seco. Con lluvia o de noche, además, ve menos y
frena peor.

Esas decisiones las toman **varios agentes especializados dentro del mismo vehículo**,
y pueden contradecirse: Navegación quiere cambiar de carril mientras Seguridad ve una
moto al lado; Velocidad quiere acelerar mientras Señales ve el amarillo. Hace falta un
mecanismo de coordinación que respete prioridades.

Además, aprender a conducir así cuesta experiencia. Si cada vehículo de una flota
tiene que aprender desde cero, cada uno repite los mismos errores.

**Pregunta del proyecto:** ¿cómo coordinar a los agentes que conducen un mismo vehículo
para que conduzca de forma segura y legal en la red real de Barranquilla, y cómo puede
un vehículo ya entrenado enseñarles a otros — incluso de otro tipo y en otras zonas —
para que aprendan más rápido y con menos choques?

## Objetivos

**General:** desarrollar un modelo de simulación multiagente de conducción autónoma en
la zona del Gran Malecón de Barranquilla, donde un vehículo instructor entrenado por
refuerzo transfiere su conocimiento a otros vehículos directamente y mediante
aprendizaje federado.

**Específicos:**

1. Construir el entorno virtual con la red vial real (OSM → SUMO): semáforos, PARE,
   límites, tráfico mixto, peatones e imprevistos estocásticos.
2. Diseñar la arquitectura de agentes del vehículo (Percepción, Señales, Obstáculos,
   Navegación, Velocidad, Seguridad) y su Coordinador por prioridades.
3. Entrenar la política de velocidad con Double DQN y la función de recompensa del
   Stack Tech, y obtener el vehículo instructor.
4. Implementar la enseñanza instructor → aprendiz (transferencia normalizada, doble
   comando, demostraciones) y la base de conocimiento federada (FedAvg / Flower).
5. Evaluar con réplicas e intervalos de confianza: aprendizaje, transferencia,
   normalización automóvil → bus, federación por zonas y comparación reglas vs.
   aprendizaje vs. híbrido bajo distintos climas.
6. Visualizar los recorridos en 3D sobre el Malecón con el razonamiento de los agentes.

## Cobertura de la tabla del profesor

| Caso de la tabla | Cobertura | Dónde |
|---|---|---|
| 1. Conducción urbana inteligente | **Completa** (núcleo del proyecto) | 6 agentes + Coordinador |
| 2. Adelantamiento autónomo | Parcial: cambio de carril táctico para esquivar obras o vehículos detenidos, con veto de Seguridad | Navegación + Seguridad |
| 3. Conducción ante emergencias | **Completa**: peatones, animales y frenadas súbitas; decisiones contradictorias resueltas por veto | Seguridad + Coordinador |
| 4. Conducción eficiente | Parcial: progreso y confort en la recompensa (sin modelo de consumo) | Recompensa |
| 5. Conducción con visibilidad limitada | **Completa**: lluvia y noche cambian alcance, ruido, omisiones y fricción | Percepción + clima |
| 6. Estacionamiento autónomo | No cubierto (fuera de alcance) | — |
| 7. Conducción adaptativa | Parcial: la política recibe fricción y visibilidad; las zonas cambian el tipo de imprevistos | Observación + zonas |

## Experimentos

| # | Pregunta | Diseño |
|---|---|---|
| E1 | ¿Aprende el instructor? | 400 episodios desde cero, sin guardrail, 3 zonas, 3 climas |
| E2/E3 | ¿Enseña el instructor? | Taxi aprendiz: desde cero vs. con instructor (doble comando) vs. copia + instructor; 2 semillas |
| E4 | ¿Es seguro transferir a un bus? | Política del instructor en un bus: normalizada vs. copiada tal cual |
| E5 | ¿Sirve compartir por la nube? | 3 vehículos en 3 zonas: solo local vs. FedAvg; evaluación cruzada |
| E6 | ¿Reglas, aprendizaje o híbrido? | Agente de reglas vs. DQN vs. DQN + guardrail, por clima |

Resultados en [EXPERIMENTOS.md](EXPERIMENTOS.md).

## Alcance

**Incluye:** red vial real de la zona del Malecón; tráfico mixto; peatones;
imprevistos; tres climas; seis agentes por vehículo; DQN; instructor; FedAvg local y
con Flower; Docker Compose; visor 3D; experimentos con réplicas.

**No incluye:** visión por computador, sensores o hardware reales, dinámica lateral,
estacionamiento, calibración con aforos reales y despliegue en AWS EKS.

## Herramientas

| Herramienta | Uso |
|---|---|
| Python 3.13 | lenguaje principal |
| SUMO 1.28 (`eclipse-sumo`, `libsumo`, TraCI, `sumolib`, `netconvert`, `randomTrips`) | simulación de tráfico |
| OpenStreetMap + Overpass API | red vial, edificios, río y parques |
| NumPy | Double DQN |
| Gymnasium | interfaz del entorno |
| Flower (`flwr`) | aprendizaje federado sobre gRPC |
| pandas + Matplotlib | métricas y gráficas |
| Three.js | visor 3D del Malecón |
| Docker Compose | servidor + vehículos federados |

## Cronograma sugerido

| Semana | Entregable |
|---|---|
| 1 | Propuesta aprobada; red de Barranquilla en SUMO |
| 2 | Agentes del vehículo y Coordinador; prueba con agente de reglas |
| 3 | Entorno Gymnasium, recompensa y entrenamiento del instructor (E1) |
| 4 | Instructor → aprendices (E2/E3) y normalización (E4) |
| 5 | Aprendizaje federado (E5) y comparación por clima (E6) |
| 6 | Visor 3D, informe final y sustentación |
