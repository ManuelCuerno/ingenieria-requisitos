#!/usr/bin/env python3
"""Control plane fail-closed para lanzar Claude o Codex en una unidad real.

La unidad, el worktree y la rama se derivan; no se aceptan rutas ni argv arbitrarios.
El proceso siempre nace dentro de un sandbox de SO y sin shell intermedia.
"""
import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import control_plane
import lease as gestion_leases
import workspace_paths

control_plane.redactar_salidas()


RAIZ = Path(__file__).resolve().parents[3]
MAIN = RAIZ / "main"
WORKTREES = RAIZ / "worktrees"
ESTADOS_EJECUTABLES = {"en_obra", "en_revision"}
RE_NOMBRE = re.compile(r"^\d{3}-[a-z0-9][a-z0-9-]*$")
RE_SKILL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
SANDBOX_CONFIABLES = {"darwin": (("seatbelt", "/usr/bin/sandbox-exec"), ("srt", "/usr/local/bin/srt")), "linux": (("bwrap", "/usr/bin/bwrap"), ("srt", "/usr/local/bin/srt"))}
EXIGIR_OWNER_SISTEMA = True

# Estas skills deciden el proceso de trabajo. El método ya lo decide y nunca las importa,
# aunque el operador intente incluirlas en la allowlist técnica.
SKILLS_DE_PROCESO = {
    "brainstorming",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "using-superpowers",
    "verification-before-completion",
    "writing-plans",
}

HEREDAR_ENV = {
    "PATH", "TERM", "COLORTERM", "LANG", "LC_ALL", "LC_CTYPE",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "no_proxy", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
    "AWS_REGION", "AWS_DEFAULT_REGION", "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
    # El sandbox bloquea el llavero del SO a propósito: la única autenticación posible
    # dentro es por entorno. Sin estos tres, ni la suscripción de Claude (setup-token)
    # ni git/gh contra GitHub funcionan en el subagente (bug 001, caja negra de campo).
    "CLAUDE_CODE_OAUTH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN",
}


class ErrorEjecucion(Exception):
    pass


def git(cwd, *args):
    resultado = subprocess.run(
        ["git", *args], cwd=str(cwd), text=True, capture_output=True
    )
    return resultado.returncode, (resultado.stdout + resultado.stderr).strip()


def frontmatter(ruta):
    try:
        ruta = workspace_paths.regular_file(RAIZ, ruta, label="ficha de unidad")
    except workspace_paths.WorkspacePathError as exc:
        raise ErrorEjecucion(str(exc)) from exc
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ErrorEjecucion(f"no puedo leer la unidad {ruta}: {exc}") from exc
    if not lineas or lineas[0].strip() != "---":
        raise ErrorEjecucion(f"la unidad {ruta} no tiene frontmatter")
    datos = {}
    clave_abierta = None
    items = []

    def cerrar_lista():
        nonlocal clave_abierta, items
        if clave_abierta and items:
            datos[clave_abierta] = ", ".join(items)
        clave_abierta, items = None, []

    for linea in lineas[1:]:
        if linea.strip() == "---":
            cerrar_lista()
            return datos
        encontrado = re.match(r"^(\w+):\s*(.*)$", linea)
        if encontrado:
            cerrar_lista()
            valor = encontrado.group(2).split("#", 1)[0].strip()
            datos[encontrado.group(1)] = valor
            if not valor:
                clave_abierta = encontrado.group(1)
            continue
        item = re.match(r"^\s+-\s*(.+)$", linea)
        if item and clave_abierta:
            items.append(item.group(1).split("#", 1)[0].strip().strip("'\""))
    raise ErrorEjecucion(f"frontmatter sin cierre en {ruta}")


def recursos_de(datos):
    recursos = set()
    for crudo in (datos.get("ficheros") or "").strip("[]").split(","):
        ruta = crudo.strip().strip("'\"").replace("\\", "/")
        if not ruta:
            continue
        partes = [parte for parte in ruta.split("/") if parte not in {"", "."}]
        if ruta.startswith("/") or ".." in partes:
            raise ErrorEjecucion(f"recurso fuera del repo de código: {ruta}")
        recursos.add("/".join(partes).casefold())
    return sorted(recursos)


def ficha_unidad(nombre, rol=None):
    if not RE_NOMBRE.fullmatch(nombre):
        raise ErrorEjecucion("unidad inválida: se esperaba NNN-slug")
    candidatas = [
        RAIZ / "docs/05-trabajo" / nombre / "especificacion.md",
        RAIZ / "docs/bugs" / f"{nombre}.md",
    ]
    for ruta in candidatas:
        if ruta.exists() or ruta.is_symlink():
            try:
                ruta = workspace_paths.regular_file(
                    RAIZ, ruta, label=f"ficha canónica de {nombre}"
                )
            except workspace_paths.WorkspacePathError as exc:
                raise ErrorEjecucion(str(exc)) from exc
            datos = frontmatter(ruta)
            estado = (datos.get("estado") or "").strip()
            if estado not in ESTADOS_EJECUTABLES:
                raise ErrorEjecucion(
                    f"la unidad {nombre} está en estado {estado or 'vacío'}; "
                    "solo en_obra/en_revision se ejecutan"
                )
            carril = (datos.get("carril") or "normal").strip().lower()
            # Solo el CONSTRUCTOR queda vetado en directo/exprés (regla 1: en esos
            # carriles construye el padre, a la vista del usuario). El revisor fresco
            # sí se lanza por aquí en CUALQUIER carril — la frontera del revisor "no la
            # relaja ningún carril" (ADR-017, ADR-022; bug 002 de campo, ADR-040).
            if rol == "constructor" and carril in {"directo", "expres", "exprés"}:
                raise ErrorEjecucion(
                    f"el carril {carril} lo construye el padre; no se lanza otro LLM"
                )
            return ruta, datos
    raise ErrorEjecucion(f"no existe la ficha canónica de {nombre}")


def inventario_worktrees():
    codigo, salida = git(MAIN, "worktree", "list", "--porcelain")
    if codigo:
        raise ErrorEjecucion(f"no puedo leer el inventario Git de worktrees: {salida}")
    inventario = {}
    actual = None
    for linea in salida.splitlines():
        if linea.startswith("worktree "):
            actual = Path(linea[9:]).resolve()
            inventario[actual] = {}
        elif actual is not None and " " in linea:
            clave, valor = linea.split(" ", 1)
            inventario[actual][clave] = valor
    return inventario


def resolver_worktree(nombre):
    destino = (WORKTREES / nombre).resolve()
    if destino.parent != WORKTREES.resolve():
        raise ErrorEjecucion("el worktree escaparía de worktrees/")
    entrada = inventario_worktrees().get(destino)
    if entrada is None:
        raise ErrorEjecucion(f"{destino} no figura en git worktree list")
    rama_ref = entrada.get("branch")
    if rama_ref != f"refs/heads/{nombre}":
        raise ErrorEjecucion(
            f"rama registrada incorrecta: {rama_ref or 'sin rama'}; se esperaba {nombre}"
        )
    codigo, toplevel = git(destino, "rev-parse", "--show-toplevel")
    if codigo or Path(toplevel).resolve() != destino:
        raise ErrorEjecucion("el destino no es la raíz real del worktree")
    codigo, rama = git(destino, "branch", "--show-current")
    if codigo or rama.strip() != nombre:
        raise ErrorEjecucion(
            f"la rama activa es {rama.strip() or 'detached'}; se esperaba {nombre}"
        )
    dotgit = destino / ".git"
    if not dotgit.is_file():
        raise ErrorEjecucion("el worktree no tiene un gitdir enlazado")
    encontrado = re.match(
        r"gitdir:\s*(.+)", dotgit.read_text(encoding="utf-8").strip()
    )
    if not encontrado:
        raise ErrorEjecucion("no puedo resolver el gitdir del worktree")
    gitdir = Path(encontrado.group(1)).resolve()
    esperado = (MAIN / ".git/worktrees").resolve()
    if gitdir.parent != esperado:
        raise ErrorEjecucion(f"gitdir fuera del repositorio canónico: {gitdir}")
    common = (gitdir / (gitdir / "commondir").read_text(encoding="utf-8").strip()).resolve()
    if common != (MAIN / ".git").resolve():
        raise ErrorEjecucion("commondir no pertenece a main/.git")
    return destino, gitdir, common


def _fichero_skill_canonico(raiz, candidata, nombre_solicitado):
    try:
        relativa = candidata.relative_to(raiz)
    except ValueError as exc:
        raise ErrorEjecucion(
            f"skill técnica fuera de su raíz: {nombre_solicitado}"
        ) from exc
    actual = raiz
    for parte in relativa.parts:
        actual = actual / parte
        if actual.is_symlink():
            raise ErrorEjecucion(
                f"skill técnica {nombre_solicitado} usa un symlink: {actual}"
            )
    try:
        raiz_real = raiz.resolve(strict=True)
        candidata_real = candidata.resolve(strict=True)
        candidata_real.relative_to(raiz_real)
        modo = candidata.lstat().st_mode
    except (OSError, ValueError) as exc:
        raise ErrorEjecucion(
            f"skill técnica fuera de su raíz real: {nombre_solicitado}"
        ) from exc
    if not stat.S_ISREG(modo):
        raise ErrorEjecucion(f"SKILL.md no es un fichero regular: {nombre_solicitado}")
    return candidata_real


def _nombre_skill_declarado(ruta, nombre_solicitado):
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ErrorEjecucion(f"no puedo leer la skill técnica {nombre_solicitado}: {exc}") from exc
    if not lineas or lineas[0].strip() != "---":
        raise ErrorEjecucion(f"skill técnica sin frontmatter: {nombre_solicitado}")
    for linea in lineas[1:]:
        if linea.strip() == "---":
            break
        encontrado = re.match(r"^name:\s*([^#]+?)\s*$", linea)
        if encontrado:
            declarado = encontrado.group(1).strip().strip("'\"")
            if not RE_SKILL.fullmatch(declarado):
                raise ErrorEjecucion(
                    f"nombre canónico inválido en la skill técnica {nombre_solicitado}"
                )
            return declarado
    raise ErrorEjecucion(f"skill técnica sin nombre canónico: {nombre_solicitado}")


def _validar_skill(raiz, candidata, nombre):
    ruta = _fichero_skill_canonico(raiz, candidata, nombre)
    declarado = _nombre_skill_declarado(ruta, nombre)
    esperado = nombre.split(":")[-1]
    if declarado in SKILLS_DE_PROCESO or declarado.split(":")[-1] in SKILLS_DE_PROCESO:
        raise ErrorEjecucion(f"{declarado} es una skill de proceso y está excluida")
    if declarado != esperado:
        raise ErrorEjecucion(
            f"la skill solicitada {nombre} declara otro nombre canónico: {declarado}"
        )
    return ruta


def resolver_skill(nombre, home_original):
    if not RE_SKILL.fullmatch(nombre):
        raise ErrorEjecucion(f"nombre de skill técnica inválido: {nombre}")
    base = nombre.split(":")[-1]
    if nombre in SKILLS_DE_PROCESO or base in SKILLS_DE_PROCESO:
        raise ErrorEjecucion(f"{nombre} es una skill de proceso y está excluida")
    raices = [
        home_original / ".agents/skills",
        home_original / ".codex/skills",
        home_original / ".claude/skills",
    ]
    for raiz in raices:
        candidata = raiz / nombre / "SKILL.md"
        if candidata.is_file():
            return _validar_skill(raiz, candidata, nombre)
    cache = home_original / ".codex/plugins/cache"
    if cache.is_dir():
        coincidencias = sorted(cache.glob(f"**/skills/{nombre}/SKILL.md"))
        if len(coincidencias) == 1:
            candidata = coincidencias[0]
            return _validar_skill(candidata.parent.parent, candidata, nombre)
        if len(coincidencias) > 1:
            raise ErrorEjecucion(f"skill técnica ambigua en plugins: {nombre}")
    raise ErrorEjecucion(f"skill técnica no instalada: {nombre}")


def encargo(nombre, rol, ficha, prompt, skills, home_original):
    partes = [
        f"UNIDAD CANÓNICA: {nombre}",
        f"ROL: {rol}",
        f"CONTRATO: {ficha}",
        "Trabaja únicamente bajo el contrato y los permisos ya impuestos por el launcher.",
    ]
    for nombre_skill in skills:
        ruta = resolver_skill(nombre_skill, home_original)
        partes.extend(
            (
                f"\n--- SKILL TÉCNICA EXPLÍCITA: {nombre_skill} ({ruta}) ---",
                ruta.read_text(encoding="utf-8"),
                f"--- FIN SKILL TÉCNICA: {nombre_skill} ---",
            )
        )
    partes.extend(("\n--- ENCARGO ---", prompt))
    return "\n".join(partes)


def entorno_base(worktree, tmp_privado, home_original):
    limpio = {clave: os.environ[clave] for clave in HEREDAR_ENV if os.environ.get(clave)}
    limpio.update(
        {
            "PWD": str(worktree),
            "TMPDIR": str(tmp_privado),
            "TMP": str(tmp_privado),
            "TEMP": str(tmp_privado),
            "SHELL": "/bin/sh",
            "HOME": str(home_original),
        }
    )
    return limpio


def preparar_codex_home(env, tmp_privado, home_original):
    aislado = tmp_privado / "home"
    aislado.mkdir(mode=0o700)
    origen = Path(os.environ.get("CODEX_HOME", str(home_original / ".codex")))
    auth = origen / "auth.json"
    if auth.is_file():
        shutil.copyfile(auth, aislado / "auth.json")
        (aislado / "auth.json").chmod(0o600)
    env["HOME"] = str(aislado)
    env["CODEX_HOME"] = str(aislado)


def preparar_claude_home(env, tmp_privado, home_original):
    """HOME aislado y escribible para el CLI de claude, simétrico al de codex.

    El HOME real no es escribible dentro del sandbox y el CLI necesita crear su
    estado (~/.claude). La autenticación viaja por entorno (HEREDAR_ENV). Un HOME
    recién creado tampoco tiene credential helper de git: si hay token de GitHub
    y gh está instalado, se deja configurado con `gh auth setup-git`."""
    aislado = tmp_privado / "home"
    aislado.mkdir(mode=0o700)
    env["HOME"] = str(aislado)
    # La identidad de git viaja con el usuario: sin ella los commits del subagente
    # saldrían con un ident autodetectado falso, y en hosts sin FQDN (WSL2 típico)
    # git muere con "unable to auto-detect email address" (revisión ronda 1).
    origen = {"HOME": str(home_original), "PATH": env.get("PATH", "")}
    for clave in ("user.name", "user.email"):
        valor = subprocess.run(
            ["git", "config", "--get", clave], env=origen,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
        )
        if valor.returncode == 0 and valor.stdout.strip():
            subprocess.run(
                ["git", "config", "--global", clave, valor.stdout.strip()],
                env=env, stdin=subprocess.DEVNULL, capture_output=True,
            )
    if env.get("GH_TOKEN") or env.get("GITHUB_TOKEN"):
        gh = shutil.which("gh", path=env.get("PATH"))
        if gh:
            subprocess.run(
                [gh, "auth", "setup-git"], env=env, cwd=str(aislado),
                stdin=subprocess.DEVNULL, capture_output=True,
            )


def argv_harness(harness, ejecutable, rol, worktree, texto, documentos=(), lecturas=(),
                 modelo=None):
    directorios = sorted({str(ruta.parent) for ruta in documentos})
    if harness == "claude":
        # En claude --add-dir concede acceso de HERRAMIENTAS (lectura incluida) sin
        # tocar el sandbox de SO: las lecturas viajan solo aquí. En codex --add-dir
        # significa "directorio escribible adicional": pasarle docs/ cambiaría su
        # política, así que codex no recibe lecturas (revisión ronda 1).
        directorios = sorted(set(directorios) | {str(ruta) for ruta in lecturas})
        argv = [
            ejecutable,
            "--safe-mode",
            "--disable-slash-commands",
            "--strict-mcp-config",
            # El CLI exige la clave mcpServers aunque no haya servidores: un {} pelado
            # se rechaza con "Invalid MCP configuration" (bug 001).
            "--mcp-config",
            '{"mcpServers": {}}',
            "--no-session-persistence",
            # dontAsk deniega Write/Edit y Bash por defecto en headless: no es un modo
            # permisivo. La seguridad real ya la impone el sandbox de SO (bug 001).
            "--permission-mode",
            "bypassPermissions",
        ]
        if modelo:
            argv.extend(("--model", modelo))
        for directorio in directorios:
            argv.extend(("--add-dir", directorio))
        argv.extend(("-p", texto))
        return argv
    if modelo:
        raise ErrorEjecucion("--modelo solo aplica al harness claude")
    argv = [
        ejecutable,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "-C",
        str(worktree),
        "-s",
        "workspace-write",
        "-a",
        "never",
    ]
    for directorio in directorios:
        argv.extend(("--add-dir", directorio))
    argv.append(texto)
    return argv


def sbpl_path(ruta):
    return str(ruta).replace("\\", "\\\\").replace('"', '\\"')


def sbpl_regex(ruta):
    # re.escape ya produce las barras correctas para el dialecto de regex del perfil;
    # aquí SOLO se escapan las comillas del literal #"…". Pasar el resultado por
    # sbpl_path duplicaría las barras y dejaría la regla inerte (revisión ronda 1,
    # verificado contra sandbox-exec real).
    return re.escape(str(ruta)).replace('"', '\\"')


def sha256_fichero(ruta):
    huella = hashlib.sha256()
    with ruta.open("rb") as stream:
        for bloque in iter(lambda: stream.read(1024 * 1024), b""):
            huella.update(bloque)
    return huella.hexdigest()


def identidad_ejecutable_sandbox(mecanismo, encontrado, exigir_owner_sistema=True):
    localizada = Path(os.path.abspath(encontrado))
    try:
        datos_localizados = localizada.lstat()
    except OSError as exc:
        raise ErrorEjecucion(f"no puedo acreditar el sandbox {mecanismo}: {exc}") from exc
    if stat.S_ISLNK(datos_localizados.st_mode):
        raise ErrorEjecucion(
            f"el ejecutable del sandbox {mecanismo} es un symlink: {localizada}"
        )
    ruta = localizada.resolve(strict=True)
    datos = ruta.stat()
    if not stat.S_ISREG(datos.st_mode) or not os.access(ruta, os.X_OK):
        raise ErrorEjecucion(f"el ejecutable del sandbox {mecanismo} no es regular/ejecutable")
    if datos.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ErrorEjecucion(
            f"el ejecutable del sandbox {mecanismo} tiene permisos inseguros: {ruta}"
        )
    if exigir_owner_sistema and datos.st_uid != 0:
        raise ErrorEjecucion(
            f"el ejecutable del sandbox {mecanismo} no pertenece al sistema: {ruta}"
        )
    return {
        "mecanismo": mecanismo,
        "ruta": str(ruta),
        "sha256": sha256_fichero(ruta),
        "dispositivo": datos.st_dev,
        "inode": datos.st_ino,
        "owner_uid": datos.st_uid,
        "owner_sistema_exigido": exigir_owner_sistema,
    }


def afirmar_ejecutable_sandbox(identidad):
    actual = identidad_ejecutable_sandbox(
        identidad["mecanismo"], identidad["ruta"],
        identidad["owner_sistema_exigido"],
    )
    for clave in ("ruta", "sha256", "dispositivo", "inode", "owner_uid"):
        if actual[clave] != identidad[clave]:
            raise ErrorEjecucion(
                f"el ejecutable del sandbox cambió después de validarlo: {identidad['ruta']}"
            )


def perfil_sandbox(mecanismo, ejecutable_sandbox, worktree, gitdir, common, tmp_privado, rol, harness,
                   documentos=()):
    escribibles = [tmp_privado]
    if rol == "constructor":
        # `common` (main/.git) guarda objetos y refs compartidos: sin él, commit y push
        # desde el worktree mueren con EPERM (bug 001). hooks/ y config quedan protegidos
        # por deny_write donde el mecanismo lo soporta.
        escribibles = [worktree, gitdir, common, tmp_privado]
    escribibles.extend(documentos)
    if harness == "claude" and mecanismo == "seatbelt" and sys.platform == "darwin":
        # El CLI guarda estado de sesión en una ruta fija fuera de HOME/TMPDIR:
        # /private/tmp/claude-<uid>/<cwd con "/" → "-">. Sin ella, EPERM al arrancar.
        # Se pre-crea aquí, fuera del sandbox: con (deny default) el CLI no podría
        # crearla porque su padre claude-<uid> no es escribible (revisión ronda 1).
        # Solo en darwin — /private y os.getuid no existen en las demás plataformas
        # y este generador no debe hacer IO fuera de ellas (revisión ronda 2).
        try:
            padre = Path("/private/tmp") / f"claude-{os.getuid()}"
            padre.mkdir(mode=0o700, exist_ok=True)
            estado_cli = padre / str(worktree).replace(os.sep, "-")
            estado_cli.mkdir(mode=0o700, exist_ok=True)
        except OSError as exc:
            raise ErrorEjecucion(
                f"no puedo preparar la ruta de estado del CLI en {padre}: {exc}"
            ) from exc
        escribibles.append(estado_cli)
    home = Path(os.path.expanduser("~"))
    deny_read = [home / ".ssh", home / ".aws", home / ".config/gcloud"]
    deny_write = [
        common / "hooks",
        common / "config",
        worktree / ".claude/settings.json",
        worktree / ".claude/settings.local.json",
    ]
    if mecanismo == "srt":
        settings = {
            "filesystem": {
                "allowWrite": [str(ruta) for ruta in escribibles],
                "denyWrite": [str(ruta) for ruta in deny_write],
                "denyRead": [str(ruta) for ruta in deny_read],
            },
            "network": {"allowedDomains": (
                ["api.anthropic.com"] if harness == "claude"
                else ["api.openai.com", "chatgpt.com", "auth.openai.com"]
            )},
        }
        ruta = tmp_privado / "srt-settings.json"
        ruta.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        ruta.chmod(0o600)
        return settings, lambda argv: [ejecutable_sandbox, "--settings", str(ruta), "--", *argv]
    if mecanismo == "seatbelt":
        allow = " ".join(f'(subpath "{sbpl_path(r)}")' for r in escribibles)
        dw = " ".join(f'(subpath "{sbpl_path(r)}")' for r in deny_write)
        dr = " ".join(f'(subpath "{sbpl_path(r)}")' for r in deny_read)
        # Guardado atómico (bug 001): Write/Edit crean un temporal HERMANO y renombran.
        # El subpath sobre el fichero no lo permite; esta regla abre solo los hermanos
        # que empiezan por el nombre del documento, no el directorio entero.
        hermanos = " ".join(
            f'(regex #"^{sbpl_regex(d)}[^/]*$")' for d in documentos
        )
        perfil = (
            "(version 1)\n(deny default)\n(allow process*)\n(allow sysctl-read)\n"
            "(allow file-read*)\n"
            f"(deny file-read* {dr})\n"
            f"(allow file-write* {allow})\n"
            + (f"(allow file-write* {hermanos})\n" if hermanos else "")
            # git abre /dev/null para leer y escribir en casi toda operación; sin esta
            # regla muere con exit 128 y el probe ve la rama vacía (bug 001).
            + '(allow file-read* file-write-data (literal "/dev/null"))\n'
            + f"(deny file-write* {dw})\n"
            "(allow network*)\n"
        )
        ruta = tmp_privado / "seatbelt.sb"
        ruta.write_text(perfil, encoding="utf-8")
        ruta.chmod(0o600)
        policy = {"filesystem": {"allowWrite": [str(r) for r in escribibles]}}
        return policy, lambda argv: [ejecutable_sandbox, "-f", str(ruta), *argv]
    binds = ["--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"]
    binds += ["--bind", str(tmp_privado), str(tmp_privado)]
    if rol == "constructor":
        binds += ["--bind", str(worktree), str(worktree), "--bind", str(gitdir), str(gitdir),
                  "--bind", str(common), str(common)]
    for documento in documentos:
        binds += ["--bind", str(documento), str(documento)]
    policy = {"filesystem": {"allowWrite": [str(r) for r in escribibles]}}
    return policy, lambda argv: [
        ejecutable_sandbox, *binds, "--unshare-all", "--share-net", "--chdir", str(worktree), "--", *argv
    ]


def detectar_sandbox():
    plataforma = "darwin" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else ""
    for mecanismo, ruta in SANDBOX_CONFIABLES.get(plataforma, ()):
        if Path(ruta).exists() or Path(ruta).is_symlink():
            return identidad_ejecutable_sandbox(
                mecanismo, ruta, exigir_owner_sistema=EXIGIR_OWNER_SISTEMA
            )
    raise ErrorEjecucion("no hay sandbox de SO disponible; ejecución bloqueada")


PROBE = r'''# CONTROL_PLANE_PROBE
import json, os, pathlib, subprocess
paths = json.loads(__import__('sys').argv[1])
out = {}
for name, raw in paths.items():
    path = pathlib.Path(raw)
    try:
        if name.startswith('doc'):
            # El patron real de guardado (Write/Edit, editores): crear un temporal
            # HERMANO y renombrar. Abrir en modo append pasaba con el permiso viejo
            # y no detectaba el hueco (bug 001).
            hermano = path.with_name(path.name + '.probe')
            with hermano.open('w') as flujo:
                flujo.write('probe')
            hermano.unlink()
        else:
            path.write_text('probe')
    except OSError:
        out[name] = False
    else:
        out[name] = True
        if not name.startswith('doc'):
            path.unlink()
out['cwd'] = os.getcwd()
out['pwd'] = os.environ.get('PWD')
out['branch'] = subprocess.run(['git', 'branch', '--show-current'], text=True,
                               capture_output=True).stdout.strip()
print(json.dumps(out))
'''


def verificar_sandbox(envuelto, env, worktree, tmp_privado, rol, documentos=()):
    sufijo = uuid.uuid4().hex
    rutas = {
        "outside": str(RAIZ / ".runtime" / f"probe-outside-{sufijo}"),
        "worktree": str(worktree / f".probe-worktree-{sufijo}"),
        "tmp": str(tmp_privado / f"probe-tmp-{sufijo}"),
    }
    for indice, documento in enumerate(documentos):
        rutas[f"doc{indice}"] = str(documento)
    resultado = subprocess.run(
        envuelto([sys.executable, "-c", PROBE, json.dumps(rutas)]),
        cwd=str(worktree), env=env, text=True, capture_output=True,
    )
    if resultado.returncode:
        raise ErrorEjecucion(f"el probe del sandbox no pudo ejecutarse: {resultado.stderr.strip()}")
    try:
        observado = json.loads(resultado.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ErrorEjecucion("el probe del sandbox no devolvió evidencia válida") from exc
    esperado = {
        "outside": False,
        "worktree": rol == "constructor",
        "tmp": True,
        "cwd": str(worktree),
        "pwd": str(worktree),
        "branch": worktree.name,
    }
    for indice, _ in enumerate(documentos):
        esperado[f"doc{indice}"] = True
    if observado != esperado:
        for nombre, ruta in rutas.items():
            if not nombre.startswith("doc"):
                Path(ruta).unlink(missing_ok=True)
        raise ErrorEjecucion(
            f"sandbox no cumple la política: observado={observado}, esperado={esperado}"
        )


def evidencia_git(worktree):
    codigo, head = git(worktree, "rev-parse", "HEAD")
    if codigo or not head:
        raise ErrorEjecucion(f"no puedo fijar HEAD del worktree: {head}")
    diferencia = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--"], cwd=str(worktree),
        capture_output=True, check=False,
    )
    estado = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=str(worktree),
        text=True, capture_output=True, check=False,
    )
    if diferencia.returncode or estado.returncode:
        detalle = (diferencia.stderr.decode("utf-8", "replace") + estado.stderr).strip()
        raise ErrorEjecucion(f"no puedo acreditar el estado Git del worktree: {detalle}")
    return {
        "head": head,
        "diff_sha256": hashlib.sha256(diferencia.stdout).hexdigest(),
        "status_porcelain": estado.stdout.splitlines(),
    }


def guardar_recibo(ruta, recibo):
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(recibo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporal.chmod(0o600)
    os.replace(str(temporal), str(ruta))


def checkpoint(recibo, nombre, estado, detalle):
    recibo["checkpoints"].append(
        {"nombre": nombre, "estado": estado, "detalle": detalle}
    )
    print(f"CHECKPOINT {nombre} {estado}: {detalle}", flush=True)


def _lanzar_bajo_lease(args, ficha, manager, autoridades):
    # El sandbox se acredita ANTES que nada: donde no hay mecanismo (Windows) el
    # rechazo debe ser un mensaje en claro, no un traceback de un paso posterior.
    sandbox_ejecutable = detectar_sandbox()
    mecanismo = sandbox_ejecutable["mecanismo"]
    worktree, gitdir, common = resolver_worktree(args.unidad)
    home_original = Path(os.environ.get("HOME", str(Path.home()))).resolve()
    texto = encargo(
        args.unidad, args.rol, ficha, args.prompt, args.skill_tecnica, home_original
    )
    if ficha.parent == RAIZ / "docs/bugs":
        documentos = [ficha]
    else:
        hallazgos = ficha.parent / "hallazgos.md"
        documentos = [ficha, hallazgos] if args.rol == "constructor" else [hallazgos]
    seguros = []
    for documento in documentos:
        try:
            seguros.append(workspace_paths.regular_file(
                RAIZ, documento, label="documento escribible de la unidad"
            ))
        except workspace_paths.WorkspacePathError as exc:
            raise ErrorEjecucion(str(exc)) from exc
    documentos = seguros
    ejecutable = shutil.which(args.harness)
    if not ejecutable:
        raise ErrorEjecucion(f"no encuentro el ejecutable {args.harness}")
    runtime = RAIZ / ".runtime"
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    resultados = runtime / "ejecuciones"
    resultados.mkdir(mode=0o700, exist_ok=True)
    id_ejecucion = uuid.uuid4().hex
    ruta_recibo = resultados / f"{args.unidad}-{id_ejecucion}.json"
    recibo = {
        "schema": "ejecucion/v1",
        "id": id_ejecucion,
        "unidad": args.unidad,
        "harness": args.harness,
        "rol": args.rol,
        "cwd": str(worktree),
        "rama": args.unidad,
        "sandbox": mecanismo,
        "sandbox_ejecutable": {
            clave: sandbox_ejecutable[clave] for clave in ("ruta", "sha256")
        },
        "lease": {
            "session_id": manager.session_id,
            "fencing": {
                scope: token
                for autoridad in autoridades
                for scope, token in autoridad.tokens.items()
            },
        },
        "git": {"inicial": evidencia_git(worktree), "final": None},
        "skills_tecnicas": list(args.skill_tecnica),
        "checkpoints": [],
        "exit_code": None,
    }
    checkpoint(
        recibo,
        "lease",
        "ok",
        ", ".join(f"{scope}#{token}" for scope, token in recibo["lease"]["fencing"].items()),
    )
    checkpoint(recibo, "identidad", "ok", f"{worktree} · rama {args.unidad}")
    guardar_recibo(ruta_recibo, recibo)
    tmp = Path(tempfile.mkdtemp(prefix=f"ejecucion-{args.unidad}-", dir=str(runtime))).resolve()
    tmp.chmod(0o700)
    try:
        env = entorno_base(worktree, tmp, home_original)
        if args.harness == "codex":
            preparar_codex_home(env, tmp, home_original)
        else:
            preparar_claude_home(env, tmp, home_original)
        argv = argv_harness(
            args.harness, ejecutable, args.rol, worktree, texto, documentos=documentos,
            # El contrato de la unidad manda leer bias, flujos y la síntesis de su
            # petición: docs/ del meta-repo viaja como lectura de herramientas del
            # harness claude (los escribibles del sandbox de SO no cambian; codex
            # la ignora porque su --add-dir significa escribible).
            lecturas=(RAIZ / "docs",),
            modelo=getattr(args, "modelo", None),
        )
        _, envuelto = perfil_sandbox(
            mecanismo, sandbox_ejecutable["ruta"], worktree, gitdir, common, tmp,
            args.rol, args.harness,
            documentos=documentos
        )
        try:
            for autoridad in autoridades:
                autoridad.assert_owner()
            afirmar_ejecutable_sandbox(sandbox_ejecutable)
            verificar_sandbox(
                envuelto, env, worktree, tmp, args.rol, documentos=documentos
            )
        except Exception as exc:
            checkpoint(recibo, "sandbox", "fail", str(exc))
            recibo["error"] = str(exc)
            recibo["git"]["final"] = evidencia_git(worktree)
            guardar_recibo(ruta_recibo, recibo)
            if isinstance(exc, ErrorEjecucion):
                raise
            raise ErrorEjecucion(f"falló el probe del sandbox: {exc}") from exc
        checkpoint(recibo, "sandbox", "ok", f"probe {mecanismo} conforme")
        guardar_recibo(ruta_recibo, recibo)
        try:
            for autoridad in autoridades:
                autoridad.assert_owner()
            afirmar_ejecutable_sandbox(sandbox_ejecutable)
            gestion_leases.failpoint("ejecucion_antes_harness")
            # stdin CERRADO: el harness delegado corre sin nadie al otro lado — cualquier
            # cosa que pregunte por stdin (git, ssh, un instalador) se quedaba esperando
            # una respuesta que no puede llegar, y el padre lo veía como un cuelgue mudo
            # de minutos (feedback de campo 06-08, ADR-026).
            tope = getattr(args, "tope_minutos", 0) or 0
            resultado = subprocess.run(
                envuelto(argv), cwd=str(worktree), env=env,
                stdin=subprocess.DEVNULL, timeout=tope * 60 if tope else None,
            )
        except subprocess.TimeoutExpired as exc:
            checkpoint(recibo, "harness", "fail", f"tope de {tope} min superado")
            recibo["error"] = f"el harness superó el tope de {tope} min y fue detenido"
            recibo["git"]["final"] = evidencia_git(worktree)
            guardar_recibo(ruta_recibo, recibo)
            raise ErrorEjecucion(
                f"{args.harness} superó el tope de {tope} min; el trabajo parcial queda "
                f"en el worktree y el recibo en {ruta_recibo}") from exc
        except OSError as exc:
            checkpoint(recibo, "harness", "fail", str(exc))
            recibo["error"] = str(exc)
            recibo["git"]["final"] = evidencia_git(worktree)
            guardar_recibo(ruta_recibo, recibo)
            raise ErrorEjecucion(f"no pude lanzar {args.harness}: {exc}") from exc
        for autoridad in autoridades:
            autoridad.assert_owner()
        recibo["exit_code"] = resultado.returncode
        recibo["git"]["final"] = evidencia_git(worktree)
        estado = "ok" if resultado.returncode == 0 else "fail"
        checkpoint(recibo, "harness", estado, f"exit {resultado.returncode}")
        guardar_recibo(ruta_recibo, recibo)
        print(f"RESULTADO {ruta_recibo}", flush=True)
        return resultado.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def lanzar(args):
    if not RE_NOMBRE.fullmatch(args.unidad):
        raise ErrorEjecucion("unidad inválida: se esperaba NNN-slug")
    manager = gestion_leases.LeaseManager(RAIZ)
    try:
        with manager.acquire(f"unit:{args.unidad}") as autoridad_unidad:
            ficha, datos = ficha_unidad(args.unidad, rol=args.rol)
            recursos = recursos_de(datos)
            scopes_recursos = [f"resource:{ruta}" for ruta in recursos]
            contexto = (
                manager.acquire(scopes_recursos)
                if scopes_recursos
                else contextlib.nullcontext(None)
            )
            with contexto as autoridad_recursos:
                ficha_actual, datos_actuales = ficha_unidad(args.unidad, rol=args.rol)
                if ficha_actual != ficha or recursos_de(datos_actuales) != recursos:
                    raise ErrorEjecucion(
                        "la ficha o sus recursos cambiaron mientras se adquiría autoridad"
                    )
                autoridades = [autoridad_unidad]
                if autoridad_recursos is not None:
                    autoridades.append(autoridad_recursos)
                return _lanzar_bajo_lease(
                    args, ficha_actual, manager, autoridades
                )
    except gestion_leases.LeaseError as exc:
        raise ErrorEjecucion(f"autoridad de ejecución ocupada o perdida: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("lanzar", help="valida y lanza un agente en una unidad")
    p.add_argument("unidad")
    p.add_argument("--harness", required=True, choices=("claude", "codex"))
    p.add_argument("--rol", choices=("constructor", "revisor"), default="constructor")
    p.add_argument("--skill-tecnica", action="append", default=[])
    p.add_argument("--prompt", required=True)
    p.add_argument("--modelo", default=None,
                   help="modelo explícito para el harness claude (regla 10: el revisor "
                        "usa un modelo DISTINTO del que construyó)")
    p.add_argument("--tope-minutos", type=int, default=0,
                   help="mata el harness si supera este tope (0 = sin tope); el recibo "
                        "queda con el motivo en vez de un cuelgue mudo")
    args = parser.parse_args()
    try:
        return lanzar(args)
    except ErrorEjecucion as exc:
        print(f"ejecucion: FAIL {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
