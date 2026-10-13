"""Mensajes fijos de interfaz; nunca se presentan como evidencia documental."""
from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
import re
import unicodedata

import yaml


def _codigo(idioma: str) -> str:
    codigo = (idioma or "en").lower().replace("_", "-").split("-")[0]
    return codigo if codigo in {"es", "en", "pt"} else "en"


def _normalizar_pregunta(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.strip().strip("¡!¿?.,;: ").split())


@lru_cache(maxsize=3)
def _preguntas(idioma: str) -> dict:
    recurso = files("ipsis.recursos").joinpath("voz", f"faq-{idioma}.yaml")
    preguntas = yaml.safe_load(recurso.read_text(encoding="utf-8"))["questions"]
    indice = {}
    for entrada in preguntas:
        clave = _normalizar_pregunta(entrada["question"])
        if not clave or clave in indice or not entrada["answer"].strip():
            raise ValueError(f"Catálogo de preguntas inválido: {idioma}")
        indice[clave] = entrada["answer"]
    return {"questions": preguntas, "index": indice}


def preguntas_fijas(idioma: str) -> list[dict[str, str]]:
    """Copia del catálogo completo para validación y exportación documental."""
    return [dict(p) for p in _preguntas(_codigo(idioma))["questions"]]


def respuesta_fija(pregunta: str, idioma: str) -> str | None:
    """Solo preguntas completas sobre el asistente; nunca coincidencias parciales."""
    return _preguntas(_codigo(idioma))["index"].get(_normalizar_pregunta(pregunta))


@lru_cache(maxsize=3)
def _banco(idioma: str) -> dict:
    recurso = files("ipsis.recursos").joinpath("voz", f"{idioma}.yaml")
    return yaml.safe_load(recurso.read_text(encoding="utf-8"))


def voz_del_widget(idioma: str) -> dict:
    """Banco independiente de tonos, con copia para evitar cambios en la caché."""
    banco = _banco(_codigo(idioma))
    return {"interface": dict(banco["interface"]),
            "messages": {clave: list(textos) for clave, textos in banco["messages"].items()},
            "suggestions": list(banco.get("suggestions") or []),
            "questions": [{"question": p["question"], "topic": p["topic"]} for p in preguntas_fijas(idioma)]}


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
