# Control plane obligatorio de ejecución

`scripts/ejecucion.py` es la única entrada para lanzar constructores delegados y revisores.
Recibe el ID de unidad y deriva el worktree y la rama: nunca se le pasa un cwd ni un comando
arbitrario.

## Flujo

1. Crea y despacha la unidad mediante `unidad.py`; su salida da los comandos exactos para
   Claude y Codex.
2. Elige harness, rol y, si hace falta, cada `--skill-tecnica` explícita.
3. El launcher verifica unidad, estado, carril, worktree, rama, gitdir, cwd y PWD.
4. Fija el ejecutable del sandbox en una ruta del sistema propiedad de root (ignora `PATH`),
   rechaza symlinks/permisos inseguros y ejecuta
   un probe. Solo si demuestra que el límite muerde arranca el harness y deja el recibo bajo
   `.runtime/ejecuciones/`, con digest del wrapper, fencing y estado Git inicial/final.

Mecanismos por plataforma, en el orden real del código: en macOS, `sandbox-exec` (Seatbelt) y
después `srt`; en Linux, `bwrap` y después `srt`. Un `srt` que no sea propiedad de root se
rechaza (`EXIGIR_OWNER_SISTEMA`): un binario que puede reemplazar el mismo usuario no es una
frontera. Consecuencia honesta: en un macOS típico el mecanismo será Seatbelt, cuyo perfil NO
limita la red. Si no encuentra ningún mecanismo se niega a ejecutar. No hay bypass ni modo que
solo imprima un perfil.

## Windows: el camino oficial es WSL2

Windows nativo no tiene ningún mecanismo con paridad (AppContainer rompe toolchains de
desarrollo, los restricted tokens y los integrity levels no confinan filesystem ni red, Windows
Sandbox no existe en Home, y `srt-win` sigue en alpha con breaking changes). No se implementa
sandbox nativo Windows por eso: el lanzador se niega a ejecutar en `win32` y ese bloqueo se
queda como está.

El camino soportado es **WSL2**: el kernel oficial de Microsoft para WSL2 compila
`CONFIG_USER_NS=y` y no trae AppArmor, así que los user namespaces sin privilegios que
`bubblewrap` necesita funcionan sin ajuste alguno — dentro de WSL2, `sys.platform` es `"linux"`
y el `bwrap` de `apt` pasa la misma acreditación que en Linux nativo. WSL1 no vale (no hay
kernel Linux real). Condiciones operativas: workspace y home en el disco de WSL (nunca en
`/mnt/c`: ahí el rendimiento cae, los locks de flock fallan y los permisos se corrompen en
silencio), sin symlinks hacia `/mnt/c` en rutas que el sandbox monte. Verificación de 30
segundos: `wsl -l -v` debe decir `VERSION 2`, y deben pasar `unshare -Ur true` y
`bwrap --ro-bind / / true`. Si falta `bwrap`, `sudo apt install bubblewrap`.

## Límites ejecutables

- Constructor: escritura en el worktree, su gitdir, los dos documentos exactos de su unidad
  (spec + hallazgos; en bugs, la ficha) y un TMP privado 0700.
- Revisor: TMP privado y únicamente la firma derivada de su unidad (`hallazgos.md`, o la ficha
  si revisa un bug); el repo de código permanece read-only.
- Bloqueo de los puntos de configuración y hooks compartidos de Git.
- Bloqueo de lectura de directorios habituales de credenciales.
- Red denegada o limitada cuando el mecanismo puede aplicarlo realmente.

El `.git` común permanece de solo lectura. Si una versión de Git no puede commitear con ese
límite, el launcher falla cerrado: no existe una opción para ensanchar todo el repositorio
compartido. En ese caso el constructor deja cambios y evidencia; el padre inspecciona el recibo
y hace commit/push desde el worktree fuera del sandbox. Es un límite deliberado: un commit de
worktree escribe objetos y refs en el `.git` común, que no se puede abrir sin exponer ramas de
otras unidades.

Claude se ejecuta en safe mode y Codex con HOME efímero. Plugins, hooks, MCP y skills instalados
no deciden el proceso. Solo una skill técnica pedida por nombre se incorpora al encargo; las
skills de proceso conocidas se rechazan incluso si se solicitan. No se siguen symlinks ni aliases:
el nombre declarado en el frontmatter de `SKILL.md` debe coincidir con el solicitado.

Para código hostil o ejecución desatendida se necesita además una frontera administrada por el
dueño de la máquina. Seatbelt está deprecado y ni Seatbelt ni bwrap filtran red por dominio;
esa garantía solo la da un `srt` propiedad de root o un contenedor con política de red
validada — y en su ausencia este método NO promete red limitada: lo dice el recibo de la
ejecución, no lo disimula.
La ruta y el SHA-256 no protegen frente a un atacante con el mismo UID que pueda sustituir el
wrapper justo antes de `exec`; ese caso necesita aislamiento administrado por otro principal.
