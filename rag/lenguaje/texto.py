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
def cargar_palabras_generales(
    idioma: str = "es", ruta_base: str = "configuracion/dominios/idiomas"
) -> frozenset[str]:
    """Carga palabras frecuentes que no prueban pertenencia al dominio."""
    ruta = Path(ruta_base) / f"{idioma}.yaml"
    if not ruta.exists():
        return frozenset()
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return frozenset(datos.get("palabras_generales", []))


def _palabras_generales_del_paquete(idioma: str) -> frozenset[str]:
    """Lee el recurso incluido en el paquete, sin depender del directorio actual."""
    from rag.recursos import leer_plantilla

    try:
        datos = yaml.safe_load(leer_plantilla(f"dominios/idiomas/{idioma}.yaml")) or {}
    except FileNotFoundError:
        return frozenset()
    return frozenset(datos.get("palabras_generales", []))


PALABRAS_GENERALES_ES = _palabras_generales_del_paquete("es")


def escribir_idioma_es_si_falta(
    ruta_base: str = "configuracion/dominios/idiomas",
) -> bool:
    """Copia el recurso global de español incluido en el paquete."""
    from rag.recursos import leer_plantilla

    ruta = Path(ruta_base) / "es.yaml"
    if ruta.exists():
        return False
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(leer_plantilla("dominios/idiomas/es.yaml"), encoding="utf-8")
    cargar_palabras_generales.cache_clear()
    return True


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
