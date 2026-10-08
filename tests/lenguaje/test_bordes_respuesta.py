import pytest

from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.respuestas import completar_tramo


@pytest.mark.parametrize("idioma,pregunta,texto,span,esperada", [
    ("es", "¿Cuántos caracteres?", "La contraseña debe tener al menos 18 caracteres e incluir un número.", "18", "al menos 18 caracteres"),
    ("en", "How many days?", "The order is issued within seven business days from approval of the request.", "seven", "within seven business days from approval of the request"),
    ("pt", "Quantos dias?", "O auxílio é pago em até oito dias úteis após a aprovação do pedido.", "oito", "em até oito dias úteis após a aprovação do pedido"),
    ("es", "¿Cuándo?", "Se paga dentro de 9 días hábiles después de aprobar la solicitud.", "9 días", "dentro de 9 días hábiles después de aprobar la solicitud"),
])
def test_completa_unidad_limite_y_referencia_literal(idioma, pregunta, texto, span, esperada):
    inicio = texto.index(span)
    a, b = completar_tramo(pregunta, texto, inicio, inicio + len(span), cargar_paquete(idioma))
    assert texto[a:b] == esperada
    assert a <= inicio < inicio + len(span) <= b


def test_no_completa_con_otra_cantidad_ni_con_una_unidad_ausente():
    texto = "El código es 18 y se renueva a los 9 días."
    inicio = texto.index("18")
    assert completar_tramo("¿Cuál es el código?", texto, inicio, inicio + 2, cargar_paquete("es")) == (inicio, inicio + 2)


@pytest.mark.parametrize("idioma,pregunta,texto,span,esperada", [
    ("es", "¿Quién redacta?", "La Secretaría redacta el acta y la envía al Presidente para su firma.", "La Secretaría", "La Secretaría redacta el acta"),
    ("en", "Who drafts it?", "The Secretary drafts the minutes and sends them to the Chair for signature.", "The Secretary", "The Secretary drafts the minutes"),
    ("pt", "Quem redige?", "A Secretaria redige a ata e a envia ao Presidente para assinatura.", "A Secretaria", "A Secretaria redige a ata"),
])
def test_completa_actor_y_accion_sin_incluir_el_otro_actor(idioma, pregunta, texto, span, esperada):
    a, b = completar_tramo(pregunta, texto, 0, len(span), cargar_paquete(idioma))
    assert texto[a:b] == esperada


def test_no_encubre_un_actor_equivocado_con_la_cita_entera():
    texto = "La Secretaría redacta el acta y la envía al Presidente para su firma."
    inicio = texto.index("Presidente")
    assert completar_tramo("¿Quién redacta?", texto, inicio, inicio + len("Presidente"), cargar_paquete("es")) == (inicio, inicio + len("Presidente"))


def test_no_busca_la_accion_correcta_despues_de_la_accion_de_otro_actor():
    texto = "El Director firma el acta. La Secretaría redacta el acta."
    assert completar_tramo("¿Quién redacta el acta?", texto, 0, len("El Director"), cargar_paquete("es")) == (0, len("El Director"))
