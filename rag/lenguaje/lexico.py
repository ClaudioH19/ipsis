"""BM25, TF-IDF y señales léxicas: funciones puras, sin E/S.

Reciben términos ya producidos por ``rag.lenguaje.texto.terminos`` y un objeto
de estadísticas del corpus (``rag.indice.estadisticas.EstadisticasLexicas`` o
cualquiera con la misma forma). Ver ``docs/plan/lexico-y-multilenguaje.md``.
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


__all__ = [
    "B", "K1", "Estadisticas", "bm25_consulta", "bm25_doc", "bm25_puntaje",
    "coseno", "id_termino", "mmr", "tfidf_vector",
]
