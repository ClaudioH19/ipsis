import argparse
import json
from types import SimpleNamespace

import pytest

from ipsis.cli import main
from ipsis.cli.comandos.chat import ComandoChat
from ipsis.cli.progreso import actividad
from ipsis.nucleo.progreso import informar


@pytest.fixture(autouse=True)
def _ingles(monkeypatch):
    monkeypatch.setenv("IPSIS_LANG", "en")


def test_el_aviso_se_muestra_antes_del_trabajo_y_no_contamina_el_resultado(capsys):
    with actividad("index"):
        inicial = capsys.readouterr()
        assert "Preparing the search index" in inicial.err and not inicial.out
        informar("documento", archivo="manual.pdf", actual=1, total=2)
        antes_de_terminar = capsys.readouterr()
        assert "Reading manual.pdf (1/2)" in antes_de_terminar.err
        informar("vectores", total=4)
        print(json.dumps({"documentos": 2}))
    salida = capsys.readouterr()
    assert json.loads(salida.out) == {"documentos": 2}
    assert "Computing vectors for 4 passage(s)" in salida.err and "[OK]" in salida.err
    assert "\x1b" not in salida.out + salida.err


def test_un_comando_fallido_no_se_anuncia_como_completado(monkeypatch, capsys):
    monkeypatch.setattr("ipsis.cli.comandos.operacion.ComandoDoctor.ejecutar", lambda *_: 1)
    assert main(["doctor"]) == 1
    salida = capsys.readouterr()
    assert "was not completed" in salida.err and "[OK]" not in salida.err


def test_cancelar_restaurar_la_salida_y_no_deja_observadores(capsys):
    with pytest.raises(KeyboardInterrupt), actividad("query"):
        informar("lectura")
        raise KeyboardInterrupt
    primera = capsys.readouterr()
    assert "cancelled" in primera.err and "[OK]" not in primera.err
    informar("verificacion")
    assert capsys.readouterr().err == ""
    with actividad("doctor"):
        pass
    assert "[OK]" in capsys.readouterr().err


def test_una_etapa_personalizada_no_impide_la_consulta(capsys):
    with actividad("query"):
        informar("etapa_del_usuario")
    assert "Running etapa_del_usuario" in capsys.readouterr().err


def test_el_chat_sigue_despues_de_comillas_invalidas_y_de_una_cancelacion(monkeypatch, capsys):
    pendientes = iter(['/load "sin cerrar', "pregunta", "/help", "/exit"])
    def diagnosticar(*_):
        raise KeyboardInterrupt
    monkeypatch.setattr("ipsis.aplicacion.consulta.diagnosticar_pregunta", diagnosticar)
    cerrados = []
    motor = SimpleNamespace(cerrar=lambda: cerrados.append(True))
    chat = ComandoChat(entrada=lambda _: next(pendientes), construir_motor=lambda: motor)
    assert chat.ejecutar(argparse.Namespace(diagnostico=False)) == 0
    salida = capsys.readouterr()
    assert "Check the quotes" in salida.out and "You can keep typing" in salida.out
    assert "uv tool install --python 3.12" in salida.out
    assert cerrados == [True]


def test_ctrl_c_en_la_entrada_cancela_sin_salir(capsys):
    n = 0
    def entrada(_):
        nonlocal n
        n += 1
        if n == 1:
            raise KeyboardInterrupt
        return "/exit"
    assert ComandoChat(entrada=entrada).ejecutar(argparse.Namespace(diagnostico=False)) == 0
    assert n == 2 and "You can keep typing" in capsys.readouterr().out


def test_folio_conserva_la_forma_y_adapta_el_banner_a_una_terminal_angosta(tmp_path, monkeypatch):
    from ipsis.cli.terminal import FOLIO, lineas_banner
    monkeypatch.chdir(tmp_path)
    assert len(FOLIO) == 13 and {len(linea) for linea in FOLIO} == {20}
    assert sum("██" in linea for linea in FOLIO) == 1
    assert all(len(linea) <= 80 for linea in lineas_banner(80))
    estrecho = lineas_banner(40)
    assert estrecho[0].strip() == FOLIO[0].strip()
    assert any("/init" in linea for linea in estrecho)


def test_la_respuesta_no_interpreta_markup_del_documento(capsys):
    from ipsis.cli.terminal import imprimir_respuesta
    texto = "[bold]Conserva esta cita literalmente[/bold]"
    imprimir_respuesta("ok", texto, [{"doc_id": "manual", "offset_inicio": 0, "offset_fin": 10}])
    salida = capsys.readouterr().out
    assert texto in salida and "Evidence: manual offsets 0-10" in salida


def test_la_respuesta_con_formato_conserva_las_citas_literales(monkeypatch):
    import io
    import sys
    import rich.console
    from ipsis.cli.terminal import imprimir_respuesta

    salida = io.StringIO()
    consola = rich.console.Console(file=salida, width=100, color_system=None)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(rich.console, "Console", lambda **_: consola)
    texto = "[bold]Una cita literal[/bold] y https://ejemplo.cl"
    imprimir_respuesta("ok", texto, [{"doc_id": "manual", "offset_inicio": 0, "offset_fin": 10}])
    assert texto in salida.getvalue()
    assert "Folio" in salida.getvalue() and "Sources" in salida.getvalue()


def test_la_instalacion_de_extras_distingue_clon_y_proyecto(tmp_path, monkeypatch):
    from ipsis.recursos.instalacion import comando_extra
    monkeypatch.chdir(tmp_path)
    assert 'uv tool install --force --python 3.12 "ipsis[ocr] @ git+' in comando_extra("ocr")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "otro"\n', encoding="utf-8")
    assert comando_extra("ocr").startswith("uv tool install")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "ipsis"\n', encoding="utf-8")
    assert comando_extra("export") == "uv sync --extra export"
