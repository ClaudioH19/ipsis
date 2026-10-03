"""Catálogo de modelos ONNX soportados.

Cada entrada dice qué archivos descargar de Hugging Face, con qué licencia y
cómo usar el modelo. Los datos se verificaron en la tarea P5.1 del plan V3
(ver ``docs/plan/modelos-y-perfiles.md`` §2).
"""
from __future__ import annotations

import platform
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Tarea = Literal["denso", "reranker", "lector"]


class ModeloSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id_hf: str = Field(min_length=3)
    tarea: Tarea
    licencia: str
    atribucion: str | None = None
    parametros: int
    # ONNX por arquitectura de CPU ("x86_64", "arm64"); "*" es el respaldo.
    archivos_onnx: dict[str, str]
    archivos_extra: tuple[str, ...] = ("tokenizer.json", "config.json")
    max_tokens: int = 512
    prefijo_consulta: str = ""
    prefijo_pasaje: str = ""
    dimension: int | None = None
    idiomas: str = "multilingüe"

    def archivo_onnx(self, maquina: str | None = None) -> str:
        """ONNX adecuado para la CPU actual (o ``maquina``)."""
        arq = (maquina or platform.machine()).lower()
        clave = "arm64" if arq in {"arm64", "aarch64"} else "x86_64"
        return self.archivos_onnx.get(clave) or self.archivos_onnx["*"]

    def patrones(self, maquina: str | None = None) -> list[str]:
        """Archivos del repositorio que hay que descargar."""
        onnx = self.archivo_onnx(maquina)
        return [onnx, onnx + "_data", *self.archivos_extra]


CATALOGO: dict[str, ModeloSpec] = {
    spec.id_hf: spec
    for spec in [
        ModeloSpec(
            id_hf="intfloat/multilingual-e5-small",
            tarea="denso", licencia="MIT", parametros=117_654_272,
            archivos_onnx={"*": "onnx/model.onnx"},
            prefijo_consulta="query: ", prefijo_pasaje="passage: ", dimension=384,
        ),
        ModeloSpec(
            id_hf="intfloat/multilingual-e5-base",
            tarea="denso", licencia="MIT", parametros=278_044_162,
            archivos_onnx={"*": "onnx/model.onnx"},
            prefijo_consulta="query: ", prefijo_pasaje="passage: ", dimension=768,
        ),
        ModeloSpec(
            id_hf="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
            tarea="reranker", licencia="Apache-2.0", parametros=117_641_603,
            archivos_onnx={
                "x86_64": "onnx/model_quint8_avx2.onnx",
                "arm64": "onnx/model_qint8_arm64.onnx",
                "*": "onnx/model.onnx",
            },
        ),
        ModeloSpec(
            id_hf="onnx-community/bge-reranker-v2-m3-ONNX",
            tarea="reranker", licencia="Apache-2.0 (BAAI/bge-reranker-v2-m3)", parametros=567_755_777,
            archivos_onnx={"*": "onnx/model_int8.onnx"}, max_tokens=8192,
        ),
        ModeloSpec(
            id_hf="dewdev/mdeberta-v3-base-squad2-onnx",
            tarea="lector", licencia="MIT (timpal0l/mdeberta-v3-base-squad2)", parametros=278_220_802,
            archivos_onnx={"*": "onnx/model_int8.onnx"},
        ),
    ]
}


def obtener(id_hf: str) -> ModeloSpec:
    try:
        return CATALOGO[id_hf]
    except KeyError as exc:
        raise KeyError(
            f"modelo no soportado: {id_hf!r}; disponibles: {', '.join(sorted(CATALOGO))}"
        ) from exc


__all__ = ["CATALOGO", "ModeloSpec", "Tarea", "obtener"]
