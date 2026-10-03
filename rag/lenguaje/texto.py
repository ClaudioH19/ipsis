"""Utilidades léxicas deterministas compartidas por el motor."""
from __future__ import annotations

import functools
import re
import unicodedata



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
    return {tok for tok in tokenizar(texto) if len(tok) >= largo_min and tok not in STOPWORDS_ES}


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


# ---------------------------------------------------------------------------
# Términos y oraciones independientes del idioma
# ---------------------------------------------------------------------------
_RE_PALABRA = re.compile(r"\w+")
# Terminan una oración solo si les sigue un espacio o el fin del texto: así
# «1.5» o «e.g.» no la cortan.
_TERMINALES = ".!?。！？؟।"
# En escrituras sin espacios entre oraciones el signo basta.
_TERMINALES_SIN_ESPACIO = "。！？"


def _es_latino(caracter: str) -> bool:
    return caracter.isascii() or unicodedata.name(caracter, "").startswith("LATIN")


def normalizar(token: str) -> str:
    """Quita tildes solo en palabras de escritura latina; el resto queda igual."""
    if all(_es_latino(c) for c in token):
        return sin_acentos(token)
    return token


def tokenizar(texto: str, *, normalizado: bool = True) -> list[str]:
    """Palabras Unicode (``\\w+``) en minúsculas, sin tildes si ``normalizado``."""
    tokens = _RE_PALABRA.findall(texto.casefold())
    return [normalizar(t) for t in tokens] if normalizado else tokens


@functools.lru_cache(maxsize=None)
def _stemmer(nombre: str):
    import snowballstemmer

    return snowballstemmer.stemmer(nombre)


def terminos(texto: str, paquete=None) -> list[str]:
    """Términos para BM25 y señales léxicas: tokens normalizados y con stem.

    Es la ÚNICA conversión de texto a términos del proyecto: la indexación y
    la consulta usan la misma, así que sus puntajes son reproducibles. Sin
    paquete o sin stemmer en el paquete, devuelve los tokens normalizados.
    """
    tokens = tokenizar(texto)
    nombre = getattr(paquete, "stemmer", None)
    return _stemmer(nombre).stemWords(tokens) if nombre else tokens


def dividir_oraciones(texto: str) -> list[tuple[int, int]]:
    """Rangos ``[inicio, fin)`` de cada oración, sin espacios en los bordes.

    Para todo rango devuelto, ``texto[inicio:fin]`` es la oración literal.
    """
    rangos: list[tuple[int, int]] = []
    inicio: int | None = None
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if inicio is None:
            if c.isspace():
                i += 1
                continue
            inicio = i
        if c in _TERMINALES:
            j = i
            while j + 1 < n and texto[j + 1] in _TERMINALES:
                j += 1
            if c in _TERMINALES_SIN_ESPACIO or j + 1 == n or texto[j + 1].isspace():
                rangos.append((inicio, j + 1))
                inicio = None
            i = j + 1
            continue
        i += 1
    if inicio is not None:
        fin = n
        while fin > inicio and texto[fin - 1].isspace():
            fin -= 1
        rangos.append((inicio, fin))
    return rangos
