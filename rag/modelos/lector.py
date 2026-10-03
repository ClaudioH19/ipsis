"""Lector QA extractivo sobre ONNX (estilo SQuAD 2.0).

Para cada pasaje busca el tramo literal que mejor responde la pregunta y lo
compara con la opción «sin respuesta» (el token inicial ``[CLS]``). Un pasaje
largo se lee en ventanas con solapamiento; gana la ventana con mayor
probabilidad de respuesta.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from rag.modelos.onnx import ModeloOnnx
from rag.nucleo.esquemas import LecturaQA


class LectorOnnx(ModeloOnnx):
    def __init__(self, *args, max_tokens_pasaje: int = 384, stride: int = 128,
                 max_tokens_respuesta: int = 30, candidatos_por_borde: int = 20, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.max_tokens_pasaje = max_tokens_pasaje
        self.stride = stride
        self.max_tokens_respuesta = max_tokens_respuesta
        self.candidatos_por_borde = candidatos_por_borde

    def _ventanas(self, pregunta: str, pasaje: str) -> list:
        tokenizador = self.tokenizador
        tokenizador.enable_truncation(max_length=self.max_tokens_pasaje, stride=self.stride, strategy="only_second")
        try:
            principal = tokenizador.encode(pregunta, pasaje)
        finally:
            tokenizador.no_truncation()
        return [principal, *principal.overflowing]

    def _mejor_tramo(self, inicio, fin, ventana) -> tuple[float, int, int] | None:
        """(puntaje, token_inicio, token_fin) del mejor tramo dentro del pasaje."""
        import numpy as np

        validos = [i for i, s in enumerate(ventana.sequence_ids) if s == 1]
        if not validos:
            return None
        validos_arr = np.array(validos)
        k = self.candidatos_por_borde
        mejores_inicio = validos_arr[np.argsort(inicio[validos_arr])[::-1][:k]]
        mejores_fin = validos_arr[np.argsort(fin[validos_arr])[::-1][:k]]
        mejor = None
        for i in mejores_inicio:
            for j in mejores_fin:
                if j < i or j - i + 1 > self.max_tokens_respuesta:
                    continue
                puntaje = float(inicio[i] + fin[j])
                if mejor is None or puntaje > mejor[0]:
                    mejor = (puntaje, int(i), int(j))
        return mejor

    def leer(self, pregunta: str, pasajes: Sequence[str]) -> list[LecturaQA]:
        import numpy as np

        lecturas: list[LecturaQA] = []
        for indice, pasaje in enumerate(pasajes):
            ventanas = self._ventanas(pregunta, pasaje)
            largo = max(len(v.ids) for v in ventanas)
            ids = np.zeros((len(ventanas), largo), dtype=np.int64)
            mascara = np.zeros((len(ventanas), largo), dtype=np.int64)
            for fila, v in enumerate(ventanas):
                ids[fila, :len(v.ids)] = v.ids
                mascara[fila, :len(v.ids)] = v.attention_mask
            entradas = {"input_ids": ids, "attention_mask": mascara}
            nombres = {e.name for e in self.sesion.get_inputs()}
            if "token_type_ids" in nombres:
                tipos = np.zeros_like(ids)
                for fila, v in enumerate(ventanas):
                    tipos[fila, :len(v.type_ids)] = v.type_ids
                entradas["token_type_ids"] = tipos
            inicio_logits, fin_logits = self.sesion.run(None, entradas)[:2]

            mejor_lectura = None
            for fila, v in enumerate(ventanas):
                tramo = self._mejor_tramo(inicio_logits[fila], fin_logits[fila], v)
                nulo = float(inicio_logits[fila][0] + fin_logits[fila][0])
                if tramo is None:
                    continue
                puntaje, ti, tj = tramo
                # softmax sobre {mejor tramo, sin respuesta}
                maximo = max(puntaje, nulo)
                e_resp, e_nulo = math.exp(puntaje - maximo), math.exp(nulo - maximo)
                prob = e_resp / (e_resp + e_nulo)
                ini, fin = v.offsets[ti][0], v.offsets[tj][1]
                texto = pasaje[ini:fin]
                recorte = len(texto) - len(texto.lstrip())
                ini += recorte
                fin = ini + len(texto.strip())
                candidata = LecturaQA(
                    indice_pasaje=indice, inicio=ini, fin=fin, texto=pasaje[ini:fin],
                    prob_respuesta=prob, prob_sin_respuesta=1.0 - prob,
                )
                if mejor_lectura is None or candidata.prob_respuesta > mejor_lectura.prob_respuesta:
                    mejor_lectura = candidata
            if mejor_lectura is None:
                mejor_lectura = LecturaQA(indice_pasaje=indice, inicio=0, fin=0, texto="",
                                          prob_respuesta=0.0, prob_sin_respuesta=1.0)
            assert pasaje[mejor_lectura.inicio:mejor_lectura.fin] == mejor_lectura.texto
            lecturas.append(mejor_lectura)
        return lecturas

    def calentar(self) -> None:
        self.leer("¿Qué?", ["Texto de calentamiento."])


__all__ = ["LectorOnnx"]
