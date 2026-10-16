"""Grupos de unidades hermanas y rasgos que las distinguen.

Dos unidades casi iguales (la tabla de la Práctica I y la de la II, dos artículos con la
misma plantilla) se confunden porque lo que las separa es poco: una cifra, un numeral, un
actor. Este módulo las agrupa por similitud TF-IDF de su texto (determinista, sin modelo ni
segunda pasada de codificación) y calcula, para cada una, los términos más característicos
frente al resto de su grupo. Los rasgos se agregan a la cabecera de lo que se indexa y se
puntúa, y quedan en el payload.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from ipsis.lenguaje.texto import normalizar

_RE_TOKEN = re.compile(r"\w+", re.UNICODE)
_ROMANO = re.compile(r"[IVX]+")


def _tokens(texto: str, vacias: frozenset[str]) -> list[tuple[str, str]]:
    """(término normalizado, forma original). Conserva cifras, códigos (P2, S7) y numerales romanos
    (I, II): son lo que más separa a unidades hermanas y las palabras cortas normales no sirven."""
    salida = []
    for forma in _RE_TOKEN.findall(texto):
        clave = normalizar(forma.casefold())
        if clave in vacias:
            continue
        if (len(forma) >= 3 or any(c.isdigit() for c in forma) or _ROMANO.fullmatch(forma)):
            salida.append((clave, forma))
    return salida


def _idf(df: Counter, n: int, termino: str) -> float:
    return math.log((n + 1) / (df[termino] + 1)) + 1.0


def agrupar_hermanos(textos: dict[str, str], umbral: float = 0.5, vacias: frozenset[str] = frozenset()):
    """``{id: texto}`` -> (grupos, tf, df). Un grupo es una componente conexa de unidades con coseno
    TF-IDF >= ``umbral`` (mínimo dos). Orden estable: los ids ordenados."""
    ids = sorted(textos)
    tf = {i: Counter(c for c, _ in _tokens(textos[i], vacias)) for i in ids}
    df: Counter = Counter()
    for c in tf.values():
        df.update(c.keys())
    n = len(ids)
    peso = {i: {t: f * _idf(df, n, t) for t, f in tf[i].items()} for i in ids}
    norma = {i: math.sqrt(sum(v * v for v in peso[i].values())) or 1.0 for i in ids}
    invertido: dict[str, list[str]] = {}
    for i in ids:
        for t in peso[i]:
            invertido.setdefault(t, []).append(i)
    padre = {i: i for i in ids}

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for i in ids:
        acumulado: Counter = Counter()
        for t, w in peso[i].items():
            for j in invertido[t]:
                if j > i:
                    acumulado[j] += w * peso[j][t]
        for j, producto in acumulado.items():
            if producto / (norma[i] * norma[j]) >= umbral:
                a, b = raiz(i), raiz(j)
                if a != b:
                    padre[max(a, b)] = min(a, b)
    grupos: dict[str, list[str]] = {}
    for i in ids:
        grupos.setdefault(raiz(i), []).append(i)
    return [sorted(g) for g in grupos.values() if len(g) > 1], tf, df


def grupos_por_vectores(ids: list[str], vectores, umbral: float) -> list[list[str]]:
    """Componentes conexas de unidades cuyos vectores (los del modelo denso) tienen coseno >= ``umbral``.
    Los cosenos de e5 se comprimen entre 0,85 y 1: los umbrales útiles son altos (0,93 a 0,97)."""
    import numpy as np

    v = np.asarray(vectores, dtype=np.float64)
    v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
    orden = sorted(range(len(ids)), key=lambda k: ids[k])
    coseno = v @ v.T
    padre = {k: k for k in range(len(ids))}

    def raiz(k):
        while padre[k] != k:
            padre[k] = padre[padre[k]]
            k = padre[k]
        return k

    for x, i in enumerate(orden):
        for j in orden[x + 1:]:
            if coseno[i, j] >= umbral:
                a, b = raiz(i), raiz(j)
                if a != b:
                    padre[a if ids[a] > ids[b] else b] = b if ids[a] > ids[b] else a
    grupos: dict[int, list[str]] = {}
    for k in orden:
        grupos.setdefault(raiz(k), []).append(ids[k])
    return [sorted(g) for g in grupos.values() if len(g) > 1]


def rasgos_distintivos(textos: dict[str, str], umbral: float = 0.5, maximo: int = 3,
                       vacias: frozenset[str] = frozenset(), grupos: list[list[str]] | None = None) -> dict[str, dict]:
    """Para cada unidad que tiene hermanas: ``{"grupo_similar": id estable del grupo, "rasgos_distintivos": [...]}``.
    Un rasgo puntúa más cuanto más pesa en la unidad (TF-IDF) y menos aparece en el resto del grupo; las
    formas son las originales, ordenadas por puntaje y luego alfabéticamente. Con ``grupos`` los grupos vienen de
    fuera (p. ej. por vectores vecinos) y el TF-IDF solo elige los términos."""
    if maximo < 1:
        return {}
    por_texto, tf, df = agrupar_hermanos(textos, umbral, vacias)
    grupos = por_texto if grupos is None else grupos
    n = len(textos)
    resultado = {}
    for grupo in grupos:
        for i in grupo:
            otros = [j for j in grupo if j != i]
            formas: dict[str, Counter] = {}
            for clave, forma in _tokens(textos[i], vacias):
                formas.setdefault(clave, Counter())[forma] += 1
            puntajes = []
            for t, f in tf[i].items():
                compartido = sum(1 for j in otros if t in tf[j]) / len(otros)
                puntaje = f * _idf(df, n, t) * (1.0 - compartido)
                if puntaje > 0:
                    puntajes.append((-puntaje, t))
            elegidos = []
            for _, t in sorted(puntajes):
                # «bitácora» y «bitácoras» son un solo rasgo: se descarta la variante de igual raíz.
                if t.isalpha() and len(t) >= 5 and any(o.isalpha() and o[:5] == t[:5] for o in elegidos):
                    continue
                elegidos.append(t)
                if len(elegidos) == maximo:
                    break
            resultado[i] = {"grupo_similar": grupo[0],
                            "rasgos_distintivos": [max(formas[t].items(), key=lambda p: (p[1], p[0]))[0] for t in elegidos]}
    return resultado
