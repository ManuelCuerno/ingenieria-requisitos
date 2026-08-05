#!/usr/bin/env python3
"""doctor.py — qué hay REALMENTE instalado en esta máquina, ANTES de prometer nada.

Uso: python3 docs/00-metodo/scripts/doctor.py [--escribir]
Se ejecuta: al final de `setup.py` (primer arranque) y cuando la fase 4 vaya a decidir
tecnología. `--escribir` deja la foto en docs/conocimiento/entorno-de-esta-maquina.md.

Por qué existe: la fase 4 elige el entorno de desarrollo (contenedores o no, dónde corren los
tests, cómo se publica) apoyándose en supuestos sobre la máquina que nadie había comprobado.
Escribir "se desarrolla con Docker" sin saber si hay Docker es la forma más cara de
descubrirlo: se paga con un ROADMAP corregido, un ADR y una unidad reespecificada a mitad.
REGLA (runbooks/planificacion.md): el ROADMAP no fija una herramienta que el doctor no haya
visto en verde.

Esto INFORMA, no bloquea: una máquina sin Docker no es una máquina inválida, es una máquina
que va por el peldaño mínimo. Sale siempre con código 0.
Solo stdlib, y agnóstico del lenguaje del proyecto.
"""
import argparse
import datetime
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Windows: con la salida en un pipe (setup.py) el encoding por defecto es cp1252 y cualquier
# carácter fuera de él mataría el informe con UnicodeEncodeError. Se fuerza UTF-8.
for _salida in (sys.stdout, sys.stderr):
    if hasattr(_salida, "reconfigure"):
        _salida.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parents[3]
HOY = datetime.date.today().isoformat()


def correr(*comando):
    """(ok, primera línea de salida). Nunca lanza: una herramienta ausente es un dato, no un error."""
    if shutil.which(comando[0]) is None:
        return False, ""
    try:
        p = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    salida = (p.stdout or p.stderr or "").strip().splitlines()
    return p.returncode == 0, (salida[0] if salida else "")


def revisar_python():
    return "sí", f"{platform.python_version()} ({sys.executable})", ""


def revisar_git():
    hay, version = correr("git", "--version")
    if not hay:
        return "NO", "no instalado", "sin git no hay método: instálalo antes de nada"
    _, nombre = correr("git", "-C", str(RAIZ), "config", "--get", "user.name")
    _, correo = correr("git", "-C", str(RAIZ), "config", "--get", "user.email")
    if not (nombre and correo):
        return ("a medias", f"{version} · SIN IDENTIDAD",
                'el primer commit fallará con "Author identity unknown": '
                'git config --global user.name "…" y user.email "…"')
    return "sí", f"{version} · {nombre} <{correo}>", ""


def revisar_gh():
    hay, version = correr("gh", "--version")
    if not hay:
        return ("NO", "no instalado",
                "no hay pull requests: el cierre va por el CAMINO B de runbooks/cierre.md "
                "(revisión sobre el diff y merge local del padre)")
    autenticado, _ = correr("gh", "auth", "status")
    if not autenticado:
        return ("a medias", f"{version} · sin sesión",
                "`gh auth login` o, si no vas a usar GitHub, camino B de runbooks/cierre.md")
    return "sí", version, ""


def revisar_docker():
    hay, version = correr("docker", "--version")
    if not hay:
        return ("NO", "no instalado",
                "el ROADMAP NO puede prometer contenedores: se desarrolla y se prueba en el "
                "peldaño mínimo (entorno local del lenguaje). Ver 01-constitucion/bias.md")
    vivo, _ = correr("docker", "info")
    if not vivo:
        return ("a medias", f"{version} · demonio parado",
                "arranca Docker Desktop (o el servicio) antes de contar con él")
    return "sí", version, ""


def revisar_node():
    hay, version = correr("node", "--version")
    if not hay:
        return "NO", "no instalado", "solo importa si el stack lo pide"
    _, npm = correr("npm", "--version")
    return "sí", f"{version} · npm {npm or '?'}", ""


REVISIONES = (
    ("Python", revisar_python),
    ("git", revisar_git),
    ("gh (GitHub)", revisar_gh),
    ("Docker", revisar_docker),
    ("Node", revisar_node),
)


def informe():
    filas = [(nombre, *revision()) for nombre, revision in REVISIONES]
    ancho = max(len(f[0]) for f in filas)
    lineas = [f"# Entorno de esta máquina ({platform.system()} {platform.release()})",
              f"", f"Comprobado el {HOY} con `docs/00-metodo/scripts/doctor.py`.", ""]
    lineas.append("| Herramienta | ¿Está? | Qué hay | Qué implica |")
    lineas.append("|---|---|---|---|")
    for nombre, estado, detalle, consecuencia in filas:
        lineas.append(f"| {nombre} | {estado} | {detalle} | {consecuencia or '—'} |")
    lineas += ["", "REGLA: el ROADMAP no fija una herramienta que no aparezca aquí en verde",
               "(`runbooks/planificacion.md`). Esta foto caduca: se rehace, no se edita a mano."]
    pantalla = ["", "== Entorno de esta máquina =="]
    for nombre, estado, detalle, consecuencia in filas:
        marca = {"sí": "  OK  ", "a medias": "  WARN", "NO": "  FALTA"}.get(estado, "  ?   ")
        pantalla.append(f"{marca} {nombre.ljust(ancho)}  {detalle}")
        if consecuencia:
            pantalla.append(f"{' ' * (ancho + 9)}→ {consecuencia}")
    return "\n".join(pantalla), "\n".join(lineas) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Foto del entorno de esta máquina.")
    ap.add_argument("--escribir", action="store_true",
                    help="además, deja la foto en docs/conocimiento/entorno-de-esta-maquina.md")
    args = ap.parse_args()
    pantalla, documento = informe()
    print(pantalla)
    if args.escribir:
        destino = RAIZ / "docs" / "conocimiento" / "entorno-de-esta-maquina.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(documento, encoding="utf-8")
        print(f"\n  Escrito en {destino.relative_to(RAIZ)} (se sobrescribe: es una foto, "
              f"no un histórico)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
