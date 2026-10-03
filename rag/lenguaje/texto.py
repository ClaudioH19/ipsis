"""Utilidades léxicas deterministas compartidas por el motor."""
from __future__ import annotations

import functools
import re
import unicodedata
from pathlib import Path

import yaml


STOPWORDS_ES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "a", "en", "y", "o", "u", "e", "que", "se", "su", "sus", "por", "para",
    "con", "sin", "es", "son", "ser", "esta", "este", "estos", "estas",
    "esa", "ese", "esos", "esas", "lo", "le", "les", "como", "cuando",
    "cual", "cuales", "donde", "quien", "quienes", "no", "si", "ya", "mas",
    "pero", "sobre", "entre", "hasta", "desde", "durante", "cada", "todo",
    "toda", "todos", "todas", "otro", "otra", "otros", "otras", "cuanto",
    "cuanta", "cuantos", "cuantas", "tambien", "asi", "muy", "puede", "podra",
    "debera", "deben", "debe", "sera", "seran", "tiene", "tienen", "haber",
    "hay", "fue", "han", "ha", "yo", "tu", "ella", "ellos", "ellas", "nos",
    "mi", "tus",
}


@functools.lru_cache(maxsize=None)
def cargar_palabras_generales(idioma: str = "es") -> frozenset[str]:
    """Palabras frecuentes que no prueban pertenencia al dominio.

    Transitorio: la señal s_oov basada en IDF las reemplaza en el plan V3 (P4.4).
    Un idioma sin paquete devuelve un conjunto vacío.
    """
    from rag.lenguaje.paquete import cargar_paquete

    try:
        return frozenset(cargar_paquete(idioma).palabras_generales)
    except ValueError:
        return frozenset()


PALABRAS_GENERALES_ES = cargar_palabras_generales("es")


def sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def palabras_contenido(texto: str, largo_min: int = 4) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", sin_acentos(texto).lower())
    return {tok for tok in tokens if len(tok) >= largo_min and tok not in STOPWORDS_ES}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def solapamiento_lexico(pregunta: str, evidencia: str, largo_min: int = 4) -> float:
    palabras_pregunta = palabras_contenido(pregunta, largo_min)
    if not palabras_pregunta:
        return 0.0
    palabras_evidencia = palabras_contenido(evidencia, largo_min)
    return sum(1 for w in palabras_pregunta if w in palabras_evidencia) / len(palabras_pregunta)
