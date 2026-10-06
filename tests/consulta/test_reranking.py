"""Etapa de reranking."""
from __future__ import annotations

import pytest

from ipsis.consulta.contexto import ContextoConsulta
from ipsis.consulta.etapas.reranking import EtapaReranking
from ipsis.nucleo.esquemas import ChunkRecord, RetrievalCandidate, RetrievalSignals


def _candidato(chunk_id: str, texto: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=ChunkRecord(chunk_id=chunk_id, doc_id="d", doc_titulo="D", version="1", texto_fuente=texto,
                          texto_embedding=texto, offset_inicio=0, offset_fin=len(texto)),
        signals=RetrievalSignals(fusion_score=0.5, fusion_rank=1),
    )


class _RerankerFalso:
    def __init__(self, puntajes):
        self.puntajes = puntajes

    def puntuar(self, _pregunta, pasajes):
        return [self.puntajes[p] for p in pasajes]


class _Perfil:
    class cascada:  # noqa: N801 -- imita la forma del perfil
        rerank_k = 2


class _Motor:
    def __init__(self, puntajes):
        self.reranker = _RerankerFalso(puntajes)
        self.perfil_instalacion = _Perfil()


def test_ordena_por_puntaje_desempata_por_id_y_recorta():
    ctx = ContextoConsulta(pregunta="p", id_sesion="s", diagnostico={})
    ctx.candidatos = [_candidato("c3", "a"), _candidato("c1", "b"), _candidato("c2", "c")]
    EtapaReranking(_Motor({"a": 1.0, "b": 5.0, "c": 5.0})).ejecutar(ctx)
    assert [c.chunk.chunk_id for c in ctx.candidatos] == ["c1", "c2"]
    assert ctx.puntajes_rerank == [5.0, 5.0]
    assert ctx.diagnostico["puntajes_rerank"] == [5.0, 5.0]


def test_sin_reranker_no_cambia_nada():
    motor = _Motor({})
    motor.reranker = None
    ctx = ContextoConsulta(pregunta="p", id_sesion="s")
    ctx.candidatos = [_candidato("c1", "a")]
    EtapaReranking(motor).ejecutar(ctx)
    assert ctx.puntajes_rerank is None


@pytest.mark.modelos("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
def test_modelo_real_pone_primero_el_pasaje_que_responde():
    from ipsis.modelos.catalogo import obtener
    from ipsis.modelos.reranker import RerankerOnnx

    reranker = RerankerOnnx(obtener("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"))
    pasajes = ["La garantía cubre 24 meses desde la fecha de compra.",
               "El filtro de sedimentos se cambia cada 6 meses."]
    puntajes = reranker.puntuar("¿Cada cuánto se cambia el filtro de sedimentos?", pasajes)
    assert puntajes[1] > puntajes[0]
