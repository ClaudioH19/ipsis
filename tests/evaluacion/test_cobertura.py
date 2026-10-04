"""Métricas de cobertura, falsos ok y cota de riesgo (P10.1). Funciones puras."""
from __future__ import annotations

import math

import pytest

from ipsis.evaluacion.banco import CasoEvaluacion, CategoriaPregunta, EvidenciaEsperada
from ipsis.evaluacion.metricas import (
    ObservacionEvaluacion,
    SenalesObservadas,
    cota_superior_clopper_pearson,
    n_minimo,
    reporte_cobertura,
)
from ipsis.nucleo.esquemas import EvidenceSpan

TEXTO = "La garantía dura 24 meses."


def _respondible(id_: str, categoria=CategoriaPregunta.EXACTA) -> CasoEvaluacion:
    return CasoEvaluacion(
        dataset_version="1", id=id_, split="dev", categoria=categoria, pregunta="¿Cuánto dura?",
        estado_esperado="respuesta_directa", respondible=True, respuesta_literal="24 meses",
        evidencias=[EvidenciaEsperada(doc_id="d", offset_inicio=0, offset_fin=len(TEXTO), texto=TEXTO)],
    )


def _no_respondible(id_: str, categoria=CategoriaPregunta.SIN_RESPUESTA, estado="sin_respuesta",
                    subtipo=None) -> CasoEvaluacion:
    return CasoEvaluacion(dataset_version="1", id=id_, split="dev", categoria=categoria, pregunta="¿Qué incluye?",
                          estado_esperado=estado, respondible=False, subtipo=subtipo)


def _obs(id_: str, estado: str, idioma="es", texto=TEXTO, senales=None) -> ObservacionEvaluacion:
    evidencias = [EvidenceSpan(doc_id="d", chunk_id="c", texto=texto, offset_inicio=0, offset_fin=len(texto))]
    return ObservacionEvaluacion(caso_id=id_, backend="b", estado=estado, respuesta=texto,
                                 evidencias=evidencias if estado != "sin_respuesta" else [],
                                 idioma=idioma, senales=senales)


# --- cobertura -----------------------------------------------------------------------
def test_cobertura_directa_6_de_10():
    pares = [(_respondible(f"r{i}"), _obs(f"r{i}", "respuesta_directa" if i < 6 else "relacionado"))
             for i in range(10)]
    total = reporte_cobertura(pares).total
    assert total.cobertura_directa == pytest.approx(0.6)
    # relacionado no es directa, pero tampoco una pérdida total: se cuenta aparte
    assert total.cobertura_relacionada == pytest.approx(0.4)
    assert total.abstenciones == 0


def test_exacta_y_parafrasis_se_separan():
    pares = [
        (_respondible("e1"), _obs("e1", "respuesta_directa")),
        (_respondible("e2"), _obs("e2", "respuesta_directa")),
        (_respondible("p1", CategoriaPregunta.PARAFRASIS), _obs("p1", "relacionado")),
    ]
    grupos = reporte_cobertura(pares).por_grupo
    assert grupos["exacta"].cobertura_directa == 1.0
    assert grupos["parafrasis"].cobertura_directa == 0.0
    assert grupos["parafrasis"].cobertura_relacionada == 1.0


def test_falsos_ok_en_cada_tipo_no_respondible():
    pares = [
        (_no_respondible("t1", subtipo="trampa_mismo_tema"), _obs("t1", "respuesta_directa")),
        (_no_respondible("f1", estado="fuera_dominio"), _obs("f1", "sin_respuesta")),
        (_no_respondible("pf", CategoriaPregunta.PREMISA_FALSA), _obs("pf", "respuesta_directa")),
        (_no_respondible("a1", CategoriaPregunta.AMBIGUA, "necesita_aclaracion"), _obs("a1", "relacionado")),
        (_no_respondible("c1", CategoriaPregunta.CONVERSACIONAL, "conversacional"), _obs("c1", "conversacional")),
    ]
    reporte = reporte_cobertura(pares)
    assert reporte.total.falsos_ok == 2
    assert reporte.total.no_respondibles == 4  # las conversacionales miden otra conducta
    assert reporte.total.tasa_falsos_ok_no_respondibles == pytest.approx(0.5)
    assert reporte.total.recall_sin_respuesta == pytest.approx(0.5)
    assert reporte.por_grupo["trampa_mismo_tema"].falsos_ok == 1
    assert reporte.por_grupo["fuera_de_dominio"].falsos_ok == 0
    assert reporte.por_grupo["premisa_falsa"].falsos_ok == 1
    assert {f.caso_id for f in reporte.casos if f.falso_ok} == {"t1", "pf"}


def test_directa_con_tramo_equivocado_es_otro_error():
    """Respondible contestada sin la respuesta literal: no es falso ok, pero
    cuenta como respuesta aceptada errónea."""
    pares = [(_respondible("r1"), _obs("r1", "respuesta_directa", texto="La garantía cubre el motor."))]
    reporte = reporte_cobertura(pares)
    assert reporte.total.falsos_ok == 0 and reporte.total.directas_sin_literal == 1
    assert (reporte.riesgo_aceptadas.x, reporte.riesgo_aceptadas.n) == (1, 1)


def test_por_idioma_no_mezcla_casos():
    pares = [
        (_respondible("es1"), _obs("es1", "respuesta_directa", "es")),
        (_respondible("en1"), _obs("en1", "relacionado", "en")),
        (_respondible("en2"), _obs("en2", "relacionado", "en")),
        (_no_respondible("pt1", subtipo="trampa_mismo_tema"), _obs("pt1", "respuesta_directa", "pt")),
    ]
    reporte = reporte_cobertura(pares)
    assert reporte.por_idioma["es"].cobertura_directa == 1.0
    assert reporte.por_idioma["en"].cobertura_directa == 0.0
    assert reporte.por_idioma["pt"].cobertura_directa is None  # sin respondibles: no se inventa un 0
    assert reporte.por_idioma_y_grupo["pt"]["trampa_mismo_tema"].falsos_ok == 1
    assert set(reporte.por_idioma_y_grupo["en"]) == {"exacta"}


def test_las_senales_no_disponibles_quedan_en_none():
    senales = SenalesObservadas.desde_diagnostico({
        "senales_politica": {"s_ret": 0.5, "s_oov": 0.1, "s_foco": 1.0, "s_cov": 1.0, "acuerdo": None,
                             "s_rr": None, "s_qa": None, "dominio": 0.5},
        "senales_lexicas": {},
    })
    assert (senales.s_rr, senales.s_qa, senales.acuerdo, senales.s_lex) == (None, None, None, None)
    assert SenalesObservadas.desde_diagnostico({"etapas": {}}) is None  # la política no decidió
    reporte = reporte_cobertura([(_respondible("r1"), _obs("r1", "respuesta_directa", senales=senales))])
    assert reporte.casos[0].senales.s_qa is None


def test_riesgo_usa_las_respuestas_aceptadas_como_denominador():
    pares = [(_respondible(f"r{i}"), _obs(f"r{i}", "respuesta_directa")) for i in range(3)]
    pares += [(_no_respondible(f"t{i}"), _obs(f"t{i}", "sin_respuesta")) for i in range(20)]
    pares += [(_no_respondible("t9", subtipo="trampa_mismo_tema"), _obs("t9", "respuesta_directa"))]
    riesgo = reporte_cobertura(pares).riesgo_aceptadas
    assert (riesgo.n, riesgo.x, riesgo.falsos_ok) == (4, 1, 1)  # n = 4 respuestas, no 24 casos
    assert riesgo.observado == pytest.approx(0.25)
    assert riesgo.cota_superior == pytest.approx(cota_superior_clopper_pearson(1, 4))
    sin_respuestas = reporte_cobertura([(_no_respondible("t1"), _obs("t1", "sin_respuesta"))]).riesgo_aceptadas
    assert sin_respuestas.n == 0 and sin_respuestas.cota_superior is None


# --- Clopper-Pearson -----------------------------------------------------------------
def test_clopper_pearson_x0_n50():
    assert cota_superior_clopper_pearson(0, 50, 0.95) == pytest.approx(0.0582, abs=0.001)
    # Forma cerrada con 0 errores: 1 − (1 − confianza)^(1/n)
    assert cota_superior_clopper_pearson(0, 50, 0.95) == pytest.approx(1 - 0.05 ** (1 / 50), abs=1e-9)


def test_clopper_pearson_contra_referencia_externa():
    """R, ``binom.test(1, 10)``: intervalo exacto (Clopper-Pearson) al 95%
    bilateral = [0.002528579, 0.445016117]. Su límite superior es la cota
    unilateral al 97,5%."""
    assert cota_superior_clopper_pearson(1, 10, 0.975) == pytest.approx(0.445016117, abs=1e-6)


@pytest.mark.parametrize(("x", "n", "confianza"), [(0, 0, 0.95), (-1, 5, 0.95), (2, -1, 0.95), (6, 5, 0.95),
                                                   (1, 5, 0.0), (1, 5, 1.0), (1, 5, 1.5)])
def test_clopper_pearson_rechaza_argumentos_invalidos(x, n, confianza):
    with pytest.raises(ValueError):
        cota_superior_clopper_pearson(x, n, confianza)


def test_clopper_pearson_bordes_y_monotonia():
    assert cota_superior_clopper_pearson(5, 5) == 1.0
    cotas_por_errores = [cota_superior_clopper_pearson(x, 30) for x in range(31)]
    assert all(0.0 <= c <= 1.0 for c in cotas_por_errores)
    assert cotas_por_errores == sorted(cotas_por_errores)  # más errores: cota no menor
    cotas_por_n = [cota_superior_clopper_pearson(0, n) for n in range(1, 200)]
    assert all(a > b for a, b in zip(cotas_por_n, cotas_por_n[1:]))  # más n: cota menor
    assert 0.2 < cota_superior_clopper_pearson(3, 20) < 0.4  # 0 < x < n, por encima de x/n
    with pytest.raises(TypeError):
        cota_superior_clopper_pearson(1.0, 10)


def test_n_minimo_sale_de_la_funcion_estadistica():
    n = n_minimo(0, alfa=0.05, confianza=0.95)
    assert cota_superior_clopper_pearson(0, n) <= 0.05 < cota_superior_clopper_pearson(0, n - 1)
    assert n == math.ceil(math.log(0.05) / math.log(0.95))  # 0 errores: forma cerrada
    assert n_minimo(2, alfa=0.05) > n  # con errores hace falta más muestra
