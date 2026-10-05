"""Reglas del idioma (plazos, fechas, referencias) y conversación en es, en y pt.

Los mismos hechos deben producir el mismo ``valor_norm`` en cualquier idioma.
"""
from __future__ import annotations

import pytest

from ipsis.consulta.etapas.conversacional import detectar_conversacional
from ipsis.consulta.etapas.redaccion import cargar_plantillas
from ipsis.lenguaje.entidades import extraer_articulos, extraer_fechas, extraer_plazos
from ipsis.lenguaje.paquete import cargar_paquete

PLAZOS = {
    "es": [("dentro de cinco días hábiles", "5_dia_habiles"), ("dura 4 semanas", "4_semana"),
           ("cada 6 meses", "6_mes"), ("en 30 días corridos", "30_dia_corridos")],
    "en": [("within five business days", "5_dia_habiles"), ("lasts 4 weeks", "4_semana"),
           ("every 6 months", "6_mes"), ("in 30 calendar days", "30_dia_corridos")],
    "pt": [("em cinco dias úteis", "5_dia_habiles"), ("dura 4 semanas", "4_semana"),
           ("a cada 6 meses", "6_mes"), ("em 30 dias corridos", "30_dia_corridos")],
}
FECHAS = {
    "es": [("el 15 de marzo de 2024", "2024-03-15"), ("el 3 de abril", "--04-03"),
           ("el segundo viernes de enero", "2_dow5_m01")],
    "en": [("on March 15, 2024", "2024-03-15"), ("on 3 April", "--04-03"),
           ("the second Friday of January", "2_dow5_m01")],
    "pt": [("em 15 de março de 2024", "2024-03-15"), ("em 3 de abril", "--04-03"),
           ("na segunda sexta-feira de janeiro", "2_dow5_m01")],
}
REFERENCIAS = {
    "es": [("según el artículo 8", "articulo_8"), ("los artículos 13 y 14", "articulo_13_y_14"),
           ("el anexo 2", "anexo_2"), ("los artículos 20 a 23", "articulo_20_a_23")],
    "en": [("under Article 8", "articulo_8"), ("Articles 13 and 14", "articulo_13_y_14"),
           ("see Annex 2", "anexo_2"), ("Articles 20 to 23", "articulo_20_a_23")],
    "pt": [("conforme o artigo 8", "articulo_8"), ("os artigos 13 e 14", "articulo_13_y_14"),
           ("o anexo 2", "anexo_2"), ("os artigos 20 a 23", "articulo_20_a_23")],
}
CONVERSACION = {
    "es": [("hola", "greeting"), ("muchas gracias", "thanks"), ("chao", "farewell"),
           ("¿qué puedes hacer?", "capability"), ("¿cuánto dura la garantía?", None)],
    "en": [("hello there", "greeting"), ("thanks a lot", "thanks"), ("bye", "farewell"),
           ("what can you do?", "capability"), ("how long is the warranty?", None)],
    "pt": [("olá", "greeting"), ("muito obrigado", "thanks"), ("tchau", "farewell"),
           ("o que você pode fazer?", "capability"), ("quanto dura a garantia?", None)],
}


def _casos(tabla):
    return [(idioma, texto, esperado) for idioma, casos in tabla.items() for texto, esperado in casos]


def _valores(entidades, texto):
    for e in entidades:
        assert texto[e.offset:e.offset + len(e.texto)] == e.texto
    return [e.valor_norm for e in entidades]


@pytest.mark.parametrize(("idioma", "texto", "esperado"), _casos(PLAZOS))
def test_plazos(idioma, texto, esperado):
    assert _valores(extraer_plazos(texto, cargar_paquete(idioma)), texto) == [esperado]


@pytest.mark.parametrize(("idioma", "texto", "esperado"), _casos(FECHAS))
def test_fechas(idioma, texto, esperado):
    assert _valores(extraer_fechas(texto, cargar_paquete(idioma)), texto) == [esperado]


@pytest.mark.parametrize(("idioma", "texto", "esperado"), _casos(REFERENCIAS))
def test_referencias(idioma, texto, esperado):
    assert _valores(extraer_articulos(texto, cargar_paquete(idioma)), texto) == [esperado]


@pytest.mark.parametrize(("idioma", "texto", "esperado"), _casos(CONVERSACION))
def test_conversacion(idioma, texto, esperado):
    plantillas = cargar_plantillas(cargar_paquete(idioma))
    assert detectar_conversacional(texto, plantillas) == esperado


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_respuestas_conversacionales_sustituyen_variables(idioma):
    plantillas = cargar_plantillas(
        cargar_paquete(idioma),
        {"nombre_asistente": "Ana", "descripcion_dominio": "el manual"},
    )
    for opciones in plantillas["conversacional"]["respuestas"].values():
        for texto in opciones if isinstance(opciones, list) else [opciones]:
            assert "{" not in texto


def test_sin_paquete_no_hay_reglas_de_idioma():
    from ipsis.lenguaje.entidades import usar_idioma

    with usar_idioma(None):
        assert extraer_plazos("dentro de cinco días hábiles") == []
