"""Etapa de reranking: reordena los candidatos con un cross-encoder."""
from __future__ import annotations

import math

from ipsis.consulta.etapas.base import _Etapa


def sigmoide(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class EtapaReranking(_Etapa):
    """Lee pregunta y pasaje juntos (cross-encoder): distingue mejor «responde»
    de «se parece» que el coseno del recuperador. Deja ``rerank_k`` candidatos."""

    nombre = "reranking"
    usa_modelos = True

    def ejecutar(self, ctx) -> None:
        m = self.motor
        if m.reranker is None or not ctx.candidatos:
            return
        perfil = getattr(m, "perfil_instalacion", None)
        limite = getattr(perfil.cascada, "rerank_candidatos", None) if perfil is not None else None
        # Los que la fusión dejó más abajo no se puntúan: van detrás, en su orden.
        resto = ctx.candidatos[limite:] if limite else []
        if limite:
            ctx.candidatos = ctx.candidatos[:limite]
        puntajes = m.reranker.puntuar(ctx.pregunta, [c.chunk.texto_fuente for c in ctx.candidatos])
        orden = sorted(
            range(len(ctx.candidatos)),
            key=lambda i: (-puntajes[i], ctx.candidatos[i].chunk.chunk_id),
        )
        k = perfil.cascada.rerank_k if perfil is not None and perfil.cascada.rerank_k else len(orden)
        ctx.descartados_rerank = [ctx.candidatos[i] for i in orden[k:]] + list(resto)
        orden = orden[:k]
        ctx.candidatos = [ctx.candidatos[i] for i in orden]
        ctx.puntajes_rerank = [puntajes[i] for i in orden]
        ctx.diagnostico["puntajes_rerank"] = [round(p, 4) for p in ctx.puntajes_rerank]
        ctx.diagnostico["rerank"] = [{"chunk_id": c.chunk.chunk_id, "score": round(p, 4)}
                                     for c, p in zip(ctx.candidatos, ctx.puntajes_rerank)]


__all__ = ["EtapaReranking", "sigmoide"]
