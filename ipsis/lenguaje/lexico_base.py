"""Utilidades léxicas compartidas, sin interpretar preguntas ni respuestas."""
from __future__ import annotations

import re
import unicodedata

from ipsis.lenguaje.texto import terminos


def plano(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", sin_tildes.lower()).split())


_GENERICOS: dict[int, tuple[object, frozenset[str]]] = {}


def terminos_genericos(paquete) -> frozenset[str]:
    palabras = getattr(paquete, "genericas", None) or []
    if not palabras:
        return frozenset()
    guardado = _GENERICOS.get(id(paquete))
    if guardado is not None and guardado[0] is paquete:
        return guardado[1]
    salida = frozenset(r for p in palabras for r in terminos(plano(p), paquete))
    _GENERICOS[id(paquete)] = (paquete, salida)
    return salida


_GRUPOS: dict[int, tuple[object, dict]] = {}


def grupos_por_raiz(paquete) -> dict[str, list[list[tuple[str, tuple[str, ...]]]]]:
    grupos = getattr(paquete, "sinonimos", None) or []
    if not grupos and not getattr(paquete, "sinonimos_dominio", None):
        return {}
    guardado = _GRUPOS.get(id(paquete))
    if guardado is not None and guardado[0] is paquete:
        return guardado[1]
    dominio = getattr(paquete, "sinonimos_dominio", ())
    propios = {r for g in dominio for f in g if len(plano(f).split()) == 1 for r in terminos(f, paquete)}
    grupos = [[f for f in g if not propios.intersection(terminos(f, paquete))] for g in grupos]
    grupos += [g for g in dominio if all(len(plano(f).split()) == 1 for f in g)]
    por_raiz: dict[str, list[list[tuple[str, tuple[str, ...]]]]] = {}
    for grupo in grupos:
        if len(grupo) < 2:
            continue
        formas = [(plano(f), tuple(terminos(plano(f), paquete))) for f in grupo]
        for raiz in {r for _, rs in formas for r in rs}:
            por_raiz.setdefault(raiz, []).append(formas)
    _GRUPOS[id(paquete)] = (paquete, por_raiz)
    return por_raiz
