"""Benchmark reproducible sobre un banco versionado y comparación de artefactos."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from rag.evaluacion.banco import cargar_banco

from pydantic import BaseModel, ConfigDict

from rag.evaluacion.metricas import ArtefactoEvaluacion, CalibracionDev


def ejecutar_benchmark(ruta_banco: str, directorio_salida: str) -> Path:
    from rag.cli import main

    manifiesto = Path(ruta_banco).resolve()
    banco = cargar_banco(manifiesto)
    corpus = (manifiesto.parent / banco.manifiesto.corpus.directorio).resolve()
    salida = Path(directorio_salida).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    anterior = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="rag_benchmark_") as temporal:
        proyecto = Path(temporal)
        try:
            os.chdir(proyecto)
            if main(["init"]) != 0:
                raise RuntimeError("falló rag init durante el benchmark")
            for archivo in banco.manifiesto.corpus.archivos:
                if main(["cargar", str(corpus / archivo.ruta)]) != 0:
                    raise RuntimeError(f"falló la carga de {archivo.ruta}")

            ruta_cfg = proyecto / "configuracion" / "motor.yaml"
            cfg = yaml.safe_load(ruta_cfg.read_text(encoding="utf-8"))
            artefactos = []
            ejecuciones = [
                ("qdrant", "vectorial", True),
                ("qdrant", "hibrida", False),
            ]
            for retriever, modo, reindexar in ejecuciones:
                cfg["componentes"]["retriever"] = retriever
                cfg["recuperacion"]["modo"] = modo
                ruta_cfg.write_text(
                    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
                if reindexar and main(["indexar"]) != 0:
                    raise RuntimeError(f"falló la indexación de {retriever}/{modo}")
                etiqueta = f"qdrant_{modo}"
                ruta_artefacto = salida / f"{etiqueta}.json"
                main([
                    "evaluar", "--banco", str(manifiesto),
                    "--salida", str(ruta_artefacto),
                ])
                if not ruta_artefacto.is_file():
                    raise RuntimeError(f"no se produjo el artefacto {etiqueta}")
                artefactos.append(cargar_artefacto(ruta_artefacto))

            informe = comparar_artefactos(artefactos)
            ruta_informe = salida / "comparacion.json"
            ruta_informe.write_text(informe.model_dump_json(indent=2), encoding="utf-8")
            return ruta_informe
        finally:
            os.chdir(anterior)


__all__ = ["ejecutar_benchmark"]


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
    calibracion_dev: CalibracionDev


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
            calibracion_dev=artefacto.calibracion_dev,
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
