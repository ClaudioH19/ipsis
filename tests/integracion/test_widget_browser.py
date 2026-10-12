from __future__ import annotations

import re
import json
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
            "assistant_name": "Biblioteca",
            "domain_description": "Prueba de navegador",
            "greeting": "Hola desde la prueba.",
            "preset": "classic",
            "density": "comfortable",
            "citations": "accordion",
            "show_status_label": True,
        }

    @app.post("/ask")
    def consultar():
        return {
            "status": "ok",
            "answer": "La respuesta está respaldada por el manual.",
            "fragments": [{
                "doc_title": "Manual",
                "section": "Inicio",
                "text": "Texto literal de respaldo.",
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
    abrir = page.get_by_role("button", name=re.compile("Open chat"))
    abrir.focus()
    page.keyboard.press("Enter")

    dialogo = page.get_by_role("dialog")
    expect(dialogo).to_be_visible()
    assert dialogo.get_attribute("aria-modal") == "true"
    assert page.evaluate("document.querySelector('ipsis-chat').shadowRoot.activeElement.id") == "rw-input"

    cerrar = page.get_by_role("button", name="Close chat")
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
def test_fuentes_ordenadas_muestra_tarjetas_y_contexto_sin_html_crudo(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    fuente = 'Antes 😊.\nProducto A: <img src=x onerror="window.inyectado=true"> stock 10.\nDespués.'
    publico = {"status": "related", "response_mode": "ranked_sources", "answer": "1 resultado para revisar.",
        "answer_blocks": [{"type": "message", "text": "1 resultado para revisar."}],
        "fragments": [{"chunk_id": "producto", "doc_title": "Inventario", "section": "Productos", "version": "1",
            "source_name": "inventario.txt",
            "rank": 1, "offset_start": 100, "offset_end": 100 + len(fuente), "text": fuente,
            "match_start": 100 + fuente.index("Producto"), "match_end": 100 + fuente.index("\nDespués"),
            "truncated": False}]}
    page.route("**/ask", lambda ruta: ruta.fulfill(json=json.loads(json.dumps(publico))))
    page.goto(servidor_widget)
    page.get_by_role("button", name=re.compile("Open chat")).click()
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Send question").click()
    tarjeta = page.locator(".rw-resultado")
    expect(tarjeta).to_have_count(1)
    expect(tarjeta.locator(".rw-resultado-titulo")).to_have_text("Productos")
    expect(tarjeta.locator(".rw-resultado-contexto")).to_be_hidden()
    expect(tarjeta.locator(".rw-resultado-vista")).to_be_visible()
    expect(tarjeta.locator(".rw-resultado-vista")).to_contain_text("stock 10")
    expect(tarjeta.locator(".rw-resultado-vista")).to_have_text(fuente[fuente.index("Producto"):fuente.index("\nDespués")])
    tarjeta.locator(".rw-resultado-titulo").click()
    expect(tarjeta.locator(".rw-resultado-origen").first).to_contain_text("inventario.txt")
    assert page.locator(".rw-citas").count() == 0
    expect(tarjeta.locator(".rw-resultado-contexto")).to_have_text(fuente)
    assert tarjeta.locator("img").count() == 0 and page.evaluate("window.inyectado === undefined")
    assert tarjeta.evaluate("e => e.getBoundingClientRect().right") <= 375
    page.close()


def _pagina_fuentes(inicio=0, continuar=True):
    return {"status": "related", "response_mode": "ranked_sources", "answer": "Sources",
            "answer_blocks": [{"type": "message", "text": "3 results"}],
            "has_more": continuar, "continuation": "pagina-2" if continuar else None,
            "fragments": [{"chunk_id": str(i), "doc_title": "Inventory", "section": "Products",
                "version": "1", "rank": i + 1, "offset_start": 0, "offset_end": 8,
                "text": "Stock 10", "match_start": 0, "match_end": 8} for i in range(inicio, inicio + 3)]}


@pytest.mark.browser
@pytest.mark.parametrize("ancho", [375, 900])
def test_tablas_reales_con_columnas_contexto_literal_y_tipografia(navegador, servidor_widget, tmp_path, ancho):
    from tests.indice.test_presentacion import documento_tabla
    from ipsis.ingesta.parsear import parsear_docx
    from ipsis.indice.presentacion import bloques_fuente

    d = parsear_docx(str(documento_tabla(tmp_path)), "d", "Manual", "1")
    fuente = d.texto_completo
    inicio = fuente.index("Control")
    f = {"chunk_id": "tabla", "doc_title": "Manual", "section": "Evaluación > Tabla 1 > Instrumento | Peso | Observaciones",
         "version": "1", "rank": 1, "offset_start": 0, "offset_end": len(fuente), "text": fuente,
         "match_start": inicio, "match_end": fuente.index("\n", inicio),
         "source_blocks": bloques_fuente(d, 0, len(fuente))}
    page = navegador.new_page(viewport={"width": ancho, "height": 900})
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Manual", "response_mode": "ranked_sources",
               "preset": "search", "text_align": "justify"}))
    page.route("**/ask", lambda r: r.fulfill(json={"status": "related", "response_mode": "ranked_sources", "fragments": [f]}))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Manual").click()
    page.locator("#rw-input").fill("seguridad")
    page.get_by_role("button", name="Search", exact=True).click()
    titulo = page.get_by_role("heading", name="Tabla 1", level=4)
    expect(titulo).to_be_visible()
    expect(page.locator(".rw-busqueda-contador")).to_have_text('1 result for “seguridad”')
    vista = page.locator(".rw-resultado-vista")
    expect(vista.locator("table")).to_be_visible()
    expect(vista.locator("th")).to_have_count(3)
    expect(vista.locator("tr").nth(1).locator("td")).to_have_count(3)
    expect(vista.locator("tr").nth(1).locator("td").last).to_have_text("")
    expect(vista.locator("strong")).to_have_text("seguridad")
    titulo.get_by_role("button").click()
    contexto = page.locator(".rw-resultado-contexto")
    expect(contexto.get_by_role("heading", name="Evaluación", level=5)).to_be_visible()
    assert contexto.locator("p").first.evaluate("e => getComputedStyle(e).textAlign") == "justify"
    assert contexto.locator("td").first.evaluate("e => getComputedStyle(e).textAlign") == "start"
    scroll = contexto.locator(".rw-tabla-scroll")
    scroll.focus()
    expect(scroll).to_be_focused()
    assert scroll.evaluate("e => e.getBoundingClientRect().right") <= ancho
    if ancho == 375:
        assert scroll.evaluate("e => e.scrollWidth > e.clientWidth")
    page.get_by_text("View original text", exact=True).click()
    expect(page.locator(".rw-fuente-literal pre")).to_have_text(fuente)
    assert page.locator(".rw-resultado img").count() == 0
    page.screenshot(path=str(tmp_path / f"tabla-{ancho}.png"))
    page.close()


@pytest.mark.browser
def test_estructura_inconsistente_o_barra_en_prosa_no_inventa_tablas(navegador, servidor_widget):
    page = navegador.new_page()
    fuente = "Usa A | B como alternativas.\n\nLa frase siguiente."
    publico = _pagina_fuentes(0, False)
    publico["fragments"] = [{"chunk_id": "texto", "doc_title": "Manual", "section": "Uso", "version": "1",
         "offset_start": 0, "offset_end": len(fuente), "text": fuente, "source_blocks": [
             {"kind": "table", "text": "contenido inventado", "offset_start": 0, "offset_end": len(fuente),
              "columns": 2, "rows": []}]}]
    page.route("**/ask", lambda r: r.fulfill(json=publico))
    page.goto(servidor_widget)
    page.get_by_role("button", name=re.compile("Open chat")).click()
    page.locator("#rw-input").fill("alternativas")
    page.get_by_role("button", name="Send question").click()
    page.locator(".rw-resultado-titulo").click()
    contexto = page.locator(".rw-resultado-contexto")
    expect(contexto).to_have_text(fuente)
    expect(contexto.locator("p")).to_have_count(2)
    assert contexto.locator("table").count() == 0
    page.close()


@pytest.mark.browser
def test_tres_desplegables_continuacion_sin_doble_click_y_reformulacion(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    peticiones = []

    def responder(ruta):
        cuerpo = ruta.request.post_data_json
        peticiones.append(cuerpo)
        ruta.fulfill(json=_pagina_fuentes(3, False) if cuerpo.get("continuation") else _pagina_fuentes())

    page.route("**/ask", responder)
    page.goto(servidor_widget)
    page.get_by_role("button", name=re.compile("Open chat")).click()
    entrada = page.locator("#rw-input")
    entrada.fill("stock")
    page.get_by_role("button", name="Send question").click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-resultado-contexto").first).to_be_hidden()
    summary = page.locator(".rw-resultado summary").first
    summary.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".rw-resultado-contexto").first).to_be_visible()
    page.get_by_role("button", name="Show more results").evaluate("b => { b.click(); b.click(); }")
    expect(page.locator(".rw-resultado")).to_have_count(6)
    expect(page.get_by_text("No more results in this search. Try rephrasing your question.")).to_be_visible()
    assert len(peticiones) == 2 and peticiones[1]["continuation"] == "pagina-2"
    assert page.locator(".rw-msg-usuario").count() == 0
    assert page.locator(".rw-resultado").evaluate_all("es => es.map(e => e.value)") == list(range(1, 7))
    entrada.fill("delivery")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-busqueda-contador")).to_contain_text("delivery")
    expect(page.locator(".rw-resultado")).to_have_count(3)
    assert "continuation" not in peticiones[2] and peticiones[2]["question"] == "delivery"
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("error", [409, 503])
def test_continuacion_expirada_o_reintento_de_error_temporal(navegador, servidor_widget, error):
    page = navegador.new_page()
    peticiones = []

    def responder(ruta):
        cuerpo = ruta.request.post_data_json
        peticiones.append(cuerpo)
        if len(peticiones) == 2:
            ruta.fulfill(status=error, json={"detail": "retry"})
        else:
            ruta.fulfill(json=_pagina_fuentes(3, False) if cuerpo.get("continuation") else _pagina_fuentes())

    page.route("**/ask", responder)
    page.goto(servidor_widget)
    page.get_by_role("button", name=re.compile("Open chat")).click()
    entrada = page.locator("#rw-input")
    entrada.fill("stock")
    page.get_by_role("button", name="Send question").click()
    mas = page.get_by_role("button", name="Show more results")
    mas.click()
    expect(entrada).to_be_enabled()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    if error == 409:
        expect(mas).to_be_disabled()
        expect(page.locator(".rw-voz-texto")).to_have_text(
            "This search has expired. Submit your question again.")
        entrada.fill("stock")
        page.get_by_role("button", name="Search", exact=True).click()
        expect(mas).to_be_enabled()
        expect(page.locator(".rw-resultado")).to_have_count(3)
        assert "continuation" not in peticiones[2]
    else:
        expect(mas).to_be_enabled()
        mas.click()
        expect(page.locator(".rw-resultado")).to_have_count(6)
        assert peticiones[1]["continuation"] == peticiones[2]["continuation"]
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("preset", ["classic", "minimal", "editorial", "contrast", "search", "search_compact"])
def test_busqueda_tiene_barra_arriba_extractos_visibles_y_teclado(navegador, servidor_widget, preset):
    page = navegador.new_page(viewport={"width": 375, "height": 667}, color_scheme="dark" if preset == "contrast" else "light")
    page.route("**/config", lambda r: r.fulfill(json={
        "assistant_name": "Library", "response_mode": "ranked_sources", "greeting": "Hello",
        "preset": preset, "density": "compact" if preset == "search_compact" else "comfortable"}))
    publico = _pagina_fuentes()
    publico["fragments"][0].update(section="Inventory > Products", text="Pr\u00e1ctica: stock 10.",
                                  offset_end=19, match_end=19, source_name="inventory.txt")
    page.route("**/ask", lambda r: r.fulfill(json=publico))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Library").click()
    entrada = page.get_by_label("Search your documents")
    expect(page.get_by_text("Enter a question or keywords to find information.")).to_be_visible()
    assert page.evaluate("Array.from(document.querySelector('ipsis-chat').shadowRoot.querySelectorAll('.rw-form,.rw-mensajes')).map(e => e.className)") == ["rw-form", "rw-mensajes"]
    entrada.fill("practica stock")
    page.get_by_role("button", name="Search", exact=True).click()
    resultados = page.get_by_role("region", name="Search results")
    expect(resultados.locator(".rw-resultado")).to_have_count(3)
    expect(entrada).to_have_value("practica stock")
    expect(resultados.locator(".rw-resultado-vista").first).to_be_visible()
    expect(resultados.locator(".rw-resultado-vista strong").first).to_have_text("Pr\u00e1ctica")
    assert resultados.locator(".rw-msg-usuario").count() == 0
    titulo = resultados.locator(".rw-resultado-titulo").first
    titulo.focus()
    page.keyboard.press("Enter")
    expect(titulo).to_have_attribute("aria-expanded", "true")
    expect(resultados.locator(".rw-resultado-contexto").first).to_be_visible()
    assert titulo.evaluate("e => e.getBoundingClientRect().right") <= 375
    page.close()


@pytest.mark.browser
def test_movil_ocupa_la_ventana_completa(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    page.goto(servidor_widget)
    page.get_by_role("button", name=re.compile("Open chat")).click()
    page.evaluate("document.querySelector('ipsis-chat').shadowRoot.getAnimations().forEach(a => a.finish())")  # medir con la animación de entrada ya terminada
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
    page.get_by_role("button", name=re.compile("Open chat")).click()
    page.get_by_label("Type your question").fill("¿Qué dice el manual?")
    page.get_by_role("button", name="Send question").click()

    expect(page.get_by_text("La respuesta está respaldada por el manual.")).to_be_visible()
    expect(page.get_by_text("1 source from the document")).to_be_visible()
    expect(page.get_by_text("Manual › Inicio")).to_be_visible()
    page.close()


@pytest.mark.browser
def test_error_de_red_es_claro_y_permite_reintentar(navegador, servidor_widget):
    page = navegador.new_page()
    page.goto(servidor_widget + "/fallo")
    page.get_by_role("button", name=re.compile("Open chat")).click()
    entrada = page.get_by_label("Type your question")
    entrada.fill("¿Hay conexión?")
    page.get_by_role("button", name="Send question").click()

    expect(page.get_by_role("log").get_by_text("Could not reach the assistant. Check your connection and try again.")).to_be_visible()
    expect(entrada).to_be_enabled()
    expect(entrada).to_be_focused()
    page.close()


if __name__ == "__main__":
    puerto = 8765
    uvicorn.run(_crear_app_prueba(f"http://127.0.0.1:{puerto}"), host="127.0.0.1", port=puerto)


@pytest.mark.browser
@pytest.mark.parametrize("movimiento", ["no-preference", "reduce"])
def test_cerrar_anima_la_salida_y_luego_oculta(navegador, servidor_widget, movimiento):
    page = navegador.new_page(reduced_motion=movimiento)
    page.goto(servidor_widget)
    boton = page.get_by_role("button", name=re.compile("Open chat"))
    boton.click()
    dialogo = page.get_by_role("dialog")
    expect(dialogo).to_be_visible()
    page.keyboard.press("Escape")
    # El estado cambia en el acto, aunque el panel todavía se esté encogiendo.
    assert page.evaluate("window.Ipsis.state().open") is False
    assert boton.get_attribute("aria-expanded") == "false"
    if movimiento == "reduce":
        assert page.evaluate("document.querySelector('ipsis-chat').shadowRoot"
                             ".querySelector('.rw-panel').hidden") is True
    expect(dialogo).to_be_hidden()
    # Reabrir enseguida cancela una salida a medias.
    boton.click()
    expect(dialogo).to_be_visible()
    page.wait_for_timeout(700)
    expect(dialogo).to_be_visible()
    page.close()
