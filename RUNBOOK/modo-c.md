# RUNBOOK/modo-c.md — Protocolo de iteración

> Módulo de `RUNBOOK.md` (el router). Se lee junto con `RUNBOOK/comun.md` cuando
> el modo es C: hay planos previos y el usuario trae un cambio.

## Protocolo de iteración (modo C)

Lo primero, cosecha el buzón: si en la carpeta del proyecto hay
`preguntas-del-constructor.md` o `desviaciones.md`, incorpora sus puntos al
bloque `preguntas` de `planos.json` ANTES de tocar nada, para que no se
pierdan al regenerar el spec. Si en la carpeta de trabajo hay varios
proyectos, pregunta al usuario cuál es, listándolos.

Cuando el usuario vuelva con cambios ("los clientes ahora también piden por
WhatsApp"), no parchees: localiza en qué bloque de `planos.json` impacta,
pregunta lo mínimo necesario, actualiza los planos, regenera `spec.md` y
enséñale en la web solo lo que cambió. Si el cambio trae puntos calientes
nuevos (reglas, dinero, excepciones), pide ejemplos con datos reales igual
que en F2. Si toca quién entra o qué puede hacer, actualiza superficie y
matriz.

El `estado` de cada recorrido ("pendiente", "en construcción", "entregado")
lo cambias tú en los planos cuando el usuario confirme el avance; el
constructor nunca toca los planos.

Los planos son la única fuente de verdad: la obra se regenera a partir de
ellos, y los cambios nunca se le piden al agente constructor de palabra.
