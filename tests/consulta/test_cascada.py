"""Política ``cascada_v1``: un caso por regla, por límite de umbral y por perfil."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from rag.aplicacion.registro_base import registrar_componentes_base
from rag.configuracion.perfiles import perfil_efectivo
from rag.consulta.etapas.politica import CascadaV1, EtapaPolitica, forma_en_pregunta
from rag.lenguaje.paquete import cargar_paquete
from rag.lenguaje.texto import terminos
from rag.nucleo.contratos import AbstentionPolicy
from rag.nucleo.esquemas import (
    ChunkRecord,
    LecturaQA,
    QueryAnalysis,
    RetrievalCandidate,
    SenalesLexicas,
    SenalesRecuperacion,
)
from rag.nucleo.registro import RegistroComponentes

UMBRALES = {"oov": 0.6, "dominio": 0.3, "relacionado": 0.5, "foco": 0.5, "ok": 0.8, "cov": 0.6}
TEXTO = "La garantía del purificador dura 24 meses desde la compra."


def _ctx(
    *,
    pregunta: str = "¿Cuánto dura la garantía?",
    s_ret: float = 0.9,
    s_oov: float = 0.0,
    s_foco: float | None = 1.0,
    s_cov: float | None = 1.0,
    acuerdo: float | None = 1.0,
    p_rr: float | None = None,
    s_qa: float | None = None,
    terminos_foco: list[str] | None = None,
    texto: str = TEXTO,
):
    candidato = RetrievalCandidate(chunk=ChunkRecord(
        chunk_id="c1", doc_id="doc", texto_fuente=texto, texto_embedding=texto,
        offset_inicio=0, offset_fin=len(texto),
    ))
    return SimpleNamespace(
        pregunta=pregunta,
        consulta=QueryAnalysis(pregunta_original=pregunta, pregunta_normalizada=pregunta),
        candidatos=[candidato],
        senales=SenalesRecuperacion(confianza_top1=s_ret, margen_top1_top2=0.1),
        lexicas=SenalesLexicas(s_oov=s_oov, s_foco=s_foco, s_cov=s_cov, acuerdo=acuerdo),
        # El reranker entrega logits; la política usa su sigmoide.
        puntajes_rerank=None if p_rr is None else [math.log(p_rr / (1 - p_rr))],
        lecturas=None if s_qa is None else [LecturaQA(
            indice_pasaje=0, inicio=0, fin=2, texto="La", prob_respuesta=s_qa, prob_sin_respuesta=0.0)],
        terminos_foco=terminos_foco or [],
        diagnostico={"advertencias": []},
        discordancia=False,
    )


def _decidir(**senales):
    return CascadaV1(umbrales=UMBRALES).decidir_contexto(_ctx(**senales))


@pytest.mark.parametrize("senales, resultado, regla", [
    # 1. premisa
    ({"pregunta": "¿Qué dice el artículo 99?", "s_qa": 0.95}, "abstiene", "premisa"),
    # 2. fuera de dominio (con reranker y sin él)
    ({"s_oov": 0.9, "s_ret": 0.1, "p_rr": 0.1, "s_qa": 0.0}, "abstiene", "fuera_dominio"),
    ({"s_oov": 0.9, "s_ret": 0.1}, "abstiene", "fuera_dominio"),
    # 3. ok con lector y ok léxico (light)
    ({"p_rr": 0.9, "s_qa": 0.9}, "responde", "ok_lector"),
    ({"s_ret": 0.9, "s_cov": 0.9, "acuerdo": 1.0}, "responde", "ok_lexico"),
    # 4. relacionado
    ({"p_rr": 0.9, "s_qa": 0.1}, "relacionado", "relacionado"),
    # 5. sin respuesta
    ({"s_ret": 0.2, "p_rr": 0.2, "s_qa": 0.1}, "abstiene", "sin_respuesta"),
])
def test_cada_regla(senales, resultado, regla):
    decision = _decidir(**senales)
    assert (decision.resultado, decision.capa_decisora) == (resultado, regla)


@pytest.mark.parametrize("senales, regla", [
    # τ_oov: el límite cuenta como fuera de dominio
    ({"s_oov": 0.6, "s_ret": 0.29, "s_cov": 0.0}, "fuera_dominio"),
    ({"s_oov": 0.59, "s_ret": 0.29, "s_cov": 0.0}, "sin_respuesta"),
    # τ_dominio
    ({"s_oov": 0.9, "s_ret": 0.3, "s_cov": 0.0}, "sin_respuesta"),
    # τ_ok con lector
    ({"s_qa": 0.8}, "ok_lector"),
    ({"s_qa": 0.79}, "relacionado"),
    # τ_oov también exige vocabulario del corpus para responder
    ({"s_qa": 0.9, "s_oov": 0.59}, "ok_lector"),
    ({"s_qa": 0.9, "s_oov": 0.6}, "relacionado"),
    ({"s_oov": 0.6}, "relacionado"),
    # τ_foco
    ({"s_qa": 0.9, "s_foco": 0.5}, "ok_lector"),
    ({"s_qa": 0.9, "s_foco": 0.49}, "relacionado"),
    # τ_ok, τ_cov y acuerdo sin lector
    ({"s_ret": 0.8}, "ok_lexico"),
    ({"s_ret": 0.79}, "relacionado"),
    ({"s_cov": 0.6}, "ok_lexico"),
    ({"s_cov": 0.59}, "relacionado"),
    ({"acuerdo": 0.5}, "ok_lexico"),
    ({"acuerdo": 0.4}, "relacionado"),
    # τ_relacionado
    ({"s_ret": 0.5, "s_cov": 0.0}, "relacionado"),
    ({"s_ret": 0.49, "s_cov": 0.0}, "sin_respuesta"),
])
def test_limites_de_umbral(senales, regla):
    assert _decidir(**senales).capa_decisora == regla


def test_el_reranker_confirma_el_dominio_pero_no_lo_niega():
    assert _decidir(s_oov=0.9, s_ret=0.1, p_rr=0.9, s_qa=0.0).capa_decisora == "relacionado"
    assert _decidir(s_oov=0.9, s_ret=0.9, p_rr=0.01, s_qa=0.0).capa_decisora == "relacionado"


def test_foco_ausente_nombra_la_palabra_de_la_pregunta():
    es = cargar_paquete("es")
    foco = terminos("garantía", es)
    decision = CascadaV1(umbrales=UMBRALES, paquete=es).decidir_contexto(
        _ctx(s_qa=0.95, s_foco=0.0, terminos_foco=foco))
    assert (decision.resultado, decision.motivo, decision.entidad_texto) == ("relacionado", "foco_ausente", "garantía")
    assert forma_en_pregunta("¿Cuánto dura la garantía?", "inexistente", es) == "inexistente"


def test_la_decision_guarda_las_senales_en_el_diagnostico():
    ctx = _ctx(p_rr=0.9, s_qa=0.9)
    CascadaV1(umbrales=UMBRALES).decidir_contexto(ctx)
    assert ctx.diagnostico["senales_politica"]["s_qa"] == pytest.approx(0.9)
    assert ctx.diagnostico["senales_politica"]["dominio"] == pytest.approx(0.9)


def test_sin_umbrales_completos_falla():
    with pytest.raises(ValueError, match="cascada_v1"):
        CascadaV1(umbrales={"oov": 0.5})


@pytest.mark.parametrize("perfil, con_lector", [("light", False), ("medium", True), ("heavy", True)])
def test_cada_perfil_se_registra_y_decide(perfil, con_lector, tmp_path):
    umbrales = perfil_efectivo(perfil, ruta_calibracion=tmp_path / "no_existe.yaml").umbrales_por_defecto
    registro = registrar_componentes_base(RegistroComponentes())
    politica = registro.crear("abstention_policy", "cascada_v1", umbrales=umbrales)
    senales = {"p_rr": 0.95, "s_qa": 0.95} if con_lector else {"s_ret": 0.95}
    assert isinstance(politica, AbstentionPolicy)
    assert registro.disponibles("abstention_policy") == ["cascada_v1"]
    assert politica.decidir_contexto(_ctx(**senales)).resultado == "responde"


def test_etapa_politica_usa_el_contexto_y_conserva_fuera_de_dominio():
    llamadas = []
    motor = SimpleNamespace(
        politica_abstencion=CascadaV1(umbrales=UMBRALES),
        _abstener=lambda motivo, *a, **k: llamadas.append(motivo) or "abstencion",
    )
    ctx = _ctx(s_oov=0.9, s_ret=0.1)
    ctx.confianza = {}
    ctx.latencia_ms = lambda: 0
    EtapaPolitica(motor).ejecutar(ctx)
    assert llamadas == ["fuera_dominio"]
    assert ctx.diagnostico["regla"] == "fuera_dominio"
