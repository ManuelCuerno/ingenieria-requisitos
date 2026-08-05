# ADR-008 — Arranque documentado de roles operativos

> **Nota (2026-08-05):** el plano de deploy se llama hoy `docs/conocimiento/plano-deploy.md`
> — es el nombre que exigen `scripts/lint_deploy.py` y el bootstrap. Donde abajo dice
> `plano-despliegue.md`, léase ese fichero.

## Decisión vigente

La primera sesión de OBSERVABILITY entrevista a la persona y deja
`docs/conocimiento/plano-observabilidad.md`. La primera sesión de DEPLOY hace lo
mismo en `docs/conocimiento/plano-despliegue.md`. Se registran lugares, comandos,
señales, responsables, etapas, copia, restauración y vuelta atrás con evidencias
reales.

Cuando existe una aplicación, los datos desconocidos se investigan en modo de solo
lectura. Si falta una capacidad necesaria, se abre una unidad; el rol operativo no
la improvisa. Nunca se guardan credenciales en los planos. Las sesiones posteriores
releen el documento y lo actualizan cuando detectan una desviación comprobada.
