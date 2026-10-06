"""Banco de consultas naturales y banco de conversaciones: pruebas estructurales.

No usan modelos ni red. Las mediciones (lentas) se corren a mano con
``tests/datos/banco_conversaciones/medir.py`` y las herramientas del banco
universal; ver docs/methodology/evaluation.md.
"""
from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

import pytest
import yaml

from ipsis.ingesta.parsear import parsear_documento

DATOS = Path(__file__).resolve().parents[1] / "datos"
CONSULTAS = DATOS / "banco_consultas"
CONVERSACIONES = DATOS / "banco_conversaciones"
IDIOMAS = ("es", "en", "pt")
CAPACIDADES = {"cantidad", "duracion", "fecha", "persona", "ubicacion", "condicion", "causa", "procedimiento",
               "lista", "si_no"}


def _construir():
    spec = importlib.util.spec_from_file_location("banco_consultas_construir", CONSULTAS / "construir.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_derivados_del_banco_de_consultas_estan_al_dia(idioma):
    manifiesto, casos = _construir().construir(idioma)
    assert (CONSULTAS / idioma / "manifiesto.json").read_text(encoding="utf-8") == manifiesto
    assert (CONSULTAS / idioma / "banco.jsonl").read_text(encoding="utf-8") == casos


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_banco_de_consultas_tiene_60_casos_por_idioma_y_las_mismas_categorias(idioma):
    casos = yaml.safe_load((CONSULTAS / idioma / "casos.yaml").read_text(encoding="utf-8"))
    assert len(casos) == 60 and len({c["id"] for c in casos}) == 60
    categorias = Counter(c["id"].split("-")[1] for c in casos)
    assert categorias == {"exacta": 14, "parafrasis": 20, "trampa": 16, "fuera": 4, "premisa": 3, "ambigua": 3}
    assert {c["capacidad"] for c in casos if "capacidad" in c} <= CAPACIDADES


def _textos_corpus(idioma: str) -> list[str]:
    carpeta = CONSULTAS / idioma / "corpus"
    return [parsear_documento(str(p), doc_id=p.stem, doc_titulo=p.stem, version="1").texto_completo
            for p in sorted(carpeta.glob("*.md"))]


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_cada_respuesta_esperada_de_las_conversaciones_esta_literal_en_el_corpus(idioma):
    conversaciones = yaml.safe_load((CONVERSACIONES / idioma / "conversaciones.yaml").read_text(encoding="utf-8"))
    assert len({c["id"] for c in conversaciones}) == len(conversaciones) == 20
    textos = _textos_corpus(idioma)
    for conversacion in conversaciones:
        primero, *resto = conversacion["turnos"]
        assert "hereda" not in primero, conversacion["id"]  # el primer turno no tiene de quién heredar
        for turno in conversacion["turnos"]:
            assert set(turno) <= {"pregunta", "hereda", "respuesta", "directa"}, conversacion["id"]
            assert not ("respuesta" in turno and turno.get("directa") is False), conversacion["id"]
            if "respuesta" in turno:
                assert any(turno["respuesta"] in t for t in textos), (conversacion["id"], turno["respuesta"])
