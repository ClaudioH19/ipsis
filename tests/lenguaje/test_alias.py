"""Alias que el corpus define: extracción al indexar y reconocimiento al consultar."""
import pytest

from ipsis.lenguaje.alias import Alias, es_definicion, extraer_alias, pide_definicion
from ipsis.lenguaje.paquete import cargar_paquete

GLOSARIO = {
    "es": ["Práctica Profesional I (P1): primera práctica profesional del plan de estudios.\n"
           "Práctica Profesional II (P2): segunda práctica profesional del plan de estudios.\n"
           "La Comisión de Prácticas (CDP), en adelante la Comisión, revisa los informes."],
    "en": ["Professional Internship I (PI1): first professional internship of the curriculum.\n"
           "Professional Internship II (PI2): second professional internship of the curriculum."],
    "pt": ["Estágio Profissional I (EP1): primeiro estágio profissional do currículo.\n"
           "Estágio Profissional II (EP2): segundo estágio profissional do currículo."],
}


def _grupo(grupos, sigla):
    return next(g for g in grupos if sigla in g)


def test_extrae_sigla_definicion_y_en_adelante():
    grupos = extraer_alias(GLOSARIO["es"], cargar_paquete("es"))
    p1 = _grupo(grupos, "P1")
    assert "Práctica Profesional I" in p1
    assert "primera práctica profesional del plan de estudios" in p1
    assert "Comisión" in _grupo(grupos, "CDP")


def test_no_inventa_grupos_sin_sigla():
    assert extraer_alias(["La práctica dura cuatro semanas y se evalúa con un informe."],
                         cargar_paquete("es")) == []


@pytest.mark.parametrize("idioma,pregunta,sigla", [
    ("es", "cuanto dura la primera practica", "P1"),
    ("es", "cuanto vale la P2", "P2"),
    ("en", "how long is the first internship", "PI1"),
    ("pt", "quanto dura o segundo estagio", "EP2"),
])
def test_la_pregunta_nombra_el_grupo_con_otra_forma(idioma, pregunta, sigla):
    paquete = cargar_paquete(idioma)
    alias = Alias(extraer_alias(GLOSARIO[idioma], paquete), paquete)
    nombrados = [alias.grupos[i] for i in alias.mencionados(pregunta)]
    assert [sigla in g for g in nombrados] == [True]


def test_el_ordinal_distingue_los_grupos():
    paquete = cargar_paquete("es")
    alias = Alias(extraer_alias(GLOSARIO["es"], paquete), paquete)
    assert alias.mencionados("cuanto dura la tercera practica") == []
    assert alias.ordinales_ligados("la tercera practica") == {"#3"}
    # «la primera semana» no numera una práctica.
    assert alias.ordinales_ligados("en la primera semana se entrega el plan") == set()


def test_reconoce_el_grupo_en_el_titulo_de_seccion():
    paquete = cargar_paquete("es")
    alias = Alias(extraer_alias(GLOSARIO["es"], paquete), paquete)
    presentes = [alias.grupos[i] for i in alias.presentes("Evaluación de la P1")]
    assert len(presentes) == 1 and "P1" in presentes[0]


def test_linea_de_glosario_y_pregunta_de_definicion():
    assert es_definicion("Práctica Profesional I (P1): primera práctica profesional")
    assert not es_definicion("La P1 dura cuatro semanas.")
    es = cargar_paquete("es")
    assert pide_definicion("¿Qué es la P1?", es)
    assert not pide_definicion("cuanto dura la P1", es)
    assert pide_definicion("What is PI1?", cargar_paquete("en"))
    assert pide_definicion("O que é o EP1?", cargar_paquete("pt"))
