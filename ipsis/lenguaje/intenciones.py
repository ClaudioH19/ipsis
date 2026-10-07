"""Respaldo de intención por ejemplos; nunca decide si hay una respuesta."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrediccionIntencion:
    nombre: str | None
    candidato: str
    similitud: float
    margen: float
    ejemplo: str


class RespaldoIntenciones:
    """Codifica ejemplos una vez. Cada intención puntúa con su mejor ejemplo.

    El margen se mide frente a la segunda *intención*, no el segundo ejemplo.
    Los vectores de consulta se reciben del caché del retriever.
    """

    def __init__(self, paquete, codificador, *, similitud: float, margen: float, habilitadas=None):
        import numpy as np

        self.similitud = similitud
        self.margen = margen
        self.habilitadas = frozenset(habilitadas) if habilitadas is not None else None
        pares = [(nombre, ejemplo) for nombre, intencion in paquete.intenciones.items()
                 for ejemplo in intencion.ejemplos]
        if len({n for n, _ in pares}) < 2:
            raise ValueError("El respaldo requiere ejemplos de al menos dos intenciones")
        if self.habilitadas is not None and not self.habilitadas <= {n for n, _ in pares}:
            raise ValueError("Intenciones habilitadas sin ejemplos")
        self.nombres, self.ejemplos = zip(*pares)
        vectores = np.asarray(codificador.codificar_consultas(list(self.ejemplos)), dtype=np.float32)
        if vectores.ndim != 2 or len(vectores) != len(pares) or not np.isfinite(vectores).all():
            raise ValueError("Vectores de ejemplos inválidos")
        normas = np.linalg.norm(vectores, axis=1, keepdims=True)
        if (normas <= 0).any():
            raise ValueError("Un ejemplo produjo un vector vacío")
        self.vectores = vectores / normas

    def predecir(self, vector) -> PrediccionIntencion:
        import numpy as np

        vector = np.asarray(vector, dtype=np.float32)
        norma = np.linalg.norm(vector)
        if vector.shape != (self.vectores.shape[1],) or not np.isfinite(vector).all() or norma <= 0:
            raise ValueError("Vector de consulta inválido")
        scores = self.vectores @ (vector / norma)
        mejores = {}
        for i, nombre in enumerate(self.nombres):
            if nombre not in mejores or scores[i] > scores[mejores[nombre]]:
                mejores[nombre] = i
        orden = sorted(mejores.values(), key=lambda i: -float(scores[i]))
        primero, segundo = orden[:2]
        score = float(scores[primero])
        margen = score - float(scores[segundo])
        elegible = self.habilitadas is None or self.nombres[primero] in self.habilitadas
        nombre = self.nombres[primero] if elegible and score > self.similitud and margen > self.margen else None
        return PrediccionIntencion(nombre, self.nombres[primero], score, margen, self.ejemplos[primero])


def construir_respaldo(paquete, retriever):
    """Sin modelo/umbrales medidos, ni en BM25, se conservan los patrones."""
    if paquete is None or getattr(retriever, "modo", None) == "dispersa":
        return None
    codificador = getattr(retriever, "codificador", None)
    modelo = getattr(getattr(codificador, "spec", None), "id_hf", None)
    umbrales = (getattr(paquete, "respaldo_intencion", None) or {}).get(modelo)
    if umbrales is None or not callable(getattr(retriever, "vector_consulta", None)):
        return None
    return RespaldoIntenciones(paquete, codificador, similitud=umbrales.similitud, margen=umbrales.margen,
                               habilitadas=umbrales.habilitadas)


def tiene_tema(pregunta, paquete, estadisticas) -> bool:
    """Un respaldo de relación requiere al menos un término de tema del corpus."""
    from ipsis.lenguaje.consultas import terminos_de_contenido, terminos_genericos

    df = getattr(estadisticas, "df", {})
    genericos = terminos_genericos(paquete)
    return any(t not in genericos and df.get(t, 0) > 0
               for t in terminos_de_contenido(pregunta, paquete, estadisticas))
