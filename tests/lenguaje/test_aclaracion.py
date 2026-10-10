"""Preguntas que necesitan aclaración antes de leer (ipsis.lenguaje.aclaracion)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipsis.lenguaje.aclaracion import motivo_aclaracion
from ipsis.lenguaje.paquete import cargar_paquete

DOCUMENTOS = {
    "es": {"garantia": "La garantía dura 24 meses. La jefatura aprueba el cambio.",
           "biblioteca": "El préstamo de libros dura 14 días.",
           "viaticos": "La jefatura aprueba la comisión y Finanzas transfiere el viático."},
    "en": {"warranty": "The warranty lasts 24 months. The manager approves the change.",
           "library": "Book loans last 14 days.",
           "travel": "The manager approves the trip."},
    "pt": {"garantia": "A garantia dura 24 meses. A chefia aprova a troca.",
           "biblioteca": "O empréstimo de livros dura 14 dias.",
           "diarias": "A chefia aprova a viagem."},
}


def _candidatos(idioma):
    return [SimpleNamespace(chunk=SimpleNamespace(doc_id=d, texto_fuente=t)) for d, t in DOCUMENTOS[idioma].items()]


@pytest.mark.parametrize(("idioma", "pregunta", "motivo"), [
    ("es", "¿Cuánto es?", "sin_tema"),
    ("es", "¿Cuántos días son?", "sin_tema"),
    ("es", "¿Quién lo aprueba?", "pronombre"),
    ("es", "¿Cuánto dura?", "varios_documentos"),
    ("es", "¿Cuánto tarda?", "tema_desconocido"),
    ("en", "How much is it?", "sin_tema"),
    ("en", "Who approves it?", "pronombre"),
    ("en", "How long does it last?", "pronombre"),
    ("pt", "Quanto é?", "sin_tema"),
    ("pt", "Quem aprova?", "varios_documentos"),
])
def test_una_pregunta_sin_tema_pide_aclaracion(idioma, pregunta, motivo):
    assert motivo_aclaracion(pregunta, cargar_paquete(idioma), None, _candidatos(idioma)) == motivo


@pytest.mark.parametrize(("idioma", "pregunta"), [
    ("es", "¿Cuánto dura la garantía?"),           # tema propio
    ("es", "cuando empieza la compra?"),           # una palabra, pero la relación acota
    ("es", "¿Bitcoin?"),                           # una palabra ausente: fuera de dominio, no aclaración
    ("es", "¿Préstamo?"),                          # una palabra de un solo documento
    ("en", "How long does the warranty last?"),
    ("pt", "Quem aprova a viagem?"),
])
def test_una_pregunta_con_tema_sigue_el_camino_normal(idioma, pregunta):
    assert motivo_aclaracion(pregunta, cargar_paquete(idioma), None, _candidatos(idioma)) is None
