#!/usr/bin/env python3
"""Primitivas stdlib para rutas confinadas sin enlaces simbólicos."""

import os
import stat
from pathlib import Path


class WorkspacePathError(ValueError):
    pass


def confined_path(root, candidate, *, label="ruta"):
    canonical_root = Path(root).resolve()
    lexical = Path(candidate)
    if not lexical.is_absolute():
        lexical = canonical_root / lexical
    try:
        relative = lexical.relative_to(canonical_root)
    except ValueError as exc:
        raise WorkspacePathError(f"{label} queda fuera del workspace") from exc
    if ".." in relative.parts:
        raise WorkspacePathError(f"{label} contiene '..'")
    cursor = canonical_root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise WorkspacePathError(f"{label} no admite symlink ({part})")
    resolved = lexical.resolve()
    try:
        resolved.relative_to(canonical_root)
    except ValueError as exc:
        raise WorkspacePathError(f"{label} escapa del workspace") from exc
    return resolved


def regular_file(root, candidate, *, label="fichero"):
    path = confined_path(root, candidate, label=label)
    try:
        mode = os.lstat(path).st_mode
    except OSError as exc:
        raise WorkspacePathError(f"{label} no es un fichero regular legible: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise WorkspacePathError(f"{label} no es un fichero regular")
    return path
