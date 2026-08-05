# SÍNTESIS — cimientos técnicos (fase 3 / adopción; solo lo escribe el padre)

> Fichero único de los cimientos técnicos. Se llega por dos caminos:
> **proyecto de cero** — el padre la escribe tras leer TODOS los informes (`informe-NN-*.md`)
> de la fase 3; y **brownfield** — la escribe la unidad de adopción con el stack que YA vive
> en `main/`, y la fase 3 acotada le añade después sus informes (`runbooks/adopcion.md` §5-6).
> Una fila por decisión; el detalle vive en los informes o en la ruta de `main/` que la
> demuestra. Desviarse de lo aquí fijado = ADR primero. Las especificaciones (fase 5)
> consultan este fichero al rellenar su Cómo.
> **Las secciones marcadas `<solo brownfield>` se borran en un proyecto de cero.**

## Decisiones vigentes

| tema | decisión | por qué (una frase) | fecha | evidencia |
|---|---|---|---|---|
| <tema> | <qué se usa> | <motivo> | YYYY-MM-DD | informe-NN · o ruta de `main/` (brownfield) |

<En brownfield estas filas son el **bias efectivo** del proyecto: el stack real con sus
versiones LEÍDAS de los ficheros de dependencias, más los comandos de build / test / arranque
ya verificados (output real en la unidad de adopción), para que ningún constructor los
redescubra.>

## Desviaciones del bias

- — <o ADR-NNN: qué se desvió y por qué>

## Temas descartados (con porqué, para no re-investigar)

- —

## Gap-map código↔flujos `<solo brownfield>`

Qué promete `02-flujos/` que el código NO hace, y qué hace el código que el mapa NO recoge.
Cada fila con su evidencia: ruta exacta de `main/`, o la ausencia comprobada (de memoria nada).

| # | hueco | dirección | evidencia | riesgo |
|---|---|---|---|---|
| 1 | <qué falta o qué sobra> | mapa→código / código→mapa | <ruta, o "no existe: buscado en …"> | alto/medio/bajo |

## Unidades candidatas `<solo brownfield>`

Derivadas del gap-map. Las revisa el usuario y decide cuáles entran al ROADMAP y en qué orden.
Sin NNN: el número se asigna al despachar (fase 5).

| candidata (slug tentativo) | tipo | hueco que cierra | prioridad propuesta |
|---|---|---|---|
| <slug> | feature | <# del gap-map> | alta/media/baja |

## Fase 3 acotada tras la adopción `<solo brownfield>`

- **Temas investigados:** <lo desconocido o arriesgado del gap-map + versiones y
  vulnerabilidades del stack existente> → `informe-NN-*.md`. El stack NO se re-elige.
- **O bien — "fase 3 sin temas":** <por qué el gap-map no reveló nada desconocido>
  · <el usuario, YYYY-MM-DD>. Decisión escrita, nunca un salto silencioso.
