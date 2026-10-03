"""Filtros baratos antes de recuperar: política disponible y fuera de dominio."""
from __future__ import annotations

from rag.consulta.etapas.base import _Etapa


class EtapaFiltros(_Etapa):
    nombre = "filtros"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        if m.politica_abstencion is None:
            ctx.resultado = m._abstener("generico", ctx.confianza, ctx.latencia_ms(), diagnostico=ctx.diagnostico)
            return
        decision = m.politica_abstencion.decidir_dominio(ctx.consulta, ctx.senales)
        if decision is not None:
            ctx.diagnostico["decision"] = decision.__dict__
            ctx.resultado = m._abstener("fuera_dominio", ctx.confianza, ctx.latencia_ms(), diagnostico=ctx.diagnostico)


__all__ = ["EtapaFiltros"]
