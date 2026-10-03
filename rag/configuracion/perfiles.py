"""Perfiles de instalación (light, medium, heavy) y su fusión por capas.

El perfil define modelos, parámetros de la cascada, etapas y umbrales por
defecto. La configuración efectiva se arma en este orden:

    perfil (rag/recursos/perfiles/<perfil>.yaml)
      ← configuracion/motor.yaml::ajustes_perfil
      ← configuracion/calibracion.yaml::umbrales (solo si su procedencia coincide)
"""
from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from rag.configuracion import rutas

PERFILES_INSTALABLES = ("light", "medium", "heavy")


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelosPerfil(_Estricto):
    denso: str
    reranker: str | None = None
    lector: str | None = None


class LexicoPerfil(_Estricto):
    k1: float = 1.2
    b: float = 0.75
    max_terminos_foco: int = Field(default=2, ge=1)


class CascadaPerfil(_Estricto):
    recuperar_n: int = Field(ge=1)
    rerank_k: int = Field(ge=0)
    leer_m: int = Field(ge=0)
    max_tokens_pasaje: int = Field(default=384, ge=32)
    stride: int = Field(default=128, ge=0)
    salida_temprana_sin_foco: bool = True


class PerfilInstalacion(_Estricto):
    perfil: Literal["light", "medium", "heavy", "bm25"]
    descripcion: str = ""
    presupuesto_p95_ms: int = Field(ge=1)
    modelos: ModelosPerfil
    cascada: CascadaPerfil
    etapas: list[str]
    lexico: LexicoPerfil = Field(default_factory=LexicoPerfil)
    umbrales_por_defecto: dict[str, float]
    # Lo agrega la fusión: de dónde salieron los umbrales.
    origen_umbrales: Literal["perfil", "calibracion"] = "perfil"


def _fusionar(base: dict[str, Any], cambios: dict[str, Any]) -> dict[str, Any]:
    salida = deepcopy(base)
    for clave, valor in (cambios or {}).items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fusionar(salida[clave], valor)
        else:
            salida[clave] = deepcopy(valor)
    return salida


def _datos_perfil(nombre: str) -> dict[str, Any]:
    recurso = files("rag.recursos").joinpath("perfiles", f"{nombre}.yaml")
    if not recurso.is_file():
        raise ValueError(f"perfil desconocido: {nombre!r}; disponibles: {', '.join(PERFILES_INSTALABLES)}")
    return yaml.safe_load(recurso.read_text(encoding="utf-8")) or {}


def cargar_perfil_instalacion(nombre: str) -> PerfilInstalacion:
    return PerfilInstalacion.model_validate(_datos_perfil(nombre))


def _calibracion_aplicable(perfil: PerfilInstalacion, ruta: Path) -> dict[str, float] | None:
    """Umbrales calibrados, solo si se calcularon con este perfil y estos modelos."""
    if not ruta.is_file():
        return None
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    procedencia = datos.get("procedencia") or {}
    if datos.get("perfil") != perfil.perfil:
        return None
    if (procedencia.get("modelos") or {}) != perfil.modelos.model_dump():
        return None
    umbrales = datos.get("umbrales")
    return dict(umbrales) if isinstance(umbrales, dict) else None


def perfil_efectivo(
    nombre: str,
    ajustes: dict[str, Any] | None = None,
    ruta_calibracion: str | Path = rutas.CALIBRACION,
) -> PerfilInstalacion:
    """Perfil ← ajustes del proyecto ← calibración vigente."""
    perfil = PerfilInstalacion.model_validate(_fusionar(_datos_perfil(nombre), ajustes or {}))
    calibrados = _calibracion_aplicable(perfil, Path(ruta_calibracion))
    if calibrados:
        perfil = perfil.model_copy(update={
            "umbrales_por_defecto": {**perfil.umbrales_por_defecto, **calibrados},
            "origen_umbrales": "calibracion",
        })
    return perfil


__all__ = [
    "PERFILES_INSTALABLES", "PerfilInstalacion", "cargar_perfil_instalacion", "perfil_efectivo",
]
