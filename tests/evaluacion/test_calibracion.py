"""Calibración con control de riesgo (P10.2): bancos sintéticos, sin modelos."""
from __future__ import annotations

from pathlib import Path

import pytest

from rag.configuracion.calibracion import EstadoCalibracion, ProcedenciaCalibracion, umbrales_aplicables
from rag.consulta.etapas.politica import CascadaV1
from rag.evaluacion.banco import (
    ArchivoCorpus,
    BancoEvaluacion,
    CasoEvaluacion,
    CategoriaPregunta,
    CorpusBanco,
    EvidenciaEsperada,
    ManifiestoBanco,
    cargar_banco,
)
from rag.evaluacion.calibracion import calibrar, escribir_calibracion, redecidir
from rag.evaluacion.metricas import ObservacionEvaluacion, SenalesObservadas
from rag.nucleo.esquemas import EvidenceSpan

BASE = {"oov_dominio": 0.6, "oov_ok": 0.6, "dominio": 0.33, "relacionado": 0.33, "foco": 0.5, "ok": 0.8, "cov": 0.6}
TEXTO = "La garantía dura 24 meses."


def _caso(id_, split, respondible, categoria=None, subtipo=None, estado=None):
    if respondible:
        return CasoEvaluacion(
            dataset_version="1", id=id_, split=split, categoria=categoria or CategoriaPregunta.EXACTA,
            pregunta="¿Cuánto dura?", estado_esperado="respuesta_directa", respondible=True,
            respuesta_literal="24 meses",
            evidencias=[EvidenciaEsperada(doc_id="d", offset_inicio=0, offset_fin=len(TEXTO), texto=TEXTO)])
    return CasoEvaluacion(dataset_version="1", id=id_, split=split, categoria=categoria or CategoriaPregunta.SIN_RESPUESTA,
                          pregunta="¿Qué incluye?", estado_esperado=estado or "sin_respuesta", respondible=False,
                          subtipo=subtipo)


def _obs(id_, *, s_qa=None, s_ret=0.9, s_oov=0.0, s_foco=1.0, s_cov=1.0, regla=None):
    senales = SenalesObservadas(s_ret=s_ret, s_oov=s_oov, s_foco=s_foco, s_cov=s_cov, s_qa=s_qa, s_rr=None,
                                dominio=s_ret)
    return ObservacionEvaluacion(
        caso_id=id_, backend="b", estado="relacionado", respuesta=TEXTO, regla=regla or "relacionado",
        evidencias=[EvidenceSpan(doc_id="d", chunk_id="c", texto=TEXTO, offset_inicio=0, offset_fin=len(TEXTO))],
        senales=senales)


def _banco(casos, uso="evaluacion"):
    manifiesto = ManifiestoBanco(
        dataset_id="golden", dataset_version="1", tipo="manual", estado="estable", casos="golden.jsonl",
        corpus=CorpusBanco(directorio=".", archivos=[ArchivoCorpus(ruta="d.md", doc_id="d")], sha256="0" * 64),
        categorias_requeridas=[], uso=uso)
    return BancoEvaluacion(manifiesto=manifiesto, casos=casos)


def _escenario(respondibles: list[float], trampas: list[float], split="dev", prefijo=""):
    """Respondibles correctas y trampas (mismo tema) con sus ``s_qa``."""
    casos, obs = [], []
    for i, qa in enumerate(respondibles):
        casos.append(_caso(f"{prefijo}r{i}", split, True))
        obs.append(_obs(f"{prefijo}r{i}", s_qa=qa))
    for i, qa in enumerate(trampas):
        casos.append(_caso(f"{prefijo}t{i}", split, False, subtipo="trampa_mismo_tema"))
        obs.append(_obs(f"{prefijo}t{i}", s_qa=qa))
    return casos, obs


# --- la simulación es la política de producción ----------------------------------------
@pytest.fixture
def ctx_de_cascada():
    import importlib.util

    ruta = Path(__file__).resolve().parents[1] / "consulta" / "test_cascada.py"
    spec = importlib.util.spec_from_file_location("test_cascada_apoyo", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo._ctx


@pytest.mark.parametrize("senales", [
    {"s_qa": 0.9}, {"s_qa": 0.79}, {"s_qa": 0.9, "s_foco": 0.49}, {"s_oov": 0.9, "s_ret": 0.1},
    {"s_ret": 0.9}, {"s_ret": 0.79}, {"s_cov": 0.59}, {"s_ret": 0.2, "s_cov": 0.0}, {"s_oov": 0.6, "s_qa": 0.95},
    {"pregunta": "¿Qué dice el artículo 99?", "s_qa": 0.95},
])
def test_redecidir_reproduce_cada_decision_de_produccion(ctx_de_cascada, senales):
    """Antes y después del refactor: mismas señales y umbrales → misma regla."""
    ctx = ctx_de_cascada(**senales)
    decision = CascadaV1(umbrales=BASE).decidir_contexto(ctx)
    diagnostico = {"senales_politica": ctx.diagnostico["senales_politica"], "senales_lexicas": {}}
    obs = ObservacionEvaluacion(caso_id="x", backend="b", estado="?", regla=decision.capa_decisora,
                                senales=SenalesObservadas.desde_diagnostico(diagnostico))
    assert redecidir(obs, BASE).regla == decision.capa_decisora


def test_redecidir_conserva_premisa_concordancia_y_casos_sin_senales():
    assert redecidir(_obs("p", s_qa=0.99, regla="premisa"), BASE).estado == "sin_respuesta"
    assert redecidir(_obs("c", s_qa=0.99, regla="concordancia"), BASE).estado == "relacionado"
    sin = ObservacionEvaluacion(caso_id="h", backend="b", estado="conversacional")
    assert redecidir(sin, BASE) == sin


# --- estados ------------------------------------------------------------------------
def test_elige_el_umbral_mas_permisivo_que_cumple():
    # 70 correctas con s_qa 0,71…0,99; 10 trampas en 0,70; 5 correctas en 0,60.
    respondibles = [0.71 + i * 0.004 for i in range(70)] + [0.60] * 5
    casos, obs = _escenario(respondibles, [0.70] * 10)
    resultado = calibrar(_banco(casos), obs, BASE)
    assert resultado.estado == EstadoCalibracion.CALIBRADO
    assert resultado.umbrales["ok"] == pytest.approx(0.71)  # más bajo sin dejar entrar trampas
    assert resultado.dev.riesgo.n == 70 and resultado.dev.riesgo.x == 0
    assert resultado.dev.riesgo.cota_superior <= 0.05
    assert resultado.dev.falsos_ok_trampas == 0
    assert resultado.dev.cobertura_directa == pytest.approx(70 / 75)


def test_ante_empate_conserva_el_valor_del_perfil():
    """P10.3: con todos los s_oov en 0 y s_foco en 1, dev no distingue oov_ok ni foco;
    antes el desempate «más estricto» los llevaba a ~0 y a 1,0 sin evidencia."""
    respondibles = [0.71 + i * 0.004 for i in range(70)] + [0.60] * 5
    casos, obs = _escenario(respondibles, [0.70] * 10)
    resultado = calibrar(_banco(casos), obs, BASE)
    assert resultado.umbrales["oov_ok"] == BASE["oov_ok"] and resultado.umbrales["foco"] == BASE["foco"]
    assert resultado.umbrales["ok"] == pytest.approx(0.71)  # ok sí lo mueve la evidencia


def test_sin_umbral_seguro_si_las_trampas_puntuan_mas_alto():
    casos, obs = _escenario([0.80 + i * 0.002 for i in range(70)], [0.99] * 10)
    resultado = calibrar(_banco(casos), obs, BASE)
    assert resultado.estado == EstadoCalibracion.SIN_UMBRAL_SEGURO
    assert resultado.umbrales == resultado.umbrales_perfil  # no se aplica nada «certificado»
    assert resultado.aceptadas_max_dev >= resultado.n_minimo_sin_errores


def test_muestra_insuficiente_no_es_inseguro():
    casos, obs = _escenario([0.9] * 37, [0.5] * 10)
    resultado = calibrar(_banco(casos), obs, BASE)
    assert resultado.estado == EstadoCalibracion.MUESTRA_INSUFICIENTE
    assert resultado.dev.riesgo.x == 0  # sin errores…
    assert resultado.aceptadas_sin_error_max_dev == 37
    assert resultado.faltan_aceptadas == resultado.n_minimo_sin_errores - 37  # …pero faltan observaciones
    assert resultado.umbrales == resultado.umbrales_perfil
    assert "No es evidencia de inseguridad" in resultado.mensaje


def test_test_no_participa_en_la_eleccion():
    dev_casos, dev_obs = _escenario([0.71 + i * 0.004 for i in range(70)], [0.70] * 10)
    test_casos, test_obs = _escenario([0.9] * 10, [0.95] * 5, split="test", prefijo="x")
    primero = calibrar(_banco(dev_casos + test_casos), dev_obs + test_obs, BASE)
    # Otro test (todas las trampas con s_qa 0,99): mismos umbrales, otra verificación.
    otro_test = [o.model_copy(update={"senales": o.senales.model_copy(update={"s_qa": 0.99})}) for o in test_obs]
    segundo = calibrar(_banco(dev_casos + test_casos), dev_obs + otro_test, BASE)
    assert primero.umbrales == segundo.umbrales
    assert primero.dev == segundo.dev
    assert primero.test.falsos_ok == 5 and primero.verificacion_test in ("excede", "muestra_insuficiente")


def test_determinista():
    casos, obs = _escenario([0.71 + i * 0.004 for i in range(70)], [0.70] * 10)
    assert calibrar(_banco(casos), obs, BASE) == calibrar(_banco(casos), list(obs), BASE)


def test_oov_dominio_y_oov_ok_pueden_quedar_distintos():
    """Paráfrasis con 70% de vocabulario ausente pero lector seguro: con
    ``oov_ok`` separado se responden sin tocar el filtro de dominio."""
    casos, obs = [], []
    for i in range(70):
        casos.append(_caso(f"p{i}", "dev", True, CategoriaPregunta.PARAFRASIS))
        obs.append(_obs(f"p{i}", s_qa=0.95, s_oov=0.7))
    for i in range(10):  # fuera de dominio: vocabulario ajeno y recuperación baja
        casos.append(_caso(f"f{i}", "dev", False, estado="fuera_dominio"))
        obs.append(_obs(f"f{i}", s_qa=0.95, s_oov=0.95, s_ret=0.1))
    separado = calibrar(_banco(casos), obs, BASE)
    assert separado.estado == EstadoCalibracion.CALIBRADO
    assert separado.umbrales["oov_ok"] > 0.7 > separado.umbrales["oov_dominio"] == 0.6
    assert separado.dev.cobertura_parafrasis == 1.0
    assert separado.dev.recall_fuera_de_dominio == 1.0
    unido = calibrar(_banco(casos), obs, BASE, separar_oov=False)
    assert unido.umbrales["oov_dominio"] == unido.umbrales["oov_ok"]


# --- banco universal y persistencia ---------------------------------------------------
def test_el_banco_universal_no_se_puede_calibrar():
    raiz = Path(__file__).resolve().parents[1] / "datos" / "banco_universal" / "es" / "manifiesto.json"
    with pytest.raises(ValueError, match="no para calibrar"):
        calibrar(cargar_banco(raiz), [], BASE)


def test_escribir_y_aplicar_solo_con_la_misma_procedencia(tmp_path):
    casos, obs = _escenario([0.71 + i * 0.004 for i in range(70)], [0.70] * 10)
    resultado = calibrar(_banco(casos), obs, BASE)
    modelos = {"denso": "e5", "reranker": None, "lector": None}
    procedencia = ProcedenciaCalibracion(perfil="light", modelos=modelos, hash_corpus="sha256:c",
                                         banco="golden@1", hash_banco="h")
    ruta = escribir_calibracion(resultado, procedencia, tmp_path / "calibracion.yaml")
    aplicados = umbrales_aplicables(ruta, perfil="light", modelos=modelos, hash_corpus="sha256:c")
    assert aplicados["ok"] == pytest.approx(resultado.umbrales["ok"])
    assert umbrales_aplicables(ruta, perfil="light", modelos=modelos, hash_corpus="sha256:otro") is None
    assert umbrales_aplicables(ruta, perfil="medium", modelos=modelos, hash_corpus="sha256:c") is None

    insuficiente = calibrar(_banco(_escenario([0.9] * 20, [])[0]), _escenario([0.9] * 20, [])[1], BASE)
    ruta = escribir_calibracion(insuficiente, procedencia, tmp_path / "otra.yaml")
    assert umbrales_aplicables(ruta, perfil="light", modelos=modelos, hash_corpus="sha256:c") is None
