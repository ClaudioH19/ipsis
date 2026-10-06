"""Esquemas versionados que cruzan las fronteras entre etapas, servicio y evaluación."""
from __future__ import annotations

from dataclasses import dataclass
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
    metodo_confianza: str | None = None
    estado_calibracion: Literal["sin_calibrar", "calibrado"] | None = None
    terminos_encontrados: list[str] = Field(default_factory=list)
    terminos_ausentes: list[str] = Field(default_factory=list)


class LecturaQA(EsquemaEstricto):
    """Resultado del lector QA sobre un pasaje (estilo SQuAD 2.0)."""

    indice_pasaje: int = Field(ge=0)
    inicio: int = Field(ge=0)  # offset de carácter dentro del pasaje
    fin: int = Field(ge=0)
    texto: str  # == pasaje[inicio:fin]; vacío si ganó «sin respuesta»
    prob_respuesta: float = Field(ge=0.0, le=1.0)
    prob_sin_respuesta: float = Field(ge=0.0, le=1.0)

    @property
    def s_qa(self) -> float:
        """Señal de la política: probabilidad del tramo menos la de «sin respuesta», en [0, 1]."""
        return max(0.0, self.prob_respuesta - self.prob_sin_respuesta)


class SenalesLexicas(EsquemaEstricto):
    """Señales léxicas de una consulta, todas en [0, 1] (ver ``ipsis.lenguaje.lexico``)."""

    terminos_foco: list[str] = Field(default_factory=list)  # forma de superficie
    s_oov: float = Field(default=0.0, ge=0.0, le=1.0)
    s_cov: float | None = Field(default=None, ge=0.0, le=1.0)
    s_foco: float | None = Field(default=None, ge=0.0, le=1.0)
    s_lex: float | None = Field(default=None, ge=0.0, le=1.0)
    acuerdo: float | None = Field(default=None, ge=0.0, le=1.0)


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


class DiagnosticCandidate(EsquemaEstricto):
    chunk_id: str = Field(min_length=1)
    score: float
    signals: dict[str, Any] = Field(default_factory=dict)
    inicio: str = ""  # comienzo del texto, para reconocerlo en el diagnóstico


class QueryDiagnostic(EsquemaEstricto):
    """Traza interna estable de una consulta; nunca se publica por defecto."""

    schema_version: Literal[2] = 2
    backend: str = Field(min_length=1)
    perfil: str | None = None
    etapas: dict[str, int] = Field(default_factory=dict)
    candidatos: list[DiagnosticCandidate] = Field(default_factory=list)
    senales: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] | None = None
    evidencias: list[EvidenceSpan] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    senales_lexicas: dict[str, Any] | None = None
    puntajes_rerank: list[float] | None = None
    rerank: list[dict[str, Any]] | None = None  # chunk_id y puntaje, en el orden del reranker
    lectura_por_pista: str | None = None
    pregunta_interpretada: str | None = None  # la de seguimiento, con el tema heredado  # chunk que el lector leyó por la pista de la intención
    lecturas: list[dict[str, Any]] | None = None
    regla: str | None = None
    senales_politica: dict[str, Any] | None = None
    oracion_foco: str | None = None
    salto_modelos: bool = False
    tono: str | None = None
    plantillas: list[str] = Field(default_factory=list)  # <tono>.<situación>.<n> usadas en la respuesta


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
    "DiagnosticCandidate", "DocumentRecord", "ElementRecord", "EvidenceSpan",
    "FiltroEntidad", "QueryAnalysis", "QueryDiagnostic", "RetrievalCandidate",
    "RetrievalSignals", "SenalesRecuperacion",
]


Resultado = Literal["responde", "relacionado", "abstiene"]


@dataclass(frozen=True)
class DecisionAbstencion:
    resultado: Resultado
    motivo: str
    entidad_texto: str | None = None
    capa_decisora: str = ""
    confianza_utilizada: float | None = None
    candidato_id: str | None = None

    @property
    def abstiene(self) -> bool:
        return self.resultado == "abstiene"
