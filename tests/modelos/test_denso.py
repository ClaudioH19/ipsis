"""Codificador denso ONNX (requiere el modelo en caché)."""
from __future__ import annotations

import numpy as np
import pytest

E5 = "intfloat/multilingual-e5-small"
pytestmark = pytest.mark.modelos(E5)


@pytest.fixture(scope="module")
def codificador():
    from rag.modelos.catalogo import obtener
    from rag.modelos.denso import CodificadorDenso

    return CodificadorDenso(obtener(E5))


def test_vectores_de_384_normalizados(codificador):
    vectores = codificador.codificar_documentos(["uno", "dos frases distintas"])
    assert vectores.shape == (2, 384)
    assert np.allclose(np.linalg.norm(vectores, axis=1), 1.0, atol=1e-3)


def test_parafrasis_mas_cercana_que_texto_no_relacionado(codificador):
    q = codificador.codificar_consultas(["¿Cada cuánto se reemplaza el filtro?"])[0]
    docs = codificador.codificar_documentos([
        "El filtro de sedimentos se cambia cada 6 meses.",
        "La factura se envía por correo electrónico.",
    ])
    assert q @ docs[0] > q @ docs[1]


def test_registro_construye_el_codificador_onnx():
    from rag.aplicacion.registro_base import registrar_componentes_base

    codificador = registrar_componentes_base().crear("dense_encoder", "onnx", modelo=E5)
    assert codificador.dimension == 384
