# ADR-005 — Contrato y plan en una única especificación

## Decisión vigente

Cada unidad normal o completa vive en
`docs/05-trabajo/NNN-slug/especificacion.md`. Ese único documento contiene contexto,
alcance, criterios comprobables, límites, archivos que posee, deltas al mapa, plan de
pasos y forma de verificación. No existe un `tareas.md` paralelo.

La persona aprueba la especificación con fecha antes del despacho. El linter y
`unidad.py` bloquean plantillas vacías, contratos sin plan o unidades sin aprobación.
La fase 5 especifica; la fase 6 construye en el worktree de la unidad.
