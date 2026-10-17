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


def _pedir_ayuda(page, nombre):
    """El menú de ayuda es un icono «?» en el encabezado del asistente: se abre y se elige la opción (se cierra solo)."""
    page.locator(".rw-cabecera .rw-voz-menu summary").click()
    page.get_by_role("button", name=nombre, exact=True).click()


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    assert main(["widget", "theme", "apply", "search"]) == 0
    from ipsis.lenguaje.paquete import cargar_paquete
    m = motor(idioma=cargar_paquete("es"), opciones={"corregir_erratas": False})
    m.plantillas["conversacional"] = m.idioma.conversacional.model_dump()
    app = crear_app(m, modo=ModoServicio(modo="desarrollo", demo=True, token_admin="a" * 40))
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
    if ancho > 480:
        expect(page.get_by_role("heading", name="Encuentra lo que necesitas")).to_be_visible()
        expect(page.get_by_role("link", name="Administrar proyecto")).to_be_visible()
    else:  # en teléfonos la página de prueba no tiene encabezado y el asistente ocupa toda la pantalla
        expect(page.get_by_role("heading", name="Encuentra lo que necesitas")).to_be_hidden()
        expect(page.get_by_role("link", name="Administrar proyecto")).to_be_hidden()
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


@pytest.mark.browser
@pytest.mark.parametrize("ancho,tema", [(1280, "light"), (390, "dark")])
def test_voz_separada_escribe_sin_retrasar_fuentes_y_conserva_resultados(navegador, demo, ancho, tema):
    from pathlib import Path
    from playwright.sync_api import expect
    from tests.integracion.test_widget_browser import _pagina_fuentes

    url, _ = demo
    page = navegador.new_page(viewport={"width": ancho, "height": 900}, color_scheme=tema)
    peticiones = []
    def responder(ruta):
        cuerpo = ruta.request.post_data_json
        peticiones.append(cuerpo)
        if cuerpo["question"] == "hola":
            ruta.fulfill(json={"status": "conversational", "conversational_category": "greeting", "answer": "Hola."})
        else:
            ruta.fulfill(json=_pagina_fuentes(3, False) if cuerpo.get("continuation") else _pagina_fuentes())
    page.route("**/ask", responder)
    page.goto(url.replace("/widget/demo.html", "/"))
    expect(page.locator(".rw-voz")).to_be_visible()
    _pedir_ayuda(page, "Cómo buscar")
    expect(page.locator(".rw-voz")).to_have_attribute("data-typing", "true")
    parcial = page.locator(".rw-voz-texto").inner_text()
    completo = page.locator(".rw-voz .rw-sr-solo").inner_text()
    assert len(parcial) < len(completo)
    page.get_by_role("button", name="Mostrar completo").click()
    expect(page.locator(".rw-voz-texto")).to_have_text(completo)
    # el botón pasa a «Mostrar menos» y conserva el foco: quien lo activó con el teclado puede volver a contraer
    expect(page.locator(".rw-voz-mas")).to_be_focused()
    page.locator("#rw-input").fill("stock")
    page.locator(".rw-enviar").click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-voz")).to_have_attribute("data-category", "results")
    expect(page.locator(".rw-voz")).to_have_attribute("data-typing", "true")
    assert page.locator(".rw-mensajes .rw-voz").count() == 0
    expect(page.locator(".rw-resultado-vista").first).to_have_text("Stock 10")
    page.locator(".rw-resultado-titulo").first.click()
    expect(page.locator(".rw-resultado-contexto").first).to_be_visible()
    page.locator("#rw-input").fill("hola")
    page.locator(".rw-enviar").click()
    expect(page.locator(".rw-voz")).to_have_attribute("data-category", "greeting")
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-resultado-contexto").first).to_be_visible()
    page.locator(".rw-seguir").click()
    expect(page.locator(".rw-resultado")).to_have_count(6)
    assert peticiones[-1]["question"] == "stock" and peticiones[-1]["continuation"] == "pagina-2"
    expect(page.locator(".rw-voz")).to_have_attribute("data-category", "continuation")
    page.get_by_role("button", name="Mostrar completo").click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    captura = Path(__file__).resolve().parents[2] / ".cache/voz-widget" / f"demo-voz-{ancho}.png"
    captura.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(captura), full_page=True)
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("reducido,activadas", [(True, True), (False, False)])
def test_voz_sin_movimiento_y_error_no_reemplaza_fuentes(navegador, demo, reducido, activadas):
    from playwright.sync_api import expect
    from tests.integracion.test_widget_browser import _pagina_fuentes
    from ipsis.lenguaje.voz import voz_del_widget

    url, _ = demo
    banco = voz_del_widget("es")
    page = navegador.new_page(reduced_motion="reduce" if reducido else "no-preference")
    page.route("**/config", lambda r: r.fulfill(json={"response_mode": "ranked_sources", "language": "es",
        "assistant_messages": banco["messages"], "interface": banco["interface"], "animations_enabled": activadas}))
    page.route("**/ask", lambda r: r.fulfill(json=_pagina_fuentes()))
    page.goto(url)
    expect(page.locator(".rw-voz-texto")).not_to_be_empty()
    expect(page.locator(".rw-voz")).to_have_attribute("data-typing", "false")
    expect(page.get_by_role("button", name="Mostrar completo")).to_be_hidden()
    _pedir_ayuda(page, "Qué puedo hacer")
    expect(page.locator(".rw-voz")).to_have_attribute("data-category", "capability")
    assert page.locator(".rw-voz-texto").inner_text() == page.locator(".rw-voz .rw-sr-solo").inner_text()
    page.locator("#rw-input").fill("stock")
    page.locator(".rw-enviar").click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    page.route("**/ask", lambda r: r.fulfill(status=500))
    page.locator("#rw-input").fill("otro")
    page.locator(".rw-enviar").click()
    expect(page.locator(".rw-voz")).to_have_attribute("data-category", "error")
    expect(page.locator(".rw-resultado")).to_have_count(3)
    assert page.locator(".rw-mensajes .rw-msg").count() == 0
    page.close()


@pytest.mark.browser
def test_nuevo_mensaje_cancela_escritura_y_cambio_de_movimiento_la_completa(navegador, demo):
    from playwright.sync_api import expect

    url, _ = demo
    page = navegador.new_page(reduced_motion="no-preference")
    errores = []
    page.on("pageerror", lambda e: errores.append(str(e)))
    page.goto(url)
    expect(page.locator(".rw-voz")).to_be_visible()
    _pedir_ayuda(page, "Cómo buscar")
    anterior = page.locator(".rw-voz .rw-sr-solo").inner_text()
    _pedir_ayuda(page, "Qué puedo hacer")
    siguiente = page.locator(".rw-voz .rw-sr-solo").inner_text()
    assert siguiente != anterior
    page.emulate_media(reduced_motion="reduce")
    expect(page.locator(".rw-voz")).to_have_attribute("data-typing", "false")
    expect(page.locator(".rw-voz-texto")).to_have_text(siguiente)
    _pedir_ayuda(page, "Qué puedo hacer")
    assert page.locator(".rw-voz-texto").inner_text() != siguiente
    assert not errores
    page.close()
