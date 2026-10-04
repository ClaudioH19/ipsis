from __future__ import annotations

import re
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

if __name__ != "__main__":
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    sync_playwright = playwright.sync_playwright


RAIZ = Path(__file__).resolve().parents[2]
WIDGET = RAIZ / "ipsis/servicio/estaticos/widget.js"


def _pagina(api: str) -> str:
    return f"""<!doctype html>
<html lang=\"es\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"></head>
<body><button id=\"antes\">Antes del widget</button>
<ipsis-chat api=\"{api}\" titulo=\"Ayuda documental\"></ipsis-chat>
<script src=\"/widget.js\"></script></body></html>"""


def _crear_app_prueba(base: str) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def pagina():
        return _pagina(base)

    @app.get("/fallo", response_class=HTMLResponse)
    def pagina_fallo():
        return _pagina("http://127.0.0.1:1")

    @app.get("/widget.js")
    def javascript():
        return FileResponse(WIDGET, media_type="text/javascript")

    @app.get("/config")
    def config():
        return {
            "nombre_asistente": "Biblioteca",
            "descripcion_dominio": "Prueba de navegador",
            "saludo": "Hola desde la prueba.",
            "preset": "clasico",
            "densidad": "comoda",
            "citas": "acordeon",
            "mostrar_etiqueta_estado": True,
        }

    @app.post("/consultar")
    def consultar():
        return {
            "estado": "ok",
            "respuesta": "La respuesta está respaldada por el manual.",
            "fragmentos": [{
                "doc_titulo": "Manual",
                "seccion": "Inicio",
                "texto": "Texto literal de respaldo.",
            }],
        }
    return app


@pytest.fixture(scope="module")
def servidor_widget():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        puerto = sock.getsockname()[1]
    base = f"http://127.0.0.1:{puerto}"
    app = _crear_app_prueba(base)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="error"))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.02)
    else:
        raise RuntimeError("El servidor del widget no arrancó")
    yield base
    server.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture(scope="module")
def navegador():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.mark.browser
def test_teclado_dialogo_aria_y_captura_de_foco(navegador, servidor_widget):
    page = navegador.new_page()
    page.goto(servidor_widget)
    abrir = page.get_by_role("button", name=re.compile("Abrir chat"))
    abrir.focus()
    page.keyboard.press("Enter")

    dialogo = page.get_by_role("dialog")
    expect(dialogo).to_be_visible()
    assert dialogo.get_attribute("aria-modal") == "true"
    assert page.evaluate("document.querySelector('ipsis-chat').shadowRoot.activeElement.id") == "rw-input"

    cerrar = page.get_by_role("button", name="Cerrar chat")
    cerrar.focus()
    page.keyboard.press("Shift+Tab")
    # El último enfocable es el enlace «Código fuente» (AGPL §13), bajo el campo.
    assert page.evaluate(
        "document.querySelector('ipsis-chat').shadowRoot.activeElement.className"
    ) == "rw-fuente"
    page.keyboard.press("Tab")
    assert page.evaluate(
        "document.querySelector('ipsis-chat').shadowRoot.activeElement.className"
    ) == "rw-cerrar"

    page.keyboard.press("Escape")
    expect(dialogo).to_be_hidden()
    assert page.evaluate(
        "document.querySelector('ipsis-chat').shadowRoot.activeElement.className"
    ) == "rw-boton"
    page.close()


@pytest.mark.browser
def test_movil_ocupa_la_ventana_completa(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    page.goto(servidor_widget)
    page.get_by_role("button", name=re.compile("Abrir chat")).click()
    caja = page.get_by_role("dialog").bounding_box()

    assert caja is not None
    assert caja["x"] == pytest.approx(0, abs=1)
    assert caja["y"] == pytest.approx(0, abs=1)
    assert caja["width"] == pytest.approx(375, abs=1)
    assert caja["height"] == pytest.approx(667, abs=1)
    page.close()


@pytest.mark.browser
def test_respuesta_y_cita_se_renderizan(navegador, servidor_widget):
    page = navegador.new_page()
    page.goto(servidor_widget)
    page.get_by_role("button", name=re.compile("Abrir chat")).click()
    page.get_by_label("Escribe tu pregunta").fill("¿Qué dice el manual?")
    page.get_by_role("button", name="Enviar pregunta").click()

    expect(page.get_by_text("La respuesta está respaldada por el manual.")).to_be_visible()
    expect(page.get_by_text("1 fuente del documento")).to_be_visible()
    expect(page.get_by_text("Manual › Inicio")).to_be_visible()
    page.close()


@pytest.mark.browser
def test_error_de_red_es_claro_y_permite_reintentar(navegador, servidor_widget):
    page = navegador.new_page()
    page.goto(servidor_widget + "/fallo")
    page.get_by_role("button", name=re.compile("Abrir chat")).click()
    entrada = page.get_by_label("Escribe tu pregunta")
    entrada.fill("¿Hay conexión?")
    page.get_by_role("button", name="Enviar pregunta").click()

    expect(page.get_by_text("No se pudo contactar al asistente. Revisa tu conexión e intenta de nuevo.")).to_be_visible()
    expect(entrada).to_be_enabled()
    expect(entrada).to_be_focused()
    page.close()


if __name__ == "__main__":
    puerto = 8765
    uvicorn.run(_crear_app_prueba(f"http://127.0.0.1:{puerto}"), host="127.0.0.1", port=puerto)
