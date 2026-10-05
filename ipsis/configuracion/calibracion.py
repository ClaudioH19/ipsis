"""``config/calibration.yaml``: umbrales calibrados con el golden del cliente.

Solo se aplican si la calibración está en estado ``calibrado`` y su
procedencia coincide con la instalación actual: mismo perfil, mismos modelos
y mismo corpus indexado (``hash_corpus`` del manifiesto del índice). Si algo
cambió, se ignora y el motor usa los umbrales del perfil.

La calibración solo elige umbrales escalares; no entrena nada.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

VERSION_CALIBRACION = 1


class EstadoCalibracion(str, Enum):
    CALIBRADO = "calibrado"  # hay muestra y un umbral cumple α
    MUESTRA_INSUFICIENTE = "muestra_insuficiente"  # n no permite certificar α (no es «inseguro»)
    SIN_UMBRAL_SEGURO = "sin_umbral_seguro"  # hay muestra, pero ningún umbral cumple α


class ProcedenciaCalibracion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    perfil: str
    modelos: dict[str, str | None]
    hash_corpus: str  # del manifiesto del índice: el corpus que respondió el golden
    banco: str  # dataset_id@versión
    hash_banco: str


class ArchivoCalibracion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = VERSION_CALIBRACION
    estado: EstadoCalibracion
    alfa: float = Field(gt=0.0, lt=1.0)
    confianza: float = Field(gt=0.0, lt=1.0)
    procedencia: ProcedenciaCalibracion
    umbrales: dict[str, float]
    resultado: dict[str, Any] = Field(default_factory=dict)  # dev, test y motivo, para auditoría


def normalizar_umbrales(umbrales: dict[str, Any] | None) -> dict[str, Any]:
    """Traduce el umbral ``oov`` anterior a sus dos usos (``oov_dominio`` y
    ``oov_ok``) sin pisar valores explícitos. Proyectos y calibraciones viejas
    siguen funcionando con el mismo comportamiento."""
    salida = dict(umbrales or {})
    if "oov" in salida:
        anterior = salida.pop("oov")
        salida.setdefault("oov_dominio", anterior)
        salida.setdefault("oov_ok", anterior)
    return salida


def leer_calibracion(ruta: str | Path) -> ArchivoCalibracion | None:
    ruta = Path(ruta)
    if not ruta.is_file():
        return None
    from ipsis.configuracion.archivos import interpretar

    archivo = ArchivoCalibracion.model_validate(interpretar(ruta.read_text(encoding="utf-8"), "calibracion"))
    return archivo.model_copy(update={"umbrales": normalizar_umbrales(archivo.umbrales)})


def motivo_no_aplicable(
    archivo: ArchivoCalibracion,
    *,
    perfil: str,
    modelos: dict[str, str | None],
    hash_corpus: str | None,
) -> str | None:
    """Por qué no se aplica la calibración (``None`` si se aplica)."""
    if archivo.estado != EstadoCalibracion.CALIBRADO:
        return f"la calibración quedó en estado {archivo.estado.value}: se usan los umbrales del perfil"
    procedencia = archivo.procedencia
    if procedencia.perfil != perfil:
        return f"se calibró con el perfil {procedencia.perfil!r} y el proyecto usa {perfil!r}"
    if procedencia.modelos != modelos:
        return "se calibró con otros modelos"
    if hash_corpus is None or procedencia.hash_corpus != hash_corpus:
        return "el corpus indexado cambió desde la calibración (o no hay índice)"
    return None


def umbrales_aplicables(
    ruta: str | Path,
    *,
    perfil: str,
    modelos: dict[str, str | None],
    hash_corpus: str | None,
) -> dict[str, float] | None:
    archivo = leer_calibracion(ruta)
    if archivo is None or motivo_no_aplicable(archivo, perfil=perfil, modelos=modelos, hash_corpus=hash_corpus):
        return None
    return dict(archivo.umbrales)


__all__ = [
    "ArchivoCalibracion", "EstadoCalibracion", "ProcedenciaCalibracion", "VERSION_CALIBRACION",
    "leer_calibracion", "motivo_no_aplicable", "normalizar_umbrales", "umbrales_aplicables",
]
