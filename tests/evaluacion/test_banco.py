from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from apoyo import BANCO_SINTETICO, CORPUS, RAIZ_REPO
from rag.evaluacion.banco import (
    CasoEvaluacion,
    CategoriaPregunta,
    cargar_banco,
    hash_banco,
    validar_evidencias_contra_corpus,
)
from rag.ingesta.parsear import parsear_markdown

MANIFIESTO = BANCO_SINTETICO


def _documentos() -> dict[str, str]:
    salida = {}
    for ruta in CORPUS.glob("*.md"):
        doc_id = ruta.stem.replace("_", "-")
        documento = parsear_markdown(
            str(ruta),
            doc_id=doc_id,
            doc_titulo=doc_id,
            version="1",
        )
        salida[doc_id] = documento.texto_completo
    return salida


def test_banco_sintetico_es_versionado_balanceado_y_reproducible():
    banco = cargar_banco(MANIFIESTO)

    assert banco.manifiesto.dataset_version == "1.1.0"
    assert banco.manifiesto.tipo == "sintetico"
    assert len(banco.casos) == 27
    assert len(hash_banco(banco)) == 64
    assert {caso.categoria for caso in banco.casos} == set(CategoriaPregunta)
    for categoria in CategoriaPregunta:
        assert {caso.split for caso in banco.casos if caso.categoria == categoria} == {
            "dev",
            "test",
        }


def test_hash_banco_cambia_si_cambia_un_caso():
    banco = cargar_banco(MANIFIESTO)
    copia = banco.model_copy(deep=True)
    copia.casos[0].pregunta += " detalle"

    assert hash_banco(copia) != hash_banco(banco)


def test_evidencias_del_banco_reconstruyen_el_corpus_literalmente():
    banco = cargar_banco(MANIFIESTO)

    validar_evidencias_contra_corpus(banco, _documentos())


def test_pregunta_respondible_exige_respuesta_y_offsets():
    with pytest.raises(ValidationError, match="respuesta literal y evidencia"):
        CasoEvaluacion(
            dataset_version="1.0.0",
            id="caso_invalido",
            split="dev",
            categoria="exacta",
            pregunta="¿Cuál es el dato?",
            estado_esperado="respuesta_directa",
            respondible=True,
        )


def test_pregunta_no_respondible_no_admite_evidencia_inventada():
    with pytest.raises(ValidationError, match="no debe declarar evidencia"):
        CasoEvaluacion(
            dataset_version="1.0.0",
            id="caso_invalido",
            split="test",
            categoria="premisa_falsa",
            pregunta="¿Qué dice el artículo inexistente?",
            estado_esperado="sin_respuesta",
            respondible=False,
            respuesta_literal="texto inventado",
        )


def test_loader_rechaza_version_de_caso_distinta(tmp_path):
    original = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    original["casos"] = "casos.jsonl"
    original["corpus"]["directorio"] = str(CORPUS.resolve())
    manifiesto = tmp_path / "manifiesto.json"
    manifiesto.write_text(json.dumps(original), encoding="utf-8")
    caso = json.loads(
        (MANIFIESTO.parent / "banco_v1.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    caso["dataset_version"] = "2.0.0"
    (tmp_path / "casos.jsonl").write_text(json.dumps(caso), encoding="utf-8")

    with pytest.raises(ValueError, match="versión de un caso"):
        cargar_banco(manifiesto)


def test_el_repositorio_documenta_el_golden_pero_no_incluye_uno():
    assert (RAIZ_REPO / "docs" / "guia" / "golden.md").is_file()
    assert not (RAIZ_REPO / "golden").exists()
    assert not (RAIZ_REPO / "data").exists()
