# ADR-022 · El cwd y el sandbox los impone un control plane

**Fecha:** 2026-08-05 · **Estado:** aceptada

## Contexto

Decir «trabaja solo en el worktree» no cambia el directorio del proceso. En Aurora un
constructor nació en `main/`, recibió fish como shell declarado pero ejecutó zsh y una variable
vacía convirtió `$SCRATCH/mut048` en `/mut048`. En otra incidencia, el padre intentó abrir el
bug 065 desde `main/` y una ruta relativa buscó el método dentro del repo de código.

Los plugins y skills instalados añaden otra entrada invisible: una skill de proceso puede
reemplazar el método aunque el prompt no la nombre. El sandbox opcional anterior tampoco era
una puerta: hacía dry-run por defecto y ofrecía un bypass explícito.

## Decisión

`scripts/ejecucion.py` es el único launcher de constructores delegados y revisores. Recibe una
unidad, no una ruta: deriva `worktrees/NNN-slug`, comprueba el inventario Git, la rama, el
estado y el carril, fija `cwd`/`PWD`, sanea el entorno y ejecuta argv directos, nunca
`/bin/sh -c`.

Antes de lanzar ejecuta dentro del mismo sandbox un probe negativo y positivo. Sin mecanismo,
gitdir inequívoco o evidencia conforme se niega a continuar; no existe flag de bypass. Cada
ejecución deja en `.runtime/ejecuciones/` un recibo `ejecucion/v1` con checkpoints de identidad,
sandbox y harness. El ejecutable de aislamiento se elige de rutas fijas del sistema
(`/usr/bin/sandbox-exec` en macOS, `/usr/bin/bwrap` en Linux, antes de cualquier `srt`), se
rechaza si es symlink, no pertenece a root o es escribible por grupo/otros, y el recibo
conserva ruta y SHA-256. Un `srt` que solo aparece antes en `PATH` no es candidato. El
launcher mantiene además leases de unidad y recursos durante toda la ejecución; el recibo
incluye su fencing y HEAD/diff Git inicial y final.

Claude se abre en safe mode. Codex recibe HOME/CODEX_HOME efímeros y no carga configuración ni
reglas de usuario. Las skills de proceso conocidas se rechazan siempre; una skill técnica solo
entra mediante `--skill-tecnica` explícito y se incorpora al encargo como texto visible. Su
`SKILL.md` debe ser un fichero real bajo la raíz de skills, sin aliases/symlinks, y el nombre
canónico de su frontmatter debe coincidir con el solicitado y no pertenecer al proceso.

Exprés y directo no usan este launcher para construir: sigue trabajando el padre, sin pagar un
LLM adicional. El revisor fresco sí se lanza con `--rol revisor`.

## Límites

El revisor conserva la única excepción que exige el cierre: puede firmar el `hallazgos.md` de
su unidad (o la ficha del bug), pero no escribir código ni otros documentos.

El `.git` común queda read-only. Si el Git de la máquina necesita escribir objetos o refs allí
para commitear, el constructor termina con cambios sin commit y el padre, tras leer el recibo,
hace commit/push fuera del sandbox. Abrir todo el common dir rompería el aislamiento entre
worktrees; el P0 prefiere fallar cerrado.

El launcher garantiza el cwd inicial y la frontera de escritura, no prohíbe que el proceso haga
`cd` después. La clasificación semántica de una skill desconocida es imposible: pedir una skill
técnica es una decisión de confianza explícita. Seatbelt está deprecado y Seatbelt/bwrap no
filtran red por dominio; código hostil o exfiltración requieren `srt` o aislamiento administrado.
Actualizar Claude o Codex exige repetir el smoke de compatibilidad de sus flags.

Ruta, owner, permisos y digest no son por sí solos una attestation frente a otro proceso del
MISMO UID del wrapper capaz de reescribirlo entre validación y `exec`. Por eso el flujo normal
solo acepta binarios de root; cualquier fixture o despliegue userland necesita una frontera
administrada por otro principal y no puede presentarse como equivalente.
