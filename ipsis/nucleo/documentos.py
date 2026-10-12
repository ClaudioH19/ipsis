"""Representación estructural versionada; referencias al texto extraído y al XML."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ipsis.nucleo.esquemas import DocumentRecord, EsquemaEstricto


class ReferenciaFuente(EsquemaEstricto):
    element_id: str
    offset_inicio: int = Field(ge=0)
    offset_fin: int = Field(ge=0)
    localizador: str

    @model_validator(mode="after")
    def rango(self):
        if self.offset_fin < self.offset_inicio:
            raise ValueError("rango fuente invertido")
        return self


class CeldaPreparada(EsquemaEstricto):
    cell_id: str
    fila: int = Field(ge=0)
    columna: int = Field(ge=0)
    columnas: int = Field(default=1, ge=1)
    filas: int = Field(default=1, ge=1)
    texto: str
    continuacion_de: str | None = None
    referencia: ReferenciaFuente


class TablaPreparada(EsquemaEstricto):
    table_id: str
    filas: int = Field(ge=0)
    columnas: int = Field(ge=0)
    celdas: list[CeldaPreparada]
    filas_encabezado: list[int] = Field(default_factory=list)
    # La primera fila puede servir de contexto sin afirmar que es un encabezado.
    encabezado_explicito: bool = False
    contexto_previo_id: str | None = None
    filas_ids: list[str]
    referencia: ReferenciaFuente


class DocumentoPreparado(DocumentRecord):
    preparation_version: Literal["estructura-1"] = "estructura-1"
    parser_version: str
    source_hash: str
    structure_hash: str
    tablas: list[TablaPreparada] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def literalidad(self):
        ids = {e.element_id for e in self.elementos}
        if len(ids) != len(self.elementos):
            raise ValueError("element_id repetido")
        for e in self.elementos:
            if not 0 <= e.offset_inicio <= e.offset_fin <= len(self.texto_completo) or self.texto_completo[e.offset_inicio:e.offset_fin] != e.texto:
                raise ValueError(f"elemento no literal: {e.element_id}")
            padre = e.metadata.get("parent_id")
            if padre is not None and padre not in ids:
                raise ValueError(f"padre ausente: {e.element_id}")
        for tabla in self.tablas:
            por_celda = {c.cell_id: c for c in tabla.celdas}
            if len(por_celda) != len(tabla.celdas) or len(tabla.filas_ids) != tabla.filas:
                raise ValueError("celdas repetidas o cantidad de filas inconsistente")
            if tabla.table_id not in ids or any(fid not in ids for fid in tabla.filas_ids):
                raise ValueError("tabla o fila ausente")
            if tabla.contexto_previo_id is not None and tabla.contexto_previo_id not in ids:
                raise ValueError("contexto previo ausente")
            for celda in tabla.celdas:
                r = celda.referencia
                if (r.element_id not in ids or not 0 <= r.offset_inicio <= r.offset_fin <= len(self.texto_completo)
                        or self.texto_completo[r.offset_inicio:r.offset_fin] != celda.texto):
                    raise ValueError(f"celda no literal: {celda.cell_id}")
                if celda.fila + celda.filas > tabla.filas or celda.columna + celda.columnas > tabla.columnas:
                    raise ValueError("celda fuera de la cuadrícula")
                if celda.continuacion_de is not None:
                    origen = por_celda.get(celda.continuacion_de)
                    if origen is None or origen.fila >= celda.fila or origen.columna != celda.columna:
                        raise ValueError("referencia a combinación inválida")
        return self
