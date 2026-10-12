"""Base común para ejecutar modelos ONNX en CPU (patrón Template Method).

``ModeloOnnx`` resuelve lo que comparten todos los modelos: ubicar los
archivos en la caché, abrir una sola sesión de onnxruntime por modelo, cargar
el tokenizador y preparar las entradas. Cada subclase solo decide qué textos
tokenizar y cómo interpretar las salidas.
"""
from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ipsis.modelos.catalogo import ModeloSpec


class ModeloOnnx:
    def __init__(self, spec: ModeloSpec, carpeta: str | Path | None = None, hilos: int | None = None) -> None:
        self.spec = spec
        self._carpeta = Path(carpeta) if carpeta is not None else None
        self.hilos = hilos or int(os.environ.get("IPSIS_ONNX_THREADS", "0")) or None
        self._sesion = None
        self._tokenizador = None
        self._candado = threading.Lock()
        self._candado_tokenizador = threading.Lock()

    @property
    def carpeta(self) -> Path:
        if self._carpeta is None:
            from ipsis.modelos.descarga import ruta_local

            self._carpeta = ruta_local(self.spec)
        return self._carpeta

    @property
    def sesion(self):
        """Sesión de onnxruntime, creada una vez y compartida entre consultas."""
        if self._sesion is None:
            with self._candado:
                if self._sesion is None:
                    import onnxruntime as ort

                    opciones = ort.SessionOptions()
                    if self.hilos:
                        opciones.intra_op_num_threads = self.hilos
                    self._sesion = ort.InferenceSession(
                        str(self.carpeta / self.spec.archivo_onnx()),
                        sess_options=opciones,
                        providers=["CPUExecutionProvider"],
                    )
        return self._sesion

    @property
    def tokenizador(self):
        if self._tokenizador is None:
            from tokenizers import Tokenizer

            tokenizador = Tokenizer.from_file(str(self.carpeta / "tokenizer.json"))
            tokenizador.no_padding()
            tokenizador.no_truncation()
            self._tokenizador = tokenizador
        return self._tokenizador

    def tokenizar(self, textos: Sequence[str] | Sequence[tuple[str, str]], max_tokens: int | None = None):
        """Codificaciones con truncado y relleno al más largo del lote."""
        # Truncado/relleno son estado mutable del tokenizador compartido.
        with self._candado_tokenizador:
            return self._tokenizar(textos, max_tokens)

    def _tokenizar(self, textos, max_tokens):
        tokenizador = self.tokenizador
        tokenizador.enable_truncation(max_length=max_tokens or self.spec.max_tokens)
        id_relleno = self.spec.pad_token_id
        if id_relleno is None:
            id_relleno = tokenizador.token_to_id("<pad>") or tokenizador.token_to_id("[PAD]") or 0
        tokenizador.enable_padding(pad_id=id_relleno)
        try:
            return tokenizador.encode_batch(list(textos))
        finally:
            tokenizador.no_padding()
            tokenizador.no_truncation()

    def entradas(self, codificaciones) -> dict[str, Any]:
        """Tensores que espera la sesión: ids, máscara y, si los usa, tipos de token."""
        import numpy as np

        nombres = {e.name for e in self.sesion.get_inputs()}
        tensores = {
            "input_ids": np.array([c.ids for c in codificaciones], dtype=np.int64),
            "attention_mask": np.array([c.attention_mask for c in codificaciones], dtype=np.int64),
        }
        if "token_type_ids" in nombres:
            tensores["token_type_ids"] = np.array([c.type_ids for c in codificaciones], dtype=np.int64)
        for nombre, forma in self.spec.entradas_vacias.items():
            if nombre in nombres:
                tensores[nombre] = np.empty(forma, dtype=np.float32)
        return {nombre: valor for nombre, valor in tensores.items() if nombre in nombres}

    def ejecutar(self, codificaciones) -> list:
        return self.sesion.run(None, self.entradas(codificaciones))


__all__ = ["ModeloOnnx"]
