"""Línea clave de una fuente publicada (ADR 0013): la línea del pasaje más cercana a la pregunta.

Es una **señal de lectura**, no una respuesta: no cambia qué fuentes se publican ni su orden, y su texto es siempre un
tramo literal del pasaje (offsets del documento). Se elige por similitud densa entre la pregunta y cada línea, con el
mismo codificador del recuperador, y solo se publica si la mejor línea se separa de la segunda por ``margen``: cuando
ninguna destaca, mostrar una sería adivinar. Sin margen suficiente, con una sola línea o con demasiadas, no hay línea
clave y la tarjeta se ve como siempre.

Cada línea se codifica una sola vez: los vectores quedan en una caché acotada, de modo que una fuente repetida no vuelve
a costar tiempo.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

MAX_LINEAS = 80  # más líneas que esto: el pasaje no es una tabla corta ni un párrafo breve; no se arriesga el costo
MIN_CARACTERES_UTILES = 3


def tramos_de_linea(texto: str) -> list[tuple[int, int]]:
    """``(inicio, fin)`` de cada línea con contenido, sin espacios en los bordes ni salto de línea.

    Las líneas casi vacías (solo signos o menos de ``MIN_CARACTERES_UTILES`` letras o cifras) no cuentan.
    """
    tramos, posicion = [], 0
    for linea in texto.split("\n"):
        inicio = posicion + len(linea) - len(linea.lstrip())
        fin = posicion + len(linea.rstrip())
        if fin > inicio and sum(c.isalnum() for c in texto[inicio:fin]) >= MIN_CARACTERES_UTILES:
            tramos.append((inicio, fin))
        posicion += len(linea) + 1
    return tramos


def elegir(puntajes, margen: float) -> tuple[int, float] | None:
    """``(índice, separación)`` de la mejor línea, o ``None`` si hay menos de dos o no se separa por ``margen``."""
    if len(puntajes) < 2:
        return None
    ordenados = sorted(range(len(puntajes)), key=lambda i: -float(puntajes[i]))
    separacion = float(puntajes[ordenados[0]]) - float(puntajes[ordenados[1]])
    return (ordenados[0], separacion) if separacion >= margen else None


class SelectorLineaClave:
    """Elige la línea clave de un pasaje; guarda los vectores de las líneas ya vistas."""

    def __init__(self, codificador, *, capacidad: int = 20000):
        self.codificador = codificador
        self.capacidad = capacidad
        self._vectores: OrderedDict[str, object] = OrderedDict()
        self._cerrojo = threading.Lock()

    def lineas_nuevas(self, texto: str) -> int:
        """Cuántas líneas de ``texto`` aún no tienen vector (para estimar el costo antes de codificar)."""
        with self._cerrojo:
            return sum(1 for a, b in tramos_de_linea(texto) if texto[a:b] not in self._vectores)

    def _matriz(self, lineas: list[str]):
        import numpy as np

        with self._cerrojo:
            faltan = [l for l in dict.fromkeys(lineas) if l not in self._vectores]
        if faltan:
            nuevos = self.codificador.codificar_documentos(faltan)
            with self._cerrojo:
                for linea, vector in zip(faltan, nuevos, strict=True):
                    self._vectores[linea] = vector
        with self._cerrojo:
            matriz = np.stack([self._vectores[l] for l in lineas])
            for linea in lineas:
                self._vectores.move_to_end(linea)
            while len(self._vectores) > self.capacidad:
                self._vectores.popitem(last=False)
        return matriz

    def seleccionar(self, vector_pregunta, texto: str, *, base: int = 0, margen: float) -> dict | None:
        """``{"offset_inicio", "offset_fin", "margen", "metodo"}`` (offsets del documento: ``base`` + posición)."""
        tramos = tramos_de_linea(texto)
        if not 2 <= len(tramos) <= MAX_LINEAS:
            return None
        puntajes = self._matriz([texto[a:b] for a, b in tramos]) @ vector_pregunta
        elegida = elegir(puntajes, margen)
        if elegida is None:
            return None
        indice, separacion = elegida
        inicio, fin = tramos[indice]
        return {"offset_inicio": base + inicio, "offset_fin": base + fin,
                "margen": round(separacion, 4), "metodo": "denso"}


__all__ = ["MAX_LINEAS", "SelectorLineaClave", "elegir", "tramos_de_linea"]
