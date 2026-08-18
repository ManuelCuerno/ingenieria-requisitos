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


# Política de publicación del workspace (unidad 018). `agente` es el comportamiento de
# siempre: el método empuja la rama y abre el PR. `usuario` significa que publicar es cosa
# de la persona, y entonces el método se detiene en el commit/merge local y le deja el
# comando exacto. Ausente ⇒ `agente`: ningún workspace existente necesita migrar.
MODOS_PUSH = ("agente", "usuario")


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


def modo_push_de(text):
    """Valida y normaliza la clave `push:` de un repos.yaml ya leído."""
    crudo = value(text, "push") or "agente"
    if crudo not in MODOS_PUSH:
        raise RepoConfigError(
            f"repos.yaml: push inválido ({crudo!r}); valores válidos: "
            f"{' | '.join(MODOS_PUSH)}"
        )
    return crudo


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


def _leer(workspace, *, require_file=False):
    """Texto de repos.yaml (o cadena vacía si no existe y no se exige)."""
    root = Path(workspace).resolve()
    config = root / "repos.yaml"
    if config.is_symlink():
        raise RepoConfigError("repos.yaml no puede ser symlink")
    if not config.is_file():
        if require_file:
            raise RepoConfigError("repos.yaml ausente")
        return root, ""
    try:
        return root, config.read_text(encoding="utf-8")
    except OSError as exc:
        raise RepoConfigError(f"repos.yaml ilegible: {exc}") from exc


def modo_push(workspace, *, require_file=False):
    """Política de publicación declarada en repos.yaml: `agente` (defecto) | `usuario`."""
    return modo_push_de(_leer(workspace, require_file=require_file)[1])


def repo_code(workspace, *, require_file=False):
    root, text = _leer(workspace, require_file=require_file)
    # Un `push:` inválido se descubre aquí, en la misma lectura que `rama_principal`: si
    # solo fallara en quien pregunta por el modo, media herramienta seguiría corriendo con
    # una política de publicación que nadie entiende.
    modo_push_de(text)
    raw_path = value(text, "ruta_local") or "main/"
    branch = value(text, "rama_principal") or "main"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch) or ".." in branch.split("/"):
        raise RepoConfigError("repos.yaml: rama_principal inválida")
    return canonical_local_path(root, raw_path.rstrip("/")), branch
