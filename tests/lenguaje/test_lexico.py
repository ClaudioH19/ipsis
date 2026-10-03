"""BM25 y TF-IDF con un corpus de tres documentos y valores calculados a mano."""
from __future__ import annotations

import math

import pytest

from rag.indice.estadisticas import EstadisticasLexicas
from rag.lenguaje.lexico import (
    bm25_consulta,
    bm25_doc,
    bm25_puntaje,
    coseno,
    id_termino,
    mmr,
    tfidf_vector,
)
from rag.lenguaje.paquete import cargar_paquete
from rag.lenguaje.texto import terminos

DOCS = ["El filtro se cambia", "El filtro de carbón", "La garantía dura un año"]


@pytest.fixture()
def est() -> EstadisticasLexicas:
    return EstadisticasLexicas.construir(DOCS)


def test_estadisticas_basicas(est):
    assert est.n_chunks == 3
    assert est.largo_medio == pytest.approx(13 / 3)
    assert est.df["filtro"] == 2 and est.df["garantia"] == 1


def test_idf_de_bm25(est):
    assert est.idf("filtro") == pytest.approx(math.log(1.6))
    assert est.idf("garantia") == pytest.approx(math.log(1 + 2.5 / 1.5))
    assert est.idf("inexistente") == pytest.approx(math.log(8))  # df = 0: máximo


def test_superficie_conserva_tildes():
    est = EstadisticasLexicas.construir(DOCS, cargar_paquete("es"))
    termino = terminos("garantía", cargar_paquete("es"))[0]
    assert est.superficie[termino] == "garantía"


def test_bm25_doc_satura_y_normaliza_por_largo(est):
    esperado = 2.2 / (1 + 1.2 * (0.25 + 0.75 * 4 / (13 / 3)))
    assert bm25_doc(terminos(DOCS[0]), est)[id_termino("filtro")] == pytest.approx(esperado)
    uno = bm25_doc(["filtro", "x", "y"], est)[id_termino("filtro")]
    tres = bm25_doc(["filtro", "filtro", "filtro"], est)[id_termino("filtro")]
    assert uno < tres < 3 * uno  # más ocurrencias suman, pero saturan


def test_bm25_puntaje_y_consulta(est):
    q = terminos("¿filtro o garantía?")
    esperado = math.log(1.6) * 2.2 / (1 + 1.2 * (0.25 + 0.75 * 4 / (13 / 3)))
    assert bm25_puntaje(q, terminos(DOCS[0]), est) == pytest.approx(esperado)
    assert bm25_puntaje(q, terminos(DOCS[2]), est) > bm25_puntaje(q, terminos(DOCS[0]), est)
    assert set(bm25_consulta(q).values()) == {1.0}


def test_tfidf_y_coseno(est):
    a = tfidf_vector(terminos(DOCS[0]), est)
    b = tfidf_vector(terminos(DOCS[1]), est)
    c = tfidf_vector(terminos(DOCS[2]), est)
    assert sum(v * v for v in a.values()) == pytest.approx(1.0)
    assert coseno(a, a) == pytest.approx(1.0)
    assert coseno(a, b) > coseno(a, c) == 0.0


def test_mmr_elige_diversos(est):
    vectores = [tfidf_vector(terminos(t), est) for t in DOCS + ["El filtro se cambia pronto"]]
    elegidos = mmr(vectores, 2, lambda_=0.3)
    assert len(elegidos) == 2
    assert 2 in elegidos  # el documento de garantía aporta diversidad


def test_guardar_y_cargar(tmp_path, est):
    ruta = tmp_path / "estadisticas.json"
    est.guardar(ruta)
    assert EstadisticasLexicas.cargar(ruta) == est
    assert not (tmp_path / "estadisticas.json.tmp").exists()
