# ADR-026 · Guiar, no bloquear: gate duro solo ante daño irreversible

**Fecha:** 2026-08-12 · **Estado:** aceptada · Reclasifica los gates de ADR-009/013/022 sin retirarlos

## Contexto

El feedback de campo de agosto de 2026 mostró el mismo patrón cuatro veces: un control
pensado para proteger dejaba al usuario parado sin salida. `setup.py` moría si el linter
daba FAIL — también cuando el FAIL lo causaba un bug del propio método (CI sin identidad
git, E2E del visor con timeout) que el usuario tiene PROHIBIDO arreglar en su workspace.
Publicar exigía verde de una comprobación rota por nosotros. Modo D revertía la
actualización entera por fallos que el workspace ya arrastraba o porque el texto de un
check cambió de redacción. Mientras tanto, las protecciones de verdad — no absorber
trabajo sin commitear, no matar procesos ajenos, hacer la adopción brownfield — vivían
solo en prosa, y la prosa se salta.

El propósito del método es guiar a una persona de negocio hasta desplegar. Un control que
la deja atrapada trabaja contra ese propósito, por bien intencionado que sea.

## Decisión

Todo control del método se clasifica con una sola pregunta: **¿evita daño irreversible**
(perder trabajo, pisar producción, filtrar secretos, absorber cambios ajenos)?

- **Sí → gate duro, con salida nombrada.** El mensaje de bloqueo dice siempre qué
  comprobación falló, qué la arregla y cuál es la alternativa segura. Un gate sin salida
  escrita es un bug del método.
- **No → guía.** Se avisa en claro, se registra en la caja negra si es una rareza, y se
  continúa. Proceso, calidad y estilo jamás dejan al usuario parado.

Y una regla transversal: **un rojo cuya causa es el método no bloquea al usuario.** Si el
FAIL viene de `docs/00-metodo/` (no de su proyecto), se registra con `caja_negra.py`,
queda como deuda del método y se sigue trabajando; el arreglo llega por Modo D con la
versión siguiente. El workspace no es el sitio donde se arregla el método (eso no cambia).

## Consecuencias aplicadas

- `setup.py` ya no muere por un FAIL del linter: lo enseña, da la guía (¿tuyo? arréglalo;
  ¿del método? caja negra y sigue) y termina bien.
- Modo D mide antes y después **con el mismo linter** (el nuevo, `--raiz`): un cambio de
  redacción o un check nuevo ya no se disfraza de regresión ni revierte nada. Revertir
  queda solo para fallos que la actualización introduce de verdad.
- La adopción brownfield gana señal ejecutable (ESTADO.md la nombra, el despacho avisa si
  falta `ADOPCION.md`) pero como guía: avisa, no encierra.
- Los procesos ajenos ganan protección real: no se borra un worktree con procesos vivos
  dentro y sondear un lease jamás mata a su dueño.

## Límites

Esta decisión no relaja los gates de daño irreversible: producción, secretos, trabajo sin
commitear y la frontera del revisor siguen siendo duros. Lo que exige es que cada uno
tenga su salida escrita en el mensaje que bloquea.
