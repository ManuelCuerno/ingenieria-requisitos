#!/usr/bin/env python3
"""Lectura única y confinada de ``repos.yaml``.

``ruta_local`` siempre es una ruta relativa directa del workspace. No se aceptan rutas
absolutas, ``..`` ni componentes symlink: todos los consumidores obtienen así exactamente
la misma frontera antes de pasar la ruta a Git o escribir en ella.
"""

import re
from pathlib import Path, PureWindowsPath

import workspace_paths


class RepoConfigError(ValueError):
    pass


def value(text, key):
    pattern = re.compile(rf"^\s*{re.escape(key)}:\s*(.*?)\s*$")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            result = match.group(1).strip().strip("\"'")
            if result.startswith("PENDIENTE"):
                return ""
            return result.split("  #", 1)[0].strip()
    return ""


def canonical_local_path(workspace, raw_path):
    root = Path(workspace).resolve()
    raw = str(raw_path or "").strip()
    candidate = Path(raw)
    windows = PureWindowsPath(raw)
    if not raw:
        raise RepoConfigError("repos.yaml: ruta_local ausente")
    if candidate.is_absolute() or windows.is_absolute() or windows.drive:
        raise RepoConfigError("repos.yaml: ruta_local debe ser relativa al workspace")
    if ".." in candidate.parts or ".." in windows.parts:
        raise RepoConfigError("repos.yaml: ruta_local no admite '..'")
    if candidate.parts in {(), (".",)}:
        raise RepoConfigError("repos.yaml: ruta_local no puede ser el workspace")

    try:
        resolved = workspace_paths.confined_path(
            root, root / candidate, label="repos.yaml: ruta_local"
        )
    except workspace_paths.WorkspacePathError as exc:
        raise RepoConfigError(str(exc)) from exc
    if resolved == root:
        raise RepoConfigError("repos.yaml: ruta_local no puede ser el workspace")
    return resolved


def repo_code(workspace, *, require_file=False):
    root = Path(workspace).resolve()
    config = root / "repos.yaml"
    if config.is_symlink():
        raise RepoConfigError("repos.yaml no puede ser symlink")
    if not config.is_file():
        if require_file:
            raise RepoConfigError("repos.yaml ausente")
        text = ""
    else:
        try:
            text = config.read_text(encoding="utf-8")
        except OSError as exc:
            raise RepoConfigError(f"repos.yaml ilegible: {exc}") from exc
    raw_path = value(text, "ruta_local") or "main/"
    branch = value(text, "rama_principal") or "main"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch) or ".." in branch.split("/"):
        raise RepoConfigError("repos.yaml: rama_principal inválida")
    return canonical_local_path(root, raw_path.rstrip("/")), branch
