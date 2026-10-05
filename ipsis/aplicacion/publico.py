"""Nombres públicos (los de los archivos y la API, en inglés) ↔ internos.

La CLI y el servicio no importan ``ipsis.configuracion``: cuando necesitan
traducir un cuerpo de ``/admin`` usan estas funciones.
"""
from __future__ import annotations

from typing import Any


def a_publico(datos: Any, archivo: str) -> Any:
    """``datos`` (nombres internos) con los nombres de ``archivo`` (``personalidad``, ``estilos``…)."""
    from ipsis.configuracion.glosario import a_externo

    return a_externo(datos, archivo)


def desde_publico(datos: Any, archivo: str) -> Any:
    """Inverso de ``a_publico``."""
    from ipsis.configuracion.glosario import a_interno

    return a_interno(datos, archivo)


__all__ = ["a_publico", "desde_publico"]
