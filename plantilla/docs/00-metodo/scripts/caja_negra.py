#!/usr/bin/env python3
"""Registra incidentes de ejecución sin copiar conversaciones ni secretos.

El JSONL es material de entrada para una revisión semántica posterior. Este comando captura
contexto; no clasifica causas ni pretende reemplazar el análisis de un LLM.
"""
import argparse
import datetime
import json
import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path

import control_plane


def morir(mensaje):
    raise SystemExit(f"caja_negra: {mensaje}")


def redactar(texto):
    return control_plane.redact_secrets(texto or "").replace("***", "[REDACTADO]")


def git(repo, *argumentos):
    resultado = subprocess.run(
        ["git", "-C", str(repo), *argumentos],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return resultado.stdout.strip() if resultado.returncode == 0 else ""


def dentro(ruta, raiz):
    try:
        ruta.relative_to(raiz)
        return True
    except ValueError:
        return False


def evidencia_relativa(repo, valor):
    ruta = Path(valor)
    if ruta.is_absolute() or ".." in ruta.parts:
        morir(f"la evidencia debe ser una ruta relativa dentro del repo: {valor}")
    resuelta = (repo / ruta).resolve()
    if resuelta != repo and not dentro(resuelta, repo):
        morir(f"la evidencia sale del repo: {valor}")
    return str(ruta).replace("\\", "/")


def detectar_harness():
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID"):
        return "codex"
    if os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID"):
        return "claude"
    return os.environ.get("AGENT_HARNESS", "desconocido")


def detectar_sesion():
    for clave in (
        "CODEX_THREAD_ID",
        "CODEX_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_SESSION_ID",
        "AGENT_SESSION_ID",
    ):
        if os.environ.get(clave):
            return redactar(os.environ[clave])
    return "desconocida"


def registrar(args):
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        morir(f"el repo no existe: {repo}")
    evidencias = [evidencia_relativa(repo, item) for item in args.evidencia]
    worktree = git(repo, "rev-parse", "--show-toplevel")
    git_common = git(repo, "rev-parse", "--git-common-dir")
    if git_common and not Path(git_common).is_absolute():
        git_common = str((repo / git_common).resolve())
    registro = {
        "schema": "incidente-metarepo-v1",
        "id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "harness": detectar_harness(),
        "session_id": detectar_sesion(),
        "fase": redactar(args.fase),
        "repo_root": str(repo),
        "cwd": str(Path.cwd().resolve()),
        "worktree_root": str(Path(worktree).resolve()) if worktree else "",
        "git_common_dir": git_common,
        "branch": git(repo, "branch", "--show-current"),
        "sintoma": redactar(args.sintoma),
        "esperado": redactar(args.esperado),
        "actual": redactar(args.actual),
        "workaround": redactar(args.workaround),
        "evidencia": evidencias,
    }
    directorio = repo / ".caja-negra"
    directorio.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        directorio.chmod(0o700)
    except OSError:
        pass
    destino = directorio / "incidentes.jsonl"
    descriptor = os.open(str(destino), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(descriptor, "a", encoding="utf-8") as salida:
            salida.write(json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n")
    finally:
        try:
            destino.chmod(0o600)
        except OSError:
            pass
    print(f"OK incidente {registro['id']} registrado en {destino}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("registrar", help="añade un episodio a la caja negra privada")
    p.add_argument("--repo", default=".", help="raíz declarada del meta-repo")
    p.add_argument("--fase", required=True)
    p.add_argument("--sintoma", required=True)
    p.add_argument("--esperado", required=True)
    p.add_argument("--actual", required=True)
    p.add_argument("--workaround", default="")
    p.add_argument("--evidencia", action="append", default=[])
    p.set_defaults(func=registrar)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
