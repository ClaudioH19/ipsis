"""Texto para modelos y mapa de sus copias al documento, sin inferencia temática."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ipsis.nucleo.documentos import ReferenciaFuente
from ipsis.nucleo.esquemas import EsquemaEstricto


class CopiaFuente(EsquemaEstricto):
    inicio: int = Field(ge=0)
    fin: int = Field(ge=0)
    referencia: ReferenciaFuente
    cell_id: str | None = None
    rol: str = "contenido"


class ContextoLectura(EsquemaEstricto):
    version: Literal["campos-1"] = "campos-1"
    texto: str
    copias: list[CopiaFuente] = Field(default_factory=list)
    supuestos: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def mapa(self):
        anterior = 0
        for copia in self.copias:
            ref = copia.referencia
            if not anterior <= copia.inicio < copia.fin <= len(self.texto):
                raise ValueError("copias de lectura solapadas o fuera del texto")
            if copia.fin - copia.inicio != ref.offset_fin - ref.offset_inicio:
                raise ValueError("copia de lectura con longitud ajena a la fuente")
            anterior = copia.fin
        return self

    def verificar_fuente(self, fuente):
        for copia in self.copias:
            ref = copia.referencia
            if not 0 <= ref.offset_inicio <= ref.offset_fin <= len(fuente) or (
                fuente[ref.offset_inicio:ref.offset_fin] != self.texto[copia.inicio:copia.fin]
            ):
                raise ValueError("copia de lectura no literal")

    def recortar(self, limite):
        copias = []
        for copia in self.copias:
            fin = min(copia.fin, limite)
            if copia.inicio < fin:
                ref = copia.referencia.model_copy(update={
                    "offset_fin": copia.referencia.offset_inicio + fin - copia.inicio})
                copias.append(copia.model_copy(update={"fin": fin, "referencia": ref}))
        return self.model_copy(update={"texto": self.texto[:limite], "copias": copias})

    def referencias_span(self, inicio, fin):
        """Solo partes copiadas: la puntuación añadida nunca obtiene offsets fuente."""
        if not 0 <= inicio <= fin <= len(self.texto):
            raise ValueError("span fuera del contexto de lectura")
        salida = []
        for copia in self.copias:
            desde, hasta = max(inicio, copia.inicio), min(fin, copia.fin)
            if desde < hasta:
                ref = copia.referencia.model_dump(mode="json")
                ref.update(offset_inicio=copia.referencia.offset_inicio + desde - copia.inicio,
                           offset_fin=copia.referencia.offset_inicio + hasta - copia.inicio,
                           texto=self.texto[desde:hasta], cell_id=copia.cell_id, rol=copia.rol)
                salida.append(ref)
        return salida
