# ADR-017 · Quién construye lo dice el carril (la regla 1, acotada)

**Fecha:** 2026-08-03 · **Estado:** aceptada · **Modifica:** la regla dura 1

## Contexto

La regla 1 decía, sin excepción: *"el agente padre trabaja SOLO en este meta-repo y jamás escribe
código"*. Todo el código lo hacía un subagente constructor en un worktree aparte.

Esa regla tenía una razón buena —los documentos que juzgan la obra viven fuera del alcance de
quien construye— pero se aplicaba igual a un cambio de dos ficheros que a una migración. Y para
el trabajo pequeño el precio resultó ser el problema del usuario, no una molestia teórica:

**1. La delegación es lo que produce la caja negra.** Un subagente devuelve *"only a condensed,
distilled summary"* y quien delegó *"can't steer subagents"* — está declarado por el fabricante.
No es un fallo del método: es el contrato de delegar. Los 40 minutos a ciegas de ADR-016 son, en
su mayor parte, esto.

**2. Cuesta dinero medible.** La caché de prompt está acotada por directorio, *"y eso incluye los
worktrees"*: un constructor en worktree **nunca** acierta la caché del padre. Cada delegación
paga ~7.850 tokens fijos y todas sus lecturas a precio completo en vez de al 10%.

**3. Cuatro fuentes independientes dicen que para trabajo pequeño no se delega.** OpenAI
(*"maximize a single agent's capabilities first… often a single agent with tools is sufficient"*
y *"subagent workflows consume more tokens than comparable single-agent runs"*), Microsoft
(*"Don't assume role separation requires multiple agents"*), AWS (*"Still avoid swarms… one
disciplined reasoning loop"*) y Anthropic (multiagente ≈ 15× tokens).

Además, ADR-014 había resuelto mal un problema derivado: para ahorrar un contexto puso al padre a
revisar en el carril directo, lo que chocaba con la plantilla de hallazgos —que prohíbe
expresamente que el padre firme— y dejaba el carril del día a día sin poder cerrar.

## Decisión

**Quién construye lo dice el carril:**

| Carril | Construye | Revisa |
|---|---|---|
| exprés · **directo** | **el padre**, en el worktree de la unidad, a la vista del usuario | agente fresco de solo lectura |
| normal · completo | subagente constructor en su worktree | agente fresco de solo lectura |

> **Nota (2026-08-05):** en exprés no hay revisor — su única puerta es el verde del área tocada (`runbooks/cierre.md`, `README.md` §Lo que cuesta cada carril); la fila de arriba aplica al carril directo.

**El revisor vuelve a ser SIEMPRE fresco.** Esto no es una concesión: es más fuerte que lo que
ADR-014 dejó. Al construir el padre, la revisión ya no puede recaer en él, así que la garantía
"quien revisa no construyó" se cumple sola, sin excepciones que documentar.

El aislamiento se conserva: el trabajo sigue ocurriendo en `worktrees/NNN-slug/`, en su rama, con
su PR. Lo que cambia es **quién teclea**, no dónde.

## Consecuencias

- El carril del día a día deja de ser una caja negra: el usuario ve el trabajo en la misma
  conversación donde lo pidió, y puede cortar en el minuto tres.
- Se ahorra el salto de contexto y el fallo de caché en la parte cara (construir), y se paga solo
  en la barata (revisar un diff pequeño).
- **Coste asumido:** el padre carga con el código en su contexto durante la construcción. Es
  aceptable precisamente porque el carril directo está acotado a 1-3 ficheros y menos de 250
  líneas de diff; si crece, la escalada manda re-abrirlo por `feature.md`, donde vuelve a
  delegarse.
- La regla 2 (quién escribe qué) sigue intacta: los ficheros compartidos los escribe solo el
  padre en el cierre, y quien construye toca su worktree, `hallazgos.md` y sus casillas.
- **Cómo se revierte:** devolver la regla 1 a su forma anterior y quitar el paso 3 de
  `runbooks/directo.md`. El resto del método no depende de esta decisión.
