"""Página de prueba real: tema, widget incrustado y claves sin parámetros de URL."""
import socket
from threading import Thread
import time

import pytest
import uvicorn

from ipsis.cli import main
from ipsis.servicio.api import crear_app
from ipsis.aplicacion.modo import ModoServicio
from tests.consulta.test_motor_v2 import motor
from tests.integracion.test_widget_browser import navegador


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    assert main(["widget", "theme", "apply", "search"]) == 0
    app = crear_app(motor(), modo=ModoServicio(modo="desarrollo", demo=True, token_admin="a" * 40))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        puerto = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="error"))
    hilo = Thread(target=server.run, daemon=True)
    hilo.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(.02)
    else:
        raise RuntimeError("servidor demo no inició")
    try:
        yield f"http://127.0.0.1:{puerto}/widget/demo.html", app
    finally:
        server.should_exit = True
        hilo.join(timeout=5)


@pytest.mark.browser
@pytest.mark.parametrize("ancho,tema", [(1280, "light"), (390, "dark")])
def test_demo_embedded_tema_y_consulta(navegador, demo, ancho, tema):
    from playwright.sync_api import expect

    url, _ = demo
    page = navegador.new_page(viewport={"width": ancho, "height": 900}, color_scheme=tema)
    errores = []
    page.on("pageerror", lambda e: errores.append(str(e)))
    page.goto(url)
    expect(page.get_by_role("heading", name="Explora tus documentos")).to_be_visible()
    expect(page.get_by_role("link", name="Administrar proyecto")).to_be_visible()
    expect(page.locator("#rw-input")).to_be_visible()
    assert page.evaluate("window.Ipsis.state().position") == "embedded"
    assert page.evaluate("getComputedStyle(document.body).getPropertyValue('--rw-fondo') === "
        "getComputedStyle(document.querySelector('ipsis-chat').shadowRoot.querySelector('.rw-raiz')).getPropertyValue('--rw-fondo')")
    page.locator("#rw-input").fill("ponderación")
    page.locator(".rw-enviar").click()
    expect(page.locator(".rw-resultados .rw-resultado")).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errores
    page.close()


@pytest.mark.browser
def test_clave_se_aplica_a_una_instancia_inicializada(navegador, demo):
    from playwright.sync_api import expect

    url, app = demo
    app.state.servicio.claves_widget = ["clave-de-prueba"]
    page = navegador.new_page()
    page.goto(url)
    page.locator(".ayuda summary").click()
    page.locator("#clave").fill("clave-de-prueba")
    with page.expect_navigation():
        page.locator("#clave-form button").click()
    expect(page.locator("#rw-input")).to_be_visible()
    page.locator("#rw-input").fill("ponderación")
    with page.expect_response(lambda r: r.url.endswith("/ask")) as llamada:
        page.locator(".rw-enviar").click()
    assert llamada.value.status == 200
    assert llamada.value.request.headers["x-ipsis-widget-key"] == "clave-de-prueba"
    assert "clave-de-prueba" not in page.url
    page.close()
