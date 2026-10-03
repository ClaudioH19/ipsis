"""Tests de metadata.py: clasificación de categoría, construcción de payload
y validaciones de ingesta (sección 3.4)."""
import copy

import pytest

from rag.ingesta.metadata import (
    cargar_taxonomia, clasificar_categoria, extraer_keywords, validar_chunk,
)


@pytest.fixture(scope="module")
def taxonomia(proyecto_suite):
    return cargar_taxonomia(str(proyecto_suite / "configuracion" / "dominio.yaml"))


def test_clasificar_categoria_contenido(taxonomia):
    texto = "El manual explica el mantenimiento periódico del equipo."
    res = clasificar_categoria(texto, taxonomia)
    assert res.categoria in {c["id"] for c in taxonomia["categorias"]}


def test_clasificar_categoria_siempre_pertenece_a_taxonomia(taxonomia):
    texto = "La garantía cubre el equipo durante 12 meses."
    res = clasificar_categoria(texto, taxonomia)
    assert res.categoria in {c["id"] for c in taxonomia["categorias"]}


def test_clasificar_categoria_texto_vacio_cae_en_otro(taxonomia):
    res = clasificar_categoria("", taxonomia)
    assert res.categoria == "otro"
    assert res.score == 0.0


def test_extraer_keywords_excluye_stopwords():
    kws = extraer_keywords("El estudiante debe entregar el portfolio antes del plazo establecido")
    assert "el" not in kws
    assert "del" not in kws
    assert len(kws) <= 5


def _payload_valido():
    texto = "El plazo es de 15 días hábiles."
    return {
        "chunk_id": "doc__c0001",
        "texto": texto,
        "entidades": [{"tipo": "plazo", "texto": "15 días hábiles", "valor_norm": "15_dia_habiles", "offset": 15}],
        "categoria": "contenido",
        "categoria_score": 0.5,
        "offset_inicio": 0,
        "offset_fin": len(texto),
        "hash_texto": None,  # se completa abajo
    }


def _con_hash(payload):
    import hashlib
    p = copy.deepcopy(payload)
    p["hash_texto"] = "sha256:" + hashlib.sha256(p["texto"].encode("utf-8")).hexdigest()
    return p


def test_validar_chunk_payload_valido_no_da_errores(taxonomia):
    p = _con_hash(_payload_valido())
    errores = validar_chunk(p, taxonomia)
    assert errores == []


def test_validar_chunk_detecta_offset_de_entidad_invalido(taxonomia):
    p = _con_hash(_payload_valido())
    p["entidades"][0]["offset"] = 999  # offset fuera de rango / no coincide
    errores = validar_chunk(p, taxonomia)
    assert any(e.campo == "entidades" for e in errores)


def test_validar_chunk_detecta_categoria_fuera_de_taxonomia(taxonomia):
    p = _con_hash(_payload_valido())
    p["categoria"] = "categoria_inventada"
    errores = validar_chunk(p, taxonomia)
    assert any(e.campo == "categoria" for e in errores)


def test_validar_chunk_detecta_hash_incorrecto(taxonomia):
    p = _con_hash(_payload_valido())
    p["hash_texto"] = "sha256:0000"
    errores = validar_chunk(p, taxonomia)
    assert any(e.campo == "hash_texto" for e in errores)


def test_validar_chunk_detecta_offsets_de_chunk_invertidos(taxonomia):
    p = _con_hash(_payload_valido())
    p["offset_inicio"], p["offset_fin"] = p["offset_fin"], p["offset_inicio"]
    errores = validar_chunk(p, taxonomia)
    assert any(e.campo == "offsets" for e in errores)
