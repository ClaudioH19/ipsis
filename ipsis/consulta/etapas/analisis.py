"""Etapa de análisis: normaliza la pregunta y detecta su intención."""
from __future__ import annotations

from ipsis.consulta.etapas.base import _Etapa


class EtapaAnalisis(_Etapa):
    nombre = "analisis"

    def ejecutar(self, ctx) -> None:
        ctx.consulta = self.motor._analizar(ctx.pregunta, ctx.id_sesion)


__all__ = ["EtapaAnalisis"]
