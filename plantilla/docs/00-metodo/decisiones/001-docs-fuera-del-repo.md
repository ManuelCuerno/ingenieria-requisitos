# ADR-001 — Meta-repositorio separado del código

## Decisión vigente

El workspace `<proyecto>-agents` es el repositorio padre. Guarda planos, contratos,
estado, investigación, decisiones y método. `main/` es un clon independiente del
repositorio hijo y contiene únicamente el producto. El padre ignora `main/` y
`worktrees/`; nunca fija el hijo a un commit concreto.

Cada unidad se construye en una rama y un worktree propios del repositorio hijo. El
constructor de código no modifica el contrato que sirve para juzgar su trabajo. El
padre revisa, integra y actualiza los documentos compartidos durante el cierre.

## Motivo

Separar contrato y obra evita que un agente cambie la vara de medir para aparentar
que ha terminado. También permite mover, publicar y actualizar ambos repositorios de
forma independiente y conserva una trazabilidad clara mediante commits y pull
requests.
