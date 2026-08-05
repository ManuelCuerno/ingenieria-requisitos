# ADR-018 · El CI real nace con el stack y producción se revalida

**Fecha:** 2026-08-04 · **Estado:** aceptada

## Contexto

El bootstrap creaba un workflow Python antes de saber si el proyecto usaría Python, Node,
Go u otra cosa. Podía terminar verde sin configuración de Ruff, sin tests y sin haber
instalado correctamente el proyecto: no era una red de seguridad, era un verde falso.

En el otro extremo, el gate de despliegue comprobaba que el camino estuviera escrito, pero no
ejecutaba la suite del commit que iba a producción. Entre el último test y el deploy podía
haber cambiado `main` sin que la puerta lo detectara.

## Decisión

1. El repositorio vacío nace solo con README y protección de secretos. Sin stack no se
   presuponen tests, linters ni gestor de paquetes.
2. La primera unidad del esqueleto, ya con el stack decidido, crea y prueba tres interfaces:
   `scripts/ci/full-suite`, `scripts/ci/lint` y `scripts/ci/security`; los workflows `tests` y
   `quality-security`; y el Dependabot del gestor real.
3. En brownfield, la adopción sigue siendo de solo lectura. La primera unidad técnica
   posterior materializa esas piezas reutilizando los comandos descubiertos, antes de tocar
   comportamiento.
4. Pull requests bloquean con `tests` y `quality-security`. Al entrar en la principal se
   repiten lint y seguridad; el análisis profundo se programa semanalmente.
5. Dependabot propone actualizaciones ordinarias. Una vulnerabilidad conocida devuelve rojo;
   no se bloquea solo porque exista una versión más nueva.
6. Las Actions externas se fijan por SHA y ningún control puede esconder un fallo con
   `|| true`.
7. Antes de desplegar, `lint_deploy.py` ejecuta la suite completa y seguridad sobre el commit
   exacto de `main/`, guardando el output en `.runtime/`.

## Consecuencias

- El desarrollo local no paga escáneres en cada guardado: el coste vive en PR, principal,
  despliegue y la revisión semanal.
- La primera unidad cuesta algo más, una sola vez; a cambio, toda unidad posterior hereda
  comandos reales y repetibles.
- Un stack sin receta no obtiene un verde genérico: debe declarar y probar su propia receta.
- GitHub protege automáticamente cuando el plan lo permite; sin protección remota, el mismo
  contrato se ejecuta localmente durante el cierre.
