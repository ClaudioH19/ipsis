"""Paquetes de idioma: todo texto y patrón que depende del idioma.

Cada idioma soportado tiene un YAML en ``rag/recursos/idiomas/<código>.yaml``.
Un proyecto puede sobrescribir cualquier clave en ``configuracion/idioma.yaml``;
la fusión es profunda para objetos y reemplaza listas completas.
"""
from __future__ import annotations

import functools
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from rag.configuracion import rutas


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Marcadores(_Estricto):
    excepcion: list[str] = Field(default_factory=list)
    condicion: list[str] = Field(default_factory=list)


class Conversacional(_Estricto):
    categorias: list[str] = Field(default_factory=list)
    patrones: dict[str, list[str]] = Field(default_factory=dict)
    respuestas: dict[str, list[str] | str] = Field(default_factory=dict)


class Mensajes(_Estricto):
    sin_respuesta: str
    premisa_no_encontrada: str
    relacionado_intro: str
    relacionado_foco_ausente: str
    sin_seccion: str
    conectores: dict[str, list[str]] = Field(default_factory=dict)


class GoldenInstrucciones(_Estricto):
    """Textos de ``rag golden plantilla`` (ver docs/plan/comandos-y-golden.md §3).

    ``nota_*`` admiten ``{terminos}`` (términos clave de la sección),
    ``{documento}`` y ``{par}``. ``conversacionales`` son tres preguntas ya
    completas.
    """

    leeme: str
    nota_respondible: str
    nota_trampa: str
    conversacionales: list[str] = Field(min_length=3, max_length=3)


class PaqueteIdioma(_Estricto):
    codigo: str = Field(min_length=2)
    nombre: str = Field(min_length=1)
    stemmer: str | None = None
    stopwords: list[str] = Field(default_factory=list)
    numeros: dict[str, int] = Field(default_factory=dict)
    ordinales: dict[str, int] = Field(default_factory=dict)
    meses: list[str] = Field(default_factory=list)
    dias_semana: dict[str, list[str]] = Field(default_factory=dict)  # ISO: 1=lunes … 7=domingo
    unidades_tiempo: dict[str, list[str]] = Field(default_factory=dict)
    calificadores_plazo: dict[str, list[str]] = Field(default_factory=dict)
    referencias_documento: dict[str, list[str]] = Field(default_factory=dict)
    conectores_rango: dict[str, list[str]] = Field(default_factory=dict)  # claves: y (lista), a (rango)
    conectores_fecha: list[str] = Field(default_factory=list)
    conectores_fecha_relativa: list[str] = Field(default_factory=list)
    marcadores: Marcadores = Field(default_factory=Marcadores)
    conversacional: Conversacional = Field(default_factory=Conversacional)
    mensajes: Mensajes
    interfaz: dict[str, str] = Field(default_factory=dict)
    # Contracciones obligatorias al insertar variables en un texto fijo
    # (en español: «de el» -> «del»).
    contracciones: dict[str, str] = Field(default_factory=dict)
    golden_instrucciones: GoldenInstrucciones | None = None


def _carpeta_paquetes():
    return files("rag.recursos").joinpath("idiomas")


def idiomas_disponibles() -> list[str]:
    """Códigos de idioma con paquete incluido en la instalación."""
    return sorted(
        recurso.name.removesuffix(".yaml")
        for recurso in _carpeta_paquetes().iterdir()
        if recurso.name.endswith(".yaml")
    )


def _fusionar(base: dict[str, Any], cambios: dict[str, Any]) -> dict[str, Any]:
    salida = deepcopy(base)
    for clave, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fusionar(salida[clave], valor)
        else:
            salida[clave] = deepcopy(valor)
    return salida


@functools.lru_cache(maxsize=None)
def _paquete_base(codigo: str) -> dict[str, Any]:
    disponibles = idiomas_disponibles()
    if codigo not in disponibles:
        raise ValueError(
            f"no hay paquete de idioma {codigo!r}; disponibles: {', '.join(disponibles)}"
        )
    texto = _carpeta_paquetes().joinpath(f"{codigo}.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(texto) or {}


def cargar_paquete(codigo: str, proyecto: str | Path | None = None) -> PaqueteIdioma:
    """Paquete del idioma ``codigo``, con las sobrescrituras del proyecto si existen."""
    datos = _paquete_base(codigo)
    if proyecto is not None:
        ruta = Path(proyecto) / rutas.IDIOMA
        if ruta.is_file():
            datos = _fusionar(datos, yaml.safe_load(ruta.read_text(encoding="utf-8")) or {})
    return PaqueteIdioma.model_validate(datos)


__all__ = ["PaqueteIdioma", "cargar_paquete", "idiomas_disponibles"]
