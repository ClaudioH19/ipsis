from __future__ import annotations

from ipsis.nucleo.contratos import AnswerExtractor, EvidenceVerifier
from ipsis.nucleo.esquemas import (
    ChunkRecord,
    EvidenceSpan,
    QueryAnalysis,
    RetrievalCandidate,
    RetrievalSignals,
)
from ipsis.indice.payload import payload_desde_evidencia
from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier, SentenceSelectorExtractor


def _candidato(
    chunk_id: str,
    texto: str,
    *,
    offset: int,
    score: float,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=ChunkRecord(
            chunk_id=chunk_id,
            doc_id="manual",
            doc_titulo="Manual de prueba",
            version="2",
            texto_fuente=texto,
            texto_embedding=texto,
            offset_inicio=offset,
            offset_fin=offset + len(texto),
            seccion_path=["Reglas"],
            tiene_condicion=True,
        ),
        signals=RetrievalSignals(fusion_score=score),
    )


def test_selector_y_verificador_cumplen_protocolos_tipados():
    assert isinstance(SentenceSelectorExtractor(), AnswerExtractor)
    assert isinstance(LiteralOffsetsVerifier(), EvidenceVerifier)


def test_selector_devuelve_evidencia_literal_y_prioriza_entidad():
    consulta = QueryAnalysis(
        pregunta_original="¿Qué dice el artículo 9?",
        pregunta_normalizada="¿Qué dice el artículo 9?",
    )
    sin_entidad = _candidato(
        "c-alto",
        "Este fragmento tiene similitud general, pero no contiene la referencia.",
        offset=0,
        score=0.95,
    )
    con_entidad = _candidato(
        "c-entidad",
        "Introducción. El artículo 9 fija un plazo de 10 días. Cierre.",
        offset=100,
        score=0.70,
    )
    candidatos = [sin_entidad, con_entidad]

    evidencias = SentenceSelectorExtractor(limite_caracteres=45).extraer(
        consulta,
        candidatos,
    )

    assert evidencias[0].chunk_id == "c-entidad"
    assert "artículo 9" in evidencias[0].texto
    assert evidencias[0].score == 0.70
    assert LiteralOffsetsVerifier().verificar(evidencias, candidatos) == (True, [])


def test_verificador_rechaza_texto_no_literal_aunque_el_largo_coincida():
    candidato = _candidato("c1", "dato literal", offset=20, score=0.8)
    evidencia = EvidenceSpan(
        doc_id="manual",
        chunk_id="c1",
        texto="dato alterad",
        offset_inicio=20,
        offset_fin=32,
    )

    valido, errores = LiteralOffsetsVerifier().verificar([evidencia], [candidato])

    assert valido is False
    assert errores == ["texto u offsets no literales en c1"]


def test_adaptador_de_evidencia_preserva_metadata_del_chunk():
    candidato = _candidato("c1", "inicio dato literal cierre", offset=50, score=0.8)
    evidencia = EvidenceSpan(
        doc_id="manual",
        chunk_id="c1",
        texto="dato literal",
        offset_inicio=57,
        offset_fin=69,
        seccion_path=["Reglas"],
        score=0.8,
    )

    payload = payload_desde_evidencia(evidencia, candidato.chunk)

    assert payload["texto"] == "dato literal"
    assert payload["offset_inicio"] == 57
    assert payload["offset_fin"] == 69
    assert payload["doc_titulo"] == "Manual de prueba"
    assert payload["version"] == "2"
    assert payload["tiene_condicion"] is True
