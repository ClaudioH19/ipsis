"""Los mensajes de interfaz nunca reemplazan una consulta documental."""
from types import SimpleNamespace

import pytest

from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.voz import voz_del_widget, categoria_cortesia
from ipsis.nucleo.esquemas import AssistantState
from tests.consulta.test_motor_v2 import motor


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_banco_completo_y_copias_independientes(idioma):
    voz = voz_del_widget(idioma)
    mensajes = [texto for lista in voz["messages"].values() for texto in lista]
    assert len(mensajes) == len(set(mensajes)) == 100
    assert all(isinstance(texto, str) and texto.strip() for texto in mensajes)
    assert voz_del_widget(idioma + "-XX") == voz
    voz["messages"]["greeting"].clear()
    assert len(voz_del_widget(idioma)["messages"]["greeting"]) == 10


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
