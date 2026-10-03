"""Contratos de los componentes intercambiables de la tubería.

Los protocolos describen capacidades, no implementaciones. Esto mantiene la
API, CLI y servicio independientes de Docling, Qdrant o un modelo concreto.
Las implementaciones actuales se adaptarán gradualmente a estos contratos.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Protocol, runtime_checkable

from rag.nucleo.esquemas import (
    AssistantResult,
    ChunkRecord,
    DecisionAbstencion,
    DocumentRecord,
    EvidenceSpan,
    FiltroEntidad,
    QueryAnalysis,
    RetrievalCandidate,
    SenalesRecuperacion,
)


@runtime_checkable
class DocumentParser(Protocol):
    def parsear(self, ruta: str, **metadata: Any) -> DocumentRecord: ...


@runtime_checkable
class Chunker(Protocol):
    def fragmentar(self, documento: DocumentRecord) -> Iterable[ChunkRecord]: ...


@runtime_checkable
class DenseEncoder(Protocol):
    def codificar_documentos(self, textos: Sequence[str]) -> Any: ...
    def codificar_consultas(self, textos: Sequence[str]) -> Any: ...


@runtime_checkable
class SparseEncoder(Protocol):
    def codificar_documentos(self, textos: Sequence[str]) -> Any: ...
    def codificar_consulta(self, texto: str) -> Any: ...


@runtime_checkable
class Retriever(Protocol):
    """Dueño de un índice ya construido.

    ``estimar_confianza`` va separado de ``recuperar`` porque el servicio
    decide si la pregunta pertenece al dominio antes de pagar la recuperación
    completa. Los inventarios alimentan la verificación de premisa y el
    grounding léxico sin que el servicio conozca dónde se persisten.
    """

    def estimar_confianza(self, consulta: QueryAnalysis, limite: int) -> SenalesRecuperacion: ...
    def recuperar(self, consulta: QueryAnalysis, limite: int,
                  filtro: FiltroEntidad | None = None) -> list[RetrievalCandidate]: ...
    def n_chunks(self) -> int: ...
    def inventario_entidades(self) -> set[str]: ...
    def estadisticas_lexico(self) -> Any: ...
    def calentar(self) -> None: ...


@runtime_checkable
class AbstentionPolicy(Protocol):
    """Decide si continuar, responder, relacionar o abstenerse."""

    def decidir_dominio(
        self,
        consulta: QueryAnalysis,
        senales: SenalesRecuperacion,
    ) -> DecisionAbstencion | None: ...

    def decidir(
        self,
        consulta: QueryAnalysis,
        senales: SenalesRecuperacion,
        candidatos: Sequence[RetrievalCandidate],
    ) -> DecisionAbstencion: ...


@runtime_checkable
class FusionStrategy(Protocol):
    def fusionar(self, resultados: Sequence[Sequence[RetrievalCandidate]], limite: int) -> list[RetrievalCandidate]: ...


@runtime_checkable
class Reranker(Protocol):
    def reordenar(self, consulta: QueryAnalysis, candidatos: Sequence[RetrievalCandidate]) -> list[RetrievalCandidate]: ...


@runtime_checkable
class IntentClassifier(Protocol):
    def analizar(self, pregunta: str, contexto: dict[str, Any] | None = None) -> QueryAnalysis: ...


@runtime_checkable
class AnswerExtractor(Protocol):
    def extraer(self, consulta: QueryAnalysis, candidatos: Sequence[RetrievalCandidate]) -> list[EvidenceSpan]: ...


@runtime_checkable
class EvidenceVerifier(Protocol):
    def verificar(
        self,
        evidencias: Sequence[EvidenceSpan],
        candidatos: Sequence[RetrievalCandidate],
    ) -> tuple[bool, list[str]]: ...


@runtime_checkable
class ResponseRenderer(Protocol):
    def renderizar(self, resultado: AssistantResult) -> str: ...


__all__ = [
    "AbstentionPolicy", "AnswerExtractor", "Chunker", "DenseEncoder", "DocumentParser",
    "EvidenceVerifier", "FusionStrategy", "IntentClassifier", "Reranker",
    "ResponseRenderer", "Retriever", "SparseEncoder",
]
