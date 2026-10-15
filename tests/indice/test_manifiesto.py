"""Manifiesto del índice."""
from __future__ import annotations

import pytest

from ipsis.indice.manifiesto import (
    ManifiestoIndice,
    cargar_manifiesto,
    es_compatible,
    guardar_manifiesto,
    hash_corpus,
    inventario_entidades,
)

PAYLOADS = [
    {"hash_texto": "sha256:b", "entidades": [{"valor_norm": "articulo_8"}]},
    {"hash_texto": "sha256:a", "entidades": [{"valor_norm": "6_mes"}, {"valor_norm": "articulo_8"}]},
]


def _manifiesto(**cambios):
    datos = dict(coleccion="demo_v1", modelo_denso="intfloat/multilingual-e5-small", dimension=384,
                 stemmer="spanish", hash_corpus=hash_corpus(PAYLOADS), n_chunks=2,
                 inventario_entidades=inventario_entidades(PAYLOADS))
    datos.update(cambios)
    return ManifiestoIndice(**datos)


def test_huella_e_inventario_no_dependen_del_orden():
    assert hash_corpus(PAYLOADS) == hash_corpus(list(reversed(PAYLOADS)))
    assert inventario_entidades(PAYLOADS) == ["6_mes", "articulo_8"]


def test_guardar_y_cargar(tmp_path):
    manifiesto = _manifiesto()
    guardar_manifiesto(manifiesto, str(tmp_path))
    assert cargar_manifiesto("demo_v1", str(tmp_path)) == manifiesto


def test_sin_manifiesto_pide_reindexar(tmp_path):
    with pytest.raises(FileNotFoundError, match="ipsis index"):
        cargar_manifiesto("otro_v1", str(tmp_path))


def test_compatibilidad():
    manifiesto = _manifiesto()
    assert es_compatible(manifiesto, "intfloat/multilingual-e5-small")
    assert es_compatible(manifiesto, "intfloat/multilingual-e5-small", "spanish")
    assert not es_compatible(manifiesto, "intfloat/multilingual-e5-base")
    assert not es_compatible(manifiesto, "intfloat/multilingual-e5-small", "english")


def _p(texto, embebido=None):
    import hashlib

    p = {"hash_texto": "sha256:" + hashlib.sha256(texto.encode()).hexdigest(), "texto": texto}
    if embebido is not None:
        p["texto_embebido"] = embebido
    return p


def test_sin_cabecera_la_huella_no_cambia_con_texto_embebido_igual_al_texto():
    # Misma huella que antes de incluir el texto embebido: las calibraciones existentes siguen valiendo.
    antiguo = [{"hash_texto": p["hash_texto"]} for p in (_p("uno"), _p("dos"))]
    nuevo = [_p("uno", "uno"), _p("dos", "dos")]
    assert hash_corpus(nuevo) == hash_corpus(antiguo) == hash_corpus([_p("uno"), _p("dos")])


def test_activar_la_cabecera_cambia_la_huella():
    sin = [_p("uno", "uno"), _p("dos", "dos")]
    con = [_p("uno", "Documento: D | Sección: S\nuno"), _p("dos", "Documento: D | Sección: S\ndos")]
    assert hash_corpus(con) != hash_corpus(sin)


def test_cambiar_la_cabecera_cambia_la_huella():
    a = [_p("uno", "Documento: D | Sección: S\nuno")]
    b = [_p("uno", "Documento: D | Sección: S\nContiene: plazo\nuno")]
    assert hash_corpus(a) != hash_corpus(b)
    assert hash_corpus(a) == hash_corpus([_p("uno", "Documento: D | Sección: S\nuno")])
