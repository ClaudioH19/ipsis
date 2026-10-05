"""Catálogo de mensajes: inglés por defecto, español con IPSIS_LANG=es, ambos completos."""
from __future__ import annotations

import re
import string
from pathlib import Path

import pytest

from ipsis.cli import main
from ipsis.recursos.mensajes import IDIOMAS, catalogo, idioma_interfaz, t

RAIZ = Path(__file__).resolve().parents[2]


def _variables(texto: str) -> set[str]:
    return {campo for _, campo, _, _ in string.Formatter().parse(texto) if campo}


def test_los_idiomas_tienen_las_mismas_claves_y_variables():
    ingles = catalogo("en")
    for idioma in IDIOMAS:
        otro = catalogo(idioma)
        assert set(otro) == set(ingles), idioma
        for clave, texto in ingles.items():
            assert _variables(otro[clave]) == _variables(texto), (idioma, clave)


def test_cada_clave_usada_en_el_codigo_existe_y_cada_clave_se_usa():
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "ipsis").rglob("*.py"))
    usadas = set(re.findall(r'["\']([a-z_]+\.[a-z0-9_]+)["\']', codigo))
    claves = set(catalogo("en"))
    secciones = {c.split(".")[0] for c in claves}
    extensiones = {"yaml", "js", "json", "jsonl", "csv", "md", "html", "txt"}  # nombres de archivo, no claves
    usadas = {c for c in usadas if c.split(".")[0] in secciones and c.split(".")[1] not in extensiones}
    # Las claves armadas con un prefijo ("profile." + rol, f"{'doctor.errors'}_one") también cuentan como usadas.
    prefijos = set(re.findall(r'["\']([a-z_]+\.)["\']\s*\+', codigo))
    prefijos |= {c + "_" for c in usadas - claves if any(k.startswith(c + "_") for k in claves)}
    assert {c for c in usadas - claves if c + "_" not in prefijos} == set()
    sin_uso = {c for c in claves - usadas if not any(c.startswith(p) for p in prefijos)}
    assert sin_uso == set()


@pytest.mark.parametrize("valor, esperado", [("", "en"), ("es", "es"), ("es_CL.UTF-8", "es"), ("en", "en"),
                                             ("fr", "en"), ("ES", "es")])
def test_idioma_de_la_interfaz(monkeypatch, valor, esperado):
    monkeypatch.setenv("IPSIS_LANG", valor)
    assert idioma_interfaz() == esperado


def test_ingles_por_defecto_y_espanol_con_ipsis_lang(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("IPSIS_LANG")
    assert t("load.next") == "Next step: 'ipsis index'."
    assert main(["doctor"]) == 1
    assert "No ipsis project found in this folder." in capsys.readouterr().out
    monkeypatch.setenv("IPSIS_LANG", "es")
    assert main(["doctor"]) == 1
    assert "No se encontró un proyecto ipsis en esta carpeta." in capsys.readouterr().out


def test_init_usa_el_idioma_de_la_interfaz_y_sus_nombres(monkeypatch, tmp_path, capsys):
    from apoyo import leer_proyecto

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("IPSIS_LANG")
    assert main(["init", "--profile", "light"]) == 0
    asistente = leer_proyecto(tmp_path / "config" / "assistant.yaml")
    assert asistente["idioma"] == "en" and asistente["nombre_asistente"] == "Document assistant"
    assert "Next step: 'ipsis load <file|folder>', then 'ipsis index'." in capsys.readouterr().out

    otro = tmp_path / "otro"
    otro.mkdir()
    monkeypatch.chdir(otro)
    monkeypatch.setenv("IPSIS_LANG", "es")
    assert main(["init", "--profile", "light"]) == 0
    asistente = leer_proyecto(otro / "config" / "assistant.yaml")
    assert asistente["idioma"] == "es" and asistente["nombre_asistente"] == "Asistente documental"
