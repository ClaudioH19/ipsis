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
def test_busqueda_tiene_barra_abajo_extractos_visibles_y_teclado(navegador, servidor_widget, preset):
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
    entrada = page.get_by_label("Type your search")
    expect(page.get_by_text("Enter a question or keywords to find information.")).to_be_visible()
    assert page.evaluate("Array.from(document.querySelector('ipsis-chat').shadowRoot.querySelectorAll('.rw-form,.rw-mensajes')).map(e => e.className)") == ["rw-mensajes", "rw-form"]
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
    expect(page.get_by_text("1 source consulted")).to_be_visible()
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


@pytest.mark.browser
@pytest.mark.parametrize("preset", ["classic", "minimal", "editorial", "contrast", "search", "search_compact",
                                    "ocean", "forest", "midnight"])
@pytest.mark.parametrize("modo", ["light", "dark"])
def test_temas_reales_demarcadores_y_titulos_personalizables(navegador, servidor_widget, tmp_path, preset, modo):
    from ipsis.aplicacion.estilos import render_css
    from ipsis.aplicacion.widget import aplicar_preset, presentacion_publica

    tema = aplicar_preset(preset, str(tmp_path / "styles.yaml"))
    page = navegador.new_page(viewport={"width": 375, "height": 800}, color_scheme=modo)
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources",
               **presentacion_publica(tema)}))
    page.route("**/styles.css", lambda r: r.fulfill(body=render_css(tema), content_type="text/css"))
    page.route("**/ask", lambda r: r.fulfill(json=_pagina_fuentes(continuar=False)))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-resultado-numero")).to_have_text(["1", "2", "3"])
    tarjeta = page.locator(".rw-resultado").first
    assert tarjeta.evaluate("e => parseFloat(getComputedStyle(e).borderBottomWidth)") > 0 or tarjeta.evaluate(
        "e => parseFloat(getComputedStyle(e).borderInlineStartWidth)") > 0
    titulo = tarjeta.locator(".rw-resultado-titulo")
    assert titulo.evaluate("e => getComputedStyle(e).color") == titulo.evaluate(
        "e => { var x=document.createElement('span');x.style.color='var(--rw-titulo)';e.append(x);"
        "var c=getComputedStyle(x).color;x.remove();return c; }")
    assert tarjeta.evaluate("e => e.getBoundingClientRect().right") <= 375
    if preset in {"ocean", "forest", "midnight"}:
        page.screenshot(path=str(tmp_path / f"{preset}-{modo}.png"), full_page=True)
    # Una asignación personalizada gana incluso en search/search_compact/contrast.
    page.evaluate("document.querySelector('ipsis-chat').shadowRoot.querySelector('.rw-raiz').style.setProperty('--rw-tamano-titulo','23px')")
    assert titulo.evaluate("e => getComputedStyle(e).fontSize") == "23px"
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_preguntas_y_mensajes_localizados_sin_consultas_automaticas(navegador, servidor_widget, tmp_path, idioma):
    from ipsis.aplicacion.proyecto import interfaz_del_idioma
    from ipsis.lenguaje.voz import respuesta_fija, voz_del_widget

    voz = voz_del_widget(idioma)
    interfaz = {**interfaz_del_idioma(idioma), **voz["interface"]}
    page = navegador.new_page(viewport={"width": 375, "height": 667}, reduced_motion="reduce")
    consultas = []
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources",
               "language": idioma, "interface": interfaz, "assistant_messages": voz["messages"],
               "suggested_questions": voz["suggestions"], "default_questions": voz["questions"],
               "widget_content": {"welcome_title": "Mi biblioteca"}}))
    page.on("request", lambda r: consultas.append(r.url) if r.url.endswith('/ask') else None)
    page.goto(servidor_widget)
    page.get_by_role("button", name=interfaz["search_open"].replace("{title}", "Biblioteca")).click()
    expect(page.get_by_role("heading", name="Mi biblioteca")).to_be_visible()
    expect(page.locator(".rw-sugerencias button")).to_have_count(6)
    page.locator(".rw-sugerencias button").first.click()
    expect(page.locator("#rw-input")).to_have_value(voz["suggestions"][0])
    expect(page.locator("#rw-input")).to_be_focused()
    for categoria in ("about", "limits", "examples"):
        page.locator(".rw-voz-menu summary").click()
        page.get_by_role("button", name=interfaz["voice_" + categoria], exact=True).click()
        assert page.locator(".rw-voz-texto").inner_text() in voz["messages"][categoria]
    assert consultas == []
    page.locator(".rw-faq summary").click()
    expect(page.locator(".rw-faq-lista button")).to_have_count(len(voz["questions"]))
    page.locator(".rw-faq select").select_option(voz["questions"][0]["topic"])
    expect(page.locator(".rw-faq-lista button")).to_have_count(
        sum(p["topic"] == voz["questions"][0]["topic"] for p in voz["questions"]))
    page.locator(".rw-faq-lista button").first.click()
    pregunta_faq = voz["questions"][0]["question"]
    expect(page.locator("#rw-input")).to_have_value(pregunta_faq)
    assert consultas == []
    page.route("**/ask", lambda r: r.fulfill(json={"status": "conversational", "conversational_category": "help",
               "answer": respuesta_fija(r.request.post_data_json["question"], idioma), "fragments": []}))
    page.get_by_role("button", name=interfaz["search_send"], exact=True).click()
    expect(page.locator(".rw-voz-texto")).to_have_text(respuesta_fija(pregunta_faq, idioma))
    expect(page.locator(".rw-faq")).to_be_visible()
    assert len(consultas) == 1
    if idioma == "es":
        page.screenshot(path=str(tmp_path / "bienvenida-es.png"), full_page=True)
    page.close()


@pytest.mark.browser
def test_vista_previa_autonoma_renderiza_widget_real_y_texto_seguro(navegador, tmp_path):
    from ipsis.aplicacion.widget import aplicar_preset, cambiar_estilo, generar_vista_previa

    ruta = str(tmp_path / "styles.yaml")
    aplicar_preset("forest", ruta)
    cambiar_estilo(['content.title=</script><img src=x onerror=alert(1)>', 'presentation.expand_context=true',
                    'presentation.show_result_numbers=false', 'presentation.show_section_path=false'], ruta)
    vista = generar_vista_previa(str(tmp_path / "preview.html"), ruta)
    page = navegador.new_page(viewport={"width": 1000, "height": 1000}, reduced_motion="reduce")
    errores = []
    page.on('pageerror', lambda e: errores.append(str(e)))
    page.goto(vista.as_uri())
    expect(page.locator('.rw-sugerencias button')).to_have_count(6)
    page.locator('#mostrar').click()
    expect(page.locator('.rw-resultado')).to_have_count(3)
    expect(page.locator('.rw-resultado-contexto').first).to_be_visible()
    assert page.locator('.rw-resultado-numero').count() == page.locator('.rw-resultado-ruta').count() == 0
    expect(page.locator('#rw-titulo')).to_have_text('</script><img src=x onerror=alert(1)>')
    assert page.locator('img').count() == 0 and errores == []
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("movimiento,activadas", [("no-preference", True), ("reduce", True), ("no-preference", False)])
def test_carga_transicion_ayuda_compacta_y_scrollbar(navegador, servidor_widget, movimiento, activadas):
    page = navegador.new_page(viewport={"width": 375, "height": 667}, reduced_motion=movimiento)
    pendientes = []
    llamadas = []
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources",
               "animations_enabled": activadas, "assistant_messages": {"results": ["Review the source context. " * 15]}}))
    def responder(ruta):
        llamadas.append(ruta.request.post_data_json)
        if len(llamadas) == 1:
            ruta.fulfill(json=_pagina_fuentes(continuar=False))
        else:
            pendientes.append(ruta)
    page.route("**/ask", responder)
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("stock inicial")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    voz = page.locator(".rw-voz")
    assert voz.evaluate("e => e.getBoundingClientRect().height") <= 100
    alto_resultados = page.locator(".rw-mensajes").evaluate("e => e.getBoundingClientRect().height")
    assert alto_resultados >= 350
    page.locator(".rw-voz-menu summary").click()
    expect(page.get_by_role("button", name="Search tips", exact=True)).to_be_visible()
    assert page.locator(".rw-mensajes").evaluate("e => e.getBoundingClientRect().height") == alto_resultados
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_be_visible()
    expect(page.locator(".rw-voz-menu")).not_to_have_attribute("open", "")
    page.get_by_role("button", name="Show full message", exact=True).click()
    expect(voz).to_have_attribute("data-expandido", "true")
    page.get_by_role("button", name="Show less", exact=True).click()
    expect(voz).to_have_attribute("data-expandido", "false")
    page.locator("#rw-input").fill("stock actualizado")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-mensajes")).to_have_attribute("aria-busy", "true")
    expect(page.locator(".rw-carga")).to_be_visible()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    siguiente = _pagina_fuentes(continuar=False)
    for fuente in siguiente["fragments"]:
        fuente["text"] = "Stock 17"
    assert len(pendientes) == 1
    pendientes[0].fulfill(json=siguiente)
    expect(page.locator(".rw-resultado-vista").first).to_have_text("Stock 17")
    expect(page.locator(".rw-mensajes")).to_have_attribute("aria-busy", "false")
    expect(page.locator(".rw-carga")).to_be_hidden()
    animacion = page.locator(".rw-resultado").first.evaluate("e => getComputedStyle(e).animationName")
    assert animacion == ("rw-resultados-entrar" if activadas and movimiento != "reduce" else "none")
    assert page.locator(".rw-mensajes").evaluate("e => getComputedStyle(e).scrollbarWidth") == "thin"
    assert page.locator(".rw-mensajes").evaluate("e => getComputedStyle(e).scrollbarColor") != "auto"
    page.close()


@pytest.mark.browser
def test_resultado_muestra_titulo_del_documento_y_archivo_como_dato_secundario(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    publico = _pagina_fuentes(continuar=False)
    for f in publico["fragments"]:
        f.update(doc_title="Reglamento de Prácticas (Plan 26)", source_name="Reglamento_Practicas_Plan26_v4.docx")
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources"}))
    page.route("**/ask", lambda r: r.fulfill(json=publico))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("plazo")
    page.get_by_role("button", name="Search", exact=True).click()
    tarjeta = page.locator(".rw-resultado").first
    expect(tarjeta.locator(".rw-resultado-doc")).to_have_text("Reglamento de Prácticas (Plan 26) · v1")
    expect(tarjeta.locator(".rw-resultado-archivo")).to_have_text("Reglamento_Practicas_Plan26_v4.docx")
    page.close()


@pytest.mark.browser
def test_busqueda_muestra_esqueleto_y_los_resultados_entran_en_secuencia(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    pendientes = []
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources"}))
    page.route("**/ask", lambda ruta: pendientes.append(ruta))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Search", exact=True).click()
    esqueleto = page.locator(".rw-esqueleto")
    expect(esqueleto).to_be_visible()
    expect(esqueleto).to_have_attribute("aria-hidden", "true")
    expect(esqueleto.locator(".rw-esq-tarjeta")).to_have_count(3)
    expect(esqueleto.locator(".rw-esqueleto-estado span")).to_have_text("Reviewing the information…")
    expect(page.locator(".rw-busqueda-vacia")).to_be_hidden()
    pendientes[0].fulfill(json=_pagina_fuentes(continuar=False))
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-esqueleto")).to_have_count(0)
    indices = page.locator(".rw-resultado").evaluate_all("els => els.map(e => e.style.getPropertyValue('--rw-i'))")
    assert indices == ["0", "1", "2"]
    page.close()


@pytest.mark.browser
def test_boton_borrar_limpia_el_buscador_y_solo_aparece_con_texto(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources"}))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    borrar = page.get_by_role("button", name="Clear search")
    expect(borrar).to_be_hidden()
    page.locator("#rw-input").fill("plazo de entrega")
    expect(borrar).to_be_visible()
    borrar.click()
    expect(page.locator("#rw-input")).to_have_value("")
    expect(borrar).to_be_hidden()
    expect(page.locator("#rw-input")).to_be_focused()
    page.close()


@pytest.mark.browser
def test_resultado_muestra_el_alcance_para_distinguir_practica_i_de_ii(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    publico = _pagina_fuentes(continuar=False)
    publico["fragments"][0].update(doc_title="Reglamento de Prácticas", scope="Práctica Profesional II")
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources"}))
    page.route("**/ask", lambda r: r.fulfill(json=publico))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("defensa oral")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-resultado").first.locator(".rw-resultado-alcance")).to_have_text("Práctica Profesional II")
    expect(page.locator(".rw-resultado-alcance")).to_have_count(1)
    page.close()


@pytest.mark.browser
def test_resultado_muestra_los_terminos_que_lo_distinguen(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    publico = _pagina_fuentes(continuar=False)
    publico["fragments"][0].update(distinctive_terms=["II", "45%", "Defensa"])
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources"}))
    page.route("**/ask", lambda r: r.fulfill(json=publico))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("defensa oral")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-resultado").first.locator(".rw-resultado-rasgos")).to_have_text("Distinguished by: II · 45% · Defensa")
    expect(page.locator(".rw-resultado-rasgos")).to_have_count(1)
    page.close()


@pytest.mark.browser
def test_sin_alcance_la_etiqueta_es_el_titulo_de_la_seccion_que_contiene_la_unidad(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    publico = _pagina_fuentes(continuar=False)
    publico["fragments"][0].update(section="CAPÍTULO IV > Artículo 14. Proceso")
    publico["fragments"][1].update(section="Productos")           # sin sección padre ni alcance: sin etiqueta
    publico["fragments"][2].update(section="A > B > C", scope="Práctica Profesional I")
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources"}))
    page.route("**/ask", lambda r: r.fulfill(json=publico))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("proceso")
    page.get_by_role("button", name="Search", exact=True).click()
    tarjetas = page.locator(".rw-resultado")
    expect(tarjetas).to_have_count(3)
    expect(tarjetas.nth(0).locator(".rw-resultado-alcance")).to_have_text("CAPÍTULO IV")
    expect(tarjetas.nth(0).locator(".rw-resultado-padre")).to_have_count(1)
    expect(tarjetas.nth(0).locator(".rw-resultado-ruta")).to_have_count(0)        # no repite lo que dice la etiqueta
    expect(tarjetas.nth(1).locator(".rw-resultado-alcance")).to_have_count(0)
    expect(tarjetas.nth(2).locator(".rw-resultado-alcance")).to_have_text("Práctica Profesional I")
    expect(tarjetas.nth(2).locator(".rw-resultado-padre")).to_have_count(0)
    expect(tarjetas.nth(2).locator(".rw-resultado-ruta")).to_have_text("A › B")
    page.close()


def _abrir_busqueda(page, servidor_widget, mensajes=None):
    config = {"assistant_name": "Biblioteca", "response_mode": "ranked_sources"}
    if mensajes:
        config["assistant_messages"] = mensajes
    page.route("**/config", lambda r: r.fulfill(json=config))
    page.route("**/ask", lambda r: r.fulfill(json=_pagina_fuentes(continuar=False)))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()


@pytest.mark.browser
def test_la_ayuda_es_un_icono_en_el_encabezado_y_el_conteo_va_en_el_mensaje(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _abrir_busqueda(page, servidor_widget, {"results": ["Review the sources."]})
    ayuda = page.locator(".rw-cabecera .rw-voz-menu summary")
    expect(ayuda).to_be_visible()
    expect(ayuda).to_have_attribute("aria-label", "Help")
    assert page.locator(".rw-voz .rw-voz-menu").count() == 0              # ya no hay una fila de ayuda bajo el encabezado
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-voz-texto")).to_have_text("3 results. Review the sources.", timeout=8000)   # conteo antepuesto
    contador = page.locator(".rw-busqueda-contador")
    assert contador.evaluate("e => e.getBoundingClientRect().height") <= 2          # solo para lectores de pantalla
    page.close()


@pytest.mark.browser
def test_las_plantillas_ubican_el_conteo_con_count_n_y_query(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _abrir_busqueda(page, servidor_widget, {"results": ["{count} for «{query}» ({n} in all). Open one."]})
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-voz-texto")).to_have_text("3 results for «stock» (3 in all). Open one.", timeout=8000)
    page.close()


def _buscar_con_forma(page, servidor_widget, mensajes, forma, documentos=("Inventory", "Inventory", "Inventory"), alcances=None):
    pagina = _pagina_fuentes(continuar=False)
    for i, (fragmento, doc) in enumerate(zip(pagina["fragments"], documentos)):
        fragmento["doc_title"], fragmento["doc_id"] = doc, doc.lower()
        if alcances:
            fragmento["scope"] = alcances[i]
    if forma:
        pagina["result_shape"] = forma
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources",
                                                       "assistant_messages": mensajes}))
    page.route("**/ask", lambda r: r.fulfill(json=pagina))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-resultado")).to_have_count(3)


BANCO_FORMAS = {"results": ["Standard message."], "results_variants": ["{count}. It depends on your case."],
                "results_documents": ["{count} in {n_docs} documents."]}


@pytest.mark.browser
@pytest.mark.parametrize("forma, documentos, esperado", [
    ("variants", ("Inventory",) * 3, "3 results. It depends on your case."),
    ("documents", ("Inventory", "Orders", "Orders"), "3 results in 2 documents."),
    ("neutral", ("Inventory",) * 3, "3 results. Standard message."),
    (None, ("Inventory",) * 3, "3 results. Standard message.")])
def test_el_mensaje_sigue_la_forma_de_la_pagina(navegador, servidor_widget, forma, documentos, esperado):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_forma(page, servidor_widget, BANCO_FORMAS, forma, documentos)
    expect(page.locator(".rw-voz-texto")).to_have_text(esperado, timeout=8000)
    expect(page.locator(".rw-voz")).to_have_attribute("data-category", "results")   # la categoría visible no cambia
    page.close()


@pytest.mark.browser
def test_las_variantes_ofrecen_atajos_por_alcance_sin_cambiar_el_orden(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_forma(page, servidor_widget, BANCO_FORMAS, "variants", alcances=("Práctica I", "Práctica II", "Práctica I"))
    atajos = page.locator(".rw-atajos .rw-atajo")
    expect(atajos).to_have_text(["Práctica I", "Práctica II"])                   # uno por variante distinta
    expect(page.locator(".rw-resultado-alcance")).to_have_text(["Práctica I", "Práctica II", "Práctica I"])
    expect(page.locator(".rw-resultado .rw-resultado-titulo")).to_have_count(3)
    atajos.nth(1).click()
    expect(page.locator(".rw-resultado").nth(1).locator(".rw-resultado-titulo")).to_be_focused()
    assert page.locator(".rw-atajos").evaluate("e => e.getBoundingClientRect().right") <= 375
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("forma, alcances", [("variants", ("Práctica I", "Práctica I", "Práctica I")), ("variants", None),
                                              ("neutral", ("Práctica I", "Práctica II", "Práctica I")), (None, None)])
def test_sin_variantes_distintas_o_sin_forma_no_hay_atajos(navegador, servidor_widget, forma, alcances):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_forma(page, servidor_widget, BANCO_FORMAS, forma, alcances=alcances)
    assert page.locator(".rw-atajos").count() == 0
    page.close()


@pytest.mark.browser
def test_los_documentos_marcan_el_inicio_de_cada_grupo_sin_cambiar_el_orden(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_forma(page, servidor_widget, BANCO_FORMAS, "documents", documentos=("Inventory", "Orders", "Orders"))
    tarjetas = page.locator(".rw-resultado")
    assert [tarjetas.nth(i).get_attribute("data-grupo") for i in range(3)] == ["nuevo", "nuevo", None]
    expect(page.locator(".rw-resultado-doc")).to_have_text(["Inventory \u00b7 v1", "Orders \u00b7 v1", "Orders \u00b7 v1"])
    expect(page.locator(".rw-resultados")).to_have_attribute("data-forma", "documents")
    assert tarjetas.nth(1).evaluate("e => getComputedStyle(e).borderTopWidth") == "3px"
    page.close()


@pytest.mark.browser
def test_sin_forma_los_documentos_no_se_marcan(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_forma(page, servidor_widget, BANCO_FORMAS, None, documentos=("Inventory", "Orders", "Orders"))
    assert page.locator(".rw-resultado[data-grupo]").count() == 0
    page.close()


def _ficha(**extra):
    return {"media_id": "m1", "title": "Orientation video", "kind": "video", "url": "https://example.org/watch",
            "description": "How to enroll.", "duration": 872, "version": "2026-03", **extra}


def _buscar_con_media(page, servidor_widget, media):
    pagina = _pagina_fuentes(continuar=False)
    if media is not None:
        pagina["media"] = media
    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources"}))
    page.route("**/ask", lambda r: r.fulfill(json=pagina))
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-resultado")).to_have_count(3)


@pytest.mark.browser
def test_la_ficha_multimedia_va_aparte_despues_de_las_fuentes_con_texto_literal(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_media(page, servidor_widget, [_ficha(chapter_title="Enroll in courses", start_seconds=410,
                                                     chapter_description="Pick sections and confirm.")])
    bloque = page.locator(".rw-media")
    expect(bloque.locator(".rw-media-titulo")).to_have_text("There is also a video about this")
    tarjeta = bloque.locator(".rw-media-tarjeta")
    expect(tarjeta).to_have_count(1)
    expect(tarjeta.locator(".rw-media-tipo")).to_have_text("Video")
    expect(tarjeta.locator(".rw-media-meta")).to_contain_text("Duration 14:32")
    expect(tarjeta.locator(".rw-media-nombre")).to_have_text("Orientation video")
    expect(tarjeta.locator(".rw-media-capitulo")).to_have_text("Enroll in courses \u00b7 From 6:50")
    expect(tarjeta.locator(".rw-media-descripcion")).to_have_text("Pick sections and confirm.")  # la del capítulo, literal
    expect(tarjeta.locator(".rw-media-origen")).to_have_text("According to the video description")
    # después de las tres fuentes, sin tocarlas ni su orden
    ultima = page.locator(".rw-resultado").nth(2)
    assert bloque.evaluate("(m, u) => !!(u.compareDocumentPosition(m) & Node.DOCUMENT_POSITION_FOLLOWING)", ultima.element_handle())
    assert page.locator(".rw-media").evaluate("e => e.getBoundingClientRect().right") <= 375
    assert tarjeta.locator("iframe, video, audio").count() == 0
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("media", [None, []])
def test_sin_fichas_no_hay_bloque_multimedia(navegador, servidor_widget, media):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_media(page, servidor_widget, media)
    assert page.locator(".rw-media").count() == 0
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("url, segundos, esperado", [
    ("https://www.youtube.com/watch?v=abc", 90, "https://www.youtube.com/watch?v=abc&t=90s"),
    ("https://youtu.be/abc", 90, "https://youtu.be/abc?t=90s"),
    ("https://vimeo.com/123", 90, "https://vimeo.com/123#t=90s"),
    ("https://example.org/video", 90, "https://example.org/video"),
    ("https://www.youtube.com/watch?v=abc", None, "https://www.youtube.com/watch?v=abc")])
def test_el_enlace_lleva_al_minuto_solo_en_youtube_y_vimeo(navegador, servidor_widget, url, segundos, esperado):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_media(page, servidor_widget, [_ficha(url=url, start_seconds=segundos, chapter_title="Cap" if segundos else None)])
    enlace = page.locator(".rw-media-abrir")
    expect(enlace).to_have_attribute("href", esperado)
    expect(enlace).to_have_attribute("target", "_blank")
    expect(enlace).to_have_attribute("rel", "noopener noreferrer")
    expect(enlace).to_have_attribute("aria-label", "Open the video: Orientation video (opens in a new tab)")
    page.close()


@pytest.mark.browser
def test_un_enlace_que_no_es_http_no_se_muestra(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_media(page, servidor_widget, [_ficha(url="javascript:alert(1)"), _ficha(media_id="m2", url="data:text/html,x")])
    assert page.locator(".rw-media").count() == 0
    page.close()


@pytest.mark.browser
def test_audio_y_mezcla_usan_su_propio_encabezado(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_media(page, servidor_widget, [_ficha(kind="audio", title="Welcome talk", duration=None, version=None)])
    expect(page.locator(".rw-media-titulo")).to_have_text("There is also an audio about this")
    expect(page.locator(".rw-media-origen")).to_have_text("According to the audio description")
    expect(page.locator(".rw-media-abrir")).to_have_text("Open the audio")
    page.close()
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_media(page, servidor_widget, [_ficha(), _ficha(media_id="m2", kind="audio", title="Talk")])
    expect(page.locator(".rw-media-titulo")).to_have_text("There is also audio and video about this")
    expect(page.locator(".rw-media-tarjeta")).to_have_count(2)
    page.close()


BANCO_CORRECCION = {"results": ["Standard."], "continuation": ["Added {count}."],
                    "opened_source": ["Source of {doc}{scope_suffix}."], "results_retry": ["Then maybe this. {count} now."]}


def _buscar_para_corregir(page, servidor_widget, forma="variants", banco=None, continuar=True):
    """Primera página con (o sin) forma y, si se pide, una continuación de tres fuentes más."""
    peticiones = []

    def responder(ruta):
        cuerpo = ruta.request.post_data_json
        peticiones.append(cuerpo)
        if cuerpo.get("continuation"):
            ruta.fulfill(json=_pagina_fuentes(3, False))
            return
        pagina = _pagina_fuentes(continuar=continuar)
        for fragmento, alcance in zip(pagina["fragments"], ("Práctica I", "Práctica II", "Práctica III")):
            fragmento["scope"] = alcance
        if forma:
            pagina["result_shape"] = forma
        ruta.fulfill(json=pagina)

    page.route("**/config", lambda r: r.fulfill(json={"assistant_name": "Biblioteca", "response_mode": "ranked_sources",
                                                       "assistant_messages": banco or BANCO_CORRECCION}))
    page.route("**/ask", responder)
    page.goto(servidor_widget)
    page.get_by_role("button", name="Open search of Biblioteca").click()
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".rw-resultado")).to_have_count(3)
    expect(page.locator(".rw-voz-texto")).to_have_text("3 results. Standard.", timeout=8000)
    return peticiones


@pytest.mark.browser
def test_abrir_una_fuente_que_no_es_la_primera_dice_de_donde_es_una_sola_vez(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    peticiones = _buscar_para_corregir(page, servidor_widget)
    voz = page.locator(".rw-voz-texto")
    page.locator(".rw-resultado .rw-resultado-titulo").nth(0).click()                # la primera: no cambia el mensaje
    page.wait_for_timeout(300)
    expect(voz).to_have_text("3 results. Standard.")
    page.locator(".rw-resultado .rw-resultado-titulo").nth(1).click()
    expect(voz).to_have_text("Source of Inventory, Práctica II.", timeout=8000)
    page.locator(".rw-resultado .rw-resultado-titulo").nth(2).click()                # otra tarjeta: su propio mensaje
    expect(voz).to_have_text("Source of Inventory, Práctica III.", timeout=8000)
    page.locator(".rw-resultado .rw-resultado-titulo").nth(1).click()                # cerrar
    page.locator(".rw-resultado .rw-resultado-titulo").nth(1).click()                # y volver a abrir: ya se dijo
    page.wait_for_timeout(300)
    expect(voz).to_have_text("Source of Inventory, Práctica III.")
    assert len(peticiones) == 1                                                      # nada va al servidor
    page.close()


@pytest.mark.browser
def test_abrir_con_el_resumen_tambien_lo_dice(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_para_corregir(page, servidor_widget)
    page.locator(".rw-resultado summary").nth(2).click()
    expect(page.locator(".rw-voz-texto")).to_have_text("Source of Inventory, Práctica III.", timeout=8000)
    page.close()


@pytest.mark.browser
def test_sin_forma_no_hay_caminos_de_correccion(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_para_corregir(page, servidor_widget, forma=None)
    page.locator(".rw-resultado .rw-resultado-titulo").nth(1).click()
    page.wait_for_timeout(300)
    expect(page.locator(".rw-voz-texto")).to_have_text("3 results. Standard.")
    assert page.get_by_role("button", name="This isn't it").count() == 0
    page.close()


@pytest.mark.browser
def test_no_es_esto_pide_la_continuacion_responde_con_su_mensaje_y_compacta_las_anteriores(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    peticiones = _buscar_para_corregir(page, servidor_widget)
    page.get_by_role("button", name="This isn't it").click()
    expect(page.locator(".rw-resultado")).to_have_count(6)
    assert len(peticiones) == 2 and peticiones[1]["continuation"] == "pagina-2"
    expect(page.locator(".rw-voz-texto")).to_have_text("Then maybe this. 6 results now.", timeout=8000)
    tarjetas = page.locator(".rw-resultado")
    assert [tarjetas.nth(i).get_attribute("data-compacta") for i in range(6)] == ["si"] * 3 + [None] * 3
    expect(tarjetas.nth(0).locator(".rw-resultado-vista")).to_be_hidden()        # compactas, no borradas
    expect(tarjetas.nth(0).locator(".rw-resultado-titulo")).to_be_visible()
    expect(tarjetas.nth(4).locator(".rw-resultado-vista")).to_be_visible()
    tarjetas.nth(0).locator(".rw-resultado-titulo").click()                      # abrir el contexto la vuelve a mostrar
    expect(tarjetas.nth(0).locator(".rw-resultado-vista")).to_be_visible()
    assert page.get_by_role("button", name="This isn't it").count() == 0
    page.close()


@pytest.mark.browser
def test_mostrar_mas_no_compacta_y_usa_el_mensaje_de_continuacion(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_para_corregir(page, servidor_widget)
    page.get_by_role("button", name="Show more results").click()
    expect(page.locator(".rw-resultado")).to_have_count(6)
    expect(page.locator(".rw-voz-texto")).to_have_text("Added 6 results.", timeout=8000)
    assert page.locator(".rw-resultado[data-compacta]").count() == 0
    page.close()


@pytest.mark.browser
def test_sin_mas_paginas_no_hay_no_es_esto(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_para_corregir(page, servidor_widget, continuar=False)
    assert page.get_by_role("button", name="This isn't it").count() == 0
    page.close()


@pytest.mark.browser
def test_sin_mensajes_de_correccion_en_el_banco_no_se_rompe_nada(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_para_corregir(page, servidor_widget, banco={"results": ["Standard."], "continuation": ["Added {count}."]})
    page.locator(".rw-resultado .rw-resultado-titulo").nth(1).click()
    page.wait_for_timeout(300)
    expect(page.locator(".rw-voz-texto")).to_have_text("3 results. Standard.")          # sin plantilla, no dice nada
    page.get_by_role("button", name="This isn't it").click()
    expect(page.locator(".rw-voz-texto")).to_have_text("Added 6 results.", timeout=8000)  # cae en «continuation»
    page.close()


@pytest.mark.browser
def test_sin_mensaje_propio_para_la_forma_se_usa_el_de_siempre(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _buscar_con_forma(page, servidor_widget, {"results": ["Standard message."]}, "variants")
    expect(page.locator(".rw-voz-texto")).to_have_text("3 results. Standard message.", timeout=8000)
    page.close()


@pytest.mark.browser
def test_punto_de_espera_parpadea_cuando_no_habla_y_se_oculta_al_escribir(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _abrir_busqueda(page, servidor_widget, {"results": ["Review the sources. " * 4]})
    page.locator("#rw-input").fill("stock")
    page.get_by_role("button", name="Search", exact=True).click()
    voz = page.locator(".rw-voz")
    expect(voz).to_have_attribute("data-typing", "false", timeout=8000)
    estilo = "e => { const s = getComputedStyle(e, '::after'); return [s.animationName, s.display, s.borderRadius]; }"
    nombre, mostrar, _ = page.locator(".rw-voz-texto").evaluate(estilo)
    assert nombre == "rw-espera" and mostrar == "inline-block"
    page.evaluate("document.querySelector('ipsis-chat').shadowRoot.querySelector('.rw-voz').dataset.typing = 'true'")
    assert page.locator(".rw-voz-texto").evaluate(estilo)[1] == "none"
    page.close()


@pytest.mark.browser
def test_el_mensaje_del_asistente_va_abajo_junto_al_campo_con_lugar_para_el_avatar(navegador, servidor_widget):
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    _abrir_busqueda(page, servidor_widget)
    orden = page.evaluate("Array.from(document.querySelector('ipsis-chat').shadowRoot.querySelectorAll("
                          "'.rw-mensajes,.rw-voz,.rw-form')).map(e => e.className.split(' ')[0])")
    assert orden == ["rw-mensajes", "rw-voz", "rw-form"]
    cajas = page.evaluate("""() => { const r = document.querySelector('ipsis-chat').shadowRoot;
        const v = r.querySelector('.rw-voz').getBoundingClientRect(), f = r.querySelector('.rw-form').getBoundingClientRect();
        return [v.bottom, f.top, v.height]; }""")
    assert abs(cajas[0] - cajas[1]) <= 2 and cajas[2] <= 100             # pegado al campo y compacto
    assert page.locator(".rw-voz-burbuja .rw-voz-texto").count() == 1
    assert page.locator(".rw-voz-avatar").count() == 1                    # sin avatar activo está vacío y oculto
    expect(page.locator(".rw-voz-avatar")).to_be_hidden()
    page.close()
