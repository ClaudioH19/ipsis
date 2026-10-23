"""Implementaciones base conectables al registry de componentes.

Este módulo contiene adaptadores del código existente al contrato declarativo.
Las dependencias pesadas se importan dentro de las factories, de modo que
consultar el catálogo no descarga modelos ni inicializa Qdrant.
"""
from __future__ import annotations

from typing import Any, Sequence

from ipsis.nucleo.registro import RegistroComponentes, registro_componentes
from ipsis.recursos.mensajes import t
from ipsis.nucleo.esquemas import EvidenceSpan, RetrievalCandidate


class ParserBuiltin:
    def parsear(self, ruta: str, **metadata: Any):
        from ipsis.ingesta.parsear import parsear_documento

        return parsear_documento(ruta, **metadata)


class ChunkerBuiltin:
    def __init__(self, estrategia: str = "CH-SEC") -> None:
        from ipsis.ingesta.chunking import ESTRATEGIAS

        if estrategia not in ESTRATEGIAS:
            raise ValueError(f"estrategia de chunking desconocida: {estrategia}")
        self.estrategia = estrategia

    def fragmentar(self, documento):
        from ipsis.ingesta.chunking import ESTRATEGIAS

        return ESTRATEGIAS[self.estrategia](documento)


class SparseEncoderBM25:
    """BM25 con los términos del proyecto; requiere las estadísticas del índice."""

    def __init__(self, estadisticas=None, paquete=None) -> None:
        self.estadisticas = estadisticas
        self.paquete = paquete

    def codificar_documentos(self, textos: Sequence[str]):
        from ipsis.indice.qdrant import vector_disperso
        from ipsis.lenguaje.lexico import bm25_doc
        from ipsis.lenguaje.texto import terminos

        return [vector_disperso(bm25_doc(terminos(t, self.paquete), self.estadisticas)) for t in textos]

    def codificar_consulta(self, texto: str):
        from ipsis.indice.qdrant import vector_disperso
        from ipsis.lenguaje.lexico import bm25_consulta
        from ipsis.lenguaje.texto import terminos

        return vector_disperso(bm25_consulta(terminos(texto, self.paquete)))


class FusionRRF:
    def __init__(self, k: int = 60) -> None:
        if k < 1:
            raise ValueError(t("runtime.positive", name="k"))
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


def _crear_retriever_qdrant(*args: Any, **kwargs: Any):
    from ipsis.consulta.recuperador import RetrieverQdrant

    if "coleccion" in kwargs:
        coleccion = kwargs.pop("coleccion")
        return RetrieverQdrant(coleccion, **kwargs)
    return RetrieverQdrant.desde_configuracion(*args, **kwargs)


def _crear_reranker_onnx(modelo: str, **opciones: Any):
    from ipsis.modelos.catalogo import obtener
    from ipsis.modelos.reranker import RerankerOnnx

    return RerankerOnnx(obtener(modelo), **opciones)


def _crear_lector_onnx(modelo: str, **opciones: Any):
    from ipsis.modelos.catalogo import obtener
    from ipsis.modelos.lector import LectorOnnx

    return LectorOnnx(obtener(modelo), **opciones)


def _crear_codificador_onnx(modelo: str = "intfloat/multilingual-e5-small", **opciones: Any):
    from ipsis.modelos.catalogo import obtener
    from ipsis.modelos.denso import CodificadorDenso

    return CodificadorDenso(obtener(modelo), **opciones)


def registrar_componentes_base(
    registro: RegistroComponentes | None = None,
) -> RegistroComponentes:
    """Registra adaptadores base sin cargar modelos ni abrir conexiones."""
    destino = registro or registro_componentes
    destino.registrar("parser", "builtin", ParserBuiltin, reemplazar=True)
    destino.registrar("chunker", "builtin", ChunkerBuiltin, reemplazar=True)
    destino.registrar("dense_encoder", "onnx", _crear_codificador_onnx, reemplazar=True)
    destino.registrar("sparse_encoder", "bm25", SparseEncoderBM25, reemplazar=True)
    destino.registrar("reranker", "onnx", _crear_reranker_onnx, reemplazar=True)
    destino.registrar("answer_reader", "onnx", _crear_lector_onnx, reemplazar=True)
    destino.registrar("retriever", "qdrant", _crear_retriever_qdrant, reemplazar=True)
    destino.registrar("fusion", "rrf", FusionRRF, reemplazar=True)
    destino.registrar("evidence_verifier", "literal_offsets", LiteralOffsetsVerifier, reemplazar=True)
    return destino


__all__ = [
    "ChunkerBuiltin", "FusionRRF", "LiteralOffsetsVerifier", "ParserBuiltin", "SparseEncoderBM25",
    "registrar_componentes_base",
]
