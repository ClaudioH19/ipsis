"""Motor del avatar empaquetado (P12.9), con la librería real en Chromium.

Un servidor de prueba sirve ``widget.js``, el ``avatar.js`` real y una
definición válida; la página fija su CSP por parámetro para comprobar las
dos situaciones: sin ``'unsafe-eval'`` queda el ícono y el chat funciona; con
ella se monta el avatar.
"""
from __future__ import annotations

import gzip
import hashlib
import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from apoyo import definicion_avatar

RAIZ = Path(__file__).resolve().parents[2]
ESTATICOS = RAIZ / "ipsis/servicio/estaticos"
CSP_ESTRICTA = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'"
CSP_PERMISIVA = ("default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
                 "connect-src 'self'")


# --- estáticos (sin navegador) -----------------------------------------------------------------
def test_avatar_js_coincide_con_su_sha256_y_cabe_en_el_presupuesto():
    contenido = (ESTATICOS / "avatar.js").read_bytes()
    esperado = (ESTATICOS / "avatar.js.sha256").read_text(encoding="utf-8").split()[0]
    assert hashlib.sha256(contenido).hexdigest() == esperado  # sin conversión de fin de línea
    assert len(gzip.compress(contenido, 9)) <= 150 * 1024
    assert contenido.startswith(b"/*! avatar.js | licencias: avatar.js.LICENSE.txt */")


def test_exportar_incluye_el_motor(tmp_path: Path):
    from ipsis.aplicacion.widget import exportar_widget

    destino = exportar_widget(str(tmp_path / "web"))
    assert (destino / "avatar.js").read_bytes() == (ESTATICOS / "avatar.js").read_bytes()
    assert (destino / "avatar.js.LICENSE.txt").is_file()


def test_exportar_incluye_la_definicion_activa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import json

    from ipsis.aplicacion.personalidad import actualizar_personalidad, importar_avatar_desde
    from ipsis.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    importar_avatar_desde(json.dumps(definicion_avatar()).encode(), "mi-avatar")
    actualizar_personalidad({"avatar": {"definicion": "mi-avatar", "colores": {"cuerpo": "#123456"}}})
    from ipsis.aplicacion.widget import exportar_widget

    destino = exportar_widget(str(tmp_path / "web"))
    datos = json.loads((destino / "avatares/mi-avatar.avatar.json").read_text(encoding="utf-8"))
    assert datos["colors"]["body"] == "#123456"
    assert 'avatar-base="."' in (destino / "snippet.html").read_text(encoding="utf-8")


# --- navegador ---------------------------------------------------------------------------------
playwright = pytest.importorskip("playwright.sync_api")


def _app(estado: dict):
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def pagina(request: Request):
        csp = CSP_PERMISIVA if request.query_params.get("csp") == "permisiva" else CSP_ESTRICTA
        cuerpo = """<!doctype html><html lang="es"><head><meta charset="utf-8"></head><body>
<ipsis-chat titulo="Ayuda"></ipsis-chat><script src="/widget.js"></script></body></html>"""
        return HTMLResponse(cuerpo, headers={"Content-Security-Policy": csp})

    @app.get("/widget.js")
    def widget():
        return FileResponse(ESTATICOS / "widget.js", media_type="text/javascript")

    @app.get("/avatar.js")
    def motor():
        return FileResponse(ESTATICOS / "avatar.js", media_type="text/javascript")

    @app.get("/avatares/prueba.avatar.json")
    def definicion():
        if estado.get("definicion_rota"):
            return JSONResponse({"schema": "otra"})
        return definicion_avatar()

    @app.get("/config")
    def config():
        return {"nombre_asistente": "Ayuda", "descripcion_dominio": "manual", "saludo": "Hola.",
                "interfaz": {}, "microcopia": {}, "ubicacion": {},
                "avatar": {"activo": True, "nombre": "prueba", "url_definicion": "/avatares/prueba.avatar.json",
                           "url_motor": "/avatar.js", "ubicacion": "cabecera", "tamano": 48,
                           "en_lanzador": estado.get("en_lanzador", False), "mirada": {"activa": False},
                           "inactividad_min": 2, "eventos": {"idle": "idle"}}}

    @app.post("/consultar")
    def consultar():
        return {"estado": "conversacional", "nivel_servicio": "normal", "plan": "conversacional",
                "latencia_ms": 1, "confianza": {"top1": 0, "margen": 0, "acuerdo_bm25": None},
                "respuesta": "Respuesta de prueba.", "respuesta_exacta": None, "fragmentos": []}

    return app


@pytest.fixture
def servidor():
    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        puerto = sock.getsockname()[1]
    estado: dict = {}
    server = uvicorn.Server(uvicorn.Config(_app(estado), host="127.0.0.1", port=puerto, log_level="error"))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    for _ in range(250):
        if server.started:
            break
        time.sleep(0.02)
    yield f"http://127.0.0.1:{puerto}", estado
    server.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture(scope="module")
def navegador():
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


def _pagina(navegador, url: str):
    page = navegador.new_page(viewport={"width": 1280, "height": 800})
    page.add_init_script("window.__avatar = []; document.addEventListener('rag:avatar', "
                         "e => window.__avatar.push(e.detail));")
    page.goto(url)
    return page


def _sombra(page, expresion: str):
    return page.evaluate(f"(() => {{ const r = document.querySelector('ipsis-chat').shadowRoot; "
                         f"return {expresion}; }})()")


def _esperar_evento(page, limite_s: float = 10.0) -> dict:
    fin = time.monotonic() + limite_s
    while time.monotonic() < fin:
        eventos = page.evaluate("window.__avatar")
        if eventos:
            return eventos[0]
        time.sleep(0.05)
    raise AssertionError("no llegó rag:avatar")


@pytest.mark.browser
def test_csp_permisiva_monta_el_avatar(navegador, servidor):
    base, _ = servidor
    page = _pagina(navegador, f"{base}/?csp=permisiva")
    page.evaluate("window.RagChat.abrir()")
    evento = _esperar_evento(page)
    assert evento == {"estado": "listo", "nombre": "prueba"}, evento
    assert _sombra(page, "!!r.querySelector('.rw-avatar.rw-avatar-vivo .rw-avatar-lienzo svg path')")
    assert _sombra(page, "r.querySelector('.rw-avatar-lienzo').getAttribute('aria-hidden')") == "true"
    assert _sombra(page, "r.querySelector('.rw-avatar').getBoundingClientRect().width") == pytest.approx(48, abs=1)
    page.close()


@pytest.mark.browser
def test_csp_estricta_deja_el_icono_y_el_chat_funciona(navegador, servidor):
    base, _ = servidor
    page = _pagina(navegador, f"{base}/")
    page.evaluate("window.RagChat.abrir()")
    evento = _esperar_evento(page)
    assert evento["estado"] == "error" and evento["mensaje"], evento
    assert _sombra(page, "!r.querySelector('.rw-avatar-lienzo')")
    assert _sombra(page, "!!r.querySelector('.rw-avatar svg')")  # el ícono sigue
    page.fill("ipsis-chat >> #rw-input", "hola")
    page.keyboard.press("Enter")
    page.wait_for_selector("ipsis-chat >> text=Respuesta de prueba.")
    page.close()


@pytest.mark.browser
def test_definicion_invalida_deja_el_icono(navegador, servidor):
    base, estado = servidor
    estado["definicion_rota"] = True
    page = _pagina(navegador, f"{base}/?csp=permisiva")
    page.evaluate("window.RagChat.abrir()")
    evento = _esperar_evento(page)
    assert evento["estado"] == "error" and "Invalid avatar definition" in evento["mensaje"]
    assert _sombra(page, "!r.querySelector('.rw-avatar-lienzo')")
    page.close()


@pytest.mark.browser
def test_en_el_lanzador_se_carga_sin_abrir_el_panel(navegador, servidor):
    base, estado = servidor
    estado["en_lanzador"] = True
    page = _pagina(navegador, f"{base}/?csp=permisiva")
    assert _esperar_evento(page)["estado"] == "listo"
    assert _sombra(page, "!!r.querySelector('.rw-boton.rw-con-avatar .rw-avatar-lienzo svg')")
    page.evaluate("window.RagChat.abrir()")
    assert _sombra(page, "!!r.querySelector('.rw-avatar .rw-avatar-lienzo')")  # pasa a la cabecera
    page.evaluate("window.RagChat.cerrar()")
    assert _sombra(page, "!!r.querySelector('.rw-boton .rw-avatar-lienzo')")
    page.close()


@pytest.mark.browser
def test_sin_avatar_activo_no_se_pide_el_motor(navegador, servidor):
    base, _ = servidor
    pedidos: list[str] = []
    page = navegador.new_page()
    page.on("request", lambda r: pedidos.append(r.url))
    page.route("**/config", lambda ruta: ruta.fulfill(json={"nombre_asistente": "Ayuda", "descripcion_dominio": "x",
                                                            "saludo": "Hola.", "avatar": {"activo": False}}))
    page.goto(f"{base}/?csp=permisiva")
    page.evaluate("window.RagChat.abrir()")
    time.sleep(0.5)
    assert not [p for p in pedidos if p.endswith("/avatar.js")]
    page.close()
