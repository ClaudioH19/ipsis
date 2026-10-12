"""Aceptar una línea resuelve comandos, preserva argumentos y frena ambigüedades."""
import argparse
from threading import Event
import os

import pytest

from ipsis.cli import construir_parser, main
from ipsis.cli.resolucion import ComandoAmbiguo, resolver
from ipsis.cli.comandos.chat import ComandoChat


@pytest.mark.parametrize("entrada,salida", [
    (["ser", "--port", "8123"], ["serve", "--port", "8123"]),
    (["srve"], ["serve"]),
    (["widg", "the", "app", "search"], ["widget", "theme", "apply", "search"]),
    (["load", r"C:\Users\ser\archivo.csv"], ["load", r"C:\Users\ser\archivo.csv"]),
    (["ask", "ser"], ["ask", "ser"]),
    (["serve", "--prt", "8123"], ["serve", "--prt", "8123"]),
    (["--help"], ["--help"]),
    (["ninguno"], ["ninguno"]),
])
def test_solo_normaliza_selectores(entrada, salida):
    assert resolver(entrada, construir_parser())[0] == salida


def test_prefijo_ambiguo_no_se_ejecuta(monkeypatch, capsys):
    with pytest.raises(ComandoAmbiguo) as error:
        resolver(["in"], construir_parser())
    assert error.value.opciones == ["index", "init"]
    monkeypatch.setattr("ipsis.cli.comandos.proyecto.ComandoInit.ejecutar", lambda *_: pytest.fail("ejecutó"))
    assert main(["in"]) == 2
    assert "index, init" in capsys.readouterr().out


def test_enter_resuelve_comandos_propios_y_anidados(monkeypatch, capsys):
    llamadas = []
    monkeypatch.setattr("ipsis.cli.main", lambda argv: llamadas.append(argv) or 0)
    lineas = iter(["/diag on", "/widg the app search", "/ex", "/doctor"])
    chat = ComandoChat(entrada=lambda _: next(lineas))
    assert chat.ejecutar(argparse.Namespace(diagnostico=False)) == 0
    assert chat.diagnostico is True
    assert llamadas == [["widget", "theme", "apply", "search"]]
    assert "diag" in capsys.readouterr().out


def test_serve_demo_factory_modo_y_entorno(monkeypatch, capsys):
    monkeypatch.delenv("IPSIS_DEMO", raising=False)
    monkeypatch.delenv("IPSIS_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("IPSIS_MODE", "production")
    llamadas = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: llamadas.append((a, k, os.environ.get("IPSIS_DEMO"))))
    assert main(["ser", "--demo", "--port", "8123"]) == 0
    assert llamadas[0][0] == ("ipsis.servicio.api:crear_app",)
    assert llamadas[0][1]["factory"] is True and llamadas[0][2] == "1"
    assert "http://127.0.0.1:8123/widget/demo.html" in capsys.readouterr().out
    assert "IPSIS_DEMO" not in os.environ and "IPSIS_ADMIN_TOKEN" not in os.environ
    assert os.environ["IPSIS_MODE"] == "production"


def test_open_implica_demo_y_cancela_apertura_al_terminar(monkeypatch):
    evento, urls = Event(), []
    monkeypatch.setenv("IPSIS_DEMO", "0")
    monkeypatch.setattr("ipsis.aplicacion.vista_servicio.abrir_cuando_listo", lambda url: urls.append(url) or evento)
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: None)
    assert main(["serve", "--open", "--host", "0.0.0.0"]) == 0
    assert urls == ["http://127.0.0.1:8000/widget/demo.html"]
    assert evento.is_set() and os.environ["IPSIS_DEMO"] == "0"


def test_apertura_espera_http_disponible(monkeypatch):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread
    from ipsis.aplicacion.vista_servicio import abrir_cuando_listo

    intentos, urls, abierto = [], [], Event()

    class Pagina(BaseHTTPRequestHandler):
        def do_GET(self):
            intentos.append(self.path)
            self.send_response(503 if len(intentos) == 1 else 200)
            self.end_headers()

        def log_message(self, *_):
            pass

    def abrir(url):
        urls.append(url)
        abierto.set()

    monkeypatch.setattr("ipsis.aplicacion.vista_servicio.webbrowser.open", abrir)
    servidor = HTTPServer(("127.0.0.1", 0), Pagina)
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{servidor.server_port}/widget/demo.html"
    cancelar = abrir_cuando_listo(url, intentos=4)
    try:
        assert abierto.wait(5)
        assert urls == [url] and len(intentos) == 2
    finally:
        cancelar.set()
        servidor.shutdown()
        servidor.server_close()
        hilo.join(5)
