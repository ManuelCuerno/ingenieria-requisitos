# ADR-004 — Adopción brownfield y doctrina de comprobaciones

## Decisión vigente

Antes de cambiar una aplicación existente se cartografían su estructura, comandos
reales, tecnologías, flujos observables, datos, estados, permisos, integraciones y
pruebas. El resultado queda en `03-investigacion/ADOPCION.md` junto al mapa de
diferencias entre el presente y los planos aprobados.

El código original no se modifica durante la adopción. Se clona o copia en `main/`,
que sigue siendo un repositorio hijo de solo producto. Si no existe una red fiable
de pruebas, crear la línea base necesaria es el primer trabajo antes de alterar el
comportamiento.

Las features y los bugs demuestran primero la ausencia o el fallo con una prueba que
falla por la razón esperada. Después se implementa lo mínimo, se ejecuta la suite
completa y se conserva una prueba de regresión. Un bug se reproduce antes de
arreglarse, salvo la excepción de emergencia definida por el runbook de hotfix.
