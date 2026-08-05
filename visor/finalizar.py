#!/usr/bin/env python3
"""Congela un workspace aprobado y, opcionalmente, publica sus dos repos.

La operación se hace sobre el mismo ``<nombre>-agents`` creado por
``iniciar.py``: valida los planos completos, prueba el visor real, regenera
constitución y flows, conserva ``main/`` y deja ambos repos enlazados.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from . import revision
except ImportError:
    import revision

BASE = Path(__file__).resolve().parent


def morir(mensaje):
    raise SystemExit("finalizar: %s" % mensaje)


def ejecutar(comando, cwd=None):
    return subprocess.run(
        comando,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def exigir_verde(comando, etiqueta, cwd=None):
    r = ejecutar(comando, cwd=cwd)
    if r.returncode:
        morir("%s falló:\n%s" % (etiqueta, r.stdout))
    print(r.stdout, end="")


# Estados del mapa en los que una actividad DICE tener planos completos
# (mismo criterio que validar.py). Una actividad "sin empezar" o "en
# entrevista" no tiene planos todavía y eso es un estado normal del mapa,
# no un impedimento para congelar la versión aprobada.
ESTADOS_ACTIVIDAD_CON_PLANOS = ("especificada", "en obra", "entregada")


def rutas_planos(mapa, datos):
    yield mapa, None
    base = mapa.parent
    for actividad in datos.get("actividades", []):
        yield base / "actividades" / actividad["id"] / "planos.json", actividad


def congelar_planos(mapa):
    datos_mapa = json.loads(mapa.read_text(encoding="utf-8"))
    for ruta, actividad in rutas_planos(mapa, datos_mapa):
        pendiente = actividad is not None and (
            actividad.get("estado") not in ESTADOS_ACTIVIDAD_CON_PLANOS
        )
        if pendiente:
            # Sin planos, o con un borrador a medias: no forma parte de la
            # versión congelada; seguirá su vida en el workspace (modo C).
            continue
        if not ruta.is_file():
            morir(
                "falta el plano %s (la actividad dice %r)"
                % (ruta, (actividad or {}).get("estado"))
            )
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        definicion = datos.get("definicion") or {}
        if definicion.get("estado") not in ("aprobado", "congelado"):
            morir(
                "%s no está aprobado por el usuario (definicion.estado=%r)"
                % (ruta, definicion.get("estado"))
            )
        definicion["estado"] = "congelado"
        datos["definicion"] = definicion
        ruta.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def copiar_documentacion(workspace, salida):
    constitucion = salida / "01-constitution" / "constitution.md"
    flows = salida / "02-flows"
    if not constitucion.is_file():
        morir("la compilación no produjo constitution.md")
    destino_constitucion = workspace / "docs" / "01-constitucion" / "manifiesto.md"
    shutil.copyfile(constitucion, destino_constitucion)

    destino_flows = workspace / "docs" / "02-flujos"
    for anterior in destino_flows.glob("*.md"):
        anterior.unlink()
    indice = salida / "README.md"
    shutil.copyfile(indice, destino_flows / "INDICE.md")
    for documento in sorted(flows.rglob("*.md")):
        nombre = documento.stem + ".md"
        if (destino_flows / nombre).exists():
            morir("dos actividades compiladas tienen el mismo id: %s" % documento.stem)
        shutil.copyfile(documento, destino_flows / nombre)


def commit_si_hay_cambios(repo, mensaje, incluir_todo=False):
    if incluir_todo:
        ejecutar(["git", "add", "-A"], cwd=repo)
    estado = ejecutar(["git", "status", "--porcelain=v1"], cwd=repo)
    if estado.returncode:
        morir("%s no es un repositorio git:\n%s" % (repo, estado.stdout))
    if estado.stdout.strip():
        r = ejecutar(["git", "commit", "-m", mensaje], cwd=repo)
        if r.returncode:
            morir("no pude crear el commit en %s:\n%s" % (repo, r.stdout))


def repo_github(owner, nombre):
    if not shutil.which("gh"):
        morir("falta GitHub CLI (`gh`) para publicar repositorios")
    existe = ejecutar(["gh", "repo", "view", "%s/%s" % (owner, nombre), "--json", "name"])
    if existe.returncode:
        creado = ejecutar(
            ["gh", "repo", "create", "%s/%s" % (owner, nombre), "--private"]
        )
        if creado.returncode:
            morir("no pude crear %s/%s:\n%s" % (owner, nombre, creado.stdout))
    return "https://github.com/%s/%s.git" % (owner, nombre)


def configurar_remoto(repo, url):
    actual = ejecutar(["git", "remote", "get-url", "origin"], cwd=repo)
    if actual.returncode:
        r = ejecutar(["git", "remote", "add", "origin", url], cwd=repo)
    else:
        r = ejecutar(["git", "remote", "set-url", "origin", url], cwd=repo)
    if r.returncode:
        morir("no pude configurar origin en %s:\n%s" % (repo, r.stdout))


def publicar_github(workspace, owner, nombre):
    main = workspace / "main"
    nombre_meta = nombre + "-agents"
    url_codigo = repo_github(owner, nombre)
    url_meta = repo_github(owner, nombre_meta)

    # La copia de trabajo es propiedad de este workspace: se conserva también
    # cualquier fichero local que llegó al ingerir una carpeta sin remoto.
    commit_si_hay_cambios(main, "Importa el estado inicial del código", incluir_todo=True)
    configurar_remoto(main, url_codigo)
    subida = ejecutar(["git", "push", "-u", "origin", "HEAD:main"], cwd=main)
    if subida.returncode:
        morir("no pude publicar el repo de código:\n%s" % subida.stdout)

    repos = workspace / "repos.yaml"
    texto = repos.read_text(encoding="utf-8")
    texto = texto.replace(
        "PENDIENTE  # crear el remoto del repo de código y poner aquí su URL",
        url_codigo,
    )
    repos.write_text(texto, encoding="utf-8")
    ejecutar(["git", "add", "repos.yaml"], cwd=workspace)
    commit_si_hay_cambios(workspace, "Configura los dos repositorios independientes")
    configurar_remoto(workspace, url_meta)
    subida = ejecutar(["git", "push", "-u", "origin", "main"], cwd=workspace)
    if subida.returncode:
        morir("no pude publicar el meta-repo:\n%s" % subida.stdout)
    print("GitHub: %s/%s y %s/%s" % (owner, nombre, owner, nombre_meta))


def main():
    ap = argparse.ArgumentParser(
        description="Valida, congela y finaliza un workspace aprobado."
    )
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--nombre", help="nombre final del repo; por defecto el del workspace")
    # Una de las dos, OBLIGATORIA. Antes, olvidarse de --github finalizaba el proyecto en
    # silencio y sin remoto: el usuario se quedaba con todo su trabajo en un solo disco
    # creyendo que estaba publicado, y nada volvía a mencionarlo jamás. Ahora la decisión
    # hay que tomarla —y por tanto preguntársela a él— para poder terminar.
    destino = ap.add_mutually_exclusive_group(required=True)
    destino.add_argument("--github", metavar="CUENTA",
                         help="crea/publica los dos repos privados en esa cuenta")
    destino.add_argument("--sin-github", action="store_true",
                         help="el usuario ha dicho que NO quiere GitHub: todo queda en este "
                              "ordenador, sin copia de seguridad, y se le advierte")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not (workspace / ".git").exists() or not (workspace / "main" / ".git").exists():
        morir("no es un workspace válido creado por iniciar.py: %s" % workspace)
    mapa = workspace / "docs" / "02-flujos" / "planos" / "planos.json"
    if not mapa.is_file():
        morir("no encuentro los planos canónicos: %s" % mapa)

    # No basta con escribir "aprobado" en el JSON: el recibo firmado desde
    # la revisión web debe coincidir byte a byte con la versión actual.
    if not revision.aprobacion_vigente(mapa):
        morir(
            "no hay una aprobación vigente para estos planos; ábrelos con "
            "requisitos.py, resuelve el feedback y aprueba esa versión"
        )

    exigir_verde(
        [sys.executable, str(BASE / "validar.py"), "--datos", str(mapa),
         "--perfil", "congelado"],
        "validación de congelación",
    )
    exigir_verde(
        [sys.executable, str(BASE / "validar_web.py"), "--datos", str(mapa)],
        "E2E del visor",
    )
    congelar_planos(mapa)
    exigir_verde(
        [sys.executable, str(BASE / "validar.py"), "--datos", str(mapa),
         "--perfil", "congelado"],
        "validación final",
    )

    with tempfile.TemporaryDirectory(prefix="ingenieria-requisitos-final-") as temporal:
        salida = Path(temporal) / "especificaciones"
        exigir_verde(
            [sys.executable, str(BASE / "compilar.py"), "--mapa", str(mapa),
             "--salida", str(salida)],
            "compilación",
        )
        copiar_documentacion(workspace, salida)

    estado = workspace / "docs" / "05-trabajo" / "ESTADO.md"
    estado.write_text(
        "# ESTADO — diseño congelado\n\n"
        "- Los planos fueron aprobados y pasaron validación estructural y E2E.\n"
        "- Constitución y flows están regenerados desde la fuente canónica.\n"
        "- Siguiente fase: investigación/planificación e implementación por recorridos.\n",
        encoding="utf-8",
    )
    ejecutar(["git", "add", "docs"], cwd=workspace)
    commit_si_hay_cambios(workspace, "Congela planos aprobados y documentación")

    nombre = args.nombre or workspace.name.removesuffix("-agents")
    if args.github:
        publicar_github(workspace, args.github, nombre)
    print("Proyecto finalizado en %s" % workspace)
    print("Repo de código conservado en %s" % (workspace / "main"))
    # El método viaja por copia: cuando la herramienta mejore, este
    # workspace NO se entera solo. El reparto es el Modo D.
    print(
        "Nota: el método de trabajo viaja DENTRO del workspace por copia. "
        "Cuando esta herramienta se actualice, pon el proyecto al día desde "
        "aquí con «pon al día mis proyectos» (Modo D: visor/actualizar.py)."
    )
    if args.sin_github:
        print(
            "\n" + "=" * 70 + "\n"
            "AVISO: este proyecto existe SOLO en este ordenador.\n"
            "No hay copia en ningún otro sitio: si se rompe el disco, se pierde todo —\n"
            "los planos, el código y el historial. Díselo al usuario con estas palabras.\n"
            "Cuando quiera publicarlo, se ejecuta esto mismo con --github <su-cuenta>.\n"
            + "=" * 70
        )


if __name__ == "__main__":
    main()
