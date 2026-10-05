"""Leer y escribir los YAML del proyecto pasando por el glosario (inglés en el disco)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ipsis.configuracion.glosario import a_externo, a_interno


def interpretar(texto: str, archivo: str) -> dict[str, Any]:
    """Texto YAML de un archivo del proyecto → datos con nombres internos."""
    return a_interno(yaml.safe_load(texto) or {}, archivo)


def leer(ruta: str | Path, archivo: str) -> dict[str, Any]:
    """El archivo con nombres internos; ``{}`` si no existe."""
    ruta = Path(ruta)
    if not ruta.is_file():
        return {}
    return interpretar(ruta.read_text(encoding="utf-8"), archivo)


def volcar(datos: dict[str, Any], archivo: str) -> str:
    """Datos internos → texto YAML del archivo (claves y valores en inglés)."""
    return yaml.safe_dump(a_externo(datos, archivo), allow_unicode=True, sort_keys=False)


def escribir(ruta: str | Path, datos: dict[str, Any], archivo: str, encabezado: str = "") -> Path:
    """Escritura atómica (temporal + reemplazo) con nombres en inglés."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(encabezado + volcar(datos, archivo), encoding="utf-8")
    os.replace(temporal, ruta)
    return ruta


__all__ = ["escribir", "interpretar", "leer", "volcar"]
