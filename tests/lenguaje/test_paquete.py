"""Paquetes de idioma: carga, validación y sobrescrituras del proyecto."""
from __future__ import annotations

from pathlib import Path

import pytest

from ipsis.cli import main
from ipsis.lenguaje.paquete import cargar_paquete, idiomas_disponibles


def test_el_paquete_espanol_esta_completo():
    paquete = cargar_paquete("es")
    assert "es" in idiomas_disponibles()
    assert paquete.stemmer == "spanish"
    assert paquete.numeros["dos"] == 2
    assert "enero" in paquete.meses
    assert paquete.conversacional.patrones["greeting"]
    assert paquete.mensajes.sin_seccion and paquete.mensajes.conectores["secuencia"]
    assert paquete.interfaz["placeholder"]


def test_idioma_sin_paquete_usa_el_respaldo_universal():
    """docs/metodologia/multilenguaje.md: reglas universales, términos sin stem y mensajes de en."""
    from ipsis.lenguaje.texto import terminos

    ru, en = cargar_paquete("ru"), cargar_paquete("en")
    assert ru.respaldo and not en.respaldo
    assert ru.codigo == "ru" and ru.stemmer is None
    assert ru.mensajes == en.mensajes and ru.interfaz == en.interfaz
    assert ru.stopwords == [] and ru.meses == [] and ru.numeros == {}
    assert terminos("Как часто меняют фильтр?", ru) == ["как", "часто", "меняют", "фильтр"]


def test_variante_regional_usa_el_paquete_de_su_idioma():
    pt_br = cargar_paquete("pt-br")
    assert pt_br.codigo == "pt-br" and not pt_br.respaldo
    assert pt_br.stemmer == cargar_paquete("pt").stemmer and pt_br.mensajes == cargar_paquete("pt").mensajes


@pytest.mark.parametrize("codigo", ["", "ruso!", "ES", "x"])
def test_codigo_con_forma_invalida_falla(codigo):
    with pytest.raises(ValueError, match="código de idioma inválido"):
        cargar_paquete(codigo)


def test_el_proyecto_sobrescribe_solo_lo_que_declara(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "language.yaml").write_text(
        "mensajes:\n  sin_respuesta: Nada por aquí.\n", encoding="utf-8"
    )
    paquete = cargar_paquete("es", proyecto=tmp_path)
    # Ese texto ahora es del tono: el paquete lo entrega como sobrescritura de tono.
    assert paquete.plantillas_legado == {"no_answer": ["Nada por aquí."]}
    from ipsis.lenguaje.tonos import cargar_tono

    tono = cargar_tono("es", sobrescrituras=paquete.plantillas_legado)
    assert tono.variantes("no_answer") == ["Nada por aquí."]
    assert tono.variantes("premise_not_found") == cargar_tono("es").variantes("premise_not_found")


def test_init_acepta_un_idioma_sin_paquete_y_avisa_el_respaldo(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--language", "ru"]) == 0
    assert "no hay un paquete para 'ru'" in capsys.readouterr().out
    assert main(["configure", "language=es"]) == 0
    assert "Nota" not in capsys.readouterr().out


def test_init_rechaza_un_codigo_de_idioma_invalido(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--language", "ruso!"]) == 1
    assert not (tmp_path / "config" / "assistant.yaml").exists()
