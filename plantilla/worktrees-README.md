# worktrees/

Una copia de trabajo del repo de código POR UNIDAD, con el mismo nombre que su carpeta en
`docs/05-trabajo/NNN-slug/` y rama `NNN-slug`. Su contenido está ignorado por git en el meta.

Reglas (las completas, en AGENTS.md):
- Los crea el padre al despachar una unidad; los borra el ritual de cierre (con su rama).
- El constructor escribe SOLO dentro del suyo.
- Un worktree sin unidad activa es un huérfano: `lint_metodo.py` lo detecta como FAIL.

El repo de código y su remoto: ver `repos.yaml` en la raíz.
