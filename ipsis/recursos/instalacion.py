"""La misma ruta de instalación uv en la ayuda y los errores del paquete."""
from __future__ import annotations

import tomllib
from pathlib import Path

FUENTE = "git+https://github.com/ClaudioH19/ipsis.git"
INSTALAR = f'uv tool install --python 3.12 "ipsis @ {FUENTE}"'


def comando_extra(extra: str) -> str:
    try:
        proyecto = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        proyecto = {}
    if proyecto.get("project", {}).get("name") == "ipsis":
        return f"uv sync --extra {extra}"
    return f'uv tool install --force --python 3.12 "ipsis[{extra}] @ {FUENTE}"'
