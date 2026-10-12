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


# --- banco informal de validación --------------------------------------------------------
INFORMAL = DATOS / "banco_informal"


def _construir_informal():
    spec = importlib.util.spec_from_file_location("banco_informal_construir", INFORMAL / "construir.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_derivados_del_banco_informal_estan_al_dia(idioma):
    manifiesto, casos = _construir_informal().construir(idioma)
    assert (INFORMAL / idioma / "manifiesto.json").read_text(encoding="utf-8") == manifiesto
    assert (INFORMAL / idioma / "banco.jsonl").read_text(encoding="utf-8") == casos


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_banco_informal_usa_el_corpus_de_consultas_y_las_mismas_categorias(idioma):
    """Mismos documentos que el banco de consultas: mide la forma de preguntar, no otro corpus."""
    casos = yaml.safe_load((INFORMAL / idioma / "casos.yaml").read_text(encoding="utf-8"))
    assert len(casos) == 32 and len({c["id"] for c in casos}) == 32
    assert Counter(c["id"].split("-")[1] for c in casos) == {"parafrasis": 20, "trampa": 8, "premisa": 2, "fuera": 2}
    assert {c["capacidad"] for c in casos if "capacidad" in c} <= CAPACIDADES
    for archivo in (CONSULTAS / idioma / "corpus").glob("*.md"):
        assert (INFORMAL / idioma / "corpus" / archivo.name).read_bytes() == archivo.read_bytes()


# --- banco de garantías ------------------------------------------------------------------
GARANTIAS = DATOS / "banco_garantias"


def _construir_garantias():
    spec = importlib.util.spec_from_file_location("banco_garantias_construir", GARANTIAS / "construir.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_derivados_del_banco_de_garantias_estan_al_dia(idioma):
    manifiesto, casos = _construir_garantias().construir(idioma)
    assert (GARANTIAS / idioma / "manifiesto.json").read_text(encoding="utf-8") == manifiesto
    assert (GARANTIAS / idioma / "banco.jsonl").read_text(encoding="utf-8") == casos


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_banco_de_garantias_tiene_las_mismas_categorias_en_los_tres_idiomas(idioma):
    """Los mismos hechos en es/en/pt: la cota de riesgo se compara entre idiomas."""
    casos = yaml.safe_load((GARANTIAS / idioma / "casos.yaml").read_text(encoding="utf-8"))
    assert len(casos) == 134 and len({c["id"] for c in casos}) == 134
    assert Counter(c["id"].split("-")[1] for c in casos) == {
        "exacta": 51, "parafrasis": 47, "trampa": 20, "premisa": 6, "fuera": 6, "ambigua": 4}
    assert {c["capacidad"] for c in casos if "capacidad" in c} <= CAPACIDADES
    for archivo in (CONSULTAS / idioma / "corpus").glob("*.md"):  # distractores
        assert (GARANTIAS / idioma / "corpus" / archivo.name).read_bytes() == archivo.read_bytes()


# --- banco de validación -----------------------------------------------------------------
VALIDACION = DATOS / "banco_validacion"


def _construir_validacion():
    spec = importlib.util.spec_from_file_location("banco_validacion_construir", VALIDACION / "construir.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_derivados_del_banco_de_validacion_estan_al_dia(idioma):
    manifiesto, casos = _construir_validacion().construir(idioma)
    assert (VALIDACION / idioma / "manifiesto.json").read_text(encoding="utf-8") == manifiesto
    assert (VALIDACION / idioma / "banco.jsonl").read_text(encoding="utf-8") == casos


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_banco_de_validacion_tiene_las_mismas_categorias_en_los_tres_idiomas(idioma):
    """Retenido: documentos propios y los de consultas como distractores."""
    casos = yaml.safe_load((VALIDACION / idioma / "casos.yaml").read_text(encoding="utf-8"))
    assert len(casos) == 99 and len({c["id"] for c in casos}) == 99
    assert Counter(c["id"].split("-")[1] for c in casos) == {
        "exacta": 44, "parafrasis": 23, "trampa": 20, "premisa": 4, "fuera": 4, "ambigua": 4}
    assert {c["capacidad"] for c in casos if "capacidad" in c} <= CAPACIDADES
    for archivo in (CONSULTAS / idioma / "corpus").glob("*.md"):  # distractores
        assert (VALIDACION / idioma / "corpus" / archivo.name).read_bytes() == archivo.read_bytes()


# --- banco coloquial ---------------------------------------------------------------------
COLOQUIAL = DATOS / "banco_coloquial"


def _construir_coloquial():
    spec = importlib.util.spec_from_file_location("banco_coloquial_construir", COLOQUIAL / "construir.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_derivados_del_banco_coloquial_estan_al_dia(idioma):
    manifiesto, casos = _construir_coloquial().construir(idioma)
    assert (COLOQUIAL / idioma / "manifiesto.json").read_text(encoding="utf-8") == manifiesto
    assert (COLOQUIAL / idioma / "banco.jsonl").read_text(encoding="utf-8") == casos


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_banco_coloquial_usa_el_corpus_de_validacion(idioma):
    """Mismos documentos que el banco de validación: mide el vocabulario, no otro corpus."""
    casos = yaml.safe_load((COLOQUIAL / idioma / "casos.yaml").read_text(encoding="utf-8"))
    assert len(casos) == 30 and len({c["id"] for c in casos}) == 30
    assert Counter(c["id"].split("-")[1] for c in casos) == {"parafrasis": 24, "trampa": 4, "fuera": 2}
    assert {c["capacidad"] for c in casos if "capacidad" in c} <= CAPACIDADES
    for archivo in (VALIDACION / idioma / "corpus").glob("*.md"):
        assert (COLOQUIAL / idioma / "corpus" / archivo.name).read_bytes() == archivo.read_bytes()


# --- banco de erratas --------------------------------------------------------------------
ERRATAS = DATOS / "banco_erratas"


def _modulo_erratas(nombre):
    spec = importlib.util.spec_from_file_location(f"banco_erratas_{nombre}", ERRATAS / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("conjunto", ["diseno", "validacion"])
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_derivados_del_banco_de_erratas_estan_al_dia(conjunto, idioma):
    manifiesto, casos = _modulo_erratas("construir").construir(conjunto, idioma)
    assert (ERRATAS / conjunto / idioma / "manifiesto.json").read_text(encoding="utf-8") == manifiesto
    assert (ERRATAS / conjunto / idioma / "banco.jsonl").read_text(encoding="utf-8") == casos


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_las_erratas_son_deterministas_y_cambian_la_pregunta(idioma):
    """La misma semilla da la misma errata; cada caso difiere de su original."""
    generar = _modulo_erratas("generar")
    for conjunto in ("diseno", "validacion"):
        casos = yaml.safe_load((ERRATAS / conjunto / idioma / "casos.yaml").read_text(encoding="utf-8"))
        assert casos and all(c["pregunta"] != c["original"] and c["erratas"] for c in casos)
        for c in casos[:10]:
            assert generar.errar(c["original"], idioma, f"{conjunto}:{c['id']}")[0] == c["pregunta"]


# --- banco de términos (diseño y validación retenida) ----------------------------------------
TERMINOS = DATOS / "banco_terminos"


def _construir_terminos():
    spec = importlib.util.spec_from_file_location("banco_terminos_construir", TERMINOS / "construir.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("conjunto", ("diseno", "validacion"))
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_derivados_del_banco_de_terminos_estan_al_dia(conjunto, idioma):
    manifiesto, casos = _construir_terminos().construir(conjunto, idioma)
    assert (TERMINOS / conjunto / idioma / "manifiesto.json").read_text(encoding="utf-8") == manifiesto
    assert (TERMINOS / conjunto / idioma / "banco.jsonl").read_text(encoding="utf-8") == casos
