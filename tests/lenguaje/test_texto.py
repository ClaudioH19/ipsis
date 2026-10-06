"""Términos y oraciones independientes del idioma."""
from __future__ import annotations

import pytest

from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.texto import dividir_oraciones, terminos, tokenizar

TEXTOS = {
    "es": "¿Cada cuánto se cambia el filtro? Se cambia cada 6 meses. El precio es 1.5 UF.",
    "en": "How often is the filter changed? Every 6 months. The price is 1.5 USD.",
    "pt": "Com que frequência se troca o filtro? A cada 6 meses. O preço é 1,5 reais.",
    "ru": "Как часто меняют фильтр? Каждые 6 месяцев. Цена 1.5 рубля.",
    "ja": "フィルターはいつ交換しますか？6か月ごとです。価格は1.5ドルです。",
}


@pytest.mark.parametrize("idioma", sorted(TEXTOS))
def test_oraciones_con_offsets_exactos(idioma: str):
    texto = TEXTOS[idioma]
    rangos = dividir_oraciones(texto)
    assert len(rangos) == 3
    for ini, fin in rangos:
        oracion = texto[ini:fin]
        assert oracion == oracion.strip() and oracion


def test_un_punto_decimal_no_corta_la_oracion():
    texto = "El precio es 1.5 UF. Fin."
    assert [texto[i:f] for i, f in dividir_oraciones(texto)] == ["El precio es 1.5 UF.", "Fin."]


@pytest.mark.parametrize("idioma", sorted(TEXTOS))
def test_tokenizar_conserva_palabras_de_cualquier_escritura(idioma: str):
    tokens = tokenizar(TEXTOS[idioma])
    assert tokens
    assert all(t == t.casefold() for t in tokens)


def test_tokenizar_quita_tildes_solo_en_escritura_latina():
    assert tokenizar("Garantía ÑANDÚ") == ["garantia", "nandu"]
    assert tokenizar("фильтр") == ["фильтр"]
    assert tokenizar("Garantía", normalizado=False) == ["garantía"]


def test_terminos_con_stemmer_unifican_plurales_y_tildes():
    es = cargar_paquete("es")
    assert terminos("documentos", es) == terminos("documento", es)
    assert terminos("garantía", es) == terminos("garantias", es)


def test_terminos_sin_paquete_son_los_tokens():
    assert terminos("Los Documentos") == ["los", "documentos"]


def test_un_rotulo_numerado_va_con_la_oracion_que_sigue():
    """«Artículo 4.» no es una oración: sin él, «artículo» faltaba en la que responde."""
    texto = "Hola. Artículo 4. Si el cliente no está, se cobra un recargo. 4.2. Otro paso."
    assert [texto[i:f] for i, f in dividir_oraciones(texto)] == [
        "Hola.", "Artículo 4. Si el cliente no está, se cobra un recargo.", "4.2. Otro paso."]
    # Al final del texto queda como está.
    fin = "Fin. Artículo 9."
    assert [fin[i:f] for i, f in dividir_oraciones(fin)] == ["Fin.", "Artículo 9."]
