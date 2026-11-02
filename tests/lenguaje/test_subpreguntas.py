"""División de un mensaje con varias preguntas (ADR 0014): signos de interrogación, interrogativas por idioma y tope."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.subpreguntas import dividir


def partes(mensaje, idioma="es", **kwargs):
    return list(dividir(mensaje, cargar_paquete(idioma), **kwargs).partes)


@pytest.mark.parametrize("idioma,mensaje,esperado", [
    ("es", "¿Cuánto cuesta el P1? ¿Y cuánto dura la garantía?", ["¿Cuánto cuesta el P1?", "¿Cuánto dura la garantía?"]),
    ("en", "How much is the P1? And how long is the warranty?", ["How much is the P1?", "How long is the warranty?"]),
    ("pt", "Quanto custa o P1? E quanto dura a garantia?", ["Quanto custa o P1?", "Quanto dura a garantia?"]),
])
def test_dos_preguntas_con_su_signo_se_separan_y_pierden_el_enlace_inicial(idioma, mensaje, esperado):
    assert partes(mensaje, idioma) == esperado


@pytest.mark.parametrize("idioma,mensaje,esperado", [
    ("es", "¿Cuánto cuesta el purificador P1 y cuánto cuesta el purificador P2?",
     ["¿Cuánto cuesta el purificador P1?", "¿Cuánto cuesta el purificador P2?"]),
    ("es", "¿Cuánto cuesta el P1, cuánto dura la garantía del filtro?",
     ["¿Cuánto cuesta el P1?", "¿Cuánto dura la garantía del filtro?"]),
    ("en", "What does the P1 cost and how long does the warranty on the filter last?",
     ["What does the P1 cost?", "How long does the warranty on the filter last?"]),
    ("pt", "Quanto custa o purificador P1 e quanto custa o purificador P2?",
     ["Quanto custa o purificador P1?", "Quanto custa o purificador P2?"]),
])
def test_una_pregunta_que_arranca_dentro_de_otra_se_corta_con_las_palabras_del_idioma(idioma, mensaje, esperado):
    assert partes(mensaje, idioma) == esperado


@pytest.mark.parametrize("idioma,mensaje", [
    ("es", "¿Cómo y cuándo se paga?"),  # una mitad quedaría sin tema
    ("es", "¿Qué es X y cómo se usa?"),
    ("es", "¿Cuál es el plazo de la garantía?"),
    ("es", "garantía devolución"),  # búsqueda por palabras clave
    ("es", "hola"),
    ("en", "How and when do I pay?"),
    ("en", "Hello! What is the refund period? Thanks"),  # una sola pregunta con cortesía alrededor
    ("pt", "Como e quando pago?"),
])
def test_lo_que_no_es_claramente_mas_de_una_pregunta_se_devuelve_intacto(idioma, mensaje):
    division = dividir(mensaje, cargar_paquete(idioma))
    assert not division.multiple and list(division.partes) == [mensaje]


def test_saludos_y_agradecimientos_no_son_preguntas_ni_ensucian_la_busqueda():
    division = dividir("Hola, ¿cuánto cuesta el P1? ¿cuándo se paga el reembolso? Gracias", cargar_paquete("es"))
    assert list(division.partes) == ["¿Cuánto cuesta el P1?", "¿Cuándo se paga el reembolso?"]


def test_el_tope_deja_las_demas_como_omitidas_sin_perderlas():
    division = dividir("¿A tarifa? ¿B tarifa? ¿C tarifa? ¿D tarifa? ¿F tarifa?", cargar_paquete("es"), maximo=3)
    assert list(division.partes) == ["¿A tarifa?", "¿B tarifa?", "¿C tarifa?"]
    assert list(division.omitidas) == ["¿D tarifa?", "¿F tarifa?"]


def test_un_enlace_pegado_a_la_palabra_siguiente_no_se_quita():
    assert partes("¿Cuánto cuesta el P1? ¿E-mail de contacto?")[1] == "¿E-mail de contacto?"


def test_unir_falso_deja_solo_los_signos_de_interrogacion():
    pregunta = "¿Cuánto cuesta el purificador P1 y cuánto cuesta el purificador P2?"
    assert not dividir(pregunta, cargar_paquete("es"), unir=False).multiple
    assert dividir("¿Cuánto cuesta P1? ¿Cuánto cuesta P2?", cargar_paquete("es"), unir=False).multiple


def test_dividir_una_parte_devuelve_la_misma_parte():
    paquete = cargar_paquete("es")
    for parte in partes("¿Cuánto cuesta el purificador P1 y cuánto cuesta el purificador P2? ¿Y la garantía del filtro?"):
        assert list(dividir(parte, paquete).partes) == [parte]


def test_sin_paquete_solo_cuentan_los_signos_y_nada_falla():
    for idioma in (None, SimpleNamespace(codigo="xx"), cargar_paquete("xx")):
        assert list(dividir("Wie viel kostet P1? Und die Garantie?", idioma).partes) == [
            "Wie viel kostet P1?", "Und die Garantie?"]
        # sin interrogativas del idioma no se corta por palabras
        assert not dividir("Wie viel kostet das und wie lange dauert es?", idioma).multiple


def test_maximo_menor_que_dos_desactiva_la_division():
    assert not dividir("¿A tarifa? ¿B tarifa?", cargar_paquete("es"), maximo=1).multiple


def test_cada_paquete_declara_interrogativas_y_enlaces_sin_tildes_ni_mayusculas():
    for idioma in ("es", "en", "pt"):
        datos = cargar_paquete(idioma).varias_preguntas
        assert len(datos.interrogativos) >= 8 and len(datos.enlaces) >= 3
        for palabra in datos.interrogativos + datos.enlaces:
            assert palabra == palabra.lower() and palabra.isascii(), (idioma, palabra)


CLAVES_INTERFAZ = ("multi_sources", "multi_heading", "multi_jump_label", "multi_question_n", "multi_group_count",
                   "multi_group_count_one", "multi_group_empty", "multi_group_exhausted", "multi_more_for",
                   "multi_no_results_chip", "multi_unsearched", "multi_added", "voice_count_questions")


def _marcadores(texto):
    import re

    return set(re.findall(r"\{(\w+)\}", texto))


def test_los_textos_de_la_interfaz_de_varias_preguntas_existen_en_cada_idioma_con_los_mismos_marcadores():
    ingles = cargar_paquete("en").interfaz
    for idioma in ("es", "en", "pt"):
        interfaz = cargar_paquete(idioma).interfaz
        for clave in CLAVES_INTERFAZ:
            assert interfaz.get(clave), (idioma, clave)
            assert _marcadores(interfaz[clave]) == _marcadores(ingles[clave]), (idioma, clave)


def test_el_respaldo_en_ingles_del_widget_tiene_los_mismos_textos_que_el_paquete_en():
    import re
    from pathlib import Path

    widget = (Path(__file__).resolve().parents[2] / "ipsis/servicio/estaticos/widget.js").read_text(encoding="utf-8")
    ingles = cargar_paquete("en").interfaz
    for clave in CLAVES_INTERFAZ:
        if clave == "multi_sources":  # solo lo usa el servicio para el texto plano de ``answer``
            continue
        encontrado = re.search(rf'^\s+{clave}: "(.*)",$', widget, re.M)
        assert encontrado, clave
        assert encontrado.group(1) == ingles[clave], clave


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_los_mensajes_de_voz_de_varias_preguntas_existen_y_solo_usan_marcadores_conocidos(idioma):
    from ipsis.lenguaje.voz import voz_del_widget

    mensajes = voz_del_widget(idioma)["messages"]["results_multi"]
    assert len(mensajes) >= 6
    for texto in mensajes:
        usados = _marcadores(texto)
        assert usados and usados <= {"count", "questions", "n", "query"}, texto
    # Describen la página; ninguno afirma que una fuente responda (ADR 0001).
    import re

    assert not any(re.search(r"\b(correct\w*|respuesta correcta|resposta correta|right answer|answers? your)\b", t, re.I)
                   for t in mensajes)
