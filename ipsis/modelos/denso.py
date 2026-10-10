"""Codificador denso (embeddings) sobre ONNX.

Aplica los prefijos y el pooling del catálogo: media enmascarada, CLS,
último token o salida ya agregada. Valida dimensión y valores finitos y
normaliza a norma 1 antes de entregar los vectores al índice.
"""
from __future__ import annotations

from collections.abc import Sequence

from ipsis.modelos.onnx import ModeloOnnx


class CodificadorDenso(ModeloOnnx):
    lote: int = 32

    @property
    def dimension(self) -> int:
        return int(self.spec.dimension)

    def _codificar(self, textos: Sequence[str]):
        import numpy as np

        if not textos:
            return np.zeros((0, self.dimension), dtype=np.float32)
        partes = []
        for i in range(0, len(textos), self.lote):
            cod = self.tokenizar(textos[i:i + self.lote])
            salidas = self.ejecutar(cod)
            indice = 0
            if self.spec.salida:
                nombres = [s.name for s in self.sesion.get_outputs()]
                indice = nombres.index(self.spec.salida)
            ocultos = np.asarray(salidas[indice], dtype=np.float32)
            mascara = np.array([c.attention_mask for c in cod], dtype=np.float32)
            if self.spec.pooling == "sentence":
                vector = ocultos
            elif self.spec.pooling == "cls":
                vector = ocultos[:, 0, :]
            elif self.spec.pooling == "last_token":
                ultimo = np.where(mascara > 0, np.arange(mascara.shape[1]), -1).max(axis=1)
                if np.any(ultimo < 0):
                    raise ValueError("Cannot pool an empty token sequence")
                vector = ocultos[np.arange(len(cod)), ultimo]
            else:
                vector = (ocultos * mascara[..., None]).sum(axis=1) / np.clip(mascara.sum(axis=1)[:, None], 1e-9, None)
            if vector.shape != (len(cod), self.dimension) or not np.all(np.isfinite(vector)):
                raise ValueError(f"Invalid embedding output: {vector.shape}, expected {(len(cod), self.dimension)}")
            norma = np.linalg.norm(vector, axis=1, keepdims=True)
            if np.any(norma <= 1e-12):
                raise ValueError("Embedding output has zero norm")
            partes.append(vector / norma)
        return np.vstack(partes).astype(np.float32)

    def codificar_consultas(self, textos: Sequence[str]):
        return self._codificar([self.spec.prefijo_consulta + t for t in textos])

    def codificar_documentos(self, textos: Sequence[str]):
        return self._codificar([self.spec.prefijo_pasaje + t for t in textos])


__all__ = ["CodificadorDenso"]
