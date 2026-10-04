"""Formato versionado y validación del banco de evaluación."""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BANCO_SCHEMA_VERSION = 1


class CategoriaPregunta(str, Enum):
    EXACTA = "exacta"
    PARAFRASIS = "parafrasis"
    SIN_RESPUESTA = "sin_respuesta"
    PREMISA_FALSA = "premisa_falsa"
    AMBIGUA = "ambigua"
    CONVERSACIONAL = "conversacional"


class EvidenciaEsperada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(min_length=1)
    offset_inicio: int = Field(ge=0)
    offset_fin: int = Field(ge=0)
    texto: str = Field(min_length=1)

    @model_validator(mode="after")
    def validar_offsets(self):
        if self.offset_fin - self.offset_inicio != len(self.texto):
            raise ValueError("los offsets de evidencia no coinciden con el texto literal")
        return self


class CasoEvaluacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[BANCO_SCHEMA_VERSION] = BANCO_SCHEMA_VERSION
    dataset_version: str = Field(min_length=1)
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    split: Literal["dev", "test"]
    categoria: CategoriaPregunta
    pregunta: str = Field(min_length=1)
    estado_esperado: Literal[
        "respuesta_directa",
        "respuesta_parcial",
        "relacionado",
        "necesita_aclaracion",
        "sin_respuesta",
        "fuera_dominio",
        "conversacional",
    ]
    respondible: bool
    respuesta_literal: str | None = None
    evidencias: list[EvidenciaEsperada] = Field(default_factory=list)
    notas: str | None = None
    # Metadata de evaluación: «mismo tema, dato ausente» y su par respondible.
    subtipo: Literal["trampa_mismo_tema"] | None = None
    par: str | None = None

    @model_validator(mode="after")
    def validar_semantica(self):
        if self.subtipo and self.categoria not in {CategoriaPregunta.SIN_RESPUESTA, CategoriaPregunta.PREMISA_FALSA}:
            raise ValueError("trampa_mismo_tema solo aplica a sin_respuesta o premisa_falsa")
        respondibles = {CategoriaPregunta.EXACTA, CategoriaPregunta.PARAFRASIS}
        if self.categoria in respondibles:
            if not self.respondible or not self.evidencias or not self.respuesta_literal:
                raise ValueError("una pregunta respondible exige respuesta literal y evidencia")
            if not any(self.respuesta_literal in evidencia.texto for evidencia in self.evidencias):
                raise ValueError("la respuesta literal debe estar contenida en una evidencia")
            if self.estado_esperado not in {"respuesta_directa", "respuesta_parcial"}:
                raise ValueError("una pregunta respondible exige un estado de respuesta")
        else:
            if self.respondible or self.evidencias or self.respuesta_literal is not None:
                raise ValueError("una pregunta no respondible no debe declarar evidencia")

        esperado_por_categoria = {
            CategoriaPregunta.PREMISA_FALSA: {"sin_respuesta"},
            CategoriaPregunta.AMBIGUA: {"necesita_aclaracion"},
            CategoriaPregunta.CONVERSACIONAL: {"conversacional"},
            CategoriaPregunta.SIN_RESPUESTA: {"sin_respuesta", "fuera_dominio"},
        }
        permitidos = esperado_por_categoria.get(self.categoria)
        if permitidos is not None and self.estado_esperado not in permitidos:
            raise ValueError("estado esperado incompatible con la categoría")
        return self


class ArchivoCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ruta: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)


class CorpusBanco(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directorio: str = Field(min_length=1)
    archivos: list[ArchivoCorpus] = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ManifiestoBanco(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[BANCO_SCHEMA_VERSION] = BANCO_SCHEMA_VERSION
    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    dataset_version: str = Field(min_length=1)
    tipo: Literal["sintetico", "manual"]
    estado: Literal["borrador", "estable"]
    casos: str = Field(min_length=1)
    corpus: CorpusBanco
    categorias_requeridas: list[CategoriaPregunta]
    # De dónde salió el banco (``ipsis golden importar``): formato y archivo de
    # origen. Sin fecha, para que reimportar lo mismo dé el mismo banco.
    procedencia: dict[str, str] | None = None
    # «regresion»: banco universal del software (lo usan las pruebas), igual para
    # todos los clientes; mide, pero nunca calibra umbrales de un cliente.
    uso: Literal["evaluacion", "regresion"] = "evaluacion"
    # Idioma del corpus y las preguntas (código de paquete). Si falta, el del proyecto.
    idioma: str | None = None


class BancoEvaluacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifiesto: ManifiestoBanco
    casos: list[CasoEvaluacion]


def hash_banco(banco: BancoEvaluacion) -> str:
    """Identifica de forma estable el manifiesto, los casos y el corpus declarado."""
    serializado = json.dumps(
        banco.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def hash_archivos_corpus(directorio: Path, archivos: list[ArchivoCorpus]) -> str:
    digest = hashlib.sha256()
    for archivo in sorted(archivos, key=lambda item: item.ruta):
        digest.update(archivo.ruta.encode("utf-8"))
        digest.update(b"\0")
        digest.update(archivo.doc_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update((directorio / archivo.ruta).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def cargar_banco(ruta_manifiesto: str | Path) -> BancoEvaluacion:
    ruta = Path(ruta_manifiesto).resolve()
    manifiesto = ManifiestoBanco.model_validate_json(ruta.read_text(encoding="utf-8"))
    ruta_casos = (ruta.parent / manifiesto.casos).resolve()
    casos = [
        CasoEvaluacion.model_validate_json(linea)
        for linea in ruta_casos.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]
    ids = [caso.id for caso in casos]
    if len(ids) != len(set(ids)):
        raise ValueError("el banco contiene IDs de caso duplicados")
    if any(caso.dataset_version != manifiesto.dataset_version for caso in casos):
        raise ValueError("la versión de un caso no coincide con el manifiesto")
    categorias = {caso.categoria for caso in casos}
    faltantes = set(manifiesto.categorias_requeridas) - categorias
    if faltantes:
        raise ValueError(f"faltan categorías requeridas: {sorted(c.value for c in faltantes)}")
    if manifiesto.estado == "estable" and {caso.split for caso in casos} != {"dev", "test"}:
        raise ValueError("un banco estable debe separar dev y test")

    directorio_corpus = (ruta.parent / manifiesto.corpus.directorio).resolve()
    actual = hash_archivos_corpus(directorio_corpus, manifiesto.corpus.archivos)
    if actual != manifiesto.corpus.sha256:
        raise ValueError("el hash del corpus no coincide con el manifiesto")
    return BancoEvaluacion(manifiesto=manifiesto, casos=casos)


def exigir_calibrable(banco: BancoEvaluacion) -> None:
    """Solo el golden del cliente calibra: un banco de regresión no."""
    if banco.manifiesto.uso == "regresion":
        raise ValueError(f"el banco {banco.manifiesto.dataset_id!r} es de regresión del software: sirve para "
                         "medir y comparar, no para calibrar umbrales. Calibra con el golden del cliente")


def validar_evidencias_contra_corpus(
    banco: BancoEvaluacion,
    documentos: dict[str, str],
) -> None:
    """Cada evidencia sigue siendo texto literal del corpus en sus offsets.
    Junta todos los problemas en un solo ``ValueError`` (una línea por caso)."""
    errores = []
    for caso in banco.casos:
        for evidencia in caso.evidencias:
            if evidencia.doc_id not in documentos:
                errores.append(f"{caso.id}: documento desconocido {evidencia.doc_id!r}")
                continue
            texto = documentos[evidencia.doc_id]
            if texto[evidencia.offset_inicio:evidencia.offset_fin] != evidencia.texto:
                errores.append(f"{caso.id}: evidencia no literal o offsets inválidos")
    if errores:
        raise ValueError("\n".join(errores))


__all__ = [
    "BANCO_SCHEMA_VERSION", "BancoEvaluacion", "CasoEvaluacion",
    "CategoriaPregunta", "EvidenciaEsperada", "ArchivoCorpus", "ManifiestoBanco",
    "cargar_banco", "exigir_calibrable", "hash_banco", "hash_archivos_corpus",
    "validar_evidencias_contra_corpus",
]
