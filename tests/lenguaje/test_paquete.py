"""Paquetes de idioma: carga, validación y sobrescrituras del proyecto."""
from __future__ import annotations

from pathlib import Path

import pytest

from rag.cli import main
from rag.lenguaje.paquete import cargar_paquete, idiomas_disponibles


def test_el_paquete_espanol_esta_completo():
    paquete = cargar_paquete("es")
    assert "es" in idiomas_disponibles()
    assert paquete.stemmer == "spanish"
    assert paquete.numeros["dos"] == 2
    assert "enero" in paquete.meses
    assert paquete.conversacional.patrones["saludo"]
    assert paquete.mensajes.sin_respuesta
    assert paquete.interfaz["placeholder"]
    assert "curso" not in paquete.palabras_generales


def test_codigo_inexistente_falla_con_los_disponibles():
    with pytest.raises(ValueError, match="disponibles"):
        cargar_paquete("xx")


def test_el_proyecto_sobrescribe_solo_lo_que_declara(tmp_path: Path):
    (tmp_path / "configuracion").mkdir()
    (tmp_path / "configuracion" / "idioma.yaml").write_text(
        "mensajes:\n  sin_respuesta: Nada por aquí.\n", encoding="utf-8"
    )
    paquete = cargar_paquete("es", proyecto=tmp_path)
    assert paquete.mensajes.sin_respuesta == "Nada por aquí."
    assert paquete.mensajes.premisa_no_encontrada == cargar_paquete("es").mensajes.premisa_no_encontrada


def test_init_rechaza_un_idioma_sin_paquete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--idioma", "xx"]) == 1
    assert not (tmp_path / "configuracion" / "asistente.yaml").exists()
