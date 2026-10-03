"""Estado de una consulta mientras recorre las etapas de la cascada."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rag.nucleo.esquemas import (
    AssistantResult,
    AssistantState,
    DecisionAbstencion,
    EvidenceSpan,
    QueryAnalysis,
    RetrievalCandidate,
    SenalesLexicas,
    SenalesRecuperacion,
)


@dataclass
class ContextoConsulta:
    pregunta: str
    id_sesion: str
    inicio: float = field(default_factory=time.perf_counter)
    diagnostico: dict[str, Any] = field(default_factory=dict)
    consulta: QueryAnalysis | None = None
    senales: SenalesRecuperacion | None = None
    confianza: dict[str, Any] = field(default_factory=lambda: {"top1": 0.0, "margen": 0.0, "acuerdo_bm25": None})
    lexicas: SenalesLexicas | None = None
    terminos_foco: list[str] = field(default_factory=list)  # stems
    terminos_pregunta: list[str] = field(default_factory=list)  # stems, sin stopwords
    candidatos: list[RetrievalCandidate] = field(default_factory=list)
    puntajes_rerank: list[float] | None = None
    lecturas: list[Any] | None = None
    evidencia_lector: EvidenceSpan | None = None
    respuesta_exacta: dict[str, Any] | None = None
    saltar_modelos: bool = False
    decision: DecisionAbstencion | None = None
    evidencias: list[EvidenceSpan] = field(default_factory=list)
    payloads: list[dict] = field(default_factory=list)
    texto: str = ""
    estado: AssistantState | None = None
    plan: str = ""
    resultado: AssistantResult | None = None

    def latencia_ms(self) -> int:
        return int((time.perf_counter() - self.inicio) * 1000)


__all__ = ["ContextoConsulta"]
