"""Recursos globales distribuidos con :mod:`rag`.

Las plantillas viven dentro del paquete para que ``ipsis init`` funcione igual
desde una wheel, una instalación desde GitHub o un checkout editable. Ninguna
plantilla depende del repositorio fuente ni del directorio de instalación.
"""
from __future__ import annotations

from importlib.resources import files


def leer_plantilla(nombre: str) -> str:
    """Devuelve una plantilla UTF-8 incluida en ``ipsis/recursos/plantillas``."""
    recurso = files(__package__).joinpath("plantillas", *nombre.split("/"))
    return recurso.read_text(encoding="utf-8")

