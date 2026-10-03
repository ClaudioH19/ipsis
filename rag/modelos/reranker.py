"""Reranker cross-encoder sobre ONNX: puntúa pares (pregunta, pasaje)."""
from __future__ import annotations

from collections.abc import Sequence

from rag.modelos.onnx import ModeloOnnx


class RerankerOnnx(ModeloOnnx):
    lote: int = 16

    def puntuar(self, pregunta: str, pasajes: Sequence[str]) -> list[float]:
        """Logit de pertinencia de cada pasaje (mayor = más pertinente)."""
        puntajes: list[float] = []
        for i in range(0, len(pasajes), self.lote):
            pares = [(pregunta, p) for p in pasajes[i:i + self.lote]]
            salida = self.ejecutar(self.tokenizar(pares))[0]
            puntajes.extend(float(fila[0]) if getattr(fila, "shape", ()) else float(fila) for fila in salida)
        return puntajes

    def calentar(self) -> None:
        self.puntuar("calentamiento", ["calentamiento del modelo"])


__all__ = ["RerankerOnnx"]
