# Ingeniería de requisitos con IA

Convierte lo que sabes de tu negocio en unos planos que una IA puede
construir sin inventarse nada. Tú no escribes requisitos: cuentas tu negocio,
la IA te entrevista, y validas mirando una web que se va rellenando sola.

## Qué necesitas

- Un ordenador con Python 3. Si no lo tienes, tranquilo: tu propia IA lo
  comprobará al empezar y lo instalará contigo.
- Git, para guardar el historial y separar el repositorio padre del código.
- Un agente de IA que pueda ejecutar comandos en tu ordenador (por ejemplo
  Claude Code). Un chat web normal no vale: no puede levantar el visor.
- Tiempo tranquilo por delante, y tu negocio en la cabeza: el proceso de
  memoria, con nombres y números reales.

## Cómo se usa

1. Descarga este repositorio y abre una terminal dentro de él.
2. Lanza aquí tu agente de IA. `AGENTS.md` es el enrutador; `CLAUDE.md` y
   `GEMINI.md` lo redirigen al mismo sitio. El agente leerá `RUNBOOK.md`.
3. El agente te preguntará si partes de cero, de un código que ya existe o
   de unos planos anteriores.
4. En cuanto conozca el nombre, creará FUERA de esta herramienta una carpeta
   visible `<nombre>-agents`. Ahí ocurrirá toda la entrevista.
5. Tú cuentas tu negocio y corriges mirando. La IA estructura y escribe.

Durante la conversación se te abrirá una página en el navegador: son tus
planos, y se actualizan solos según avanza la entrevista. La sesión se mantiene
abierta hasta que la cierres; si sigue activa, volver a abrirla reutiliza la
misma dirección.

## Qué obtienes

Desde el primer momento tienes un workspace, o sea, una carpeta de trabajo
completa:

- `<nombre>-agents/`: el repositorio padre donde viven el método, las
  decisiones y la documentación.
- `<nombre>-agents/main/`: el repositorio hijo que contiene únicamente el
  código de la aplicación.
- `docs/02-flujos/planos/planos.json`: tu proyecto como datos (lo que pinta
  la web). En
  aplicaciones grandes, un mapa general más `actividades/<actividad>/` con
  los planos de cada actividad.
- Una web local de solo lectura donde revisas todos los flujos.
- Constitución y flujos compilados, siempre regenerables desde
  `planos.json`.
- Investigación, planificación y trabajo vacíos hasta que toque recorrer
  esas fases en una sesión nueva dentro de `<nombre>-agents`.
- Una cola persistente de peticiones: lo que pides se escribe antes de decidir
  si cambia flujos, requiere investigación, abre una unidad o ya estaba resuelto.

## Qué hay en esta carpeta

- `RUNBOOK.md`: el método completo que sigue tu IA (incluido el Modo D, que
  reparte las mejoras del método a los proyectos ya creados).
- `CHANGELOG.md`: qué trae cada versión del método, contado en cristiano.
  Tu proyecto sabe su versión (está en su `METODO.json`) y el Modo D te dice
  el salto antes de aplicarlo.
- `visor/`: la web local y las herramientas. No se tocan.
- `plantilla/`: el molde del proyecto de trabajo que monta el bootstrap
  (el método de desarrollo por fases). No se toca; su README lo explica.
- [`manual-ingenieria-requisitos.html`](manual-ingenieria-requisitos.html):
  **el documento único**, autocontenido y sin conexión. Tres partes: cómo se
  usa esto desde cero (lo que estás leyendo aquí, con más detalle), cómo
  trabajan los agentes después, y el croquis técnico del workspace —cada
  runbook, cada estado y cada comprobación con su umbral exacto—.

## Actualizar proyectos creados anteriormente

Cuando esta herramienta mejora su método, tus proyectos ya creados **no se
enteran solos**: cada uno es un repositorio aparte y su copia del método salió
de aquí por copia de ficheros. Un `git pull` allí trae el historial de *ese*
proyecto; del método, nada.

Para repartirlo, baja lo último aquí (`git pull`), abre tu agente en esta
carpeta y dile: «pon al día mis proyectos». Hará esto:

```text
python3 visor/actualizar.py buscar            # los encuentra y los recuerda
python3 visor/actualizar.py revisar --todos   # te enseña qué cambiaría en cada uno
python3 visor/actualizar.py aplicar --todos   # lo aplica, cuando tú lo digas
```

Las garantías, que son lo importante:

- **Se te enseña antes de tocar nada.** `revisar` no escribe.
- **No se pisa lo que tú hayas adaptado.** Si en un proyecto cambiaste una regla
  del método a propósito, se queda como está y te lo señala para que decidas tú.
- **No se actualiza un proyecto con trabajo a medias**: primero se cierra.
- **Solo se toca el método.** Tus planos, tu trabajo, `repos.yaml` y tu código
  (`main/`) están fuera de alcance, y nada se borra nunca por sobrar.
- **La trazabilidad nueva entra en observación.** La actualización guarda en
  `LEGACY.json` las unidades y ramas anteriores; no inventa peticiones históricas.

La memoria de qué proyectos tienes vive en `.ingenieria-requisitos-local/`, está
ignorada por Git y no se sube a ningún sitio. Si tus proyectos están en una
carpeta rara: `python3 visor/actualizar.py buscar --en /donde/estan`.

## Reglas de oro

- Tú nunca redactas: cuentas y corriges leyendo.
- Si algo cambia después, se cambian los planos y se regenera; nunca le
  pidas cambios "de palabra" a la IA que construye.
- La validación final es usar la aplicación con los ejemplos reales de tus
  planos, no mirar pantallas bonitas.

## Licencia

MIT: úsalo, cópialo y adáptalo con libertad.
