"""Estructura de la CLI (P11.1): punto de entrada, registro, despacho y salida."""
from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
COMANDOS_ACTUALES = {
    ("prepare",),
    ("init",), ("load",), ("configure",), ("profile", "show"), ("profile", "set"), ("index",), ("sync",),
    ("models", "list"), ("models", "download"), ("models", "verify"), ("models", "export"),
    ("personality", "show"), ("personality", "validate"), ("personality", "tone", "list"),
    ("personality", "tone", "apply"), ("personality", "tone", "try"), ("personality", "avatar", "list"),
    ("personality", "avatar", "import"), ("personality", "avatar", "apply"), ("personality", "avatar", "events"),
    ("personality", "avatar", "assign"), ("personality", "avatar", "colors"),
    ("serve",), ("chat",), ("ask",), ("help",), ("doctor",), ("audit",),
    ("snapshot-config",), ("evaluate",), ("compare",), ("benchmark",),
    ("golden", "template"), ("golden", "import"), ("golden", "validate"), ("golden", "export"),
    ("widget", "theme", "list"), ("widget", "theme", "apply"), ("widget", "theme", "preview"),
    ("widget", "style", "show"), ("widget", "style", "set"),
    ("widget", "export"), ("widget", "snippet"), ("deploy", "prepare"),
}


def test_el_script_rag_sigue_apuntando_a_rag_cli_main():
    datos = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert datos["project"]["scripts"]["ipsis"] == "ipsis.cli:main"
    from ipsis.cli import main

    assert callable(main)
    assert not (RAIZ / "ipsis" / "cli.py").exists()  # sin módulo puente


def test_importar_la_cli_no_crea_ni_abre_nada(tmp_path):
    codigo = "import ipsis.cli, os; print(sorted(os.listdir('.')))"
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
    from ipsis.cli import construir_parser
    from ipsis.cli.base import Comando

    hojas = dict(_hojas(construir_parser()))
    assert set(hojas) == COMANDOS_ACTUALES
    for ruta, sub in hojas.items():
        assert isinstance(sub.get_default("comando_cli"), Comando), ruta


def test_el_command_recibe_su_namespace_y_llama_al_caso_de_uso(monkeypatch):
    from ipsis.cli import main

    llamadas = []

    def exportar_falso(formato, salida):
        llamadas.append((formato, salida))
        return Path("golden/exportado.csv"), []

    monkeypatch.setattr("ipsis.cli.comandos.golden.exportar_golden", exportar_falso)
    assert main(["golden", "export", "--format", "csv", "--output", "x.csv"]) == 0
    assert llamadas == [("csv", "x.csv")]


@pytest.mark.parametrize("codigo", [0, 1, 7])
def test_el_codigo_del_command_llega_a_main(monkeypatch, codigo):
    from ipsis.cli import main

    monkeypatch.setattr("ipsis.cli.comandos.operacion.ComandoDoctor.ejecutar", lambda _self, _args: codigo)
    assert main(["doctor"]) == codigo


def test_python_m_rag_cli_funciona():
    import os

    # Con la salida redirigida, Windows escribiría en cp1252: se fija UTF-8 para leerla.
    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    salida = subprocess.run([sys.executable, "-m", "ipsis.cli", "--help"], capture_output=True, text=True,
                            encoding="utf-8", env=entorno)
    assert salida.returncode == 0 and "golden" in salida.stdout


def test_version(capsys):
    from ipsis import __version__
    from ipsis.cli import main

    with pytest.raises(SystemExit) as salida:
        main(["--version"])
    assert salida.value.code == 0 and capsys.readouterr().out.strip() == f"ipsis {__version__}"
