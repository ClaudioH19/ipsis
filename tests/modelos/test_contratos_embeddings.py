"""Contratos de pooling/ONNX que pueden corromper silenciosamente la recuperación."""
from types import SimpleNamespace

import numpy as np
import pytest

from ipsis.modelos.catalogo import ModeloSpec
from ipsis.modelos.denso import CodificadorDenso
from ipsis.modelos.onnx import ModeloOnnx


def spec(**kw):
    return ModeloSpec(id_hf="test/encoder", tarea="denso", licencia="MIT", parametros=1,
                      archivos_onnx={"*": "model.onnx"}, dimension=2, **kw)


def modelo(pooling, salidas, mascara, nombres=None):
    m = CodificadorDenso(spec(pooling=pooling, salida="sentence_embedding" if nombres else None))
    m.tokenizar = lambda textos: [SimpleNamespace(attention_mask=fila) for fila in mascara]
    m.ejecutar = lambda cod: salidas
    if nombres:
        m._sesion = SimpleNamespace(get_outputs=lambda: [SimpleNamespace(name=n) for n in nombres])
    return m


def test_media_excluye_padding_y_cls_no_promedia():
    estados = np.array([[[3., 0.], [0., 4.], [100., 100.]]])
    media = modelo("mean", [estados], [[1, 1, 0]]).codificar_consultas(["q"])
    cls = modelo("cls", [estados], [[1, 1, 0]]).codificar_consultas(["q"])
    assert np.allclose(media, [[0.6, 0.8]])
    assert np.allclose(cls, [[1., 0.]])


def test_ultimo_token_funciona_con_padding_izquierdo_y_derecho():
    estados = np.array([[[3., 0.], [0., 4.], [9., 9.]],
                        [[9., 9.], [3., 0.], [0., 4.]]])
    m = modelo("last_token", [estados], [[1, 1, 0], [0, 1, 1]])
    assert np.allclose(m.codificar_documentos(["a", "b"]), [[0., 1.], [0., 1.]])


def test_salida_agrupada_se_selecciona_por_nombre_y_no_se_promedia():
    m = modelo("sentence", [np.zeros((1, 3, 2)), np.array([[3., 4.]])], [[1, 1, 0]],
               ["last_hidden_state", "sentence_embedding"])
    assert np.allclose(m.codificar_documentos(["a"]), [[0.6, 0.8]])


@pytest.mark.parametrize("vector", [np.zeros((1, 2)), np.array([[float("nan"), 1.]]), np.ones((1, 3))])
def test_salida_corrupta_no_se_indexa(vector):
    with pytest.raises(ValueError):
        modelo("sentence", [vector], [[1]]).codificar_documentos(["a"])


def test_entradas_multimodales_vacias_tienen_forma_y_dtype_correctos():
    m = ModeloOnnx(spec(entradas_vacias={"image_features": (0, 512)}))
    m._sesion = SimpleNamespace(get_inputs=lambda: [SimpleNamespace(name=n)
                        for n in ("input_ids", "attention_mask", "image_features")])
    entradas = m.entradas([SimpleNamespace(ids=[1, 2], attention_mask=[1, 1])])
    assert entradas["image_features"].shape == (0, 512)
    assert entradas["image_features"].dtype == np.float32
    assert entradas["input_ids"].dtype == np.int64


def test_padding_respeta_el_vocabulario_del_modelo():
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace

    tok = Tokenizer(WordLevel({"[UNK]": 0, "uno": 1, "dos": 2, "[PAD]": 3}, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    m = ModeloOnnx(spec(pad_token_id=3))
    m._tokenizador = tok
    cod = m.tokenizar(["uno", "uno dos"])
    assert cod[0].ids == [1, 3]
    assert cod[0].attention_mask == [1, 0]
