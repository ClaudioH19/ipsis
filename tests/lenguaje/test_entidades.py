"""Pruebas de extractores genéricos, independientes de cualquier dominio."""
import pytest

from rag.lenguaje.entidades import (
    extraer_articulos,
    extraer_decimales,
    extraer_entidades,
    extraer_fechas,
    extraer_plazos,
    extraer_porcentajes,
    tiene_marcador,
)


def test_decimal_coma_y_punto_normalizan_igual():
    valores = {e.valor_norm for e in extraer_decimales("la nota final es 3,9 en la escala de 1,0 a 7,0")}
    assert {"3.9", "1.0", "7.0"} <= valores
    assert [e.valor_norm for e in extraer_decimales("pesa 2.5 kg")] == ["2.5"]
    assert [e.valor_norm for e in extraer_decimales("pesa 2,5 kg")] == ["2.5"]


def test_decimal_fuera_de_la_escala_de_notas():
    assert [e.valor_norm for e in extraer_decimales("soporta 12,75 bar")] == ["12.75"]


@pytest.mark.parametrize("texto", ["1.000.000 de usuarios", "el 12.03.2024", "versión 1.2.3", "3, 20 y 4"])
def test_decimal_no_recorta_numeros_con_varios_separadores(texto):
    assert extraer_decimales(texto) == []


def test_decimal_al_final_de_oracion():
    assert [e.texto for e in extraer_decimales("La nota mínima es 4,0.")] == ["4,0"]


def test_porcentaje_se_normaliza():
    assert extraer_porcentajes("cubre al menos el 20% del total")[0].valor_norm == "20_pct"


@pytest.mark.parametrize("texto", ["cubre el 12,5% del total", "cubre el 12.5 % del total"])
def test_porcentaje_con_decimales_no_se_recorta(texto):
    assert [e.valor_norm for e in extraer_porcentajes(texto)] == ["12.5_pct"]


def test_porcentaje_parcial_no_respalda_otra_cifra():
    """Una pregunta por el 5% no debe encontrar respaldo en un texto con 12,5%."""
    fuente = {e["valor_norm"] for e in extraer_entidades("cubre el 12,5% del total")}
    pregunta = {e["valor_norm"] for e in extraer_entidades("¿cubre el 5%?")}
    assert not pregunta <= fuente


def test_plazo_dias_habiles():
    valores = {e.valor_norm for e in extraer_plazos("dentro de cinco días hábiles siguientes")}
    assert any(v.startswith("5_dia") for v in valores)


def test_plazo_semanas_numerico():
    valores = {e.valor_norm for e in extraer_plazos("duración de 4 semanas y luego 8 semanas")}
    assert {"4_semana", "8_semana"} <= valores


def test_plazo_no_infiere_unidad():
    assert extraer_plazos("podrá extenderse hasta 8") == []


def test_fecha_relativa():
    entidades = extraer_fechas("vence el segundo viernes de enero de cada año")
    assert entidades[0].valor_norm == "2_viernes_de_enero"


def test_articulo_y_anexo():
    valores = {e.valor_norm for e in extraer_articulos("conforme al artículo 18 y al Anexo 3")}
    assert {"articulo_18", "anexo_3"} <= valores


def test_articulo_lista_no_se_trunca():
    valores = {e.valor_norm for e in extraer_articulos("según los artículos 13 y 14")}
    assert "articulo_13_y_14" in valores
    assert "articulo_13" not in valores


def test_articulo_rango_no_se_trunca():
    valores = {e.valor_norm for e in extraer_articulos("lo dispuesto en los artículos 20 a 23")}
    assert "articulo_20_a_23" in valores


def test_toda_entidad_tiene_offset_literal_valido():
    texto = "El plazo es de 15 días hábiles, según el artículo 21, con nota 3,9 y un 20%."
    for entidad in extraer_entidades(texto):
        assert texto[entidad["offset"]:entidad["offset"] + len(entidad["texto"])] == entidad["texto"]


def test_marcadores_excepcion_y_condicion():
    assert tiene_marcador("salvo que sea personalizado", ["salvo", "excepto"])
    assert not tiene_marcador("no hay excepciones", ["salvo", "excepto"])
    assert tiene_marcador("siempre que se cumplan los requisitos", ["siempre que", "cuando"])


# ---------------------------------------------------------------------------
# Entidades universales: fechas numéricas y montos
# ---------------------------------------------------------------------------
import pytest as _pytest

from rag.lenguaje.entidades import extraer_fechas_numericas, extraer_montos


@_pytest.mark.parametrize(("texto", "esperado"), [
    ("Vence el 05/03/2025.", ["2025-03-05"]),
    ("Desde 2025-3-5 hasta 31.12.2025.", ["2025-03-05", "2025-12-31"]),
    ("Versión 1.2.3 y fecha inválida 45/13/2025.", []),
])
def test_fechas_numericas_se_normalizan_a_iso(texto, esperado):
    entidades = extraer_fechas_numericas(texto)
    assert sorted(e.valor_norm for e in entidades) == sorted(esperado)
    for e in entidades:
        assert texto[e.offset:e.offset + len(e.texto)] == e.texto


@_pytest.mark.parametrize(("texto", "esperado"), [
    ("Cuesta $12.500 al mes.", ["monto_12500"]),
    ("Price: US$ 3,50.", ["monto_3.50"]),
    ("Total 1.200,50 EUR y 30 USD.", ["monto_1200.50", "monto_30"]),
    ("R$ 99 ou 10 €.", ["monto_99", "monto_10"]),
    ("Norma ISO 9001 para 12.500 personas.", []),
])
def test_montos_requieren_moneda_y_normalizan_miles(texto, esperado):
    entidades = extraer_montos(texto)
    assert sorted(e.valor_norm for e in entidades) == sorted(esperado)
    for e in entidades:
        assert texto[e.offset:e.offset + len(e.texto)] == e.texto
