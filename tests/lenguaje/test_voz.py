"""Los mensajes de interfaz nunca reemplazan una consulta documental."""
from types import SimpleNamespace

import pytest

from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.voz import voz_del_widget, categoria_cortesia, preguntas_fijas, respuesta_fija
from ipsis.nucleo.esquemas import AssistantState
from tests.consulta.test_motor_v2 import motor


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_banco_completo_y_copias_independientes(idioma):
    voz = voz_del_widget(idioma)
    mensajes = [texto for lista in voz["messages"].values() for texto in lista]
    assert len(mensajes) == len(set(mensajes)) and len(mensajes) >= 100
    assert all(len(voz["messages"][categoria]) >= 6 for categoria in ("about", "limits", "examples"))
    assert len(voz["suggestions"]) == len(set(voz["suggestions"])) == 6
    assert len(voz["questions"]) >= 100
    assert len({p["topic"] for p in voz["questions"]}) >= 10
    assert all(isinstance(texto, str) and texto.strip() for texto in mensajes)
    assert voz_del_widget(idioma + "-XX") == voz
    voz["messages"]["greeting"].clear()
    assert len(voz_del_widget(idioma)["messages"]["greeting"]) == 10
    voz["suggestions"].clear()
    assert len(voz_del_widget(idioma)["suggestions"]) == 6
    voz["questions"][0]["question"] = "alterada"
    assert voz_del_widget(idioma)["questions"][0]["question"] != "alterada"


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_cien_preguntas_distintas_se_responden_sin_recuperar_documentos(idioma):
    entradas = preguntas_fijas(idioma)
    assert len(entradas) >= 100 and len({p["question"] for p in entradas}) == len(entradas)
    m = motor(idioma=SimpleNamespace(codigo=idioma), opciones={"corregir_erratas": False})
    m.plantillas["conversacional"] = cargar_paquete(idioma).conversacional.model_dump()
    for entrada in entradas:
        resultado = m.consultar(entrada["question"], "faq")
        assert resultado.estado == AssistantState.CONVERSACIONAL
        assert resultado.contrato_http["categoria_conversacional"] == "help"
        assert resultado.mensaje_usuario == entrada["answer"]
        assert not resultado.evidencias and not resultado.contrato_http["fragmentos"]
        assert respuesta_fija(entrada["question"].upper(), idioma) == entrada["answer"]
    assert not m.retriever.consultas


@pytest.mark.parametrize("idioma,sufijo", [("es", " según el manual del producto"),
                                          ("en", " according to the product manual"),
                                          ("pt", " segundo o manual do produto")])
def test_ayuda_no_captura_consultas_mixtas_y_las_sugerencias_siguen_buscando(idioma, sufijo):
    m = motor(idioma=SimpleNamespace(codigo=idioma), opciones={"corregir_erratas": False})
    voz = voz_del_widget(idioma)
    consultas = [p["question"] + sufijo for p in preguntas_fijas(idioma)] + voz["suggestions"]
    for pregunta in consultas:
        assert respuesta_fija(pregunta, idioma) is None
        m.consultar(pregunta, "docs")
    assert len(m.retriever.consultas) == len(consultas)


@pytest.mark.parametrize("idioma,saludo,consulta", [
    ("es", "¡Hola!", "hola, cuánto stock tiene el producto"),
    ("en", "Hello!", "hello, what is the product stock"),
    ("pt", "Olá!", "olá, qual é o estoque do produto"),
])
def test_cortesia_pura_no_recupera_y_pregunta_mixta_si(idioma, saludo, consulta):
    paquete = cargar_paquete(idioma)
    m = motor(idioma=SimpleNamespace(codigo=idioma), opciones={"corregir_erratas": False})
    m.plantillas["conversacional"] = paquete.conversacional.model_dump()
    resultado = m.consultar(saludo, "s")
    assert resultado.estado == AssistantState.CONVERSACIONAL
    assert resultado.contrato_http["categoria_conversacional"] == "greeting"
    assert not resultado.evidencias and not m.retriever.consultas
    assert resultado.mensaje_usuario in voz_del_widget(idioma)["messages"]["greeting"]
    assert categoria_cortesia(consulta, m.plantillas) is None
    m.consultar(consulta, "s")
    assert len(m.retriever.consultas) == 1


@pytest.mark.parametrize("pregunta,categoria", [("gracias", "thanks"), ("adiós", "farewell"),
                                               ("¿Qué puedes hacer?", "capability")])
def test_otros_mensajes_de_cortesia(pregunta, categoria):
    datos = {"conversacional": cargar_paquete("es").conversacional.model_dump()}
    assert categoria_cortesia(pregunta, datos) == categoria
    assert categoria_cortesia(pregunta + " según el manual", datos) is None


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_los_mensajes_por_forma_de_pagina_existen_y_solo_usan_marcadores_conocidos(idioma):
    import re

    mensajes = voz_del_widget(idioma)["messages"]
    for categoria in ("results_variants", "results_documents"):
        assert len(mensajes[categoria]) >= 6
        for texto in mensajes[categoria]:
            assert set(re.findall(r"\{(\w+)\}", texto)) <= {"count", "n", "query", "n_docs"}
            assert "{" not in re.sub(r"\{(count|n|query|n_docs)\}", "", texto)
    # {n_docs} solo donde hay varios documentos: en las variantes del mismo documento no tiene sentido
    assert not any("{n_docs}" in t for t in mensajes["results_variants"])


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_los_mensajes_de_correccion_existen_y_usan_los_marcadores_de_su_situacion(idioma):
    import re

    mensajes = voz_del_widget(idioma)["messages"]
    assert len(mensajes["results_retry"]) >= 6 and len(mensajes["opened_source"]) >= 6
    # «No es esto» ya sabe cuántas fuentes hay: cada mensaje lo dice con {count}, para que no se le anteponga el conteo
    assert all("{count}" in t for t in mensajes["results_retry"])
    for t in mensajes["results_retry"]:
        assert set(re.findall(r"\{(\w+)\}", t)) == {"count"}
    # al abrir una fuente: el documento siempre, y el alcance detrás de él con su coma; nada más
    for t in mensajes["opened_source"]:
        assert "{doc}{scope_suffix}" in t and set(re.findall(r"\{(\w+)\}", t)) == {"doc", "scope_suffix"}
        assert not re.search(r"\b(correct\w*|respuesta correcta|resposta correta|right answer)\b", t, re.I)
