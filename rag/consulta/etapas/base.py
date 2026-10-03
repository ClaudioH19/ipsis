"""Base común de las etapas de la cascada."""
from __future__ import annotations


class _Etapa:
    """Base de las etapas: guardan el motor del que leen sus componentes."""

    nombre = ""
    requiere_admision = True

    def __init__(self, motor) -> None:
        self.motor = motor


__all__ = ["_Etapa"]
