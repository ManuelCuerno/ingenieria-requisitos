# Proceso nativo del meta-repo

Este documento es la fuente canónica del proceso de trabajo. El meta-repo no instala ni
invoca skills, plugins o playbooks externos para brainstorming, planificación, debugging,
TDD, revisión o cierre. Esas capacidades viven aquí, en los runbooks, las plantillas y los
scripts versionados del proyecto.

## Una sola cadena de autoridad

1. La petición persistente conserva lo que pidió el usuario.
2. La ficha canónica de la unidad contiene el diseño conversado, el contrato y el plan.
3. `unidad.py` comprueba aprobación, alcance, carril y worktree antes de construir.
4. La implementación produce evidencia ligada a ese contrato.
5. Un revisor fresco contrasta el diff y la evidencia contra la misma ficha.

No se crea una segunda spec en `docs/superpowers/`, ni un plan paralelo en una carpeta del
harness. Si una herramienta propone otro artefacto de proceso, se traduce a la ficha canónica
o se descarta; nunca compiten dos verdades.

## Antes de construir una feature

El padre conversa con el usuario sobre el problema y las restricciones, inspecciona el sistema
existente, presenta opciones con sus costes y recomienda una. La decisión y las alternativas
descartadas se escriben en `especificacion.md`. Después completa criterios, límites,
verificación y tareas. Solo entonces enseña el contrato completo al usuario y registra su
aprobación. Ningún constructor —humano, agente o subagente— se lanza antes.

## Al depurar

Se trabaja como un bucle semántico, no como una búsqueda de palabras: observación demostrada,
hipótesis falsable, experimento que la discrimina y conclusión. Primero se reproduce el síntoma
y se aísla la causa; después se implementa. El mismo test debe verse rojo antes del arreglo y
verde después. Si la causa no está demostrada, el bug sigue en diagnóstico.

## Skills técnicas permitidas

Las skills técnicas o de dominio sí pueden usarse cuando aporten conocimiento específico
(por ejemplo, Vue, una nube, documentos o una API). No pueden introducir su propio ciclo de
spec/plan/review, crear artefactos canónicos alternativos, cambiar de worktree ni relanzar un
proceso de agentes. El proceso lo gobierna siempre este meta-repo.

## Coste proporcional

- Exprés y directo los construye el padre: no se añade un LLM constructor.
- Normal y completo pueden delegarse cuando el contrato ya está cerrado.
- La revisión fresca es independiente, pero no repite el diseño ni reescribe el plan.
- Las pruebas se eligen por riesgo; las matrices pesadas se reservan para cambios de alto
  impacto o ejecución programada.

## Caja negra

Lo inesperado se registra con `scripts/caja_negra.py registrar` (con `--severidad` cuando no
sea una nota). El JSONL guarda contexto de ejecución y referencias de evidencia, no
conversaciones completas. `listar` lo repasa y `validar` comprueba que sigue bien formado.
El análisis posterior lo hace un LLM leyendo episodios completos y el código relacionado; el
registro estructurado solo evita perder el contexto o confundir repositorios. Si el usuario
quiere, `enviar` comparte los incidentes —redactados y previa confirmación— con el autor del
método para mejorarlo: es siempre voluntario.
