#!/usr/bin/env python3
"""Valida que el repo de código materializó un CI real para SU stack.

No ejecuta tests ni escáneres: comprueba la interfaz común que la primera unidad crea cuando
ya conoce lenguaje, framework y gestor de paquetes. El repo vacío es válido; un repo con
código no puede dar verde con huecos o saltos silenciosos.
"""
import argparse
import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path


def _cargar_control_plane():
    """Carga el módulo hermano también cuando este fichero se importa con spec_from_file."""
    ruta = Path(__file__).with_name("control_plane.py")
    spec = importlib.util.spec_from_file_location("control_plane_lint_ci", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


control_plane = _cargar_control_plane()


for _salida in (sys.stdout, sys.stderr):
    if hasattr(_salida, "reconfigure"):
        _salida.reconfigure(encoding="utf-8", errors="replace")


RAIZ = Path(__file__).resolve().parents[3]
SOPORTE = {
    "readme", "readme.md", "readme.txt", "license", "license.md",
    "copying", ".gitignore", ".gitattributes",
}
REQUERIDOS = (
    "AGENTS.md",
    "scripts/ci/full-suite",
    "scripts/ci/lint",
    "scripts/ci/security",
    ".github/workflows/tests.yml",
    ".github/workflows/quality-security.yml",
    ".github/dependabot.yml",
)
RE_PLACEHOLDER = re.compile(r"<[^<>\n]{2,}>")
RE_ACTION = re.compile(r"\buses:\s*([^\s#]+)")
RE_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
RE_LITERAL = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")
RE_DESACTIVA_ERREXIT = re.compile(
    r"(?m)(?:^|;)\s*set\s+(?:[+-][A-Za-z]+\s+)*\+[A-Za-z]*e[A-Za-z]*\b"
)


def repo_tiene_codigo(repo):
    """Distingue implementación real de README/licencia/infra inicial de GitHub."""
    if not repo.is_dir():
        return False
    for ruta in repo.rglob("*"):
        if not ruta.is_file() or ".git" in ruta.parts:
            continue
        relativa = ruta.relative_to(repo).as_posix().lower()
        if relativa in SOPORTE or relativa.startswith(".github/"):
            continue
        return True
    return False


def leer(repo, relativa):
    try:
        return (repo / relativa).read_text(encoding="utf-8")
    except OSError:
        return ""


def sin_comentarios_de_linea(texto):
    """Quita comentarios de línea completos sin asumir el lenguaje del script."""
    return "\n".join(
        linea for linea in texto.splitlines()
        if not linea.lstrip().startswith(("#", "//"))
    )


def sin_cadenas(texto):
    """Oculta literales entre comillas para que un mensaje no parezca código ejecutable."""
    return RE_LITERAL.sub(lambda m: " " * len(m.group(0)), texto)


def tokens_shell(linea):
    try:
        return shlex.split(linea, comments=True, posix=True)
    except ValueError:
        return None


def linea_es_invocacion_directa(linea, ruta, admite_exec=False):
    tokens = tokens_shell(linea)
    if tokens is None:
        return False
    esperada = ruta.removeprefix("./")
    if admite_exec and tokens[:1] == ["exec"]:
        tokens = tokens[1:]
    return len(tokens) == 1 and tokens[0].removeprefix("./") == esperada


def contiene_sintaxis_de_bloque(texto):
    codigo = sin_cadenas(sin_comentarios_de_linea(texto))
    return bool(
        re.search(
            r"(?m)^\s*(?:if|then|fi|case|esac|while|for|until|do|done|function)\b"
            r"|[{}()]|<<",
            codigo,
        )
    )


def contiene_pipe_shell(texto):
    codigo = sin_cadenas(sin_comentarios_de_linea(texto))
    return re.search(r"(?<!\|)\|(?!\|)", codigo) is not None


def contiene_or_shell(texto):
    return "||" in sin_cadenas(sin_comentarios_de_linea(texto))


def full_suite_invoca_e2e(texto):
    if contiene_sintaxis_de_bloque(texto):
        return False
    errexit = False
    for linea in texto.splitlines():
        if linea.rstrip().endswith("\\") or tokens_shell(linea) is None:
            return False
        if linea_es_invocacion_directa(linea, "scripts/ci/e2e", admite_exec=True):
            return errexit
        cambio = cambio_errexit(linea)
        if cambio is not None:
            errexit = cambio
    return False


def cambio_errexit(linea):
    tokens = tokens_shell(linea) or []
    if tokens[:1] != ["set"]:
        return None
    estado = None
    for token in tokens[1:]:
        if token == "--":
            break
        if re.fullmatch(r"[+-][A-Za-z]+", token) and "e" in token[1:]:
            estado = token.startswith("-")
    return estado


def linea_es_prologo(linea):
    tokens = tokens_shell(linea)
    if tokens is None:
        return False
    if not tokens:
        return True
    set_simple = tokens[0] == "set" and all(
        re.fullmatch(r"[+-][A-Za-z]+", token) for token in tokens[1:]
    )
    asignaciones_simples = all(
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=[A-Za-z0-9_./:@%+-]*", token)
        for token in tokens
    )
    return set_simple or asignaciones_simples


COMANDOS_NO_SUSTANTIVOS = {
    ":", "cd", "echo", "export", "false", "printf", "pwd", "set", "sleep",
    "test", "true", "unset",
}
RUNNERS_DE_TEST = {
    "cypress", "jest", "phpunit", "playwright", "pytest", "rspec", "vitest",
}


def linea_es_comando_sustantivo(linea):
    """Distingue una orden directa de prólogos, mensajes y no-ops de shell."""
    tokens = tokens_shell(linea)
    if (not tokens or linea_es_prologo(linea)
            or contiene_sintaxis_de_bloque(linea)):
        return False
    comando = Path(tokens[0]).name.lower()
    return comando not in COMANDOS_NO_SUSTANTIVOS and comando != "exit"


def linea_ejecuta_pruebas(linea):
    """Reconoce una orden de tests, sin confundir texto impreso con ejecución."""
    if not linea_es_comando_sustantivo(linea):
        return False
    tokens = tokens_shell(linea)
    comando = Path(tokens[0]).name.lower()
    marcador = re.compile(r"(^|[-_/])(e2e|tests?|specs?)([-_/]|$)", re.I)
    if comando in RUNNERS_DE_TEST:
        return True
    gestores = {"bun", "cargo", "go", "gradle", "gradlew", "make", "mvn", "mvnw",
                "npm", "pnpm", "yarn"}
    return comando in gestores and any(marcador.search(token) for token in tokens[1:])


def e2e_provisiona_antes_de_pruebas(texto):
    """Valida orden, fail-fast y propagación de rojos en todo el runner E2E."""
    codigo = sin_comentarios_de_linea(texto)
    if (contiene_or_shell(texto) or RE_DESACTIVA_ERREXIT.search(codigo)
            or contiene_pipe_shell(texto)):
        return False
    anteriores = []
    errexit = False
    provisionado = False
    prueba = False
    for linea in texto.splitlines():
        if linea.rstrip().endswith("\\") or tokens_shell(linea) is None:
            return False
        if not provisionado:
            if linea_es_invocacion_directa(linea, "scripts/ci/provision-e2e"):
                if not errexit or contiene_sintaxis_de_bloque("\n".join(anteriores)):
                    return False
                provisionado = True
                continue
            if not linea_es_prologo(linea):
                return False
            anteriores.append(linea)
        elif linea_es_invocacion_directa(linea, "scripts/ci/provision-e2e"):
            return False
        elif linea_ejecuta_pruebas(linea):
            prueba = True
        cambio = cambio_errexit(linea)
        if cambio is not None:
            errexit = cambio
    return provisionado and prueba and errexit


RE_CASE_CANONICO = re.compile(
    r"^\s*case\s+(?P<q>\"?)(?:\$(?P<simple>[A-Za-z_][A-Za-z0-9_]*)|"
    r"\$\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)(?::-)?\})(?P=q)\s+in\s*$"
)
RE_RAMA_CANONICA = re.compile(
    r"^\s*(?P<labels>[A-Za-z0-9_*]+(?:\|[A-Za-z0-9_*]+)*)\)\s*(?P<body>.*)$"
)


def cabecera_rama(linea):
    m = RE_RAMA_CANONICA.match(linea)
    return set(m.group("labels").lower().split("|")) if m else None


def codigo_de_rama(lineas):
    codigo = sin_cadenas("\n".join(lineas))
    return re.sub(
        r"^\s*(?:\*|[A-Za-z0-9_-]+(?:\|[A-Za-z0-9_-]+)*)\)\s*",
        "",
        codigo,
        count=1,
    )


def rama_cierra_con_exit_no_cero(lineas):
    codigo = codigo_de_rama(lineas)
    return re.fullmatch(r"\s*exit\s+[1-9][0-9]*\s*;*\s*", codigo) is not None


def rama_es_noop(lineas):
    return re.fullmatch(r"[\s;]*", codigo_de_rama(lineas)) is not None


def validar_case_seguro(lineas, inicio):
    """Devuelve ``(fin, variable)`` si el case iniciado en ``inicio`` es seguro."""
    m_case = RE_CASE_CANONICO.match(lineas[inicio])
    if m_case is None:
        return None
    variable = m_case.group("simple") or m_case.group("braced")
    fin = next((i for i in range(inicio + 1, len(lineas))
                if re.fullmatch(r"\s*esac\s*", lineas[i])), None)
    if fin is None:
        return None
    cuerpos = []
    for linea in lineas[inicio + 1:fin]:
        m_rama = RE_RAMA_CANONICA.match(linea)
        cuerpos.append(m_rama.group("body") if m_rama else linea)
    if contiene_sintaxis_de_bloque("\n".join(cuerpos)):
        return None

    ramas = [(i, cabecera_rama(lineas[i])) for i in range(inicio + 1, fin)
             if cabecera_rama(lineas[i]) is not None]
    if not ramas or any(tokens_shell(linea) for linea in lineas[inicio + 1:ramas[0][0]]):
        return None
    permitidas, produccion = {"local", "test", "e2e"}, {"prod", "production"}
    vistas, categorias = set(), []
    for posicion, (indice, etiquetas) in enumerate(ramas):
        if etiquetas & vistas:
            return None
        vistas |= etiquetas
        limite = ramas[posicion + 1][0] if posicion + 1 < len(ramas) else fin
        bloque = lineas[indice:limite]
        if etiquetas and etiquetas <= permitidas:
            if not rama_es_noop(bloque):
                return None
            categorias.append(0)
        elif etiquetas and etiquetas <= produccion:
            if not rama_cierra_con_exit_no_cero(bloque):
                return None
            categorias.append(1)
        elif etiquetas == {"*"}:
            if not rama_cierra_con_exit_no_cero(bloque):
                return None
            categorias.append(2)
        else:
            return None
    if (vistas != permitidas | produccion | {"*"}
            or categorias != sorted(categorias)):
        return None
    return fin, variable


def guarda_case_segura(lineas):
    """Exige barreras canónicas e independientes de entorno y destino E2E."""
    inicio_entorno = next(
        (i for i, linea in enumerate(lineas) if RE_CASE_CANONICO.match(linea)),
        None,
    )
    if (inicio_entorno is None
            or any(not linea_es_prologo(linea) for linea in lineas[:inicio_entorno])):
        return False
    entorno = validar_case_seguro(lineas, inicio_entorno)
    if entorno is None:
        return False
    fin_entorno, variable_entorno = entorno
    if not re.search(r"(env|stage|mode)", variable_entorno, re.I):
        return False

    inicio_destino = next(
        (i for i in range(fin_entorno + 1, len(lineas))
         if RE_CASE_CANONICO.match(lineas[i])),
        None,
    )
    if (inicio_destino is None
            or any(tokens_shell(linea)
                   for linea in lineas[fin_entorno + 1:inicio_destino])):
        return False
    destino = validar_case_seguro(lineas, inicio_destino)
    if destino is None:
        return False
    fin_destino, variable_destino = destino
    if variable_destino.casefold() == variable_entorno.casefold():
        return False
    if re.search(
        r"(db|database|tenant|instance|instancia)", variable_destino, re.I
    ) is None:
        return False
    referencia = re.compile(
        rf"\$(?:{re.escape(variable_destino)}\b|"
        rf"\{{{re.escape(variable_destino)}(?::-[^}}]*)?\}})"
    )
    return any(
        linea_es_comando_sustantivo(linea) and referencia.search(linea)
        for linea in lineas[fin_destino + 1:]
    )


def provision_tiene_guarda_segura(texto):
    lineas = sin_comentarios_de_linea(texto).splitlines()
    return guarda_case_segura(lineas)


def exigir_fragmentos(texto, relativa, fragmentos):
    return [f"{relativa}: falta `{fragmento}`" for fragmento in fragmentos
            if fragmento not in texto]


def revisar_actions_pineadas(texto, relativa):
    fallos = []
    for uso in RE_ACTION.findall(texto):
        if uso.startswith("./"):
            continue
        if "@" not in uso or not RE_SHA.match(uso.rsplit("@", 1)[1]):
            fallos.append(
                f"{relativa}: `{uso}` no está fijada a un SHA de 40 caracteres"
            )
    return fallos


def revisar_workflows(repo):
    fallos = []
    tests = ".github/workflows/tests.yml"
    texto_tests = leer(repo, tests)
    fallos += exigir_fragmentos(
        texto_tests,
        tests,
        ("pull_request:", "  tests:", "scripts/ci/full-suite"),
    )
    fallos += revisar_actions_pineadas(texto_tests, tests)

    calidad = ".github/workflows/quality-security.yml"
    texto_calidad = leer(repo, calidad)
    fallos += exigir_fragmentos(
        texto_calidad,
        calidad,
        (
            "pull_request:", "push:", "main", "schedule:",
            "  lint:", "  security:", "  quality-security:", "needs:",
            "scripts/ci/lint", "scripts/ci/security",
            "needs.lint.result", "needs.security.result",
        ),
    )
    fallos += revisar_actions_pineadas(texto_calidad, calidad)

    dependabot = ".github/dependabot.yml"
    fallos += exigir_fragmentos(
        leer(repo, dependabot),
        dependabot,
        ("package-ecosystem:", "schedule:", "interval:"),
    )
    return fallos


def revisar_scripts(repo, rutas=None):
    fallos = []
    rutas = rutas or ("scripts/ci/full-suite", "scripts/ci/lint", "scripts/ci/security")
    for relativa in rutas:
        texto = leer(repo, relativa)
        if not texto.strip():
            fallos.append(f"{relativa}: está vacío")
        if RE_PLACEHOLDER.search(texto):
            fallos.append(f"{relativa}: conserva un marcador de plantilla sin rellenar")
        if contiene_or_shell(texto):
            fallos.append(
                f"{relativa}: contiene `||` (incluido `|| true`/`|| :`) y podría "
                "convertir un rojo en verde"
            )
    return fallos


def revisar_agents(repo):
    texto = leer(repo, "AGENTS.md")
    return exigir_fragmentos(
        texto,
        "AGENTS.md",
        ("scripts/ci/full-suite", "scripts/ci/lint", "scripts/ci/security"),
    )


def revisar_e2e(repo):
    fallos = []
    rutas = ("scripts/ci/e2e", "scripts/ci/provision-e2e")
    fallos += revisar_scripts(repo, rutas)
    if not full_suite_invoca_e2e(leer(repo, "scripts/ci/full-suite")):
        fallos.append(
            "scripts/ci/full-suite: no acredita invocación autónoma con set -e activo "
            "de `scripts/ci/e2e`"
        )
    if not e2e_provisiona_antes_de_pruebas(leer(repo, "scripts/ci/e2e")):
        fallos.append(
            "scripts/ci/e2e: no acredita provision como primera orden con fail-fast "
            "continuo mediante `scripts/ci/provision-e2e`"
        )
    fallos += exigir_fragmentos(
        leer(repo, "AGENTS.md"),
        "AGENTS.md",
        rutas,
    )

    provision = leer(repo, "scripts/ci/provision-e2e")
    if not provision_tiene_guarda_segura(provision):
        fallos.append(
            "scripts/ci/provision-e2e: no demuestra dos guardas independientes: "
            "entorno y destino (DB/tenant/instancia) local/test/E2E, con rechazo "
            "explícito de producción"
        )
    return fallos


def control_plane_guard_valido(texto):
    """El wrapper solo puede ejecutar el guard canónico, sin neutralizadores."""
    if contiene_or_shell(texto) or contiene_pipe_shell(texto) or contiene_sintaxis_de_bloque(texto):
        return False
    sustantivas = []
    for linea in texto.splitlines():
        if linea_es_prologo(linea) or not linea_es_comando_sustantivo(linea):
            continue
        tokens = tokens_shell(linea) or []
        if tokens[:1] == ["exec"]:
            tokens = tokens[1:]
        sustantivas.append(tokens)
    if len(sustantivas) != 1:
        return False
    tokens = sustantivas[0]
    return (
        len(tokens) >= 5
        and Path(tokens[0]).name.startswith("python")
        and tokens[1].removeprefix("./")
        == "docs/00-metodo/scripts/control_plane.py"
        and tokens[2] == "guard-test"
        and "--env-json" in tokens[3:]
    )


def provision_invoca_guard_antes_de_mutar(texto):
    """El guard es la primera orden sustantiva y su rojo detiene el provisionador."""
    codigo = sin_comentarios_de_linea(texto)
    if (contiene_or_shell(texto) or contiene_pipe_shell(texto)
            or RE_DESACTIVA_ERREXIT.search(codigo)):
        return False
    errexit = False
    for linea in texto.splitlines():
        if linea_es_invocacion_directa(linea, "scripts/ci/control-plane-guard"):
            return errexit
        if linea_es_comando_sustantivo(linea):
            return False
        cambio = cambio_errexit(linea)
        if cambio is not None:
            errexit = cambio
    return False


def revisar_control_plane(repo, required=False, trusted_allow_hosts=()):
    relativa = "scripts/ci/control-plane.json"
    ruta = repo / relativa
    if not ruta.is_file():
        return [f"falta {relativa}"] if required else []
    try:
        manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
        control_plane.validate_manifest(
            manifiesto, trusted_allow_hosts=set(trusted_allow_hosts)
        )
        if manifiesto.get("guard_script") != "scripts/ci/control-plane-guard":
            raise control_plane.InvalidManifest("guard_script canónico obligatorio")
        guard = repo / "scripts/ci/control-plane-guard"
        if (not guard.is_file() or not os.access(guard, os.X_OK)
                or not control_plane_guard_valido(leer(repo, manifiesto["guard_script"]))):
            raise control_plane.InvalidManifest(
                "scripts/ci/control-plane-guard no ejecuta únicamente guard-test"
            )
        if not provision_invoca_guard_antes_de_mutar(leer(repo, "scripts/ci/provision-e2e")):
            raise control_plane.InvalidManifest(
                "scripts/ci/provision-e2e no invoca el guard antes de mutar"
            )
        relativa_recibo = manifiesto.get("receipt")
        if not isinstance(relativa_recibo, str):
            raise control_plane.InvalidManifest("receipt obligatorio")
        partes = Path(relativa_recibo)
        if partes.is_absolute() or ".." in partes.parts:
            raise control_plane.InvalidManifest("receipt debe quedar dentro del repo")
        ruta_recibo = (repo / partes).resolve()
        try:
            ruta_recibo.relative_to(repo.resolve())
        except ValueError as exc:
            raise control_plane.InvalidManifest(
                "receipt debe quedar dentro del repo"
            ) from exc
        recibo = json.loads(ruta_recibo.read_text(encoding="utf-8"))
        targets = manifiesto["targets"]
        control_plane.validate_close_receipt(
            recibo,
            route=recibo.get("route", ""),
            expected_target_fingerprint=targets[0]["fingerprint"],
        )
    except (OSError, json.JSONDecodeError, control_plane.ControlPlaneError) as exc:
        return [f"{relativa}: {control_plane.redact_secrets(exc)}"]
    return []


def revisar(repo, require_e2e=False, require_control_plane=False,
            control_plane_allow_hosts=()):
    if not repo.is_dir():
        return [f"el repo no existe o no es una carpeta: {repo}"]
    if not repo_tiene_codigo(repo):
        print("  OK   repositorio todavía vacío: el CI real nacerá cuando se conozca el stack")
        return []
    requeridos = REQUERIDOS + (("scripts/ci/e2e", "scripts/ci/provision-e2e")
                              if require_e2e else ())
    fallos = [f"falta {relativa}" for relativa in requeridos
              if not (repo / relativa).is_file()]
    if fallos:
        return fallos
    fallos = revisar_workflows(repo) + revisar_scripts(repo) + revisar_agents(repo)
    if require_e2e:
        fallos += revisar_e2e(repo)
    fallos += revisar_control_plane(
        repo,
        required=require_control_plane,
        trusted_allow_hosts=control_plane_allow_hosts,
    )
    return fallos


def main():
    ap = argparse.ArgumentParser(
        description="Valida la interfaz CI que materializa la primera unidad con stack."
    )
    ap.add_argument("--repo", default=str(RAIZ / "main"),
                    help="raíz del repo de código (por defecto: main/ del workspace)")
    ap.add_argument(
        "--require-e2e",
        action="store_true",
        help="exige provisión y ejecución E2E cuando los planos las seleccionan",
    )
    ap.add_argument(
        "--require-control-plane",
        action="store_true",
        help="exige identidad reproducible y targets de test en scripts/ci/control-plane.json",
    )
    ap.add_argument(
        "--control-plane-allow-host",
        action="append",
        default=[],
        help="host E2E remoto confiado por CI, fuera del manifiesto; repetible",
    )
    args = ap.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    print("== Contrato CI del repo de código ==")
    fallos = revisar(
        repo,
        require_e2e=args.require_e2e,
        require_control_plane=args.require_control_plane,
        control_plane_allow_hosts=args.control_plane_allow_host,
    )
    for fallo in fallos:
        print(f"  FAIL {fallo}")
    if not fallos and repo_tiene_codigo(repo):
        print("  OK   tests, lint, seguridad y actualizaciones están materializados")
    print(f"\n{len(fallos)} FAIL")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
