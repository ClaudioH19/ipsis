"""Pregunta coloquial por su forma de escribir (ipsis.lenguaje.estilo)."""
import pytest

from ipsis.lenguaje.estilo import es_coloquial
from ipsis.lenguaje.paquete import cargar_paquete


@pytest.mark.parametrize(("idioma", "pregunta", "esperado"), [
    ("es", "cuanta plata sale el almuerzo", True),     # minúscula y sin «¿»
    ("es", "¿q hago si no llega el pedido?", True),     # abreviatura informal
    ("es", "¿Cuánto cuesta el almuerzo?", False),
    ("es", "Cuanto cuesta el almuerzo?", False),       # mayúscula: no se adivina más
    ("en", "how much is lunch", True),
    ("en", "How much is lunch, pls?", True),
    ("en", "How much is lunch?", False),
    ("pt", "quanto sai o almoco", True),
    ("pt", "Quanto custa o almoço?", False),
])
def test_la_forma_de_escribir_decide_si_la_pregunta_es_coloquial(idioma, pregunta, esperado):
    assert es_coloquial(pregunta, cargar_paquete(idioma)) is esperado


def test_sin_paquete_o_sin_texto_no_es_coloquial():
    assert not es_coloquial("hola", None) and not es_coloquial("", cargar_paquete("es"))
