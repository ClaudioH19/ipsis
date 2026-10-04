"""Estructura de la CLI (P11.1): punto de entrada, registro, despacho y salida."""
from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
COMANDOS_ACTUALES = {
    ("init",), ("cargar",), ("configurar",), ("indexar",), ("servir",), ("preguntar",), ("doctor",),
    ("snapshot-config",), ("evaluar",), ("calibrar",), ("comparar",), ("benchmark",),
    ("golden", "plantilla"), ("golden", "importar"), ("golden", "validar"), ("golden", "exportar"),
    ("widget", "tema", "listar"), ("widget", "tema", "aplicar"), ("widget", "tema", "vista-previa"),
    ("widget", "exportar"),
}


def test_el_script_rag_sigue_apuntando_a_rag_cli_main():
    datos = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert datos["project"]["scripts"]["rag"] == "rag.cli:main"
    from rag.cli import main

    assert callable(main)
    assert not (RAIZ / "rag" / "cli.py").exists()  # sin módulo puente


def test_importar_la_cli_no_crea_ni_abre_nada(tmp_path):
    codigo = "import rag.cli, os; print(sorted(os.listdir('.')))"
    salida = subprocess.run([sys.executable, "-c", codigo], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert salida.stdout.strip() == "[]"


def _hojas(parser, ruta=()):
    import argparse

    for accion in parser._actions:
        if isinstance(accion, argparse._SubParsersAction):
            for nombre, sub in accion.choices.items():
                if any(isinstance(a, argparse._SubParsersAction) for a in sub._actions):
                    yield from _hojas(sub, ruta + (nombre,))
                else:
                    yield ruta + (nombre,), sub


def test_todos_los_comandos_actuales_quedan_registrados_con_su_command():
    from rag.cli import construir_parser
    from rag.cli.base import Comando

    hojas = dict(_hojas(construir_parser()))
    assert set(hojas) == COMANDOS_ACTUALES
    for ruta, sub in hojas.items():
        assert isinstance(sub.get_default("comando_cli"), Comando), ruta


def test_el_command_recibe_su_namespace_y_llama_al_caso_de_uso(monkeypatch):
    from rag.cli import main

    llamadas = []

    def exportar_falso(formato, salida):
        llamadas.append((formato, salida))
        return Path("golden/exportado.csv"), []

    monkeypatch.setattr("rag.cli.comandos.golden.exportar_golden", exportar_falso)
    assert main(["golden", "exportar", "--formato", "csv", "--salida", "x.csv"]) == 0
    assert llamadas == [("csv", "x.csv")]


@pytest.mark.parametrize("codigo", [0, 1, 7])
def test_el_codigo_del_command_llega_a_main(monkeypatch, codigo):
    from rag.cli import main

    monkeypatch.setattr("rag.cli.comandos.operacion.ComandoDoctor.ejecutar", lambda _self, _args: codigo)
    assert main(["doctor"]) == codigo


def test_python_m_rag_cli_funciona():
    import os

    # Con la salida redirigida, Windows escribiría en cp1252: se fija UTF-8 para leerla.
    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    salida = subprocess.run([sys.executable, "-m", "rag.cli", "--help"], capture_output=True, text=True,
                            encoding="utf-8", env=entorno)
    assert salida.returncode == 0 and "golden" in salida.stdout
