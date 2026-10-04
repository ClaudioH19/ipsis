"""Lector QA: lógica con una sesión ONNX falsa y comportamiento con el modelo real."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest

from ipsis.modelos.catalogo import obtener
from ipsis.modelos.lector import LectorOnnx

LECTOR = "dewdev/mdeberta-v3-base-squad2-onnx"
PASAJE = "El filtro se cambia cada 6 meses."


@dataclass
class _Ventana:
    """Imita un Encoding de tokenizers: [CLS] pregunta [SEP] pasaje [SEP]."""

    offsets: list
    sequence_ids: list
    ids: list = field(default_factory=list)
    attention_mask: list = field(default_factory=list)
    type_ids: list = field(default_factory=list)

    def __post_init__(self):
        self.ids = list(range(len(self.offsets)))
        self.attention_mask = [1] * len(self.offsets)
        self.type_ids = [0] * len(self.offsets)


def _ventana_pasaje() -> _Ventana:
    # Tokens del pasaje: «El» «filtro» «se» «cambia» «cada» «6» «meses» «.»
    palabras = [(0, 2), (2, 9), (9, 12), (12, 19), (19, 24), (24, 26), (26, 32), (32, 33)]
    return _Ventana(offsets=[(0, 0), (0, 5), (0, 0)] + palabras + [(0, 0)],
                    sequence_ids=[None, 0, None] + [1] * len(palabras) + [None])


class _Entrada:
    def __init__(self, nombre):
        self.name = nombre


class _SesionFalsa:
    def __init__(self, inicio, fin):
        self.inicio, self.fin = np.array([inicio], dtype=np.float32), np.array([fin], dtype=np.float32)

    def get_inputs(self):
        return [_Entrada("input_ids"), _Entrada("attention_mask")]

    def run(self, _salidas, _entradas):
        return [self.inicio, self.fin]


def _lector(inicio, fin, ventanas=None) -> LectorOnnx:
    lector = LectorOnnx(obtener(LECTOR), carpeta=".")
    lector._sesion = _SesionFalsa(inicio, fin)
    lector._ventanas = lambda _p, _q: ventanas or [_ventana_pasaje()]
    return lector


def _logits(pos_inicio, pos_fin, nulo=0.0, n=12):
    inicio = np.full(n, -5.0)
    fin = np.full(n, -5.0)
    inicio[0], fin[0] = nulo, nulo
    inicio[pos_inicio], fin[pos_fin] = 6.0, 6.0
    return inicio, fin


def test_tramo_correcto_con_offsets_literales():
    inicio, fin = _logits(8, 9)  # «6» «meses»
    lectura = _lector(inicio, fin).leer("¿Cada cuánto?", [PASAJE])[0]
    assert lectura.texto == "6 meses" and PASAJE[lectura.inicio:lectura.fin] == "6 meses"
    assert lectura.s_qa > 0.9


def test_gana_sin_respuesta():
    inicio, fin = _logits(8, 9, nulo=20.0)
    lectura = _lector(inicio, fin).leer("¿Cuánto cuesta?", [PASAJE])[0]
    assert lectura.prob_sin_respuesta > 0.9 and lectura.s_qa == 0.0


def test_tramo_invertido_no_se_elige():
    inicio = np.full(12, -5.0)
    fin = np.full(12, -5.0)
    inicio[9], fin[4] = 6.0, 6.0  # el mejor inicio está después del mejor fin
    fin[9] = 1.0
    lectura = _lector(inicio, fin).leer("¿?", [PASAJE])[0]
    assert lectura.inicio <= lectura.fin and lectura.texto == PASAJE[lectura.inicio:lectura.fin]


@pytest.mark.modelos(LECTOR)
@pytest.mark.parametrize(("pregunta", "pasaje", "esperado"), [
    ("¿Cada cuánto se cambia el filtro de sedimentos?",
     "El filtro de sedimentos se cambia cada 6 meses. El de carbón, cada 12 meses.", "6 meses"),
    ("How long is the warranty?", "La garantía cubre 24 meses desde la fecha de compra.", "24 meses"),
])
def test_modelo_real_responde(pregunta, pasaje, esperado):
    lectura = LectorOnnx(obtener(LECTOR)).leer(pregunta, [pasaje])[0]
    assert esperado in lectura.texto and lectura.s_qa > 0.5


@pytest.mark.modelos(LECTOR)
def test_modelo_real_se_abstiene_con_un_pasaje_que_se_parece_pero_no_responde():
    filtro = "El filtro de sedimentos se cambia cada 6 meses."
    lectura = LectorOnnx(obtener(LECTOR)).leer("¿Cuánto dura la garantía?", [filtro])[0]
    assert lectura.s_qa < 0.2
