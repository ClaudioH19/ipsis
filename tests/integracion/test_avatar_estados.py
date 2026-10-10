"""Folio y la máquina de estados del avatar (P12.10).

Casi todo se prueba con un ``avatar.js`` falso que registra cada llamada
(``play``, ``setExpression``, ``pause``) y el reloj falso de Playwright. La
última prueba usa la librería real: Folio con la grilla de mirada.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

from ipsis.configuracion.personalidad import EVENTOS, claves_sugeridas_avatar

RAIZ = Path(__file__).resolve().parents[2]
ESTATICOS = RAIZ / "ipsis/servicio/estaticos"
FOLIO = RAIZ / "ipsis/recursos/avatares/folio.avatar.json"
CONTRATO = ("idle", "wave", "attentive", "listening", "nod", "thinking", "thinking-long", "happy",
            "unsure", "sorry", "kind", "goodbye", "worried", "sleepy", "wake-up")

MOTOR_FALSO = """
export function createAvatar(el, o) {
  window.__llamadas = [["crear", o.defaultAnimation || o.defaultExpression || null]];
  window.__definicion = o.definition;
  const s = document.createElement("span");
  s.style.display = "block"; s.style.width = "100%"; s.style.height = "100%";
  el.appendChild(s);
  const r = (x) => { window.__llamadas.push(x); return { ok: true }; };
  return { play: (k) => r(["play", k]), setExpression: (k) => r(["expr", k]), pause: () => r(["pausa"]),
           stop: () => r(["stop"]), getState: () => ({}), destroy: () => {} };
}
"""


# --- Folio (sin navegador) ---------------------------------------------------------------------
def test_folio_define_todo_el_contrato_y_sus_colores():
    datos = json.loads(FOLIO.read_text(encoding="utf-8"))
    assert datos["schema"] == "bible-strong/avatar-definition" and datos["name"] == "Folio"
    assert set(CONTRATO) <= set(datos["animations"]) and "neutral" in datos["expressions"]
    assert datos["colors"] == {"body": "#f5f1e8", "eyes": "#1e293b"}
    assert all(EVENTOS[e][0] in datos["animations"] for e in EVENTOS)  # ningún evento cae a un respaldo
    # WCAG 2.3.1: ningún paso dura menos de 1/3 s si cambia de expresión (≤ 3 destellos por segundo).
    for anim in datos["animations"].values():
        for paso in anim["steps"]:
            assert paso["holdMs"] + paso["transitionMs"] >= 333 or len(anim["steps"]) == 1
        if anim["blink"]["enabled"]:
            assert anim["blink"]["minIntervalMs"] >= 1000


def test_folio_lo_acepta_la_libreria():
    herramienta = RAIZ / "herramientas/avatar"
    if not shutil.which("node") or not (herramienta / "node_modules/@bible-strong/avatar-core").is_dir():
        pytest.skip("sin node o sin 'npm ci' en herramientas/avatar")
    salida = subprocess.run(["node", "validar.mjs", str(FOLIO)], cwd=herramienta, capture_output=True, text=True)
    assert salida.returncode == 0, salida.stderr


def test_doctor_y_config_usan_folio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from ipsis.aplicacion.personalidad import config_avatar_publica
    from ipsis.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    publica = config_avatar_publica()
    assert publica["enabled"] and publica["definition_url"] == "/avatars/folio.avatar.json"
    assert publica["events"]["thinking_long"] == "thinking-long"
    assert publica["fallbacks"]["thinking_long"] == "thinking"
    assert publica["events"]["greeting"] == "wake-up"
    assert publica["events"]["idle"] == "float"
    assert publica["events"]["sent"] == "paper-plane-out"
    assert publica["events"]["answer_ok"] == "paper-plane-in"


# --- navegador ---------------------------------------------------------------------------------
playwright = pytest.importorskip("playwright.sync_api")


def _app(estado: dict):
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def pagina():
        return """<!doctype html><html lang="es"><head><meta charset="utf-8"></head><body style="margin:0">
<ipsis-chat titulo="Ayuda"></ipsis-chat><script src="/widget.js"></script></body></html>"""

    @app.get("/widget.js")
    def widget():
        return FileResponse(ESTATICOS / "widget.js", media_type="text/javascript")

    @app.get("/avatar.js")
    def motor():
        if estado.get("real"):
            return FileResponse(ESTATICOS / "avatar.js", media_type="text/javascript")
        return Response(MOTOR_FALSO, media_type="text/javascript")

    @app.get("/avatars/folio.avatar.json")
    def definicion():
        return json.loads(FOLIO.read_text(encoding="utf-8"))

    @app.get("/config")
    def config():
        datos = json.loads(FOLIO.read_text(encoding="utf-8"))
        eventos = claves_sugeridas_avatar("folio", tuple(datos["animations"]) + tuple(datos["expressions"]))
        eventos.update(estado.get("eventos", {}))
        return {"assistant_name": "Ayuda", "domain_description": "manual", "greeting": "Hola.", "interface": {},
                "microcopy": {}, "placement": {},
                "avatar": {"enabled": True, "name": "folio", "definition_url": "/avatars/folio.avatar.json",
                           "engine_url": "/avatar.js", "placement": "header", "size": 56, "in_launcher": False,
                           "gaze": {"enabled": True, "eye_range": 6, "head_range": 8, "dead_zone": 24},
                           "idle_minutes": 2, "events": eventos,
                           "fallbacks": {e: r for e, (_, r) in EVENTOS.items() if r in EVENTOS}}}

    @app.post("/ask")
    async def consultar(request: Request):
        import asyncio

        while estado.get("retener"):
            await asyncio.sleep(0.02)
        if estado.get("fallar"):
            return Response(status_code=500)
        return {"status": estado.get("estado", "ok"), "service_level": "normal", "plan": "extractive",
                "latency_ms": 1, "confidence": {"top1": 0.9, "margin": 0.1, "bm25_agreement": None},
                "answer": "Respuesta de prueba.", "exact_answer": None, "fragments": []}

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
    estado.clear()
    server.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture(scope="module")
def navegador():
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


def _esperar(page, expresion: str, limite_s: float = 10.0):
    fin = time.monotonic() + limite_s
    while time.monotonic() < fin:
        valor = page.evaluate(expresion)
        if valor:
            return valor
        time.sleep(0.03)
    raise AssertionError(f"no se cumplió: {expresion}")


def _llamadas(page) -> list:
    return page.evaluate("window.__llamadas || []")


def _abrir(navegador, base: str, reducido: bool = False):
    page = navegador.new_page(viewport={"width": 1280, "height": 800},
                              reduced_motion="reduce" if reducido else "no-preference")
    page.clock.install()
    page.goto(base)
    page.evaluate("window.Ipsis.open()")
    _esperar(page, "window.Ipsis.avatar.state().ready")
    # Con el reloj simulado las animaciones CSS no avanzan: el panel queda abierto del todo.
    page.evaluate("document.querySelector('ipsis-chat').shadowRoot.getAnimations().forEach(a => a.finish())")
    return page


def _ultima(page):
    return _llamadas(page)[-1]


def _limpiar(page):
    page.evaluate("window.__llamadas = []")


@pytest.mark.browser
def test_secuencia_de_una_pregunta(navegador, servidor):
    base, estado = servidor
    page = _abrir(navegador, base)
    llamadas = _llamadas(page)
    assert llamadas[0] == ["crear", "float"] and ["play", "wake-up"] in llamadas
    page.clock.run_for(3000)
    assert _ultima(page) == ["play", "attentive"]  # el saludo terminó: vuelve al persistente

    page.locator("ipsis-chat >> #rw-input").press_sequentially("hola")
    assert _ultima(page) == ["play", "listening"]
    page.clock.run_for(1300)  # 1,2 s sin teclear
    assert _ultima(page) == ["play", "attentive"]

    estado["retener"] = True
    _limpiar(page)
    page.locator("ipsis-chat >> #rw-input").press("Enter")
    assert _llamadas(page)[0] == ["play", "paper-plane-out"]
    page.clock.run_for(3300)  # al terminar el despegue la búsqueda ya supera los 3 s
    assert _ultima(page) == ["play", "thinking-long"]
    estado["retener"] = False
    page.wait_for_selector("ipsis-chat >> text=Respuesta de prueba.")
    assert _ultima(page) == ["play", "paper-plane-in"]
    page.clock.run_for(3300)  # aterrizaje y despliegue: 3,2 s
    assert _ultima(page) == ["play", "attentive"]
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("reducido", [False, True])
def test_folio_autonomo_reacciona_sin_cambiar_el_evento_y_respeta_pausa(navegador, servidor, reducido):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page(reduced_motion="reduce" if reducido else "no-preference")
    page.clock.install()
    page.goto(base)
    page.evaluate("""async () => {
      const {createAvatar} = await import('/avatar.js');
      const definition = await fetch('/avatars/folio.avatar.json').then(r => r.json());
      Math.random = () => 0;
      const el = document.createElement('div'); el.id = 'autonomo'; document.body.append(el);
      window.__finalesAuto = [];
      window.__auto = createAvatar(el, {definition, defaultAnimation:'float', autonomy:true,
        onAnimationEnd:k => window.__finalesAuto.push(k)});
      window.__fotoAuto = () => el.innerHTML;
    }""")
    page.clock.run_for(1600)
    assert page.evaluate("window.__auto.getState().reaction") is None
    page.clock.run_for(900)
    if reducido:
        assert page.evaluate("window.__auto.getState().reaction") is None
    else:
        assert page.evaluate("window.__auto.getState().reaction") == "look-left"
        assert page.locator('#autonomo [data-folio="ojo-izquierdo"]').get_attribute("height") != "20"
    assert page.evaluate("window.__auto.getState().activeAnimation") == "float"
    assert page.evaluate("window.__finalesAuto") == []
    page.evaluate("window.__auto.pause()")
    foto = page.evaluate("window.__fotoAuto()")
    page.clock.run_for(8000)
    assert page.evaluate("window.__fotoAuto()") == foto
    page.evaluate("window.__auto.play('float')")
    page.clock.run_for(1800)
    assert page.evaluate("window.__auto.getState().reaction") is None
    page.clock.run_for(2000)
    assert page.evaluate("window.__auto.getState().reaction") == (None if reducido else "look-right")
    page.evaluate("window.__auto.setAutonomy(false); window.__auto.play('paper-plane-out')")
    page.clock.run_for(6000)
    assert page.evaluate("window.__auto.getState().reaction") is None
    assert page.evaluate("window.__finalesAuto") == ["paper-plane-out"]
    page.evaluate("window.__auto.play('float'); window.__auto.setAutonomy(true); window.__auto.destroy()")
    page.clock.run_for(15000)
    assert page.locator("#autonomo").inner_html() == ""
    page.close()


@pytest.mark.browser
def test_autonomia_del_widget_cede_a_puntero_tecleo_y_busqueda(navegador, servidor):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page()
    page.add_init_script("Math.random = () => 0")
    page.clock.install()
    page.goto(base)
    page.evaluate("window.Ipsis.open()")
    _esperar(page, "window.Ipsis.avatar.state().ready")
    page.evaluate("document.querySelector('ipsis-chat').shadowRoot.getAnimations().forEach(a => a.finish())")
    page.evaluate("window.__reaccion = () => document.querySelector('ipsis-chat').shadowRoot.querySelector('.bs-avatar-folio').dataset.reaccion")
    page.clock.run_for(4300)
    assert page.evaluate("window.__reaccion()") == "look-left"
    assert page.evaluate("window.Ipsis.avatar.state().persistent") == "attentive"
    page.evaluate("document.dispatchEvent(new PointerEvent('pointermove', {clientX:1000,clientY:100}))")
    page.clock.run_for(50)
    assert page.evaluate("window.__reaccion()") == ""
    page.clock.run_for(2300)
    assert page.evaluate("window.__reaccion()") == ""
    page.clock.run_for(1500)
    assert page.evaluate("window.__reaccion()") == "look-right"
    page.locator("ipsis-chat >> #rw-input").fill("pregunta")
    assert page.evaluate("window.__reaccion()") == "curious"
    assert page.evaluate("window.Ipsis.avatar.state().persistent") == "typing"
    estado["retener"] = True
    page.locator("ipsis-chat >> #rw-input").press("Enter")
    page.clock.run_for(12000)
    assert page.evaluate("window.__reaccion()") == ""
    assert page.evaluate("window.Ipsis.avatar.state().persistent") == "thinking_long"
    estado["retener"] = False
    page.wait_for_selector("ipsis-chat >> text=Respuesta de prueba.")
    page.clock.run_for(4100)
    assert page.evaluate("window.__reaccion()") == ""
    page.clock.run_for(1700)
    assert page.evaluate("window.__reaccion()") != ""
    page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true, value:true}); document.dispatchEvent(new Event('visibilitychange'))")
    page.clock.run_for(20000)
    page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true, value:false}); document.dispatchEvent(new Event('visibilitychange'))")
    page.clock.run_for(1600)
    assert page.evaluate("window.__reaccion()") == ""
    page.clock.run_for(900)
    assert page.evaluate("window.__reaccion()") != ""
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("reducido", [False, True])
def test_folio_reacciona_al_contacto_y_al_borrador_sin_interrumpir_la_busqueda(navegador, servidor, reducido):
    base, estado = servidor
    estado["real"] = True
    page = _abrir(navegador, base, reducido=reducido)
    page.clock.run_for(2500)
    page.evaluate("window.__gesto = () => document.querySelector('ipsis-chat').shadowRoot.querySelector('.bs-avatar-folio').dataset.reaccion")
    cx, cy = _centro_avatar(page)
    _mover(page, cx, cy)
    assert page.evaluate("window.__gesto()") == ("" if reducido else "kind")
    for texto, clave in [("hola", "wink"), ("Dónde?", "curious"), ("¡Mira!", "surprised"),
                         (":)", "kind"), ("🙁", "sorry"), ("hola, tengo sueño", "sleepy"),
                         ("no entiendo", "unsure"), ("jajaja", "happy"), ("estoy nerviosa", "worried"),
                         ("investigar", "thinking"), ("de acuerdo", "nod-down"),
                         ("INCREÍBLE", "surprised"), ("te quiero", "kind"), ("borrador", "reading")]:
        page.locator("ipsis-chat >> #rw-input").fill(texto)
        assert page.evaluate("window.Ipsis.avatar.state().persistent") == "typing"
        assert page.evaluate("window.__gesto()") == ("" if reducido else clave)
    page.clock.run_for(1300)
    assert page.evaluate("window.Ipsis.avatar.state().persistent") == "attentive"
    assert page.evaluate("window.__gesto()") == ("" if reducido else "reading")
    page.evaluate("window.Ipsis.avatar.trigger('thinking')")
    page.locator("ipsis-chat >> #rw-input").fill("¿Otra pregunta?")
    assert page.evaluate("window.Ipsis.avatar.state().persistent") == "thinking"
    assert page.evaluate("window.__gesto()") == ""
    _mover(page, 0, 0)
    _mover(page, cx, cy)
    assert page.evaluate("window.__gesto()") == ""
    page.evaluate("window.Ipsis.avatar.trigger('error')")
    page.locator("ipsis-chat >> #rw-input").fill("hola")
    assert page.evaluate("window.Ipsis.avatar.state().transient") == "error"
    assert page.evaluate("window.__gesto()") == ""
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("reducido", [False, True])
def test_visualizador_permite_probar_mouse_y_escritura(navegador, servidor, tmp_path, reducido):
    base, estado = servidor
    estado["real"] = True
    datos = json.loads(FOLIO.read_text(encoding="utf-8"))
    eventos = claves_sugeridas_avatar("folio", tuple(datos["animations"]) + tuple(datos["expressions"]))
    page = navegador.new_page(viewport={"width": 1100, "height": 1200},
                              reduced_motion="reduce" if reducido else "no-preference")
    page.clock.install()
    page.route("**/visualizador", lambda r: r.fulfill(content_type="text/html", body=(RAIZ / "herramientas/avatar/visualizador.html").read_text(encoding="utf-8")))
    page.route("**/config", lambda r: r.fulfill(json={"events": eventos}))
    page.route("**/folio.avatar.json", lambda r: r.fulfill(json=datos))
    page.route("**/logo.svg", lambda r: r.fulfill(content_type="image/svg+xml", body=(RAIZ / "docs/assets/logo.svg").read_text(encoding="utf-8")))
    errores = []
    consultas = []
    page.on("pageerror", lambda e: errores.append(str(e)))
    page.on("request", lambda r: consultas.append(r.url) if r.url.endswith("/ask") else None)
    page.goto(base + "/visualizador")
    page.wait_for_selector(".bs-avatar-folio")
    page.locator("#situation").select_option("attentive")
    caja = page.locator("#avatar").bounding_box()
    page.mouse.move(caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2)
    page.clock.run_for(50)
    assert page.locator(".bs-avatar-folio").get_attribute("data-reaccion") == ("" if reducido else "kind")
    ojo = page.locator('[data-folio="ojo-izquierdo"]')
    page.mouse.move(1099, 0)
    page.clock.run_for(650)
    derecha = ojo.get_attribute("transform")
    page.mouse.move(0, 0)
    page.clock.run_for(650)
    if not reducido:
        assert ojo.get_attribute("transform") != derecha
    page.locator("#draft").fill("Hola Folio, ¿qué estás leyendo?")
    assert page.locator("#situation").input_value() == "typing"
    assert page.locator(".bs-avatar-folio").get_attribute("data-reaccion") == ("" if reducido else "curious")
    page.clock.run_for(650)
    page.screenshot(path=str(tmp_path / "folio-interactivo.png"), full_page=True)
    page.clock.run_for(650)
    assert page.locator("#situation").input_value() == "attentive"
    for texto, clave in [("tengo sueño", "sleepy"), ("no entiendo", "unsure"),
                         ("jajaja", "happy"), ("estoy preocupada", "worried"),
                         ("un momento", "thinking"), ("de acuerdo", "nod-down"),
                         ("increíble", "surprised"), ("te quiero", "kind")]:
        page.locator("#draft").fill(texto)
        assert page.locator(".bs-avatar-folio").get_attribute("data-reaccion") == ("" if reducido else clave)
        assert "undefined" not in page.locator("#interaction").inner_text()
    page.locator("#pause").click()
    congelado = page.locator("#avatar").inner_html()
    page.mouse.move(caja["x"], caja["y"])
    page.clock.run_for(10000)
    assert page.locator("#avatar").inner_html() == congelado
    assert not errores and not consultas
    assert page.locator("#error").inner_text() == ""
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("clave,azar", [("sway", 0.75), ("spin", 0.95), ("plane-trip", 0.999)])
def test_autonomia_reproduce_animaciones_completas_y_vuelve_al_reposo(navegador, servidor, tmp_path, clave, azar):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page()
    page.clock.install()
    page.goto(base)
    page.evaluate("""async () => {
      const {createAvatar} = await import('/avatar.js');
      const definition = await fetch('/avatars/folio.avatar.json').then(r => r.json());
      Math.random = () => 0;
      const el = document.createElement('div'); el.id = 'extra-auto'; document.body.append(el);
      window.__extraFinales = [];
      window.__extraAuto = createAvatar(el, {definition, defaultAnimation:'attentive', autonomy:true,
        onAnimationEnd:k => window.__extraFinales.push(k)});
    }""")
    page.clock.run_for(1600)
    page.evaluate("azar => {Math.random = () => azar}", azar)
    page.clock.run_for(1700)
    assert page.evaluate("window.__extraAuto.getState().reaction") == clave
    assert page.evaluate("window.__extraAuto.getState().activeAnimation") == "attentive"
    if clave == "plane-trip":
        assert float(page.locator('#extra-auto [data-folio="avion"]').get_attribute("opacity")) > 0.5
        assert float(page.locator('#extra-auto [data-folio="ojo-izquierdo"]').get_attribute("height")) > 5
        page.locator("#extra-auto").screenshot(path=str(tmp_path / "excursion-autonoma.png"))
    else:
        assert page.locator('#extra-auto [data-folio="movimiento"]').get_attribute("transform") != "translate(0 0) rotate(0) scale(1 1)"
    page.evaluate("window.__extraAuto.pause()")
    foto = page.locator("#extra-auto").inner_html()
    page.clock.run_for(10000)
    assert page.locator("#extra-auto").inner_html() == foto
    page.evaluate("window.__extraAuto.play('attentive')")
    if clave == "plane-trip":
        page.clock.run_for(3200)
        assert float(page.locator('#extra-auto [data-folio="avion"]').get_attribute("opacity")) > 0.5
    datos = json.loads(FOLIO.read_text(encoding="utf-8"))
    def duracion(k):
        return sum(p["holdMs"] + p["transitionMs"] for p in datos["animations"][k]["steps"])
    total = duracion(clave) if clave != "plane-trip" else duracion("paper-plane-out") + duracion("paper-plane-in")
    page.clock.run_for(total + 1000 - 1500 - (3200 if clave == "plane-trip" else 0))
    assert page.evaluate("window.__extraAuto.getState().reaction") is None
    assert page.evaluate("window.__extraAuto.getState().activeAnimation") == "attentive"
    assert page.evaluate("window.__extraFinales") == []
    assert float(page.locator('#extra-auto [data-folio="hoja"]').get_attribute("opacity")) == 1
    page.evaluate("window.__extraAuto.setAutonomy(false); window.__extraAuto.play('thinking')")
    page.clock.run_for(15000)
    assert page.evaluate("window.__extraAuto.getState().reaction") is None
    page.evaluate("window.__extraAuto.destroy()")
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("reducido", [False, True])
def test_flotacion_continua_en_reposo_atencion_y_mirada(navegador, servidor, reducido):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page(reduced_motion="reduce" if reducido else "no-preference")
    page.clock.install()
    page.goto(base)
    page.evaluate("""async () => {
      const {createAvatar} = await import('/avatar.js');
      const definition = await fetch('/avatars/folio.avatar.json').then(r => r.json());
      definition.expressions['mirada-prueba'] = structuredClone(definition.expressions.attentive);
      definition.expressions['mirada-prueba'].eyes.left.x += 8;
      definition.expressionOrder.push('mirada-prueba');
      const el = document.createElement('div'); el.id = 'flotacion-base'; document.body.append(el);
      window.__flotar = createAvatar(el, {definition, defaultAnimation:'idle', autonomy:false});
      window.__fondo = () => {
        const m = el.querySelector('[data-folio="movimiento"]').transform.baseVal.consolidate().matrix;
        return [m.a, m.b, m.c, m.d, m.e, m.f];
      };
    }""")
    identidad = [1, 0, 0, 1, 0, 0]
    for clave in ("idle", "attentive"):
        page.evaluate("k => window.__flotar.play(k)", clave)
        page.clock.run_for(600)
        a = page.evaluate("window.__fondo()")
        page.clock.run_for(300)
        b = page.evaluate("window.__fondo()")
        if reducido:
            assert a == pytest.approx(identidad)
            assert b == pytest.approx(identidad)
        else:
            assert a[5] < 0 and b != pytest.approx(a)
        assert page.evaluate("window.__flotar.getState().reaction") is None
    assert float(page.locator('#flotacion-base [data-folio="ojo-izquierdo"]').get_attribute("height")) == pytest.approx(64 * 78 / 196)
    page.evaluate("window.__flotar.setExpression('mirada-prueba')")
    page.clock.run_for(700)  # la transición de ojos ya terminó
    mirada = page.evaluate("window.__fondo()")
    page.clock.run_for(300)
    mirando = page.evaluate("window.__fondo()")
    if reducido:
        assert mirada == pytest.approx(identidad)
    else:
        assert mirando != pytest.approx(mirada)
    page.evaluate("window.__flotar.play('attentive')")
    # El último rAF precede a la llamada: acepta menos de un píxel de avance,
    # pero detecta un salto al inicio de la flotación.
    assert page.evaluate("window.__fondo()") == pytest.approx(mirando, abs=0.3)
    page.evaluate("window.__flotar.pause()")
    pausado = page.locator("#flotacion-base").inner_html()
    page.clock.run_for(5000)
    assert page.locator("#flotacion-base").inner_html() == pausado
    page.evaluate("window.__flotar.play('attentive')")
    page.clock.run_for(300)
    if not reducido:
        assert page.locator("#flotacion-base").inner_html() != pausado
    page.evaluate("window.__flotar.stop()")
    assert page.evaluate("window.__fondo()") == pytest.approx(identidad)
    page.evaluate("window.__flotar.destroy()")
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize(("estado_respuesta", "clave"), [("related", "unsure"), ("no_answer", "sorry"),
                                                         ("conversational", "kind")])
def test_cada_estado_de_respuesta(navegador, servidor, estado_respuesta, clave):
    base, estado = servidor
    estado["estado"] = estado_respuesta
    page = _abrir(navegador, base)
    page.locator("ipsis-chat >> #rw-input").fill("pregunta")
    page.locator("ipsis-chat >> #rw-input").press("Enter")
    page.wait_for_selector("ipsis-chat >> text=Respuesta de prueba.")
    assert _ultima(page) == ["play", clave]
    page.close()


@pytest.mark.browser
def test_un_error_durante_pensando_gana(navegador, servidor):
    base, estado = servidor
    estado["fallar"] = True
    page = _abrir(navegador, base)
    page.locator("ipsis-chat >> #rw-input").fill("pregunta")
    page.locator("ipsis-chat >> #rw-input").press("Enter")
    _esperar(page, "(window.__llamadas || []).some(l => l[1] === 'worried')")
    page.clock.run_for(3000)
    assert _ultima(page) == ["play", "attentive"]  # el transitorio vuelve al persistente
    page.close()


@pytest.mark.browser
def test_prioridades_y_respaldo(navegador, servidor):
    base, estado = servidor
    estado["eventos"] = {"answer_ok": "no-existe"}
    page = _abrir(navegador, base)
    page.clock.run_for(3000)
    _limpiar(page)
    page.evaluate("window.Ipsis.avatar.trigger('error')")
    page.evaluate("window.Ipsis.avatar.trigger('launcher')")  # menor prioridad: se descarta
    assert _llamadas(page) == [["play", "worried"]]
    page.clock.run_for(2000)
    _limpiar(page)
    page.evaluate("window.Ipsis.avatar.trigger('answer_ok')")
    assert _llamadas(page) == [["play", "float"]]  # la clave falta: respaldo del evento
    page.close()


@pytest.mark.browser
def test_inactividad_y_despertar(navegador, servidor):
    base, _ = servidor
    page = _abrir(navegador, base)
    page.clock.run_for(2 * 60_000 + 500)
    assert _ultima(page) == ["play", "sleepy"]
    _limpiar(page)
    page.locator("ipsis-chat >> #rw-input").press_sequentially("a")
    assert _llamadas(page)[0] == ["play", "wake-up"]
    page.close()


@pytest.mark.browser
def test_pestana_oculta_pausa(navegador, servidor):
    base, _ = servidor
    page = _abrir(navegador, base)
    page.evaluate("""Object.defineProperty(document, 'hidden', {value: true, configurable: true});
                     document.dispatchEvent(new Event('visibilitychange'))""")
    assert _ultima(page) == ["pausa"]
    page.close()


def _centro_avatar(page) -> tuple[float, float]:
    caja = page.evaluate("(() => { const r = document.querySelector('ipsis-chat').shadowRoot"
                         ".querySelector('.rw-avatar-lienzo').getBoundingClientRect(); "
                         "return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    return caja[0], caja[1]


def _mover(page, x: float, y: float) -> None:
    page.mouse.move(x, y)
    page.clock.run_for(40)  # el seguimiento va por requestAnimationFrame


@pytest.mark.browser
def test_grilla_de_mirada(navegador, servidor):
    base, _ = servidor
    page = _abrir(navegador, base)
    definicion = page.evaluate("window.__definicion")
    miradas = [k for k in definicion["expressionOrder"] if k.startswith("mirada-")]
    assert len(miradas) == 15 and all(k in definicion["expressions"] for k in miradas)
    page.clock.run_for(3000)  # termina el saludo
    cx, cy = _centro_avatar(page)

    esquinas = {(0, 0): "mirada-c0-f0", (1279, 0): "mirada-c4-f0", (0, 799): "mirada-c0-f2",
                (1279, 799): "mirada-c4-f2"}
    for (x, y), clave in esquinas.items():
        _mover(page, x, y)
        assert _ultima(page) == ["expr", clave], (x, y)

    page.clock.run_for(1600)  # quieto 1,5 s: vuelve al centro y al persistente
    assert _ultima(page) == ["play", "attentive"]

    _limpiar(page)
    _mover(page, cx + 10, cy - 8)  # zona muerta
    _mover(page, cx + 26, cy)  # pasa el umbral (24) pero no la histéresis (+6)
    assert _llamadas(page) == []
    _mover(page, cx + 31, cy)
    assert _ultima(page) == ["expr", "mirada-c3-f1"]
    _mover(page, cx + 29, cy)  # 2 px de vuelta: la histéresis lo retiene
    _mover(page, cx + 31, cy)
    assert _llamadas(page) == [["expr", "mirada-c3-f1"]]
    page.close()


@pytest.mark.browser
def test_con_movimiento_reducido_no_sigue_el_puntero(navegador, servidor):
    base, _ = servidor
    page = _abrir(navegador, base, reducido=True)
    page.clock.run_for(3000)
    _limpiar(page)
    _mover(page, 0, 0)
    assert _llamadas(page) == []
    page.close()


@pytest.mark.browser
def test_folio_real_con_la_grilla(navegador, servidor):
    """La librería real acepta Folio más las 15 expresiones de mirada (CSP sin restricciones)."""
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page(viewport={"width": 1280, "height": 800})
    errores: list[str] = []
    page.on("pageerror", lambda e: errores.append(str(e)))
    page.add_init_script("window.__avatar = []; document.addEventListener('ipsis:avatar', "
                         "e => window.__avatar.push(e.detail));")
    page.goto(base)
    page.evaluate("window.Ipsis.open()")
    _esperar(page, "window.Ipsis.avatar.state().ready")
    assert page.evaluate("window.__avatar[0]") == {"state": "ready", "name": "folio"}
    for evento in EVENTOS:
        assert page.evaluate(f"window.Ipsis.avatar.trigger('{evento}')")
    assert not [e for e in page.evaluate("window.__avatar") if e.get("state") == "error"]
    assert not errores, errores
    page.close()


@pytest.mark.browser
def test_despierta_en_cada_apertura_y_vuelve_a_flotar_al_cerrar(navegador, servidor):
    base, _ = servidor
    page = _abrir(navegador, base)
    page.clock.run_for(2500)
    _limpiar(page)
    page.evaluate("window.Ipsis.close()")
    assert _ultima(page) == ["play", "goodbye"]
    page.clock.run_for(3500)
    assert _ultima(page) == ["play", "float"]
    _limpiar(page)
    page.evaluate("window.Ipsis.open()")
    assert _llamadas(page) == [["play", "wake-up"]]
    page.clock.run_for(2000)
    assert _ultima(page) == ["play", "attentive"]
    # Una reapertura rápida interrumpe la despedida y conserva el despertar.
    page.evaluate("window.Ipsis.close(); window.Ipsis.open()")
    assert _ultima(page) == ["play", "wake-up"]
    page.close()


@pytest.mark.browser
def test_apertura_respeta_el_gesto_personalizado(navegador, servidor):
    base, estado = servidor
    estado["eventos"] = {"greeting": "spin"}
    page = _abrir(navegador, base)
    assert ["play", "spin"] in _llamadas(page)
    page.clock.run_for(2500)
    page.evaluate("window.Ipsis.close(); window.Ipsis.open()")
    assert _ultima(page) == ["play", "spin"]
    page.close()


@pytest.mark.browser
def test_folio_real_conserva_el_dibujo_y_los_colores_del_logo(navegador, servidor):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page()
    page.goto(base)
    dibujo = page.evaluate("""async () => {
      const { createAvatar } = await import('/avatar.js');
      const definition = await fetch('/avatars/folio.avatar.json').then(r => r.json());
      const el = document.createElement('div'); document.body.append(el);
      const avatar = createAvatar(el, { definition, defaultExpression: 'neutral', autoplay: false, size: 128 });
      const hoja = el.querySelector('[data-folio="hoja"]');
      const ojo = el.querySelector('[data-folio="ojo-izquierdo"]');
      const matriz = hoja.transform.baseVal.consolidate().matrix;
      const resultado = {
        matriz: [matriz.a, matriz.b, matriz.c, matriz.d, matriz.e, matriz.f],
        ancho: Number(ojo.getAttribute('width')), alto: Number(ojo.getAttribute('height')),
        papel: getComputedStyle(el.querySelector('[data-folio="papel"]')).fill,
        borde: getComputedStyle(el.querySelector('[data-folio="papel"]')).stroke,
        pliegue: getComputedStyle(el.querySelector('[data-folio="pliegue"]')).fill,
        azul: getComputedStyle(el.querySelector('[data-folio="resalte"]')).fill,
        tinta: getComputedStyle(ojo).fill,
      };
      avatar.destroy(); return resultado;
    }""")
    # La inclinación del logo es de -5 grados y sus ojos miden 9 x 20.
    assert dibujo["matriz"] == pytest.approx([0.996195, -0.087156, 0.087156, 0.996195, 0, 0], abs=1e-5)
    assert (dibujo["ancho"], dibujo["alto"]) == pytest.approx((9, 20))
    assert dibujo["papel"] == "rgb(245, 241, 232)"
    assert dibujo["borde"] == "rgb(214, 205, 184)"
    assert dibujo["pliegue"] == "rgb(228, 218, 196)"
    assert dibujo["azul"] == "rgb(147, 197, 253)"
    assert dibujo["tinta"] == "rgb(30, 41, 59)"
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("reducido", [False, True])
def test_folio_real_parpadea_pausa_reanuda_y_destruye(navegador, servidor, reducido):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page(reduced_motion="reduce" if reducido else "no-preference")
    page.clock.install()
    page.goto(base)
    page.evaluate("""async () => {
      const { createAvatar } = await import('/avatar.js');
      const definition = await fetch('/avatars/folio.avatar.json').then(r => r.json());
      // Un único gesto permite observar el parpadeo sin cambiar la mirada.
      definition.animations.idle.steps = [{ expression: 'neutral', holdMs: 10000, transitionMs: 0, transition: 'smooth' }];
      definition.animations.idle.blink.initialDelayMs = 1000;
      const el = document.createElement('div'); el.id = 'folio-prueba'; document.body.append(el);
      window.__folioFinales = [];
      window.__folio = createAvatar(el, { definition, defaultAnimation: 'idle', size: 128,
        onAnimationEnd: clave => window.__folioFinales.push(clave) });
      window.__folioFoto = () => el.innerHTML;
      window.__folioOjo = () => Number(el.querySelector('[data-folio="ojo-izquierdo"]').getAttribute('height'));
    }""")
    page.clock.run_for(1088)
    if reducido:
        assert page.evaluate("window.__folioOjo()") == pytest.approx(20)
    else:
        assert page.evaluate("window.__folioOjo()") < 5
    page.evaluate("window.__folio.pause()")
    pausado = page.evaluate("window.__folioFoto()")
    page.clock.run_for(2000)
    assert page.evaluate("window.__folioFoto()") == pausado
    assert page.evaluate("window.__folio.getState().status") == "paused"
    assert page.evaluate("window.__folio.play('idle').ok")
    page.clock.run_for(300)
    assert page.evaluate("window.__folioOjo()") == pytest.approx(20)
    assert page.evaluate("window.__folio.getState().status") == "playing"
    assert page.evaluate("window.__folio.play('inexistente').error.code") == "unknown_animation"
    page.evaluate("window.__folio.play('wave')")
    page.clock.run_for(4000)
    assert page.evaluate("window.__folioFinales") == ["wave"]
    assert page.evaluate("window.__folio.getState().status") == "stopped"
    page.evaluate("window.__folio.stop()")
    assert page.evaluate("window.__folio.getState().status") == "stopped"
    page.evaluate("window.__folio.play('idle'); window.__folio.destroy()")
    page.clock.run_for(2000)
    assert page.locator("#folio-prueba").inner_html() == ""
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("reducido", [False, True])
def test_folio_real_gira_salta_y_respeta_la_pausa(navegador, servidor, reducido):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page(reduced_motion="reduce" if reducido else "no-preference")
    page.clock.install()
    page.goto(base)
    page.evaluate("""async () => {
      const { createAvatar } = await import('/avatar.js');
      const definition = await fetch('/avatars/folio.avatar.json').then(r => r.json());
      const el = document.createElement('div'); document.body.append(el);
      window.__movimiento = createAvatar(el, { definition, defaultAnimation: 'spin' });
      window.__matriz = () => {
        const m = el.querySelector('[data-folio="movimiento"]').transform.baseVal.consolidate().matrix;
        return [m.a, m.b, m.c, m.d, m.e, m.f];
      };
      window.__frente = () => el.querySelector('[data-folio="cara"]').getAttribute('opacity');
    }""")
    identidad = [1, 0, 0, 1, 0, 0]
    page.clock.run_for(900)
    giro = page.evaluate("window.__matriz()")
    if reducido:
        assert giro == pytest.approx(identidad)
    else:
        assert giro[0] < -0.99 and giro[3] < -0.99  # Media vuelta: hoja invertida.
    page.clock.run_for(1000)
    assert page.evaluate("window.__matriz()") == pytest.approx(identidad, abs=1e-5)
    assert page.evaluate("window.__movimiento.getState().status") == "stopped"

    page.evaluate("window.__movimiento.play('flip')")
    page.clock.run_for(1000)
    if reducido:
        assert page.evaluate("window.__matriz()") == pytest.approx(identidad)
        assert page.evaluate("window.__frente()") == "1"
    else:
        assert page.evaluate("window.__matriz()[0]") < -0.99
        assert page.evaluate("window.__frente()") == "0"  # El reverso no muestra la cara.
    page.clock.run_for(1100)
    assert page.evaluate("window.__matriz()") == pytest.approx(identidad, abs=1e-5)
    assert page.evaluate("window.__frente()") == "1"

    page.evaluate("window.__movimiento.play('bounce')")
    page.clock.run_for(400)
    salto = page.evaluate("window.__matriz()")
    if reducido:
        assert salto == pytest.approx(identidad)
    else:
        assert salto[5] < -10
    page.evaluate("window.__movimiento.pause()")
    pausado = page.evaluate("window.__matriz()")
    page.clock.run_for(2000)
    assert page.evaluate("window.__matriz()") == pausado
    page.evaluate("window.__movimiento.play('bounce')")
    assert page.evaluate("window.__matriz()") == pytest.approx(pausado)
    page.clock.run_for(1200)
    assert page.evaluate("window.__matriz()") == pytest.approx(identidad, abs=1e-5)

    for clave in ("sway", "dance", "float"):
        page.evaluate(f"window.__movimiento.play('{clave}')")
        page.clock.run_for(500)
        movimiento = page.evaluate("window.__matriz()")
        if reducido:
            assert movimiento == pytest.approx(identidad)
        else:
            assert movimiento != pytest.approx(identidad)
        page.clock.run_for(4500)
        assert page.evaluate("window.__movimiento.getState().status") == "playing"
    page.evaluate("window.__movimiento.stop()")
    assert page.evaluate("window.__matriz()") == pytest.approx(identidad)
    page.evaluate("window.__movimiento.destroy()")
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize("reducido", [False, True])
def test_folio_avion_dobla_vuela_vuelve_y_se_puede_interrumpir(navegador, servidor, tmp_path, reducido):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page(reduced_motion="reduce" if reducido else "no-preference")
    errores = []
    page.on("pageerror", lambda error: errores.append(str(error)))
    page.clock.install()
    page.goto(base)
    page.evaluate("""async () => {
      const { createAvatar } = await import('/avatar.js');
      const definition = await fetch('/avatars/folio.avatar.json').then(r => r.json());
      const el = document.createElement('div'); el.id = 'avion-prueba';
      el.style.cssText = 'width:260px;height:260px;background:#111923'; document.body.append(el);
      window.__avion = createAvatar(el, { definition, size:260, defaultAnimation:'paper-plane-out' });
      window.__estadoAvion = () => ({
        hoja: Number(el.querySelector('[data-folio="hoja"]').getAttribute('opacity')),
        avion: Number(el.querySelector('[data-folio="avion"]').getAttribute('opacity')),
        paneles: [...el.querySelectorAll('[data-folio^="ala-"]')].map(p => p.getAttribute('d')),
        vuelo: el.querySelector('[data-folio="avion"]').getAttribute('transform'),
        rostro: Number(el.querySelector('[data-folio="rostro"]').getAttribute('opacity')),
        ojos: [...el.querySelectorAll('[data-folio^="ojo-"]')].map(o => Number(o.getAttribute('height'))),
      });
    }""")
    page.clock.run_for(400)
    esquinas = page.evaluate("window.__estadoAvion()")
    page.clock.run_for(700)
    cuerpo = page.evaluate("window.__estadoAvion()")
    assert esquinas["rostro"] == 1 and cuerpo["rostro"] == 1
    assert len(cuerpo["ojos"]) == 2 and all(alto > 0 for alto in cuerpo["ojos"])
    if reducido:
        assert cuerpo["hoja"] == 1 and cuerpo["avion"] == 0
    else:
        assert cuerpo["paneles"] != esquinas["paneles"]
        assert all("Q" in panel for panel in cuerpo["paneles"])
        assert cuerpo["hoja"] == 0 and cuerpo["avion"] == 1
        page.locator("#avion-prueba").screenshot(path=str(tmp_path / "avion-dobleces.png"))
    page.evaluate("window.__avion.pause()")
    pausado = page.locator("#avion-prueba").inner_html()
    page.clock.run_for(1200)
    assert page.locator("#avion-prueba").inner_html() == pausado
    page.evaluate("window.__avion.play('paper-plane-out')")
    page.clock.run_for(850)
    if not reducido:
        assert page.evaluate("window.__estadoAvion().rostro") == 1
        page.locator("#avion-prueba").screenshot(path=str(tmp_path / "avion-doblado.png"))
    page.clock.run_for(700)
    volando = page.evaluate("window.__estadoAvion()")
    if not reducido:
        assert volando["vuelo"] != cuerpo["vuelo"]
    page.clock.run_for(600)
    assert page.evaluate("window.__avion.getState().status") == "stopped"
    assert page.evaluate("window.__estadoAvion().hoja") == 1
    assert page.evaluate("window.__estadoAvion().avion") == 0
    assert page.evaluate("window.__estadoAvion().rostro") == 1

    page.evaluate("window.__avion.play('paper-plane-in')")
    page.clock.run_for(1100)
    if not reducido:
        assert page.evaluate("window.__estadoAvion().avion") == 1
        assert page.evaluate("window.__estadoAvion().rostro") == 1
        page.locator("#avion-prueba").screenshot(path=str(tmp_path / "avion-llegada.png"))
    page.clock.run_for(2200)
    assert page.evaluate("window.__estadoAvion().hoja") == 1
    assert page.evaluate("window.__estadoAvion().avion") == 0
    assert page.evaluate("window.__estadoAvion().rostro") == 1
    assert page.evaluate("window.__avion.getState().status") == "stopped"

    # Una respuesta rápida y el seguimiento del puntero pueden cortar el vuelo.
    page.evaluate("window.__avion.play('paper-plane-out')")
    page.clock.run_for(1200)
    page.evaluate("window.__avion.play('paper-plane-in')")
    page.clock.run_for(400)
    page.evaluate("window.__avion.setExpression('attentive')")
    assert page.evaluate("window.__estadoAvion().hoja") == 1
    assert page.evaluate("window.__estadoAvion().avion") == 0
    page.evaluate("window.__avion.stop(); window.__avion.destroy()")
    assert page.locator("#avion-prueba").inner_html() == ""
    assert not errores
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize(("azar", "sentido"), [(0.1, -1), (0.9, 1)])
def test_folio_avion_varia_recorrido_y_anima_rafagas(navegador, servidor, tmp_path, azar, sentido):
    base, estado = servidor
    estado["real"] = True
    page = navegador.new_page(reduced_motion="no-preference")
    page.clock.install()
    page.goto(base)
    page.evaluate("""async () => {
      const { createAvatar } = await import('/avatar.js');
      const definition = await fetch('/avatars/folio.avatar.json').then(r => r.json());
      const el = document.createElement('div'); el.id = 'vuelo-prueba';
      el.style.cssText = 'width:260px;height:260px;background:#111923'; document.body.append(el);
      window.__vuelo = createAvatar(el, { definition, size:260, autoplay:false });
      window.__arrancar = (clave, azar) => {
        const original = Math.random; Math.random = () => azar;
        try { window.__vuelo.play(clave); } finally { Math.random = original; }
      };
      window.__fotoVuelo = () => {
        const avion = el.querySelector('[data-folio="avion"]');
        const m = avion.transform.baseVal.consolidate().matrix;
        return { sentido:Number(avion.dataset.sentido), x:m.e, y:m.f,
          viento:el.querySelector('[data-folio="estela"]').innerHTML,
          visible:Number(el.querySelector('[data-folio="estela"]').getAttribute('opacity')) };
      };
    }""")
    page.evaluate("([clave, azar]) => window.__arrancar(clave, azar)", ["paper-plane-out", azar])
    page.clock.run_for(2200)
    despegue = page.evaluate("window.__fotoVuelo()")
    assert despegue["sentido"] == sentido and despegue["x"] * sentido > 5
    assert despegue["y"] < 0 and despegue["visible"] > 0
    page.clock.run_for(90)
    assert page.evaluate("window.__fotoVuelo().viento") != despegue["viento"]
    page.evaluate("window.__vuelo.pause()")
    page.locator("#vuelo-prueba").screenshot(path=str(tmp_path / "despegue-rafagas.png"))
    pausado = page.locator("#vuelo-prueba").inner_html()
    page.clock.run_for(800)
    assert page.locator("#vuelo-prueba").inner_html() == pausado
    # Reanudar conserva la dirección, aunque otra llamada al azar elegiría la contraria.
    page.evaluate("([clave, azar]) => window.__arrancar(clave, azar)", ["paper-plane-out", 1 - azar])
    assert page.evaluate("window.__fotoVuelo().sentido") == sentido
    page.clock.run_for(1000)
    assert page.evaluate("window.__vuelo.getState().status") == "stopped"

    page.evaluate("([clave, azar]) => window.__arrancar(clave, azar)", ["paper-plane-in", azar])
    page.clock.run_for(400)
    llegada = page.evaluate("window.__fotoVuelo()")
    assert llegada["sentido"] == sentido and llegada["x"] * sentido < -5
    assert llegada["y"] > 0 and llegada["visible"] > 0
    page.clock.run_for(100)
    assert page.evaluate("window.__fotoVuelo().viento") != llegada["viento"]
    page.clock.run_for(800)
    page.locator("#vuelo-prueba").screenshot(path=str(tmp_path / "aterrizaje-redondo.png"))
    page.clock.run_for(2000)
    assert page.evaluate("window.__vuelo.getState().status") == "stopped"
    assert page.evaluate("window.__fotoVuelo().visible") == 0
    page.evaluate("window.__vuelo.destroy()")
    page.close()
