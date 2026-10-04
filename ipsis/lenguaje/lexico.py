"""BM25, TF-IDF y señales léxicas: funciones puras, sin E/S.

Reciben términos ya producidos por ``ipsis.lenguaje.texto.terminos`` y un objeto
de estadísticas del corpus (``ipsis.indice.estadisticas.EstadisticasLexicas`` o
cualquiera con la misma forma). Ver ``docs/metodologia/lexico.md``.
"""
from __future__ import annotations

import math
import zlib
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

K1 = 1.2
B = 0.75


class Estadisticas(Protocol):
    n_chunks: int
    largo_medio: float
    df: dict[str, int]

    def idf(self, termino: str) -> float: ...


def id_termino(termino: str) -> int:
    """Id estable de 32 bits para el vector disperso de Qdrant (sin vocabulario)."""
    return zlib.crc32(termino.encode("utf-8"))


def _peso_tf(tf: int, largo: int, est: Estadisticas, k1: float, b: float) -> float:
    medio = est.largo_medio or 1.0
    return tf * (k1 + 1) / (tf + k1 * (1 - b + b * largo / medio))


def bm25_doc(terminos_doc: Sequence[str], est: Estadisticas, k1: float = K1, b: float = B) -> dict[int, float]:
    """Parte del documento de BM25 (TF saturado y normalizado por largo).

    Qdrant aplica el IDF en el servidor (``modifier: idf``), así que aquí no
    se multiplica por él.
    """
    largo = len(terminos_doc)
    return {id_termino(t): _peso_tf(tf, largo, est, k1, b) for t, tf in Counter(terminos_doc).items()}


def bm25_consulta(terminos_q: Sequence[str]) -> dict[int, float]:
    """Vector de la consulta: 1 por término único."""
    return {id_termino(t): 1.0 for t in set(terminos_q)}


def bm25_puntaje(
    terminos_q: Sequence[str], terminos_doc: Sequence[str], est: Estadisticas, k1: float = K1, b: float = B
) -> float:
    """BM25 completo (con IDF local), para señales y pruebas."""
    tf = Counter(terminos_doc)
    largo = len(terminos_doc)
    return sum(est.idf(t) * _peso_tf(tf[t], largo, est, k1, b) for t in set(terminos_q) if tf[t])


def tfidf_vector(terminos: Sequence[str], est: Estadisticas) -> dict[str, float]:
    """Vector TF-IDF normalizado (norma L2 = 1)."""
    pesos = {t: tf * est.idf(t) for t, tf in Counter(terminos).items()}
    norma = math.sqrt(sum(p * p for p in pesos.values()))
    return {t: p / norma for t, p in pesos.items()} if norma else {}


def coseno(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    producto = sum(v * b.get(t, 0.0) for t, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return producto / (na * nb) if na and nb else 0.0


def mmr(
    vectores: Sequence[dict[str, float]],
    k: int,
    lambda_: float = 0.5,
    consulta: dict[str, float] | None = None,
) -> list[int]:
    """Máxima relevancia marginal: elige ``k`` índices relevantes y diversos.

    Sin ``consulta`` la relevancia es la similitud media con el resto
    (representatividad). Los empates se resuelven por el índice menor.
    """
    n = len(vectores)
    if n == 0 or k <= 0:
        return []
    if consulta is not None:
        relevancia = [coseno(v, consulta) for v in vectores]
    else:
        relevancia = [
            sum(coseno(vectores[i], vectores[j]) for j in range(n) if j != i) / max(n - 1, 1) for i in range(n)
        ]
    elegidos: list[int] = []
    while len(elegidos) < min(k, n):
        mejor, mejor_valor = None, -math.inf
        for i in range(n):
            if i in elegidos:
                continue
            redundancia = max((coseno(vectores[i], vectores[j]) for j in elegidos), default=0.0)
            valor = lambda_ * relevancia[i] - (1 - lambda_) * redundancia
            if valor > mejor_valor:
                mejor, mejor_valor = i, valor
        elegidos.append(mejor)
    return elegidos


# ---------------------------------------------------------------------------
# Señales léxicas, todas en [0, 1]. ``terminos_q`` ya viene sin stopwords
# (ver ``terminos_contenido``): las palabras vacías no aportan evidencia.
# ---------------------------------------------------------------------------
def terminos_contenido(terminos_q: Sequence[str], stop: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Términos de la pregunta sin stopwords ni duplicados, en orden."""
    vistos: list[str] = []
    for t in terminos_q:
        if t not in stop and t not in vistos:
            vistos.append(t)
    return vistos


def terminos_pregunta(pregunta: str, paquete=None) -> list[str]:
    """Términos de contenido de una pregunta: ``terminos()`` sin stopwords del idioma."""
    from ipsis.lenguaje.texto import terminos

    stop = set(terminos(" ".join(paquete.stopwords), paquete)) if paquete is not None else set()
    return terminos_contenido(terminos(pregunta, paquete), stop)


def terminos_foco(terminos_q: Sequence[str], est: Estadisticas, k: int = 2) -> list[str]:
    """Los ``k`` términos de la pregunta con mayor IDF que existen en el corpus.

    Son «de qué se habla»: en «¿Cuánto dura la garantía?», la garantía. Los
    términos ausentes del corpus no cuentan (los mide ``s_oov``). Empates por
    orden alfabético, para que el resultado sea determinista.
    """
    presentes = [t for t in dict.fromkeys(terminos_q) if est.df.get(t, 0) > 0]
    return sorted(presentes, key=lambda t: (-est.idf(t), t))[:k]


def s_oov(terminos_q: Sequence[str], est: Estadisticas) -> float:
    """Masa IDF de la pregunta que no existe en el corpus (1 = nada existe)."""
    unicos = list(dict.fromkeys(terminos_q))
    total = sum(est.idf(t) for t in unicos)
    if not total:
        return 0.0
    return sum(est.idf(t) for t in unicos if est.df.get(t, 0) == 0) / total


def s_cov(terminos_q: Sequence[str], terminos_tramo: Sequence[str], est: Estadisticas) -> float:
    """Fracción de la masa IDF de la pregunta presente en el tramo."""
    unicos = list(dict.fromkeys(terminos_q))
    total = sum(est.idf(t) for t in unicos)
    if not total:
        return 0.0
    presentes = set(terminos_tramo)
    return sum(est.idf(t) for t in unicos if t in presentes) / total


def s_foco(foco: Sequence[str], terminos_oracion: Sequence[str]) -> float:
    """Fracción de términos foco presentes en la oración (1 si no hay foco)."""
    if not foco:
        return 1.0
    presentes = set(terminos_oracion)
    return sum(1 for t in foco if t in presentes) / len(foco)


def s_lex(
    terminos_q: Sequence[str], terminos_oracion: Sequence[str], est: Estadisticas, k1: float = K1, b: float = B
) -> float:
    """BM25 de la oración normalizado por el máximo teórico de la pregunta."""
    maximo = sum(est.idf(t) * (k1 + 1) for t in set(terminos_q))
    return bm25_puntaje(terminos_q, terminos_oracion, est, k1, b) / maximo if maximo else 0.0


def acuerdo(ids_denso: Sequence, ids_bm25: Sequence, n: int = 3) -> float:
    """1 si cada top-1 está en el top-``n`` del otro, 0,5 si solo uno, 0 si ninguno."""
    if not ids_denso or not ids_bm25:
        return 0.0
    return (0.5 if ids_denso[0] in ids_bm25[:n] else 0.0) + (0.5 if ids_bm25[0] in ids_denso[:n] else 0.0)


__all__ = [
    "B", "K1", "Estadisticas", "acuerdo", "bm25_consulta", "bm25_doc", "bm25_puntaje",
    "coseno", "id_termino", "mmr", "s_cov", "s_foco", "s_lex", "s_oov", "terminos_contenido",
    "terminos_foco", "terminos_pregunta", "tfidf_vector",
]
