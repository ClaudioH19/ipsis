"""Consolidación reproducible de ejecuciones de evaluación comparables."""
from __future__ import annotations

from pathlib import Path



from pydantic import BaseModel, ConfigDict

from rag.evaluacion.metricas import ArtefactoEvaluacion





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
    exactitud_offsets: float
    latencia_media_ms: float
    latencia_p95_ms: float


class InformeComparativo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
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
        raise ValueError("se requieren al menos dos ejecuciones para comparar")
    nombres = [artefacto.backend for artefacto in artefactos]
    if len(nombres) != len(set(nombres)):
        raise ValueError("cada ejecución debe tener una etiqueta de backend distinta")
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
            raise ValueError("las ejecuciones no usan el mismo dataset, corpus y k")
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
            exactitud_offsets=artefacto.reporte.exactitud_offsets,
            latencia_media_ms=artefacto.reporte.latencia_media_ms,
            latencia_p95_ms=artefacto.reporte.latencia_p95_ms,
        )
        for artefacto in artefactos
    ]
    return InformeComparativo(
        dataset_id=referencia.dataset_id,
        dataset_version=referencia.dataset_version,
        dataset_sha256=referencia.dataset_sha256,
        k=referencia.reporte.k,
        filas=filas,
        decisiones=[],
    )


__all__ = ["FilaComparacion", "InformeComparativo", "cargar_artefacto", "comparar_artefactos"]
