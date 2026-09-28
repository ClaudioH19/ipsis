"""Implementaciones base conectables al registry V2.

Este módulo contiene adaptadores del código existente al contrato declarativo.
Las dependencias pesadas se importan dentro de las factories, de modo que
consultar el catálogo no descarga modelos ni inicializa Qdrant.
"""
from __future__ import annotations

import re
from typing import Any, Sequence

from rag.componentes import RegistroComponentes, registro_componentes
from rag.esquemas import EvidenceSpan, RetrievalCandidate


class ParserBuiltin:
    def parsear(self, ruta: str, **metadata: Any):
        from rag.parsear import parsear_documento

        return parsear_documento(ruta, **metadata)


class ChunkerBuiltin:
    def __init__(self, estrategia: str = "CH-SEC") -> None:
        from rag.chunking import ESTRATEGIAS

        if estrategia not in ESTRATEGIAS:
            raise ValueError(f"estrategia de chunking desconocida: {estrategia}")
        self.estrategia = estrategia

    def fragmentar(self, documento):
        from rag.chunking import ESTRATEGIAS

        return ESTRATEGIAS[self.estrategia](documento)


class DenseEncoderSentenceTransformers:
    def __new__(cls, modelo: str = "intfloat/multilingual-e5-small", **kwargs: Any):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(modelo, **kwargs)


class SparseEncoderBM25:
    def __init__(self, vocabulario: dict[str, int] | None = None) -> None:
        self.vocabulario = vocabulario or {}

    def codificar_documentos(self, textos: Sequence[str]):
        from rag.corpus import texto_a_vector_sparse

        return [texto_a_vector_sparse(texto, self.vocabulario) for texto in textos]

    def codificar_consulta(self, texto: str):
        from rag.corpus import texto_a_vector_sparse

        return texto_a_vector_sparse(texto, self.vocabulario)


class FusionRRF:
    def __init__(self, k: int = 60) -> None:
        if k < 1:
            raise ValueError("k debe ser mayor que cero")
        self.k = k

    def fusionar(
        self,
        resultados: Sequence[Sequence[RetrievalCandidate]],
        limite: int,
    ) -> list[RetrievalCandidate]:
        acumulados: dict[str, tuple[float, RetrievalCandidate]] = {}
        for candidatos in resultados:
            for rango, candidato in enumerate(candidatos, start=1):
                clave = candidato.chunk.chunk_id
                score, existente = acumulados.get(clave, (0.0, candidato))
                acumulados[clave] = (score + 1.0 / (self.k + rango), existente)

        ordenados = sorted(
            acumulados.values(),
            key=lambda item: (-item[0], item[1].chunk.chunk_id),
        )
        salida: list[RetrievalCandidate] = []
        for rango, (score, candidato) in enumerate(ordenados[:limite], start=1):
            candidato_actualizado = candidato.model_copy(deep=True)
            candidato_actualizado.signals.fusion_score = score
            candidato_actualizado.signals.fusion_rank = rango
            salida.append(candidato_actualizado)
        return salida


class SentenceSelectorExtractor:
    def __init__(self, limite_caracteres: int = 500) -> None:
        self.limite_caracteres = limite_caracteres

    def extraer(self, consulta, candidatos: Sequence[RetrievalCandidate]) -> list[EvidenceSpan]:
        from rag.seleccion_fragmento import seleccionar_texto_pertinente

        evidencias: list[EvidenceSpan] = []
        for candidato in candidatos:
            chunk = candidato.chunk
            seleccionado = seleccionar_texto_pertinente(
                consulta.pregunta_original,
                chunk.texto_fuente,
                chunk.offset_inicio,
                self.limite_caracteres,
            )
            evidencias.append(EvidenceSpan(
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                texto=seleccionado.texto,
                offset_inicio=seleccionado.offset_inicio,
                offset_fin=seleccionado.offset_fin,
                seccion_path=chunk.seccion_path,
                score=candidato.signals.fusion_score,
            ))
        return evidencias


class LiteralOffsetsVerifier:
    def verificar(self, evidencias: Sequence[EvidenceSpan]) -> tuple[bool, list[str]]:
        errores: list[str] = []
        for evidencia in evidencias:
            if evidencia.offset_fin - evidencia.offset_inicio != len(evidencia.texto):
                errores.append(f"offsets inválidos en {evidencia.chunk_id}")
        return not errores, errores


class RulesIntentClassifier:
    def analizar(self, pregunta: str, contexto: dict[str, Any] | None = None):
        from rag.esquemas import QueryAnalysis

        normalizada = re.sub(r"\s+", " ", pregunta.strip())
        return QueryAnalysis(
            pregunta_original=pregunta,
            pregunta_normalizada=normalizada,
            contexto=contexto or {},
        )


def registrar_componentes_base(
    registro: RegistroComponentes | None = None,
) -> RegistroComponentes:
    """Registra adaptadores base sin cargar modelos ni abrir conexiones."""
    destino = registro or registro_componentes
    destino.registrar("parser", "builtin", ParserBuiltin, reemplazar=True)
    destino.registrar("chunker", "builtin", ChunkerBuiltin, reemplazar=True)
    destino.registrar("dense_encoder", "sentence_transformers", DenseEncoderSentenceTransformers, reemplazar=True)
    destino.registrar("sparse_encoder", "bm25", SparseEncoderBM25, reemplazar=True)
    destino.registrar("fusion", "rrf", FusionRRF, reemplazar=True)
    destino.registrar("answer_extractor", "sentence_selector", SentenceSelectorExtractor, reemplazar=True)
    destino.registrar("evidence_verifier", "literal_offsets", LiteralOffsetsVerifier, reemplazar=True)
    destino.registrar("intent_classifier", "rules", RulesIntentClassifier, reemplazar=True)
    return destino


__all__ = [
    "ChunkerBuiltin", "DenseEncoderSentenceTransformers", "FusionRRF",
    "LiteralOffsetsVerifier", "ParserBuiltin", "RulesIntentClassifier",
    "SentenceSelectorExtractor", "SparseEncoderBM25", "registrar_componentes_base",
]
