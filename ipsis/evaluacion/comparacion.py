"""Consolidación reproducible de ejecuciones de evaluación comparables."""
from __future__ import annotations

from pathlib import Path



from pydantic import BaseModel, ConfigDict

from ipsis.evaluacion.metricas import ArtefactoEvaluacion
from ipsis.recursos.mensajes import t





class FilaComparacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str
    configuracion_sha256: str
    indice: dict
    recall_at_k: float
    mrr: float
    tasa_falsos_ok: float
    exactitud_estado: float
    exactitud_literal: float
    exactitud_tramo_qa: float | None = None
    directas_con_literal: int | None = None
    tramos_qa_evaluados: int | None = None
    tramos_qa_sin_literal: int | None = None
    exactitud_offsets: float
    latencia_media_ms: float
    latencia_p95_ms: float


class InformeComparativo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    criterio_respuesta: str = "tramo_o_respuesta_v1"
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    k: int
    filas: list[FilaComparacion]
    decisiones: list[str] = []


def cargar_artefacto(ruta: str | Path) -> ArtefactoEvaluacion:
    return ArtefactoEvaluacion.model_validate_json(Path(ruta).read_text(encoding="utf-8"))


def comparar_artefactos(artefactos: list[ArtefactoEvaluacion]) -> InformeComparativo:
    if len(artefactos) < 2:
        raise ValueError(t("evaluation.compare_two"))
    nombres = [artefacto.backend for artefacto in artefactos]
    if len(nombres) != len(set(nombres)):
        raise ValueError(t("evaluation.compare_labels"))
    referencia = artefactos[0]
    identidad = (
        referencia.dataset_id,
        referencia.dataset_version,
        referencia.dataset_sha256,
        referencia.reporte.k,
    )
    for artefacto in artefactos[1:]:
        actual = (
            artefacto.dataset_id,
            artefacto.dataset_version,
            artefacto.dataset_sha256,
            artefacto.reporte.k,
        )
        if actual != identidad:
            raise ValueError(t("evaluation.compare_identity"))
        if artefacto.reporte.criterio_respuesta != referencia.reporte.criterio_respuesta:
            raise ValueError(t("evaluation.compare_criterion"))
    filas = [
        FilaComparacion(
            backend=artefacto.backend,
            configuracion_sha256=artefacto.configuracion_sha256,
            indice=artefacto.indice,
            recall_at_k=artefacto.reporte.recall_at_k,
            mrr=artefacto.reporte.mrr,
            tasa_falsos_ok=artefacto.reporte.tasa_falsos_ok,
            exactitud_estado=artefacto.reporte.exactitud_estado,
            exactitud_literal=artefacto.reporte.exactitud_literal,
            exactitud_tramo_qa=artefacto.reporte.exactitud_tramo_qa,
            directas_con_literal=(artefacto.reporte.cobertura.total.directas_con_literal
                                  if artefacto.reporte.cobertura else None),
            tramos_qa_evaluados=(artefacto.reporte.cobertura.total.tramos_qa_evaluados
                                 if artefacto.reporte.cobertura else None),
            tramos_qa_sin_literal=(artefacto.reporte.cobertura.total.tramos_qa_sin_literal
                                  if artefacto.reporte.cobertura else None),
            exactitud_offsets=artefacto.reporte.exactitud_offsets,
            latencia_media_ms=artefacto.reporte.latencia_media_ms,
            latencia_p95_ms=artefacto.reporte.latencia_p95_ms,
        )
        for artefacto in artefactos
    ]
    return InformeComparativo(
        schema_version=2,
        criterio_respuesta=referencia.reporte.criterio_respuesta,
        dataset_id=referencia.dataset_id,
        dataset_version=referencia.dataset_version,
        dataset_sha256=referencia.dataset_sha256,
        k=referencia.reporte.k,
        filas=filas,
        decisiones=[],
    )


__all__ = ["FilaComparacion", "InformeComparativo", "cargar_artefacto", "comparar_artefactos"]
