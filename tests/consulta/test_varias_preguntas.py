"""Varias preguntas en un mensaje en el motor v2 y en la API pública (ADR 0014).

Cada pregunta se busca por separado y se publica en su grupo; el cursor de un grupo sigue a una pregunta ordinaria."""
from __future__ import annotations

import pytest

from apoyo_v2 import RecuperadorMemoria
from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier
from ipsis.consulta.v2 import MotorV2
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.nucleo.esquemas import AssistantState
from ipsis.servicio.api import RespuestaConsulta, respuesta_publica


class Espia(RecuperadorMemoria):
    """El recuperador de memoria, que anota cada consulta que recibe."""

    def __init__(self):
        super().__init__()
        self.preguntas = []

    def recuperar(self, consulta, limite, filtro=None):
        self.preguntas.append(consulta.contexto.get("pregunta_recuperacion", consulta.pregunta_original))
        return super().recuperar(consulta, limite, filtro)


def motor(idioma="es", **varias):
    recuperador = Espia()
    opciones = {"corregir_erratas": False}
    if varias:
        opciones["varias_preguntas"] = varias
    m = MotorV2(retriever=recuperador, verificador=LiteralOffsetsVerifier(), idioma=cargar_paquete(idioma),
                opciones=opciones, plantillas={})
    return m, recuperador


DOS = "¿Cuánto dura la garantía del purificador? ¿Cuándo se paga el reembolso del purificador?"


def test_una_sola_pregunta_no_trae_grupos_y_se_busca_una_vez():
    m, r = motor()
    resultado = m.consultar("¿Cuánto dura la garantía del purificador?", "s")
    assert "grupos_preguntas" not in resultado.contrato_http and "preguntas_sin_buscar" not in resultado.contrato_http
    assert len(r.preguntas) == 1
    assert "question_groups" not in respuesta_publica(resultado.contrato_http)


def test_cada_pregunta_se_busca_por_separado_y_se_publica_en_su_grupo():
    m, r = motor()
    resultado = m.consultar(DOS, "s")
    assert r.preguntas == ["¿Cuánto dura la garantía del purificador?", "¿Cuándo se paga el reembolso del purificador?"]
    contrato = resultado.contrato_http
    assert resultado.estado == AssistantState.RELACIONADO
    g1, g2 = contrato["grupos_preguntas"]
    assert [g["indice"] for g in (g1, g2)] == [1, 2]
    assert g1["pregunta"] == "¿Cuánto dura la garantía del purificador?"
    assert g1["fragmentos"][0]["chunk_id"] == "garantia" and g2["fragmentos"][0]["chunk_id"] == "reembolso"
    # Dos fuentes por pregunta en la primera página, y cada grupo conserva su propio ranking desde 1.
    assert [len(g["fragmentos"]) for g in (g1, g2)] == [2, 2]
    assert [f["rango"] for f in g1["fragmentos"]] == [1, 2]
    # Para quien no entienda los grupos, ``fragmentos`` los lista todos en orden de grupo y dice a cuál pertenece cada uno.
    assert [f["indice_pregunta"] for f in contrato["fragmentos"]] == [1, 1, 2, 2]
    assert len(resultado.evidencias) == 4
    # La continuación es de cada grupo; la del mensaje no existe.
    assert contrato["has_more"] is False and contrato["continuation"] is None
    assert g1["has_more"] and g1["continuation"] and g2["continuation"] and g1["continuation"] != g2["continuation"]


def test_una_misma_fuente_puede_ser_la_mejor_de_dos_preguntas_y_se_ve_en_las_dos():
    m, _ = motor()
    contrato = m.consultar("¿Cuánto dura la garantía? ¿Qué cubre la garantía?", "s").contrato_http
    ids = [{f["chunk_id"] for f in g["fragmentos"]} for g in contrato["grupos_preguntas"]]
    assert "garantia" in ids[0] and "garantia" in ids[1]


def test_mostrar_mas_de_un_grupo_es_una_continuacion_ordinaria_de_esa_pregunta():
    m, _ = motor()
    contrato = m.consultar(DOS, "s").contrato_http
    g2 = contrato["grupos_preguntas"][1]
    pagina = m.continuar(g2["pregunta"], "s", g2["continuation"]).contrato_http
    assert "grupos_preguntas" not in pagina
    assert [f["rango"] for f in pagina["fragmentos"]] == [3, 4]
    assert not {f["chunk_id"] for f in pagina["fragmentos"]} & {f["chunk_id"] for f in g2["fragmentos"]}
    # El cursor de un grupo no sirve para otra pregunta.
    from ipsis.consulta.errores import ContinuacionInvalida

    with pytest.raises(ContinuacionInvalida):
        m.continuar(contrato["grupos_preguntas"][0]["pregunta"], "s", g2["continuation"])


def test_el_tope_de_preguntas_deja_el_resto_sin_buscar_y_lo_dice():
    m, r = motor(max_preguntas=2)
    mensaje = "¿Cuánto dura la garantía? ¿Cuándo se paga el reembolso? ¿Cada cuánto se cambia el filtro?"
    resultado = m.consultar(mensaje, "s")
    assert len(r.preguntas) == 2
    assert resultado.contrato_http["preguntas_sin_buscar"] == ["¿Cada cuánto se cambia el filtro?"]
    assert any("sin buscar" in a for a in resultado.diagnostico["advertencias"])
    publica = respuesta_publica(resultado.contrato_http)
    assert publica["unsearched_questions"] == ["¿Cada cuánto se cambia el filtro?"]
    assert "Cada cuánto se cambia el filtro" in resultado.mensaje_usuario  # no se pierde ni en el texto plano


def test_apagado_el_mensaje_se_busca_entero_como_antes():
    m, r = motor(activo=False)
    resultado = m.consultar(DOS, "s")
    assert r.preguntas == [DOS] and "grupos_preguntas" not in resultado.contrato_http


def test_una_pregunta_sin_fuentes_tiene_su_grupo_vacio_y_las_demas_siguen():
    m, _ = motor()
    contrato = m.consultar("¿Cuánto dura la garantía? ¿Quién fabrica la bomba hidráulica?", "s").contrato_http
    g1, g2 = contrato["grupos_preguntas"]
    assert g1["fragmentos"] and g2["fragmentos"] == [] and g2["estado"] == "sin_respuesta" and not g2["continuation"]
    assert contrato["estado"] == "relacionado"


def test_si_ninguna_pregunta_tiene_fuentes_el_mensaje_no_tiene_respuesta():
    m, _ = motor()
    resultado = m.consultar("¿Quién fabrica la bomba hidráulica? ¿Dónde queda la sucursal austral?", "s")
    assert resultado.estado == AssistantState.SIN_RESPUESTA and not resultado.evidencias
    assert [g["fragmentos"] for g in resultado.contrato_http["grupos_preguntas"]] == [[], []]


def test_la_api_publica_los_grupos_y_valida_contra_el_esquema():
    m, _ = motor()
    resultado = m.consultar(DOS + " ¿Cuál es el precio del purificador? ¿Dónde se instala?", "s")
    publica = respuesta_publica(resultado.contrato_http)
    modelo = RespuestaConsulta.model_validate(publica)
    volcado = modelo.model_dump(exclude_unset=True)
    assert [g["index"] for g in volcado["question_groups"]] == [1, 2, 3]
    assert volcado["question_groups"][0]["question"] == "¿Cuánto dura la garantía del purificador?"
    assert volcado["question_groups"][0]["continuation"] and volcado["question_groups"][0]["has_more"] is True
    assert volcado["unsearched_questions"] == ["¿Dónde se instala?"]
    assert {f["question_index"] for f in volcado["fragments"]} == {1, 2, 3}
    assert volcado["has_more"] is False
    assert volcado["status"] == "related" and volcado["response_mode"] == "ranked_sources"


@pytest.mark.parametrize("idioma,mensaje", [
    ("en", "How long is the warranty on the purifier? When is the purifier refund paid?"),
    ("pt", "Quanto dura a garantia do purificador? Quando se paga o reembolso do purificador?"),
])
def test_funciona_igual_en_ingles_y_portugues(idioma, mensaje):
    m, r = motor(idioma)
    resultado = m.consultar(mensaje, "s")
    assert len(r.preguntas) == 2 and len(resultado.contrato_http["grupos_preguntas"]) == 2


def test_el_presupuesto_se_reparte_y_la_segunda_pregunta_no_se_queda_sin_tiempo():
    m, _ = motor(resultados_por_pregunta=1)
    resultado = m.consultar_con_presupuesto(DOS, "s", deadline_ms=2000)
    assert [len(g["fragmentos"]) for g in resultado.contrato_http["grupos_preguntas"]] == [1, 1]
    etapas = resultado.diagnostico["preguntas"]
    assert [p["indice"] for p in etapas] == [1, 2] and all(p["regla"] == "recuperado" for p in etapas)


def test_la_configuracion_tiene_valores_por_defecto_y_rechaza_valores_absurdos():
    from pydantic import ValidationError

    from ipsis.configuracion.esquemas import PipelineV2Config

    por_defecto = PipelineV2Config().varias_preguntas.model_dump()
    assert por_defecto == {"activo": True, "max_preguntas": 3, "resultados_por_pregunta": 2,
                           "cortar_por_interrogativas": True}
    ajustado = PipelineV2Config.model_validate({"varias_preguntas": {"max_preguntas": 4, "resultados_por_pregunta": 3}})
    assert (ajustado.varias_preguntas.max_preguntas, ajustado.varias_preguntas.resultados_por_pregunta) == (4, 3)
    for malo in ({"max_preguntas": 1}, {"max_preguntas": 9}, {"resultados_por_pregunta": 0}, {"inventada": True}):
        with pytest.raises(ValidationError):
            PipelineV2Config.model_validate({"varias_preguntas": malo})


def test_el_glosario_traduce_la_seccion_a_nombres_en_ingles():
    from ipsis.configuracion.glosario import a_externo, a_interno

    interno = {"v2": {"varias_preguntas": {"activo": True, "max_preguntas": 4, "resultados_por_pregunta": 2,
                                           "cortar_por_interrogativas": False}}}
    externo = a_externo(interno, "motor")
    assert externo == {"v2": {"multi_question": {"enabled": True, "max_questions": 4, "results_per_question": 2,
                                                  "split_on_interrogatives": False}}}
    assert a_interno(externo, "motor") == interno
