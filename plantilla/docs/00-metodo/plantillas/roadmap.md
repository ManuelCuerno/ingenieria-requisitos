# ROADMAP — qué vamos a construir y por qué (fase 4; solo lo escribe el padre)

> Estructura FIJA, siempre igual: resumen → motivos de cada decisión → tabla comparativa →
> plan de construcción. Todo en lenguaje sencillo, sin jerga (Barrio Sésamo).
> Sin NNN: el número se asigna al despachar. El estado vivo NO vive aquí (ESTADO.md).

## Resumen

<5 líneas máximo: qué se construye, con qué tecnología y por dónde se empieza.
Para leerlo en 30 segundos y enterarse de todo.>

## Decisiones y sus motivos

### <decisión: p. ej. "con qué se hace la web">

- **Elegido:** <opción> — <por qué, explicado en cristiano>
- **Descartado:** <opción> — <por qué no>
- **Decidido por:** <el usuario, YYYY-MM-DD> <· ADR-NNN si fue gorda>

### Entorno de ejecución y testing local

<decisión que SIEMPRE debe existir: ¿Docker/compose o directo sin Docker? En brownfield NO se
decide: se DESCUBRE de `main/` y se copia de `03-investigacion/SINTESIS.md` — `runbooks/adopcion.md`
regla 5; solo se abre decisión si está roto o falta.>

- **Elegido:** <opción> — <por qué, explicado en cristiano>
- **Descartado:** <opción> — <por qué no>
- **Decidido por:** <el usuario, YYYY-MM-DD> <· ADR-NNN si fue gorda>
- **Comandos resultantes:** escritos en el AGENTS.md del repo de código
  (levantar · test · e2e · instancia)

## Tabla comparativa

| decisión | elegido | alternativa descartada | por qué gana |
|---|---|---|---|
| <decisión> | <opción> | <opción> | <una frase> |

## Plan de construcción

### Esqueleto andante (lo primero que se construye)

<la cadena mínima de actividades que atraviesa el sistema de punta a punta, en 1-2 frases>

### Módulos que se tocan (y por qué NO se duplica)

<Rellenado con lo buscado en `main/` en el paso 2 de `runbooks/planificacion.md`: no se
duplica código ni responsabilidades. Una fila por módulo YA existente al que se le encaja
trabajo, y una por módulo nuevo justificando por qué ninguno existente era su sitio.>

| módulo (ruta en `main/`) | ¿existe ya? | qué se le encaja | por qué ahí y no duplicado |
|---|---|---|---|
| `<ruta>` | sí | <funcionalidad> | <ya es el dueño de esa responsabilidad; se refactoriza X> |
| `<ruta nueva>` | no | <funcionalidad> | <ningún módulo existente es su sitio: <motivo>> |

**Principios que manda este plan** (innegociables, ver `runbooks/planificacion.md` paso 2):
Single Responsibility · KISS · clean code · encapsular por funcionalidades con capas de
abstracción · los módulos se comunican entre ellos. **Prioridad nº 1: discovery de código
barato en tokens — una funcionalidad vive en SU módulo, no desperdigada por la app.**

### Tanda actual (en orden)

| # | unidad (slug tentativo) | tipo | actividad | depende de | abierta como |
|---|---|---|---|---|---|
| 1 | <slug> | feature | <id del INDICE> | — | — |

### Siguientes (sin trocear: una línea cada una)

- <idea>: <frase>

### Entregado

- <NNN-slug> — YYYY-MM-DD

### Descartado (con porqué, para no re-proponer)

- —
