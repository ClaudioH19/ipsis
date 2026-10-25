"""Perfiles de instalación (light, medium) y su fusión por capas.

El perfil define los modelos, el presupuesto de latencia y el modo de recuperación. La
configuración efectiva se arma en este orden:

    perfil (ipsis/recursos/perfiles/<perfil>.yaml)
      ← config/engine.yaml::ajustes_perfil
"""
from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ipsis.recursos.mensajes import t

PERFILES_INSTALABLES = ("light", "medium")


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelosPerfil(_Estricto):
    denso: str
    reranker: str | None = None
    lector: str | None = None


class PerfilInstalacion(_Estricto):
    perfil: Literal["light", "medium", "bm25"]
    descripcion: str = ""
    presupuesto_p95_ms: int = Field(ge=1)
    modelos: ModelosPerfil
    # Modo de recuperación propio del perfil; si falta, el de engine.yaml.
    recuperacion_modo: Literal["vectorial", "hibrida", "dispersa"] | None = None
    # Reranker propio de cada idioma del proyecto (código de idioma → modelo) y cuántos candidatos puntúa.
    # Un proyecto que fija ``modelos.reranker`` en sus ajustes no los usa.
    reranker_por_idioma: dict[str, str] = Field(default_factory=dict)
    rerank_candidatos_por_idioma: dict[str, int] = Field(default_factory=dict)


def _fusionar(base: dict[str, Any], cambios: dict[str, Any]) -> dict[str, Any]:
    salida = deepcopy(base)
    for clave, valor in (cambios or {}).items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fusionar(salida[clave], valor)
        else:
            salida[clave] = deepcopy(valor)
    return salida


def _datos_perfil(nombre: str) -> dict[str, Any]:
    recurso = files("ipsis.recursos").joinpath("perfiles", f"{nombre}.yaml")
    if not recurso.is_file():
        raise ValueError(t("core.unknown_profile", name=nombre, available=", ".join(PERFILES_INSTALABLES)))
    from ipsis.configuracion.archivos import interpretar

    return interpretar(recurso.read_text(encoding="utf-8"), "perfil")


def cargar_perfil_instalacion(nombre: str) -> PerfilInstalacion:
    return PerfilInstalacion.model_validate(_datos_perfil(nombre))


def ajustes_de_idioma(nombre: str, ajustes: dict[str, Any] | None, idioma: str | None) -> tuple[dict[str, Any] | None, int | None]:
    """Agrega a los ajustes del proyecto el reranker que el perfil define para ``idioma`` (``"es"``, ``"pt"``…).

    Devuelve ``(ajustes, candidatos)``: ``candidatos`` es cuántos candidatos puntúa ese reranker, o ``None``.
    Un proyecto que ya fija ``modelos.reranker`` conserva el suyo y no recibe ni modelo ni candidatos del perfil.
    """
    if not idioma:
        return ajustes, None
    datos = _datos_perfil(nombre)
    codigo = idioma.lower().split("-")[0]
    modelo = (datos.get("reranker_por_idioma") or {}).get(codigo)
    if modelo is None or ((ajustes or {}).get("modelos") or {}).get("reranker"):
        return ajustes, None
    candidatos = (datos.get("rerank_candidatos_por_idioma") or {}).get(codigo)
    return _fusionar(dict(ajustes or {}), {"modelos": {"reranker": modelo}}), candidatos


def perfil_efectivo(nombre: str, ajustes: dict[str, Any] | None = None) -> PerfilInstalacion:
    """Perfil ← ajustes del proyecto (``engine.yaml::ajustes_perfil``)."""
    return PerfilInstalacion.model_validate(_fusionar(_datos_perfil(nombre), dict(ajustes or {})))


__all__ = [
    "PERFILES_INSTALABLES", "PerfilInstalacion", "ajustes_de_idioma", "cargar_perfil_instalacion", "perfil_efectivo",
]
