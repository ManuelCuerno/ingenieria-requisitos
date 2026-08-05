# ADR-006 — Un bug es una ficha viva

## Decisión vigente

Cada bug usa un número compartido con las unidades y una ficha
`docs/bugs/NNN-slug.md`. La ficha conserva reporte, severidad, triaje, reproducción,
salida roja, causa, arreglo, salida verde, revisión, validación humana y cierre.

El trabajo se realiza en rama y worktree propios. Empieza reproduciendo el síntoma,
termina en una pull request revisada y no se considera cerrado hasta que la persona
prueba la aplicación real. La ficha no se archiva ni se borra: permanece como
historial operativo y se reabre si el defecto vuelve.
