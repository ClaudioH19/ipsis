"""Codificador denso (embeddings) sobre ONNX.

Aplica los prefijos que el modelo exige (E5: ``query: `` y ``passage: ``),
promedia los estados ocultos con la máscara de atención y normaliza a norma
1 (el pooling que usa E5).
"""
from __future__ import annotations

from collections.abc import Sequence

from rag.modelos.onnx import ModeloOnnx


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
            ocultos = self.ejecutar(cod)[0]  # (lote, tokens, dimensión)
            mascara = np.array([c.attention_mask for c in cod], dtype=np.float32)[..., None]
            promedio = (ocultos * mascara).sum(axis=1) / np.clip(mascara.sum(axis=1), 1e-9, None)
            norma = np.linalg.norm(promedio, axis=1, keepdims=True)
            partes.append(promedio / np.clip(norma, 1e-12, None))
        return np.vstack(partes).astype(np.float32)

    def codificar_consultas(self, textos: Sequence[str]):
        return self._codificar([self.spec.prefijo_consulta + t for t in textos])

    def codificar_documentos(self, textos: Sequence[str]):
        return self._codificar([self.spec.prefijo_pasaje + t for t in textos])


__all__ = ["CodificadorDenso"]
