# ADR-002 — Bootstrap desde Ingeniería de Requisitos

## Decisión vigente

Ingeniería de Requisitos y su plantilla son la fuente del workspace. El workspace
nace al principio de la entrevista y se completa en el mismo lugar; no se crea una
segunda copia al terminar. Los `planos.json` aprobados viajan como fuente canónica.

El bootstrap genera dos repositorios Git independientes, copia únicamente el
manifiesto explícito del método, prepara `main/`, `worktrees/`, `.private/` y
`.runtime/`, y ejecuta sus validaciones. `setup.py` reconstruye el entorno en otro
ordenador y deja `main/` en la última versión disponible de `origin/main`, sin
anclarlo a un commit del padre.

Con la misma plantilla y los mismos planos deben obtenerse los mismos archivos. Si
falta o sobra una pieza en el manifiesto del método, el bootstrap se detiene.
