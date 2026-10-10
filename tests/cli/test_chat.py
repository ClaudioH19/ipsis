"""Menú agrupado (``ipsis`` / ``ipsis help``) y modo interactivo (``ipsis chat``)."""
from __future__ import annotations

import argparse
from types import SimpleNamespace

import pytest

from ipsis.cli import main, registro_de_comandos
from ipsis.cli.comandos.chat import ComandoChat
from ipsis.cli.menu import GRUPOS


@pytest.fixture(autouse=True)
def _ingles(monkeypatch):
    monkeypatch.setenv("IPSIS_LANG", "en")


def test_cada_comando_registrado_esta_en_un_grupo_del_menu():
    agrupados = {n for _, nombres in GRUPOS for n in nombres}
    assert {e.nombre for e in registro_de_comandos()} <= agrupados


def test_ipsis_sin_argumentos_muestra_el_menu(capsys):
    assert main([]) == 0
    salida = capsys.readouterr().out
    assert "Measure and calibrate" in salida and "calibrate" in salida and "ipsis chat" in salida


def test_help_de_un_comando_muestra_sus_opciones(capsys):
    assert main(["help", "calibrate"]) == 0
    assert "--alpha" in capsys.readouterr().out


class _Diagnostico(SimpleNamespace):
    pass


def _entrada(lineas):
    """Como el teclado: cuando se acaban las líneas, EOF (Ctrl+D)."""
    pendientes = iter(lineas)

    def leer(_prompt):
        try:
            return next(pendientes)
        except StopIteration:
            raise EOFError from None
    return leer


def test_chat_pregunta_con_un_motor_cargado_una_vez_y_corre_sus_comandos(monkeypatch, capsys):
    import ipsis.aplicacion.consulta as consulta

    motores, preguntas = [], []

    def construir():
        motores.append(object())
        return motores[-1]

    def diagnosticar(pregunta, motor):
        preguntas.append((pregunta, motor))
        return _Diagnostico(estado="ok", respuesta="Cada 90 días.",
                            evidencias=[{"doc_id": "manual", "offset_inicio": 10, "offset_fin": 22}])

    monkeypatch.setattr(consulta, "diagnosticar_pregunta", diagnosticar)
    lineas = ["/help", "/nada", "cada cuanto vence la clave?", "y la otra?", "/diagnostics off", "/exit"]
    chat = ComandoChat(entrada=_entrada(lineas), construir_motor=construir)
    assert chat.ejecutar(argparse.Namespace(diagnostico=False)) == 0
    salida = capsys.readouterr().out
    assert "/diagnostics" in salida and "Unknown command: /nada" in salida
    assert "Cada 90 días." in salida and "manual" in salida
    assert len(motores) == 1 and [p for p, _ in preguntas] == ["cada cuanto vence la clave?", "y la otra?"]


def test_chat_despacha_un_comando_de_la_cli_y_sigue(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    chat = ComandoChat(entrada=_entrada(["/doctor", "/calibrate --help", "/chat"]))
    assert chat.ejecutar(argparse.Namespace(diagnostico=False)) == 0  # termina con EOF
    salida = capsys.readouterr().out
    assert "No ipsis project found in this folder." in salida and "--alpha" in salida
    assert "Unknown command: /chat" in salida
