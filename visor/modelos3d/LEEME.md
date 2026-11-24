# Modelos 3D propios para el visor

Pon aquí archivos `.glb` (o `.gltf`) y un `config.json` que diga qué modelo usa cada
tipo de vehículo y de persona. El visor lee `config.json` al cargar la página:

* lo que esté en `config.json` usa tu modelo;
* lo que no esté (o no cargue) sigue con las figuras de siempre;
* si no hay `config.json`, el visor queda exactamente como antes.

Copia `config.ejemplo.json` como `config.json` y deja solo lo que tengas.
Después de cambiar algo, recarga el navegador con Cmd + Shift + R (no hace falta
reiniciar Python).

## Tipos de vehículo

`sedan`, `sedanLujo`, `hatch` (compacto), `taxi`, `suv` (camioneta), `prado`, `hilux`,
`modeloY`, `mustang`, `cybertruck`, `moto`, `bus` (buseta), `camion`.
El instructor se cambia con `"instructor"`.

Opciones de cada vehículo:

| opción | qué hace | por defecto |
|---|---|---|
| `archivo` | nombre del `.glb` dentro de esta carpeta | (obligatorio) |
| `largo` | largo en metros (el modelo se escala a eso) | el de la figura actual (sedán 4.5, compacto 3.7…) |
| `girar` | grados para corregir hacia dónde mira: `0`, `90`, `180`, `270` | automático |
| `ancho` | ancho en metros, aparte del largo (para modelos con proporciones de juguete) | proporción del modelo |
| `pintura` | materiales que toman el color de cada carro: lista de nombres (o parte del nombre), o `false` para dejar los colores del modelo | se busca solo (`paint`, `body`, `carrocería`…; si no, la superficie más grande que no sea vidrio ni negra) |

`conductor` pone una persona sentada sobre el vehículo (la moto la usa):
`{ "archivo": "Casual_Male.glb", "animacion": "SitDown", "altura": 1.7, "y": 0.35, "z": 0.9 }`
(`y` = altura del asiento, `z` = metros desde el frente).

Si un carro sale andando de reversa, pon `"girar": 180`; si sale de lado, `90` o `270`.

## Personas

`"personas"` es una lista: si pones varios modelos, se reparten entre la gente.

| opción | qué hace | por defecto |
|---|---|---|
| `archivo` | el `.glb` | (obligatorio) |
| `altura` | estatura en metros | 1.72 |
| `animacion` | nombre (o parte) del clip de caminar | busca `walk`/`caminar`; si el modelo trae un solo clip, usa ese |
| `quieto` | clip para la gente parada | busca `idle`; si no hay, la pose original |
| `cuadros` | poses de caminar que se guardan (más = más suave, más memoria) | 10 |
| `velocidad_animacion` | multiplica la velocidad del paso | 1 |
| `girar` | igual que en los carros | 0 |

Las personas necesitan un modelo con esqueleto y un clip de caminar (por ejemplo,
personajes de Mixamo exportados a glTF). Sin clip, se mueven sin mover las piernas.
El peatón que cruza y el vendedor del semáforo también usan estos modelos (si no tienen
texturas); el perro y la iguana siguen con sus figuras.

## Qué tan pesados pueden ser

La ciudad dibuja hasta ~1 900 carros y ~1 100 personas a la vez. Cada modelo se dibuja
con instancias, pero los triángulos se multiplican por el número de copias:

* carros: ideal < 15 000 triángulos (la consola avisa por encima de 30 000);
* personas: ideal < 8 000.

Si va lento, baja *Gráficos* a Media o Baja, o simplifica el modelo en Blender
(modificador *Decimate*) o con https://gltf.report.

## Cómo saber qué pasó

Abre la consola del navegador (Cmd + Option + J). Al cargar aparece
`[modelos3d] cargados:` con cada modelo, sus triángulos, su largo y qué material tomó
como pintura. Si un archivo falla, sale el error con su nombre.

## Licencias

Revisa la licencia de cada modelo antes de subirlo al repositorio (en Sketchfab sale
debajo del botón de descarga). CC0 y CC-BY sirven para un proyecto académico; CC-BY
pide dar crédito (anótalo en este archivo). Evita modelos con logos o marcas.
## Modelos incluidos y créditos

Todos son **CC0 1.0** (dominio público: se pueden usar y subir al repositorio; dar crédito no
es obligatorio, pero se agradece).

| Archivo | Se usa para | Autor | Copiado de |
|---|---|---|---|
| `NormalCar1.glb`, `NormalCar2.glb`, `SUV.glb`, `Taxi.glb` | sedanes, compactos, camionetas, taxi e instructor | Quaternius (Cars pack) | github.com/boyjonauth2021-netizen/dodo-city-runner (`assets/models/city`, con su licencia CC0) |
| `SchoolBus.glb` | buseta | Quaternius (según la licencia de esa carpeta) | mismo repositorio |
| `truck.glb` | camión | Quaternius (según los créditos del repositorio) | mismo repositorio (`assets/models/moris`) |
| `motorcycle.glb` | moto | "Cartoony Purple Motorcycle", AliceCassie | mismo repositorio (`assets/models/moris`) |
| `Casual*.glb`, `Worker_*.glb`, `Suit_*.glb`, `OldClassy_*.glb` | peatones y el conductor de la moto | Quaternius (Ultimate Animated Character Pack) | github.com/Yametech12/ghostname-3d-assets |

Son modelos *low-poly* (estilo videojuego), no fotorrealistas: se eligieron porque son
libres y livianos para cientos de copias. Se pueden cambiar uno por uno en `config.json`.
