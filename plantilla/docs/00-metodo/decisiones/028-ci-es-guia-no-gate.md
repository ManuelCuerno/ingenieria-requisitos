# ADR-028 · El contrato de CI es guía, no gate: aplica ADR-026 a este control concreto

**Fecha:** 2026-08-17 · **Estado:** aceptada · Aplica ADR-026 al check de CI de `lint_metodo.py`

## Contexto

Petición P-20260817-76ef6880: 5 unidades no pudieron cerrarse en este workspace porque
`lint_metodo.py` (sección "7b") hacía `fail()` cuando el repo de código no tenía el
contrato de CI materializado — o cuando un plano declaraba `pruebas_e2e` y faltaban
`scripts/ci/e2e`/`scripts/ci/provision-e2e`. Quien construye con este método no debe verse
forzado a montar CI de ningún tipo —ni GitHub Actions ni ningún otro— para poder cerrar: si
solo quiere correr su suite de tests en local, eso debe bastar.

ADR-026 ya resuelve esto con una sola pregunta: ¿el control evita daño irreversible (perder
trabajo, pisar producción, filtrar secretos, absorber cambios ajenos)? La ausencia de CI no
hace ninguna de las cuatro cosas. Por la propia regla de ADR-026, este check nunca debió ser
un `fail()`; quedó sin reclasificar cuando se escribió ADR-026. Esta unidad completa esa
aplicación, no la revierte.

## Decisión

En `lint_metodo.py`, sección "7b", la llamada `fail("la materialización del CI está
incompleta; ...")` pasa a `warn(...)`, con el mismo mensaje y la misma guía de arreglo. La
rama `elif presentes_ci: ok(...)` no cambia: un CI ya materializado y completo sigue en OK.

`lint_ci.py` NO se modifica: sigue siendo el validador estricto que comprueba que el CI, si
alguien decide montarlo, esté bien formado (sin placeholders, sin `||` que convierta un rojo
en verde, acciones ancladas por SHA…). Deja de ser obligatorio para poder cerrar, pero sigue
siendo la misma herramienta de calidad para quien lo use — a mano o desde el aviso.

Caso límite: si `lint_ci.py` no puede ejecutarse (falta el propio script, o el repo de código
no existe / no es un repositorio git), `lint_metodo.py` avisa (WARN) y sigue el resto de la
ronda de lint, en vez de saltarse la comprobación en silencio o abortar.

## Consecuencias aplicadas

- `unidad.py cerrar` deja de revertir cierres por esta causa: el código de salida agregado de
  `lint_metodo.py` ya no incluye este FAIL, así que basta con que el resto de puertas (tests
  en verde, revisión firmada, OK del usuario) estén en orden.
- Quien SÍ quiera materializar su CI conserva exactamente el mismo detalle de qué falta o qué
  está mal formado, corriendo `lint_ci.py` a mano o leyendo el WARN.
- `AGENTS.md` no cambia: no menciona el contrato de CI como regla dura, así que no hay texto
  que corregir ahí.

## Límites

Esto no relaja ningún otro gate de cierre: revisión LIMPIA, OK del usuario, tests en verde y
worktree sin cambios pendientes siguen siendo duros, porque sí protegen contra daño
irreversible. Tampoco borra ni debilita `lint_ci.py` como herramienta de validación de
calidad para quien decida montar CI.
