"""Catálogo de modelos ONNX soportados.

Cada entrada dice qué archivos descargar de Hugging Face, con qué licencia y
cómo usar el modelo. Los datos se verificaron en la tarea P5.1 del plan V3
(ver ``docs/decisions/0003-onnx-and-profiles.md``).
"""
from __future__ import annotations

import platform
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ipsis.recursos.mensajes import t

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
    # Coseno típico entre textos sin relación: s_ret = (coseno - piso) / (1 - piso).
    # Los e5 dan ~0,7 aun a pares ajenos, así que su coseno crudo no sirve de señal.
    coseno_piso: float = Field(default=0.0, ge=0.0, lt=1.0)
    idiomas: str = "multilingüe"
    revision: str | None = None
    pooling: Literal["mean", "cls", "last_token", "sentence"] = "mean"
    salida: str | None = None
    pad_token_id: int | None = None
    entradas_vacias: dict[str, tuple[int, ...]] = Field(default_factory=dict)
    datos_externos: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    def datos_onnx(self, maquina: str | None = None) -> tuple[str, ...]:
        return self.datos_externos.get(self.archivo_onnx(maquina), ())

    def archivo_onnx(self, maquina: str | None = None) -> str:
        """ONNX adecuado para la CPU actual (o ``maquina``)."""
        arq = (maquina or platform.machine()).lower()
        clave = "arm64" if arq in {"arm64", "aarch64"} else "x86_64"
        return self.archivos_onnx.get(clave) or self.archivos_onnx["*"]

    def patrones(self, maquina: str | None = None) -> list[str]:
        """Archivos del repositorio que hay que descargar."""
        onnx = self.archivo_onnx(maquina)
        return list(dict.fromkeys([onnx, onnx + "_data", *self.datos_onnx(maquina), *self.archivos_extra]))


CATALOGO: dict[str, ModeloSpec] = {
    spec.id_hf: spec
    for spec in [
        ModeloSpec(
            id_hf="intfloat/multilingual-e5-small",
            tarea="denso", licencia="MIT", parametros=117_654_272,
            archivos_onnx={"*": "onnx/model.onnx"},
            prefijo_consulta="query: ", prefijo_pasaje="passage: ", dimension=384, coseno_piso=0.7,
        ),
        ModeloSpec(
            id_hf="intfloat/multilingual-e5-base",
            tarea="denso", licencia="MIT", parametros=278_044_162,
            archivos_onnx={"*": "onnx/model.onnx"},
            prefijo_consulta="query: ", prefijo_pasaje="passage: ", dimension=768, coseno_piso=0.7,
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
            id_hf="onnx-community/gte-multilingual-reranker-base",
            tarea="reranker", licencia="Apache-2.0 (Alibaba-NLP/gte-multilingual-reranker-base)",
            atribucion="Alibaba GTE; ONNX Community conversion", parametros=306_000_000,
            revision="ee64367e35a2db0da46bb6497e13a18f8bd585cb",
            archivos_onnx={"*": "onnx/model_int8.onnx"}, max_tokens=8192, pad_token_id=1,
        ),
        ModeloSpec(
            id_hf="dewdev/mdeberta-v3-base-squad2-onnx",
            tarea="lector", licencia="MIT (timpal0l/mdeberta-v3-base-squad2)", parametros=278_220_802,
            # fp32: la variante int8 publicada pierde la señal (logits planos) y
            # la int16 no carga en onnxruntime. Verificado en P7.2.
            archivos_onnx={"*": "onnx/model.onnx"},
        ),
        ModeloSpec(
            id_hf="ibm-granite/granite-embedding-311m-multilingual-r2",
            tarea="denso", licencia="Apache-2.0", parametros=311_664_384,
            atribucion="IBM Granite; tokenizer derived from Gemma (see model card)",
            revision="44399559930365213510b1ee2eb15ded83374f0e",
            archivos_onnx={"x86_64": "onnx/model_quint8_avx2.onnx", "*": "onnx/model.onnx"},
            dimension=768, pooling="cls", pad_token_id=0,
        ),
        ModeloSpec(
            id_hf="ibm-granite/granite-embedding-97m-multilingual-r2",
            tarea="denso", licencia="Apache-2.0", parametros=97_441_152,
            atribucion="IBM Granite; tokenizer derived from Gemma (see model card)",
            revision="835ad14087e140460703cf0fae09f97d469d65c2",
            archivos_onnx={"x86_64": "onnx/model_quint8_avx2.onnx", "*": "onnx/model.onnx"},
            dimension=384, pooling="cls", pad_token_id=179935,
        ),
        ModeloSpec(
            id_hf="onnx-community/harrier-oss-v1-270m-ONNX",
            tarea="denso", licencia="MIT", parametros=268_098_176,
            atribucion="Microsoft harrier-oss-v1-270m; ONNX Community conversion",
            revision="d59c919d0159aea2c19ed7d04288fcdd048d0f9c",
            archivos_onnx={"*": "onnx/model_quantized.onnx"},
            datos_externos={"onnx/model_quantized.onnx": ("onnx/model_quantized.onnx_data",)},
            dimension=640, pooling="sentence", salida="sentence_embedding", pad_token_id=0,
            prefijo_consulta="Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: ",
        ),
        ModeloSpec(
            id_hf="onnx-community/embeddinggemma-2-ONNX",
            tarea="denso", licencia="Apache-2.0", parametros=270_000_000,
            atribucion="Google EmbeddingGemma 2 text module; ONNX Community conversion",
            revision="daa72c51243991dfcaf9f9137d2c573d8f7790c0",
            archivos_onnx={"*": "onnx/model_quantized.onnx"},
            datos_externos={"onnx/model_quantized.onnx": ("onnx/model_quantized.onnx_data",)},
            dimension=768, pooling="sentence", salida="sentence_embedding", pad_token_id=0,
            prefijo_consulta="task: search result | query: ", prefijo_pasaje="title: none | text: ",
            entradas_vacias={"image_features": (0, 512), "video_features": (0, 512),
                             "audio_features": (0, 512)},
        ),
        ModeloSpec(
            id_hf="Horizon-Labs/multilingual-reranker-base",
            tarea="reranker", licencia="Apache-2.0", parametros=307_531_009,
            revision="1302619c8478dd630e06a934d4064ae345a7d0da",
            archivos_onnx={"*": "onnx/model_quantized.onnx"}, max_tokens=384, pad_token_id=0,
        ),
        ModeloSpec(
            id_hf="Horizon-Labs/multilingual-reranker-small",
            tarea="reranker", licencia="Apache-2.0", parametros=140_641_921,
            revision="4fd96cc3b19fd47e790cf923879b193d3ebf0bc9",
            archivos_onnx={"*": "onnx/model_quantized.onnx"}, max_tokens=384, pad_token_id=0,
        ),
        ModeloSpec(
            id_hf="cross-encoder/ms-marco-MiniLM-L6-v2",
            tarea="reranker", licencia="Apache-2.0", parametros=22_700_000, idiomas="en",
            revision="233902d25c440f23af6f7d6e94d2946bac0bee0a",
            archivos_onnx={"x86_64": "onnx/model_quint8_avx2.onnx", "arm64": "onnx/model_qint8_arm64.onnx",
                           "*": "onnx/model.onnx"},
            max_tokens=512, pad_token_id=0,
        ),
        ModeloSpec(
            id_hf="cross-encoder/ms-marco-MiniLM-L12-v2",
            tarea="reranker", licencia="Apache-2.0", parametros=33_400_000, idiomas="en",
            revision="7b0235231ca2674cb8ca8f022859a6eba2b1c968",
            archivos_onnx={"x86_64": "onnx/model_quint8_avx2.onnx", "arm64": "onnx/model_qint8_arm64.onnx",
                           "*": "onnx/model.onnx"},
            max_tokens=512, pad_token_id=0,
        ),
        ModeloSpec(
            id_hf="mixedbread-ai/mxbai-rerank-xsmall-v1",
            tarea="reranker", licencia="Apache-2.0", parametros=70_800_000, idiomas="en",
            revision="b5c6e9da73abc3711f593f705371cdbe9e0fe422",
            archivos_onnx={"*": "onnx/model_quantized.onnx"}, max_tokens=512, pad_token_id=0,
        ),
        ModeloSpec(
            id_hf="mixedbread-ai/mxbai-rerank-base-v1",
            tarea="reranker", licencia="Apache-2.0", parametros=184_000_000, idiomas="en",
            revision="800f24c113213a187e65bde9db00c15a2bb12738",
            archivos_onnx={"*": "onnx/model_quantized.onnx"}, max_tokens=512, pad_token_id=0,
        ),
    ]
}


def obtener(id_hf: str) -> ModeloSpec:
    try:
        return CATALOGO[id_hf]
    except KeyError as exc:
        raise KeyError(t("core.unsupported_model", model=id_hf, available=", ".join(sorted(CATALOGO)))) from exc


__all__ = ["CATALOGO", "ModeloSpec", "Tarea", "obtener"]
