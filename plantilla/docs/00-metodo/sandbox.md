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
