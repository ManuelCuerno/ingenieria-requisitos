# ADR-025 · El trabajo aparcado no bloquea el Modo D

**Fecha:** 2026-08-05 · **Estado:** aceptada · Supera el bloqueo por fichas en vuelo de ADR-023

## Contexto

La primera actualización de campo bloqueó todos los proyectos del usuario: un workspace vivo
tiene casi siempre alguna unidad `en_obra` o `en_revision` aparcada, y ADR-023 hacía de ese
estado un motivo de «NO TOCO NADA». El bloqueo quería impedir que Modo D absorbiera o pisara
trabajo ajeno, pero ese riesgo ya lo cierran piezas que siguen vigentes: el lease de
`workspace` excluye a cualquier sesión viva, el punto de retorno exige árbol e índice
limpios, el stage exacto solo incorpora las rutas que la operación calculó y un cambio ajeno
detectado durante la copia aborta. Una unidad aparcada no mantiene lease ni ensucia el árbol:
solo declara un estado en su ficha. El resultado real del bloqueo era que un workspace con
vida normal resultaba inactualizable — y quien descarga la herramienta se estrena con un
«todo bloqueado».

## Decisión

`actualizar.py aplicar` no bloquea por trabajo en vuelo. Avisa con la lista exacta de
unidades y aplica. La actualización sigue sin tocar `docs/05-trabajo`, `main/` ni
`worktrees/`: el trabajo aparcado queda intacto.

Siguen bloqueando, sin cambio: árbol o índice sucios, remoto adelantado, lease vivo de otra
sesión y cualquier cambio ajeno que aparezca en las rutas de la operación.

## Límites

El aviso no congela reglas: una unidad aparcada cerrará ya con el método actualizado. Si un
gate cambió entre medias, se descubre en el cierre — el HISTORIAL y el salto de versión dicen
desde cuándo. Ese coste se acepta: es menor que dejar workspaces enteros fuera de las mejoras
del método, incluidas las de seguridad, hasta que no quede nada en vuelo.
