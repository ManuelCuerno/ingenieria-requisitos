# ADR-021 · El meta-repo gobierna el proceso y conserva incidentes estructurados

- **Estado:** aceptada
- **Fecha:** 2026-08-05

## Contexto

Los historiales reales mostraron specs y planes duplicados, worktrees creados dentro del
meta-repo, sesiones que ejecutaban desde una raíz distinta a la prometida y diagnósticos que
saltaban a una solución sin conservar la cadena de evidencia. Las skills generalistas de
proceso solapan los runbooks y añaden otra autoridad; las skills técnicas no tienen ese
problema si se subordinan al contrato local.

## Decisión

Brainstorming de features, planificación, debugging, TDD proporcional, revisión y cierre pasan
a ser capacidades nativas del método. Existe una sola ficha canónica por unidad y el despacho
ocurre después de su aprobación. No se distribuyen ni se invocan skills de proceso externas.
Las skills técnicas siguen permitidas sin autoridad para alterar el ciclo ni el workspace.

Los incidentes se escriben además en `.caja-negra/incidentes.jsonl` mediante un comando
versionado. Cada episodio lleva raíz declarada y real, cwd, worktree, rama, harness, sesión,
fase, síntoma, esperado, observado y referencias relativas de evidencia. El comando redacta
secretos y rechaza referencias fuera del repo. La interpretación continúa siendo semántica y
LLM: no se sustituyen conversaciones por regex ni se emiten conclusiones automáticas.

## Consecuencias

- Desaparece la doble fuente `docs/superpowers` frente a la unidad.
- Un cambio pequeño no gana otro agente ni otra fase.
- Los fallos de raíz/cwd dejan evidencia comparable sin copiar datos sensibles.
- Las actualizaciones del método distribuyen la política y el registrador a los workspaces.
