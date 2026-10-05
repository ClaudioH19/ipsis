"""Panel gráfico ``/admin/panel`` (P12.7).

Las rutas se prueban con ``TestClient``; el flujo, en Chromium real contra el
servicio completo (``crear_app``) en loopback y en modo producción.
"""
from __future__ import annotations

import json
import re
import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apoyo import leer_proyecto
from ipsis.aplicacion.modo import ModoServicio
from ipsis.cli import main

RAIZ = Path(__file__).resolve().parents[2]
CARPETA_PANEL = RAIZ / "ipsis/servicio/estaticos/admin"
TOKEN = "p" * 40


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    carpeta = tmp_path / "proyecto"
    carpeta.mkdir()
    monkeypatch.chdir(carpeta)
    for variable in ("IPSIS_MODE", "IPSIS_ADMIN_TOKEN", "IPSIS_TRUSTED_PROXY", "IPSIS_ADMIN_IPS"):
        monkeypatch.delenv(variable, raising=False)
    assert main(["init", "--profile", "light"]) == 0
    return carpeta


def _app(modo: ModoServicio):
    from apoyo import motor_minimo as _motor

    from ipsis.servicio.api import crear_app

    return crear_app(_motor(), modo=modo)


# --- estáticos (sin navegador) -----------------------------------------------------------------
def test_panel_sin_html_crudo_ni_scripts_en_linea():
    codigo = re.sub(r"/\*.*?\*/", "", (CARPETA_PANEL / "panel.js").read_text(encoding="utf-8"), flags=re.S)
    for uso in (r"\.innerHTML\b", r"\.outerHTML\b", r"insertAdjacentHTML\s*\(", r"document\.write\s*\(",
                r"\beval\s*\(", r"localStorage"):
        assert not re.search(uso, codigo), uso
    for html in ("panel.html", "vista-previa.html"):
        texto = (CARPETA_PANEL / html).read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)", texto), html  # CSP sin 'unsafe-inline'
        assert " style=" not in texto and "onclick" not in texto, html


def test_rutas_del_panel(proyecto):
    from ipsis.servicio.admin import CSP_PANEL, CSP_VISTA_PREVIA

    c = TestClient(_app(ModoServicio(token_admin=TOKEN)), base_url="https://testserver",
                   client=("203.0.113.5", 50000))
    r = c.get("/admin/panel")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert r.headers["content-security-policy"] == CSP_PANEL and "unsafe" not in CSP_PANEL
    assert r.headers["x-content-type-options"] == "nosniff"
    assert c.get("/admin/panel/panel.js").headers["content-type"].startswith("application/javascript")
    assert c.get("/admin/panel/vista-previa.html").headers["content-security-policy"] == CSP_VISTA_PREVIA
    assert c.get("/admin/panel/otro.js").status_code == 404
    assert c.get("/admin/panel/..%2Fwidget.js").status_code == 404
    assert "access-control-allow-origin" not in c.get("/admin/panel", headers={"Origin": "https://x.cl"}).headers


def test_panel_sigue_las_reglas_de_transporte(proyecto):
    produccion = ModoServicio(token_admin=TOKEN)
    remota_http = TestClient(_app(produccion), base_url="http://testserver", client=("203.0.113.5", 50000))
    assert remota_http.get("/admin/panel").status_code == 403
    local_http = TestClient(_app(produccion), base_url="http://testserver", client=("127.0.0.1", 50000))
    assert local_http.get("/admin/panel").status_code == 200
    sin_token = TestClient(_app(ModoServicio()), base_url="https://testserver")
    assert sin_token.get("/admin/panel").status_code == 404


# --- navegador ---------------------------------------------------------------------------------
playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def servidor(proyecto):
    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        puerto = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(_app(ModoServicio(token_admin=TOKEN)), host="127.0.0.1", port=puerto,
                                           log_level="error"))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}"
    # El arranque calcula el diagnóstico de /ready (en frío, segundos): se espera a
    # que el servicio responda, no solo a que el hilo exista.
    import httpx

    fin = time.monotonic() + 60
    while True:
        try:
            if server.started and httpx.get(url + "/health", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if time.monotonic() > fin:
            pytest.fail("el servicio de prueba no respondió /health en 60 s")
        time.sleep(0.05)
    yield url
    server.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture(scope="module")
def navegador():
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def pagina(navegador):
    page = navegador.new_page(viewport={"width": 1280, "height": 900})
    errores: list[str] = []
    page.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errores.append(str(e)))
    yield page, errores
    page.close()


def _esperar(page, expresion: str, limite_s: float = 10.0):
    """Como ``wait_for_function``, pero sin evaluar texto dentro de la página: la
    CSP del panel prohíbe ``eval`` (``page.evaluate`` va por el protocolo)."""
    fin = time.monotonic() + limite_s
    while True:
        valor = page.evaluate(expresion)
        if valor:
            return valor
        if time.monotonic() > fin:
            raise AssertionError(f"no se cumplió en {limite_s} s: {expresion}")
        time.sleep(0.05)


def _entrar(page, base: str, token: str = TOKEN) -> None:
    page.goto(f"{base}/admin/panel")
    page.fill("#token", token)
    page.click("#form-acceso button[type=submit]")


@pytest.mark.browser
def test_sin_token_no_muestra_nada(servidor, pagina):
    page, errores = pagina
    page.goto(f"{servidor}/admin/panel")
    assert page.is_hidden("#contenido") and page.is_visible("#acceso")
    _entrar(page, servidor, "x" * 40)
    _esperar(page, "document.getElementById('error-acceso').textContent.length > 0")
    assert "invalid" in page.text_content("#error-acceso")
    assert page.is_hidden("#contenido")
    assert page.evaluate("sessionStorage.getItem('rag-admin-token')") is None
    assert not [e for e in errores if "401" not in e], errores  # solo el 401 esperado


@pytest.mark.browser
def test_cambiar_el_tono_actualiza_la_vista_previa_y_guarda(servidor, pagina, proyecto):
    page, errores = pagina
    _entrar(page, servidor)
    page.wait_for_selector("#contenido:not([hidden])")
    page.wait_for_selector("#variantes li")
    antes = page.locator("#variantes li").all_text_contents()
    assert len(antes) == 5
    page.select_option("#tono-activo", "formal")
    _esperar(page, "document.getElementById('estado').textContent.includes('Guardado')")
    assert page.locator("#variantes li").all_text_contents() != antes
    assert leer_proyecto(proyecto / "config/personality.yaml")["tono"]["activo"] == "formal"
    # La vista previa carga el widget real con la CSP de la vista previa.
    marco = page.frame_locator("#vista-previa")
    marco.locator("ipsis-chat").wait_for(state="attached")
    assert not errores, errores


@pytest.mark.browser
def test_textos_propios_invalidos_muestran_el_error_del_linter(servidor, pagina, proyecto):
    page, _ = pagina
    _entrar(page, servidor)
    page.wait_for_selector("#variantes li")
    page.click("details summary")
    page.fill("#propias", "Visita https://ejemplo.cl")
    page.click("#guardar-propias")
    page.wait_for_selector("#errores li")
    assert leer_proyecto(proyecto / "config/personality.yaml")["tono"]["plantillas"] == {}

    # Un regionalismo no bloquea: se guarda y queda como aviso visible.
    assert page.is_hidden("#tono-avisos")
    page.fill("#propias", "Chao, nos vemos.")
    page.click("#guardar-propias")
    page.wait_for_selector("#tono-avisos li")
    assert "chao" in page.text_content("#tono-avisos")
    assert "Chao, nos vemos." in (proyecto / "config/personality.yaml").read_text(encoding="utf-8")


@pytest.mark.browser
def test_json_invalido_muestra_el_error_sin_guardar(servidor, pagina, proyecto):
    page, _ = pagina
    _entrar(page, servidor)
    page.wait_for_selector("#contenido:not([hidden])")
    page.click("#pestana-avatar")
    page.set_input_files("#avatar-archivo", files=[{"name": "roto.avatar.json", "mimeType": "application/json",
                                                     "buffer": b"{ esto no es json"}])
    assert page.input_value("#avatar-nombre") == "roto"
    page.click("#avatar-importar")
    page.wait_for_selector("#errores li")
    assert not (proyecto / "config/avatars/roto.avatar.json").exists()


@pytest.mark.browser
def test_importar_asignar_y_probar_un_evento(servidor, pagina, proyecto):
    from apoyo import definicion_avatar

    page, errores = pagina
    _entrar(page, servidor)
    page.wait_for_selector("#contenido:not([hidden])")
    page.click("#pestana-avatar")
    contenido = json.dumps(definicion_avatar()).encode("utf-8")
    page.set_input_files("#avatar-archivo", files=[{"name": "Mi Avatar.avatar.json", "mimeType": "application/json",
                                                     "buffer": contenido}])
    page.click("#avatar-importar")
    _esperar(page, "document.getElementById('estado').textContent.includes('mi-avatar')")
    assert (proyecto / "config/avatars/mi-avatar.avatar.json").is_file()

    page.evaluate("document.getElementById('estado').textContent = ''")
    page.select_option("#avatar-activo-sel", "mi-avatar")
    # Cada cambio guarda y recarga la vista previa: se espera el «Guardado» de este
    # antes del siguiente, o el siguiente podría confundirse con este.
    _esperar(page, "document.getElementById('estado').textContent.includes('Guardado')")
    page.wait_for_selector("tr[data-evento=answer_ok] option[value=happy]", state="attached")
    page.evaluate("document.getElementById('estado').textContent = ''")
    page.select_option("tr[data-evento=answer_ok] select", "happy")
    # «Guardado» se anuncia después de iniciar la recarga de la vista previa.
    _esperar(page, "document.getElementById('estado').textContent.includes('Guardado')")
    ruta = proyecto / "config/personality.yaml"
    fin = time.monotonic() + 10
    while "answer_ok: happy" not in ruta.read_text(encoding="utf-8") and time.monotonic() < fin:
        time.sleep(0.05)
    guardado = ruta.read_text(encoding="utf-8")
    assert "definition: mi-avatar" in guardado and "answer_ok: happy" in guardado, guardado

    # La vista previa monta el avatar real; el botón ▶ le dispara el evento con la clave asignada.
    page.wait_for_selector("#vista-previa[data-lista=true]", state="attached")
    _esperar(page, "(() => { const w = document.getElementById('vista-previa').contentWindow;"
                   " return w.Ipsis && w.Ipsis.avatar.state().ready; })()")
    page.evaluate("""(() => { const w = document.getElementById('vista-previa').contentWindow;
        w.__eventos = []; w.document.addEventListener('ipsis:avatar', e => w.__eventos.push(e.detail)); })()""")
    page.click("button[data-probar=answer_ok]")
    eventos = page.evaluate("document.getElementById('vista-previa').contentWindow.__eventos")
    assert {"state": "event", "event": "answer_ok", "key": "happy"} in eventos, eventos
    assert not errores, errores


@pytest.mark.browser
def test_preset_y_ubicacion_del_widget(servidor, pagina, proyecto):
    page, errores = pagina
    _entrar(page, servidor)
    page.wait_for_selector("#contenido:not([hidden])")
    page.click("#pestana-widget")
    opciones = page.locator("#preset option").evaluate_all("os => os.map(o => o.value)")
    otro = next(o for o in opciones if o != page.input_value("#preset"))
    page.select_option("#preset", otro)
    page.click("#aplicar-preset")
    _esperar(page, "document.getElementById('estado').textContent.length > 0")
    page.select_option("#posicion", "bottom-left")
    page.click("#guardar-widget")
    _esperar(page, "document.getElementById('estado').textContent.includes('Guardado')")
    estilos = leer_proyecto(proyecto / "config/styles.yaml")
    assert estilos["preset"] == otro and estilos["ubicacion"]["posicion"] == "abajo-izquierda"
    # Al recargar, el token sigue en la sesión de la pestaña.
    page.reload()
    page.wait_for_selector("#contenido:not([hidden])")
    assert not errores, errores


@pytest.mark.browser
def test_estilo_completo_desde_el_panel(servidor, pagina, proyecto):
    page, errores = pagina
    _entrar(page, servidor)
    page.wait_for_selector("#contenido:not([hidden])")
    page.click("#pestana-widget")
    page.click("#estilo-completo summary")
    page.wait_for_selector("input[data-clave='colors.accent']")
    assert page.get_attribute("input[data-clave='colors.accent']", "type") == "color"
    assert page.get_attribute("input[data-clave='animations.enabled']", "type") == "checkbox"
    page.fill("input[data-clave='colors.accent']", "#0ea5e9")
    page.fill("input[data-clave='shape.panel_radius']", "10px")
    page.uncheck("input[data-clave='animations.enabled']")
    page.evaluate("document.getElementById('estado').textContent = ''")
    page.click("#guardar-estilo")
    _esperar(page, "document.getElementById('estado').textContent.includes('Guardado')")
    estilos = leer_proyecto(proyecto / "config/styles.yaml")
    assert estilos["colores"]["acento"] == "#0ea5e9" and estilos["forma"]["radio_panel"] == "10px"
    assert estilos["animaciones"]["activadas"] is False
    page.evaluate("document.getElementById('estado').textContent = ''")
    page.click("#guardar-estilo")  # sin cambios: no escribe y lo dice
    _esperar(page, "document.getElementById('estado').textContent.includes('No hay cambios')")
    page.fill("input[data-clave='shape.panel_radius']", "10px;color:red")
    page.click("#guardar-estilo")
    _esperar(page, "document.getElementById('errores').textContent.includes('no permitidos')")
    assert not [e for e in errores if "422" not in e], errores  # solo el rechazo esperado
