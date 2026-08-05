# ADR-007 — Planos canónicos y límites del workspace

## Decisión vigente

Los `planos.json` de `docs/02-flujos/planos/` son la fuente canónica del negocio. El
kit de requisitos viaja en `docs/00-metodo/requisitos/` para validar, visualizar,
aprobar y regenerar esos planos sin depender del repositorio lanzador.

Los secretos viven en `.private/` y el material temporal en `.runtime/`; ambos quedan
fuera de Git. No se usa `git stash` para mover trabajo entre unidades: cada unidad
tiene su worktree. Los defectos pasan por triaje y por su runbook. La investigación y
la planificación deciden el entorno ejecutable adecuado antes de construir.

Los programas auxiliares de aislamiento son apoyos opcionales. No sustituyen los
límites de permisos del sistema ni permiten afirmar una garantía que no se haya
comprobado en la máquina concreta.
