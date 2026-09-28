"""Pruebas de extractores genéricos, independientes de cualquier dominio."""
import pytest

from rag.reglas_extraccion import (
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
