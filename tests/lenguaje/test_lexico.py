"""BM25 y TF-IDF con un corpus de tres documentos y valores calculados a mano."""
from __future__ import annotations

import math

import pytest

from ipsis.indice.estadisticas import EstadisticasLexicas
from ipsis.lenguaje.lexico import (
    bm25_consulta,
    bm25_doc,
    bm25_puntaje,
    coseno,
    id_termino,
    mmr,
    tfidf_vector,
)
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.texto import terminos

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
    ruta = tmp_path / "stats.json"
    est.guardar(ruta)
    assert EstadisticasLexicas.cargar(ruta) == est
    assert not (tmp_path / "stats.json.tmp").exists()


# ---------------------------------------------------------------------------
# Señales léxicas sobre el corpus sintético
# ---------------------------------------------------------------------------
from apoyo import CORPUS
from ipsis.lenguaje.lexico import acuerdo, s_cov, s_foco, s_lex, s_oov, terminos_contenido, terminos_foco


@pytest.fixture(scope="module")
def corpus():
    es = cargar_paquete("es")
    textos = [p.read_text(encoding="utf-8") for p in sorted(CORPUS.glob("*.md"))]
    stop = set(terminos(" ".join(es.stopwords), es))
    return es, EstadisticasLexicas.construir(textos, es), stop


def _tq(corpus, pregunta):
    es, _est, stop = corpus
    return terminos_contenido(terminos(pregunta, es), stop)


ORACION_FILTRO = "El filtro de sedimentos se cambia cada 6 meses."
ORACION_GARANTIA = "La garantía cubre 24 meses desde la fecha de compra."


def test_foco_detecta_el_pasaje_que_se_parece_pero_no_responde(corpus):
    es, est, _ = corpus
    tq = _tq(corpus, "¿Cuánto dura la garantía?")
    foco = terminos_foco(tq, est)
    assert terminos("garantía", es)[0] in foco
    assert s_foco(foco, terminos(ORACION_FILTRO, es)) == 0
    assert s_foco(foco, terminos(ORACION_GARANTIA, es)) >= 0.5


def test_s_oov_alto_para_preguntas_ajenas_al_dominio(corpus):
    _es, est, _ = corpus
    assert s_oov(_tq(corpus, "¿Cómo se prepara un asado?"), est) > 0.6
    assert s_oov(_tq(corpus, "¿Cada cuánto se cambia el filtro?"), est) == 0


def test_s_cov_y_s_lex_ordenan_las_oraciones(corpus):
    es, est, _ = corpus
    tq = _tq(corpus, "¿Cada cuánto se cambia el filtro de sedimentos?")
    assert s_cov(tq, terminos(ORACION_FILTRO, es), est) == pytest.approx(1.0)
    assert s_cov(tq, terminos(ORACION_GARANTIA, es), est) == 0
    assert 0 < s_lex(tq, terminos(ORACION_FILTRO, es), est) <= 1
    assert s_lex(tq, terminos(ORACION_GARANTIA, es), est) == 0


def test_acuerdo_entre_rankings():
    assert acuerdo(["a", "b"], ["a", "c"]) == 1.0
    assert acuerdo(["a", "c"], ["c", "a"]) == 1.0
    assert acuerdo(["a", "b", "c"], ["d", "e", "a"]) == 0.5
    assert acuerdo(["a"], ["z"]) == 0.0
    assert acuerdo([], ["z"]) == 0.0
