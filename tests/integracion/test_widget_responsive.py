"""Widget embebible y responsive (P12.5), en Chromium real.

Un servidor de prueba sirve ``widget.js`` y una API controlada; la página
recibe la ubicación por parámetros de la URL.
"""
from __future__ import annotations

import gzip
import re
import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

RAIZ = Path(__file__).resolve().parents[2]
WIDGET = RAIZ / "ipsis/servicio/estaticos/widget.js"
TEXTO_CITA = "El filtro de sedimentos se cambia cada 6 meses."


# --- pruebas estáticas (sin navegador) -----------------------------------------------------------
def test_widget_no_inserta_html_crudo():
    codigo = WIDGET.read_text(encoding="utf-8")
    # Sin comentarios: el propio widget explica en ellos que nunca usa innerHTML.
    codigo = re.sub(r"/\*.*?\*/", "", codigo, flags=re.S)
    codigo = re.sub(r"(?m)^\s*//.*$", "", codigo)
    for uso in (r"\.innerHTML\b", r"\.outerHTML\b", r"insertAdjacentHTML\s*\(", r"document\.write\s*\("):
        assert not re.search(uso, codigo), uso


def test_widget_sin_avatar_pesa_menos_de_40_kb_gzip():
    assert len(gzip.compress(WIDGET.read_bytes(), 9)) <= 40 * 1024


def test_no_hay_opcion_para_ocultar_las_citas():
    from ipsis.aplicacion.widget import citas_presentacion

    assert citas_presentacion("ocultas") == "acordeon" and citas_presentacion("abiertas") == "lista"
    assert '"ocultas"' not in WIDGET.read_text(encoding="utf-8")


# --- navegador ---------------------------------------------------------------------------------
playwright = pytest.importorskip("playwright.sync_api") if __name__ != "__main__" else None


def _app(base: str, estado: dict):
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def pagina(request: Request):
        q = request.query_params
        attrs = " ".join(f'{k}="{v}"' for k, v in q.items() if k in ("posicion", "tamano", "lanzador", "modo"))
        contenedor = q.get("modo") == "incrustado"
        widget = f'<ipsis-chat api="{base}" titulo="Ayuda" {attrs}></ipsis-chat>'
        cuerpo = f'<main style="padding:20px"><div style="height:520px">{widget}</div></main>' if contenedor else widget
        return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head>
<body style="margin:0"><p>Contenido del sitio.</p>{cuerpo}<script src="/widget.js"></script></body></html>"""

    @app.get("/widget.js")
    def javascript():
        return FileResponse(WIDGET, media_type="text/javascript")

    @app.get("/config")
    def config():
        return {"nombre_asistente": "Ayuda", "descripcion_dominio": "manual", "saludo": "Hola.",
                "preset": "clasico", "densidad": "comoda", "citas": estado.get("citas", "acordeon"),
                "mostrar_etiqueta_estado": True, "interfaz": {},
                "microcopia": {"welcome": ["Bienvenida de prueba."], "waiting": ["Buscando de prueba"],
                               "citations_hint": ["Compruébalo abajo, prueba."], "network_error": ["Red caída."],
                               "rate_limit_error": ["Muy rápido."], "service_error": ["Servicio en pausa."]},
                "ubicacion": estado.get("ubicacion", {})}

    @app.post("/consultar")
    def consultar():
        if estado.get("estado_http"):
            return Response(status_code=estado["estado_http"])
        return {
            "estado": "ok", "nivel_servicio": "normal", "plan": "extractivo", "latencia_ms": 3,
            "confianza": {"top1": 0.9, "margen": 0.1, "acuerdo_bm25": None},
            "respuesta": f"Esto es lo que dice el documento: {TEXTO_CITA}",
            "respuesta_exacta": {"chunk_id": "c1", "texto": "6 meses", "offset_inicio": 139, "offset_fin": 146},
            "fragmentos": [{"chunk_id": "c1", "doc_titulo": "Manual", "seccion": "Filtro", "offset_inicio": 100,
                            "offset_fin": 147, "texto": TEXTO_CITA, "score": 0.9, "version": "1", "pagina": None}],
        }

    return app


@pytest.fixture(scope="module")
def servidor():
    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        puerto = sock.getsockname()[1]
    base = f"http://127.0.0.1:{puerto}"
    estado: dict = {}
    server = uvicorn.Server(uvicorn.Config(_app(base, estado), host="127.0.0.1", port=puerto, log_level="error"))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.02)
    yield base, estado
    server.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture(scope="module")
def navegador():
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


def _shadow(page, selector: str):
    return page.evaluate_handle(
        f"document.querySelector('ipsis-chat').shadowRoot.querySelector('{selector}')")


def _caja(page, selector: str) -> dict:
    return page.evaluate(
        f"(() => {{ const r = document.querySelector('ipsis-chat').shadowRoot"
        f".querySelector('{selector}').getBoundingClientRect(); "
        f"return {{x: r.x, y: r.y, ancho: r.width, alto: r.height}}; }})()")


def _abrir(page, incrustado: bool = False) -> None:
    if not incrustado:
        page.evaluate("window.RagChat.abrir()")
    # Sin depender de la animación de entrada: se esperan las animaciones del panel.
    page.evaluate("Promise.all(document.querySelector('ipsis-chat').shadowRoot"
                  ".querySelector('.rw-panel').getAnimations().map(a => a.finished))")


VIEWPORTS = [(360, 640), (768, 1024), (1280, 800)]
POSICIONES = ["abajo-derecha", "abajo-izquierda", "arriba-derecha", "arriba-izquierda", "incrustado"]


@pytest.mark.browser
@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: f"{v[0]}x{v[1]}")
@pytest.mark.parametrize("posicion", POSICIONES)
def test_ubicaciones_y_viewports_sin_desbordar(navegador, servidor, viewport, posicion):
    base, _ = servidor
    ancho, alto = viewport
    page = navegador.new_page(viewport={"width": ancho, "height": alto})
    incrustado = posicion == "incrustado"
    page.goto(f"{base}/?modo=incrustado" if incrustado else f"{base}/?posicion={posicion}")
    _abrir(page, incrustado)
    assert page.evaluate("document.documentElement.scrollWidth") <= ancho  # sin scroll horizontal
    panel, campo = _caja(page, ".rw-panel"), _caja(page, "#rw-input")
    assert panel["x"] >= -1 and panel["x"] + panel["ancho"] <= ancho + 1, panel
    if not incrustado:
        assert panel["y"] >= -1 and panel["y"] + panel["alto"] <= alto + 1, panel
    assert campo["alto"] > 0 and campo["x"] >= 0 and campo["x"] + campo["ancho"] <= ancho + 1
    if not incrustado:
        assert campo["y"] + campo["alto"] <= alto + 1, campo  # el campo se ve
        lado = "derecha" if posicion.endswith("derecha") else "izquierda"
        boton = _caja(page, ".rw-boton")
        assert (boton["x"] > ancho / 2) == (lado == "derecha")
    page.close()


@pytest.mark.browser
def test_en_movil_el_campo_sigue_visible_con_el_teclado(navegador, servidor):
    base, _ = servidor
    page = navegador.new_page(viewport={"width": 360, "height": 640})
    page.goto(base)
    _abrir(page)
    page.set_viewport_size({"width": 360, "height": 340})  # el teclado virtual ocupa el resto
    page.wait_for_function("window.visualViewport.height <= 340")
    page.wait_for_timeout(50)
    campo = _caja(page, "#rw-input")
    assert campo["y"] >= 0 and campo["y"] + campo["alto"] <= 340, campo
    page.close()


@pytest.mark.browser
def test_movil_hoja_a_pantalla_completa(navegador, servidor):
    base, _ = servidor
    page = navegador.new_page(viewport={"width": 375, "height": 667})
    page.goto(base)
    _abrir(page)
    caja = _caja(page, ".rw-panel")
    assert caja == pytest.approx({"x": 0, "y": 0, "ancho": 375, "alto": 667}, abs=1)
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("citas", ["acordeon", "lista", "ocultas"])
def test_citas_debajo_con_el_tramo_exacto_marcado(navegador, servidor, citas):
    base, estado = servidor
    estado.update(citas=citas, estado_http=None)
    page = navegador.new_page()
    page.goto(base)
    _abrir(page)
    page.evaluate("""() => { const r = document.querySelector('ipsis-chat').shadowRoot;
        r.querySelector('#rw-input').value = '¿Cada cuánto?';
        r.querySelector('.rw-form').requestSubmit(); }""")
    page.wait_for_function("document.querySelector('ipsis-chat').shadowRoot.querySelector('mark')")
    datos = page.evaluate("""() => { const r = document.querySelector('ipsis-chat').shadowRoot;
        const citas = r.querySelector('.rw-citas'); const marca = r.querySelector('mark.rw-tramo');
        return {marca: marca.textContent, cita: r.querySelector('.rw-cita-texto').textContent,
                invitacion: r.querySelector('.rw-citas-invitacion').textContent,
                visible: marca.getBoundingClientRect().height > 0,
                despuesDelMensaje: citas.previousElementSibling !== null,
                detalles: r.querySelectorAll('.rw-citas details').length,
                posicion: r.querySelector('.rw-cita-posicion').textContent}; }""")
    assert datos["marca"] == "6 meses" and datos["cita"] == TEXTO_CITA  # literal y completa
    assert datos["visible"] and datos["despuesDelMensaje"]
    assert datos["invitacion"] == "Compruébalo abajo, prueba."
    assert datos["posicion"] == " · caracteres 100–147"
    assert datos["detalles"] == (0 if citas == "lista" else 1)  # «ocultas» ya no oculta nada
    page.close()


@pytest.mark.browser
def test_microcopia_del_tono_y_region_viva(navegador, servidor):
    base, estado = servidor
    estado.update(estado_http=503, citas="acordeon")
    page = navegador.new_page()
    page.goto(base)
    _abrir(page)
    page.wait_for_function("document.querySelector('ipsis-chat').shadowRoot"
                           ".querySelector('.rw-msg').textContent.includes('Bienvenida de prueba')")
    page.evaluate("""() => { const r = document.querySelector('ipsis-chat').shadowRoot;
        r.querySelector('#rw-input').value = 'hola'; r.querySelector('.rw-form').requestSubmit(); }""")
    page.wait_for_function("document.querySelector('ipsis-chat').shadowRoot"
                           ".querySelector('[role=status]').textContent === 'Servicio en pausa.'")
    estado.update(estado_http=None)
    page.close()


@pytest.mark.browser
def test_lanzador_oculto_y_api_del_sitio(navegador, servidor):
    base, _ = servidor
    page = navegador.new_page()
    page.goto(f"{base}/?lanzador=oculto&posicion=arriba-izquierda&tamano=compacto")
    assert _caja(page, ".rw-boton")["alto"] == 0  # no hay botón: abre el sitio
    assert page.evaluate("window.RagChat.estado()")["abierto"] is False
    _abrir(page)
    estado = page.evaluate("window.RagChat.estado()")
    assert estado["abierto"] is True and estado["posicion"] == "arriba-izquierda" and estado["tamano"] == "compacto"
    assert _caja(page, ".rw-panel")["ancho"] == pytest.approx(340, abs=1)
    page.evaluate("window.RagChat.cerrar()")
    assert page.evaluate("window.RagChat.estado()")["abierto"] is False
    page.close()


@pytest.mark.browser
def test_ubicacion_de_estilos_yaml_si_el_sitio_no_la_declara(navegador, servidor):
    base, estado = servidor
    estado.update(ubicacion={"posicion": "abajo-izquierda", "lanzador": "pestana", "tamano": "amplio"})
    page = navegador.new_page(viewport={"width": 1280, "height": 900})
    page.goto(base)
    page.wait_for_function("document.querySelector('ipsis-chat').shadowRoot"
                           ".querySelector('.rw-raiz').dataset.lanzador === 'pestana'")
    assert _caja(page, ".rw-boton")["x"] < 640  # izquierda
    assert page.evaluate("document.querySelector('ipsis-chat').shadowRoot"
                         ".querySelector('.rw-boton-texto').getBoundingClientRect().width") > 0
    page.goto(f"{base}/?posicion=abajo-derecha")  # el sitio manda
    page.wait_for_function("document.querySelector('ipsis-chat').shadowRoot"
                           ".querySelector('.rw-raiz').dataset.lanzador === 'pestana'")
    assert _caja(page, ".rw-boton")["x"] > 640
    estado.pop("ubicacion")
    page.close()
