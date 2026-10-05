"""Manifiesto del índice: con qué se construyó y qué contiene.

Se guarda junto a la colección (``.ipsis/index/<colección>.manifest.json``).
Permite auditar el índice y decidir si un perfil o modelo puede usarlo sin
reindexar.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ipsis.configuracion import rutas
from ipsis.nucleo.esquemas import SCHEMA_VERSION
from ipsis.recursos.mensajes import t

VERSION_MANIFIESTO = 1


class ManifiestoIndice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = VERSION_MANIFIESTO
    coleccion: str
    modelo_denso: str
    dimension: int
    stemmer: str | None = None
    hash_corpus: str
    # Huella barata de los archivos indexados (bytes + configuración de fragmentado):
    # si coincide, el corpus no cambió sin tener que parsearlo. Opcional: los
    # manifiestos anteriores no la tienen.
    hash_archivos: str | None = None
    version_payload: int = SCHEMA_VERSION
    n_chunks: int = Field(ge=0)
    inventario_entidades: list[str] = Field(default_factory=list)
    fecha: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


def hash_corpus(payloads: list[dict]) -> str:
    """Huella del contenido indexado: hash de los hashes de cada fragmento."""
    huellas = sorted(p["hash_texto"] for p in payloads)
    return "sha256:" + hashlib.sha256("\n".join(huellas).encode("utf-8")).hexdigest()


def inventario_entidades(payloads: list[dict]) -> list[str]:
    """Todos los ``valor_norm`` de entidades presentes en algún fragmento."""
    return sorted({e["valor_norm"] for p in payloads for e in p.get("entidades", [])})


def ruta_manifiesto(coleccion: str, directorio: str = rutas.INDICE) -> Path:
    return Path(directorio) / f"{coleccion}.manifest.json"


def guardar_manifiesto(manifiesto: ManifiestoIndice, directorio: str = rutas.INDICE) -> Path:
    destino = ruta_manifiesto(manifiesto.coleccion, directorio)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".json.tmp")
    temporal.write_text(manifiesto.model_dump_json(indent=1), encoding="utf-8")
    os.replace(temporal, destino)
    return destino


def cargar_manifiesto(coleccion: str, directorio: str = rutas.INDICE) -> ManifiestoIndice:
    ruta = ruta_manifiesto(coleccion, directorio)
    if not ruta.is_file():
        raise FileNotFoundError(t("core.index_no_manifest", name=coleccion, path=ruta))
    return ManifiestoIndice.model_validate(json.loads(ruta.read_text(encoding="utf-8")))


def es_compatible(manifiesto: ManifiestoIndice, modelo_denso: str, stemmer: str | None = None,
                  dimension: int | None = None) -> bool:
    """El índice sirve para este modelo denso (y stemmer y dimensión, si se indican)."""
    if manifiesto.version_payload != SCHEMA_VERSION or manifiesto.modelo_denso != modelo_denso:
        return False
    if dimension is not None and manifiesto.dimension != dimension:
        return False
    return stemmer is None or manifiesto.stemmer == stemmer


__all__ = [
    "ManifiestoIndice", "cargar_manifiesto", "es_compatible", "guardar_manifiesto",
    "hash_corpus", "inventario_entidades", "ruta_manifiesto",
]
