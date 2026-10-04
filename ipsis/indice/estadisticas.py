"""Estadísticas léxicas del corpus indexado (``.ipsis/indice/estadisticas.json``).

Se calculan al indexar con la misma función ``terminos()`` que usa la consulta,
y alimentan BM25 y todas las señales léxicas. Es un JSON legible: cualquier
puntaje léxico se puede reproducir a mano desde este archivo.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ipsis.lenguaje.texto import terminos, tokenizar

VERSION_ESTADISTICAS = 1


class EstadisticasLexicas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = VERSION_ESTADISTICAS
    stemmer: str | None = None
    hash_corpus: str = ""
    n_chunks: int = Field(default=0, ge=0)
    largo_medio: float = Field(default=0.0, ge=0.0)
    df: dict[str, int] = Field(default_factory=dict)
    superficie: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def construir(cls, textos: Iterable[str], paquete=None, *, hash_corpus: str = "") -> "EstadisticasLexicas":
        """Calcula frecuencia de documentos, largo medio y forma de superficie."""
        df: Counter[str] = Counter()
        formas: dict[str, Counter[str]] = {}
        largos: list[int] = []
        for texto in textos:
            terms = terminos(texto, paquete)
            largos.append(len(terms))
            df.update(set(terms))
            # Cada término conserva la forma original más frecuente (con tildes)
            # para mostrarla al usuario: «garantía», no «garanti».
            for termino, forma in zip(terms, tokenizar(texto, normalizado=False)):
                formas.setdefault(termino, Counter())[forma] += 1
        superficie = {t: max(c.items(), key=lambda par: (par[1], par[0]))[0] for t, c in formas.items()}
        return cls(
            stemmer=getattr(paquete, "stemmer", None),
            hash_corpus=hash_corpus,
            n_chunks=len(largos),
            largo_medio=(sum(largos) / len(largos)) if largos else 0.0,
            df=dict(sorted(df.items())),
            superficie=dict(sorted(superficie.items())),
        )

    def idf(self, termino: str) -> float:
        """IDF de BM25: ``ln(1 + (N - df + 0,5) / (df + 0,5))``; un término ausente
        del corpus recibe el valor máximo (df = 0)."""
        df = self.df.get(termino, 0)
        return math.log(1 + (self.n_chunks - df + 0.5) / (df + 0.5))

    def guardar(self, ruta: str | Path) -> None:
        """Escritura atómica: un fallo a mitad nunca deja un archivo corrupto."""
        destino = Path(ruta)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(destino.suffix + ".tmp")
        temporal.write_text(self.model_dump_json(indent=1), encoding="utf-8")
        os.replace(temporal, destino)

    @classmethod
    def cargar(cls, ruta: str | Path) -> "EstadisticasLexicas":
        return cls.model_validate(json.loads(Path(ruta).read_text(encoding="utf-8")))


__all__ = ["EstadisticasLexicas", "VERSION_ESTADISTICAS"]
