"""Esquemas versionados que conectarán las etapas de la tubería V2."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1


class EsquemaEstricto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(default=SCHEMA_VERSION, ge=1)


class ElementRecord(EsquemaEstricto):
    element_id: str = Field(min_length=1)
    tipo: Literal["titulo", "parrafo", "lista", "tabla", "imagen", "pie", "otro"]
    texto: str
    offset_inicio: int = Field(ge=0)
    offset_fin: int = Field(ge=0)
    pagina: int | None = Field(default=None, ge=1)
    seccion_path: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validar_offsets(self):
        if self.offset_fin < self.offset_inicio:
            raise ValueError("offset_fin debe ser mayor o igual a offset_inicio")
        return self


class DocumentRecord(EsquemaEstricto):
    doc_id: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    version: str = "1"
    ruta_origen: str | None = None
    texto_completo: str
    elementos: list[ElementRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkRecord(EsquemaEstricto):
    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    texto_fuente: str
    texto_embedding: str
    offset_inicio: int = Field(ge=0)
    offset_fin: int = Field(ge=0)
    seccion_path: list[str] = Field(default_factory=list)
    tipo_contenido: str = "narrativo"
    parent_id: str | None = None
    prev_id: str | None = None
    next_id: str | None = None
    pagina: int | None = Field(default=None, ge=1)
    # Campos que la cita, los conectores y la verificación de premisa leen en
    # cada consulta; por eso son tipados y no viven en ``metadata``.
    doc_titulo: str = ""
    version: str = "1"
    tiene_excepcion: bool = False
    tiene_condicion: bool = False
    entidades: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validar_offsets(self):
        if self.offset_fin < self.offset_inicio:
            raise ValueError("offset_fin debe ser mayor o igual a offset_inicio")
        return self


class QueryAnalysis(EsquemaEstricto):
    pregunta_original: str = Field(min_length=1)
    pregunta_normalizada: str = Field(min_length=1)
    intencion: str = "desconocida"
    entidades: list[dict[str, Any]] = Field(default_factory=list)
    filtros: dict[str, Any] = Field(default_factory=dict)
    terminos_protegidos: list[str] = Field(default_factory=list)
    contexto: dict[str, Any] = Field(default_factory=dict)


class RetrievalSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dense_score: float | None = None
    dense_rank: int | None = Field(default=None, ge=1)
    sparse_score: float | None = None
    sparse_rank: int | None = Field(default=None, ge=1)
    fusion_score: float | None = None
    fusion_rank: int | None = Field(default=None, ge=1)
    reranker_score: float | None = None
    reranker_rank: int | None = Field(default=None, ge=1)


class RetrievalCandidate(EsquemaEstricto):
    chunk: ChunkRecord
    signals: RetrievalSignals = Field(default_factory=RetrievalSignals)

    @property
    def score(self) -> float:
        """Puntaje del orden final: el de la etapa más tardía que lo asignó."""
        for valor in (self.signals.reranker_score, self.signals.fusion_score,
                      self.signals.dense_score, self.signals.sparse_score):
            if valor is not None:
                return valor
        return 0.0


class FiltroEntidad(EsquemaEstricto):
    """Restringe la recuperación a chunks que contienen esta entidad exacta.

    Es propio del contrato, no de un motor: cada retriever lo traduce (un
    ``Filter`` en Qdrant, un ``JOIN`` en SQLite)."""
    valor_norm: str = Field(min_length=1)


class SenalesRecuperacion(EsquemaEstricto):
    """Qué tan bien cubre el índice una pregunta, antes de recuperar.

    Cada retriever define cómo calcula ``confianza_top1`` (en Qdrant, el coseno
    denso del mejor chunk). No son comparables entre retrievers: los umbrales
    de abstención se configuran por retriever."""
    confianza_top1: float
    margen_top1_top2: float


class EvidenceSpan(EsquemaEstricto):
    doc_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    texto: str
    offset_inicio: int = Field(ge=0)
    offset_fin: int = Field(ge=0)
    seccion_path: list[str] = Field(default_factory=list)
    score: float | None = None

    @model_validator(mode="after")
    def validar_span(self):
        if self.offset_fin < self.offset_inicio:
            raise ValueError("offset_fin debe ser mayor o igual a offset_inicio")
        if self.offset_fin - self.offset_inicio != len(self.texto):
            raise ValueError("el largo del texto debe coincidir con sus offsets")
        return self


class AssistantState(str, Enum):
    RESPUESTA_DIRECTA = "respuesta_directa"
    RESPUESTA_PARCIAL = "respuesta_parcial"
    RELACIONADO = "relacionado"
    NECESITA_ACLARACION = "necesita_aclaracion"
    MULTIPLES_RESPUESTAS = "multiples_respuestas"
    CONFLICTO_DOCUMENTAL = "conflicto_documental"
    SIN_RESPUESTA = "sin_respuesta"
    FUERA_DOMINIO = "fuera_dominio"
    CONVERSACIONAL = "conversacional"
    DEGRADADO = "degradado"
    SATURADO = "saturado"
    NO_LISTO = "no_listo"
    ERROR_TEMPORAL = "error_temporal"


class AssistantResult(EsquemaEstricto):
    estado: AssistantState
    motivo: str
    mensaje_usuario: str
    evidencias: list[EvidenceSpan] = Field(default_factory=list)
    opciones: list[str] = Field(default_factory=list)
    puede_reintentar: bool = False
    confianza: dict[str, Any] = Field(default_factory=dict)
    diagnostico: dict[str, Any] = Field(default_factory=dict, exclude=True)


__all__ = [
    "SCHEMA_VERSION", "AssistantResult", "AssistantState", "ChunkRecord",
    "DocumentRecord", "ElementRecord", "EvidenceSpan", "FiltroEntidad",
    "QueryAnalysis", "RetrievalCandidate", "RetrievalSignals", "SenalesRecuperacion",
]
