"""Implementaciones base conectables al registry V2.

Este módulo contiene adaptadores del código existente al contrato declarativo.
Las dependencias pesadas se importan dentro de las factories, de modo que
consultar el catálogo no descarga modelos ni inicializa Qdrant.
"""
from __future__ import annotations

import re
from typing import Any, Sequence

from rag.nucleo.registro import RegistroComponentes, registro_componentes
from rag.nucleo.esquemas import EvidenceSpan, RetrievalCandidate


class ParserBuiltin:
    def parsear(self, ruta: str, **metadata: Any):
        from rag.ingesta.parsear import parsear_documento

        return parsear_documento(ruta, **metadata)


class ChunkerBuiltin:
    def __init__(self, estrategia: str = "CH-SEC") -> None:
        from rag.ingesta.chunking import ESTRATEGIAS

        if estrategia not in ESTRATEGIAS:
            raise ValueError(f"estrategia de chunking desconocida: {estrategia}")
        self.estrategia = estrategia

    def fragmentar(self, documento):
        from rag.ingesta.chunking import ESTRATEGIAS

        return ESTRATEGIAS[self.estrategia](documento)


class DenseEncoderSentenceTransformers:
    def __new__(cls, modelo: str = "intfloat/multilingual-e5-small", **kwargs: Any):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(modelo, **kwargs)


class SparseEncoderBM25:
    def __init__(self, vocabulario: dict[str, int] | None = None) -> None:
        self.vocabulario = vocabulario or {}

    def codificar_documentos(self, textos: Sequence[str]):
        from rag.indice.qdrant import texto_a_vector_sparse

        return [texto_a_vector_sparse(texto, self.vocabulario) for texto in textos]

    def codificar_consulta(self, texto: str):
        from rag.indice.qdrant import texto_a_vector_sparse

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
    def __init__(
        self,
        limite_caracteres: int = 500,
        metodo: str = "lexico",
        modelo_st: Any = None,
        prefijo_query: str = "",
    ) -> None:
        if limite_caracteres < 1:
            raise ValueError("limite_caracteres debe ser mayor que cero")
        if metodo not in {"lexico", "denso"}:
            raise ValueError("metodo debe ser 'lexico' o 'denso'")
        self.limite_caracteres = limite_caracteres
        self.metodo = metodo
        self.modelo_st = modelo_st
        self.prefijo_query = prefijo_query

    def extraer(self, consulta, candidatos: Sequence[RetrievalCandidate]) -> list[EvidenceSpan]:
        from rag.indice.payload import payload_desde_chunk
        from rag.lenguaje.entidades import extraer_entidades
        from rag.consulta.etapas.seleccion import (
            ordenar_por_pertinencia_global,
            recortar_payload_a_texto_pertinente,
        )

        entidades = extraer_entidades(consulta.pregunta_original)
        payloads = [
            recortar_payload_a_texto_pertinente(
                payload_desde_chunk(candidato.chunk),
                consulta.pregunta_original,
                self.limite_caracteres,
                metodo=self.metodo,
                modelo_st=self.modelo_st,
                prefijo_query=self.prefijo_query,
                entidades_pregunta=entidades,
            )
            for candidato in candidatos
        ]
        scores = [candidato.score for candidato in candidatos]
        payloads, scores = ordenar_por_pertinencia_global(payloads, scores)
        return [
            EvidenceSpan(
                doc_id=payload["doc_id"],
                chunk_id=payload["chunk_id"],
                texto=payload["texto"],
                offset_inicio=payload["offset_inicio"],
                offset_fin=payload["offset_fin"],
                seccion_path=payload.get("seccion_path") or [],
                score=score,
            )
            for payload, score in zip(payloads, scores, strict=True)
        ]


class LiteralOffsetsVerifier:
    def verificar(
        self,
        evidencias: Sequence[EvidenceSpan],
        candidatos: Sequence[RetrievalCandidate],
    ) -> tuple[bool, list[str]]:
        errores: list[str] = []
        chunks = {candidato.chunk.chunk_id: candidato.chunk for candidato in candidatos}
        for evidencia in evidencias:
            chunk = chunks.get(evidencia.chunk_id)
            if chunk is None or chunk.doc_id != evidencia.doc_id:
                errores.append(f"chunk fuente ausente para {evidencia.chunk_id}")
                continue
            inicio = evidencia.offset_inicio - chunk.offset_inicio
            fin = evidencia.offset_fin - chunk.offset_inicio
            if inicio < 0 or fin > len(chunk.texto_fuente):
                errores.append(f"evidencia fuera del chunk {evidencia.chunk_id}")
                continue
            if chunk.texto_fuente[inicio:fin] != evidencia.texto:
                errores.append(f"texto u offsets no literales en {evidencia.chunk_id}")
        return not errores, errores


class RulesIntentClassifier:
    def analizar(self, pregunta: str, contexto: dict[str, Any] | None = None):
        from rag.nucleo.esquemas import QueryAnalysis

        normalizada = re.sub(r"\s+", " ", pregunta.strip())
        return QueryAnalysis(
            pregunta_original=pregunta,
            pregunta_normalizada=normalizada,
            contexto=contexto or {},
        )


class TemplatesResponseRenderer:
    """Renderer mínimo para mantener la salida de dominio independiente.

    La composición extractiva ya produce ``mensaje_usuario``; este adaptador
    declara esa decisión en el registro y deja un punto de extensión para
    renderers alternativos sin acoplarlos al transporte HTTP.
    """

    def renderizar(self, resultado) -> str:
        return resultado.mensaje_usuario


def _crear_retriever_qdrant(*args: Any, **kwargs: Any):
    from rag.consulta.etapas.recuperacion import RetrieverQdrant

    if "coleccion" in kwargs:
        coleccion = kwargs.pop("coleccion")
        return RetrieverQdrant(coleccion, **kwargs)
    return RetrieverQdrant.desde_configuracion(*args, **kwargs)


def registrar_componentes_base(
    registro: RegistroComponentes | None = None,
) -> RegistroComponentes:
    """Registra adaptadores base sin cargar modelos ni abrir conexiones."""
    destino = registro or registro_componentes
    destino.registrar("parser", "builtin", ParserBuiltin, reemplazar=True)
    destino.registrar("chunker", "builtin", ChunkerBuiltin, reemplazar=True)
    destino.registrar("dense_encoder", "sentence_transformers", DenseEncoderSentenceTransformers, reemplazar=True)
    destino.registrar("sparse_encoder", "bm25", SparseEncoderBM25, reemplazar=True)
    destino.registrar("retriever", "qdrant", _crear_retriever_qdrant, reemplazar=True)
    from rag.consulta.etapas.politica import LayeredV1

    destino.registrar("abstention_policy", "layered_v1", LayeredV1, reemplazar=True)
    destino.registrar("fusion", "rrf", FusionRRF, reemplazar=True)
    destino.registrar("answer_extractor", "sentence_selector", SentenceSelectorExtractor, reemplazar=True)
    destino.registrar("evidence_verifier", "literal_offsets", LiteralOffsetsVerifier, reemplazar=True)
    destino.registrar("intent_classifier", "rules", RulesIntentClassifier, reemplazar=True)
    destino.registrar("response_renderer", "templates", TemplatesResponseRenderer, reemplazar=True)
    return destino


__all__ = [
    "ChunkerBuiltin", "DenseEncoderSentenceTransformers", "FusionRRF",
    "LiteralOffsetsVerifier", "ParserBuiltin", "RulesIntentClassifier",
    "SentenceSelectorExtractor", "SparseEncoderBM25", "TemplatesResponseRenderer",
    "registrar_componentes_base",
]
