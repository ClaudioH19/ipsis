"""Mensajes fijos de interfaz; nunca se presentan como evidencia documental."""
from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
import re

import yaml


@lru_cache(maxsize=3)
def _banco(idioma: str) -> dict:
    recurso = files("ipsis.recursos").joinpath("voz", f"{idioma}.yaml")
    return yaml.safe_load(recurso.read_text(encoding="utf-8"))


def voz_del_widget(idioma: str) -> dict:
    """Banco independiente de tonos, con copia para evitar cambios en la caché."""
    codigo = (idioma or "en").lower().replace("_", "-").split("-")[0]
    banco = _banco(codigo if codigo in {"es", "en", "pt"} else "en")
    return {"interface": dict(banco["interface"]),
            "messages": {clave: list(textos) for clave, textos in banco["messages"].items()},
            "suggestions": list(banco.get("suggestions") or [])}


def categoria_cortesia(pregunta: str, plantillas: dict) -> str | None:
    """Solo expresiones completas: 'hola, precio del producto' sigue buscando.

    Reutiliza el vocabulario del idioma, sin la búsqueda por prefijo de v1.
    No introduce filtros de documentos ni reglas de pertinencia.
    """
    texto = pregunta.strip().strip("¡!¿?.,;: ")
    patrones = plantillas.get("conversacional", {}).get("patrones", {})
    for categoria in ("greeting", "thanks", "farewell", "capability"):
        if any(re.fullmatch(patron, texto, re.IGNORECASE) for patron in patrones.get(categoria, [])):
            return categoria
    return None
