"""Contratos de los componentes intercambiables de la tubería.

Los protocolos describen capacidades, no implementaciones. Esto mantiene la
API, CLI y servicio independientes de Docling, Qdrant o un modelo concreto.
Las implementaciones actuales se adaptarán gradualmente a estos contratos.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Protocol, runtime_checkable

from ipsis.nucleo.esquemas import (
    AssistantResult,
    ChunkRecord,
    DocumentRecord,
    EvidenceSpan,
    FiltroEntidad,
    QueryAnalysis,
    RetrievalCandidate,
)


@runtime_checkable
class QueryEngine(Protocol):
    """Frontera de consulta; independiente de clasificador, política y pipeline."""

    pipeline: str
    backend: str
    abstencion_calibrada: bool
    control_admision: Any

    def consultar(self, pregunta: str, id_sesion: str) -> AssistantResult: ...
    def calentar(self) -> None: ...
    def cerrar(self) -> None: ...
    def n_chunks(self) -> int: ...
    def inventario_entidades(self) -> set[str]: ...
    def respuesta_conversacional(self, categoria: str, pregunta: str = "") -> str: ...


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

    Los inventarios y las estadísticas léxicas alimentan la preparación de la
    pregunta (ortografía, sinónimos) sin que el servicio conozca dónde se persisten.
    """

    def recuperar(self, consulta: QueryAnalysis, limite: int,
                  filtro: FiltroEntidad | None = None) -> list[RetrievalCandidate]: ...
    def n_chunks(self) -> int: ...
    def inventario_entidades(self) -> set[str]: ...
    def estadisticas_lexico(self) -> Any: ...
    def calentar(self) -> None: ...


@runtime_checkable
class FusionStrategy(Protocol):
    def fusionar(self, resultados: Sequence[Sequence[RetrievalCandidate]], limite: int) -> list[RetrievalCandidate]: ...


@runtime_checkable
class Reranker(Protocol):
    def reordenar(self, consulta: QueryAnalysis, candidatos: Sequence[RetrievalCandidate]) -> list[RetrievalCandidate]: ...


@runtime_checkable
class EvidenceVerifier(Protocol):
    def verificar(
        self,
        evidencias: Sequence[EvidenceSpan],
        candidatos: Sequence[RetrievalCandidate],
    ) -> tuple[bool, list[str]]: ...


__all__ = [
    "Chunker", "DenseEncoder", "DocumentParser", "EvidenceVerifier", "FusionStrategy", "Reranker",
    "Retriever", "SparseEncoder", "QueryEngine",
]
