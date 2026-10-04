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

from ipsis.configuracion.personalidad import EVENTOS

RAIZ = Path(__file__).resolve().parents[2]
ESTATICOS = RAIZ / "ipsis/servicio/estaticos"
FOLIO = RAIZ / "ipsis/recursos/avatares/folio.avatar.json"
CONTRATO = ("inactivo", "saludo", "atento", "escuchando", "asentir", "pensando", "pensando-largo", "contento",
            "dudoso", "apenado", "amable", "despedida", "preocupado", "somnoliento", "despertar")

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
    assert main(["init", "--perfil", "light"]) == 0
    publica = config_avatar_publica()
    assert publica["activo"] and publica["url_definicion"] == "/avatares/folio.avatar.json"
    assert publica["eventos"]["pensando_largo"] == "pensando-largo"
    assert publica["respaldos"]["pensando_largo"] == "pensando"


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

    @app.get("/avatares/folio.avatar.json")
    def definicion():
        return json.loads(FOLIO.read_text(encoding="utf-8"))

    @app.get("/config")
    def config():
        eventos = {e: s for e, (s, _) in EVENTOS.items()}
        eventos.update(estado.get("eventos", {}))
        return {"nombre_asistente": "Ayuda", "descripcion_dominio": "manual", "saludo": "Hola.", "interfaz": {},
                "microcopia": {}, "ubicacion": {},
                "avatar": {"activo": True, "nombre": "folio", "url_definicion": "/avatares/folio.avatar.json",
                           "url_motor": "/avatar.js", "ubicacion": "cabecera", "tamano": 56, "en_lanzador": False,
                           "mirada": {"activa": True, "amplitud_ojos": 6, "amplitud_cabeza": 8, "zona_muerta": 24},
                           "inactividad_min": 2, "eventos": eventos,
                           "respaldos": {e: r for e, (_, r) in EVENTOS.items() if r in EVENTOS}}}

    @app.post("/consultar")
    async def consultar(request: Request):
        import asyncio

        while estado.get("retener"):
            await asyncio.sleep(0.02)
        if estado.get("fallar"):
            return Response(status_code=500)
        return {"estado": estado.get("estado", "ok"), "nivel_servicio": "normal", "plan": "extractivo",
                "latencia_ms": 1, "confianza": {"top1": 0.9, "margen": 0.1, "acuerdo_bm25": None},
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
    page.evaluate("window.RagChat.abrir()")
    _esperar(page, "window.RagChat.avatar.estado().listo")
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
    assert llamadas[0] == ["crear", "inactivo"] and ["play", "saludo"] in llamadas
    page.clock.run_for(3000)
    assert _ultima(page) == ["play", "atento"]  # el saludo terminó: vuelve al persistente

    page.locator("ipsis-chat >> #rw-input").press_sequentially("hola")
    assert _ultima(page) == ["play", "escuchando"]
    page.clock.run_for(1300)  # 1,2 s sin teclear
    assert _ultima(page) == ["play", "atento"]

    estado["retener"] = True
    _limpiar(page)
    page.locator("ipsis-chat >> #rw-input").press("Enter")
    assert _llamadas(page)[0] == ["play", "asentir"]
    page.clock.run_for(1700)  # asentir de Folio: 1,58 s
    assert _ultima(page) == ["play", "pensando"]
    page.clock.run_for(3000)
    assert _ultima(page) == ["play", "pensando-largo"]
    estado["retener"] = False
    page.wait_for_selector("ipsis-chat >> text=Respuesta de prueba.")
    assert _ultima(page) == ["play", "contento"]
    page.clock.run_for(3500)  # contento de Folio: 3,02 s
    assert _ultima(page) == ["play", "atento"]
    page.close()


@pytest.mark.browser
@pytest.mark.parametrize(("estado_respuesta", "clave"), [("relacionado", "dudoso"), ("sin_respuesta", "apenado"),
                                                         ("conversacional", "amable")])
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
    _esperar(page, "(window.__llamadas || []).some(l => l[1] === 'preocupado')")
    page.clock.run_for(3000)
    assert _ultima(page) == ["play", "atento"]  # el transitorio vuelve al persistente
    page.close()


@pytest.mark.browser
def test_prioridades_y_respaldo(navegador, servidor):
    base, estado = servidor
    estado["eventos"] = {"respuesta_ok": "no-existe"}
    page = _abrir(navegador, base)
    page.clock.run_for(3000)
    _limpiar(page)
    page.evaluate("window.RagChat.avatar.disparar('error')")
    page.evaluate("window.RagChat.avatar.disparar('lanzador')")  # menor prioridad: se descarta
    assert _llamadas(page) == [["play", "preocupado"]]
    page.clock.run_for(2000)
    _limpiar(page)
    page.evaluate("window.RagChat.avatar.disparar('respuesta_ok')")
    assert _llamadas(page) == [["play", "inactivo"]]  # la clave falta: respaldo del evento
    page.close()


@pytest.mark.browser
def test_inactividad_y_despertar(navegador, servidor):
    base, _ = servidor
    page = _abrir(navegador, base)
    page.clock.run_for(2 * 60_000 + 500)
    assert _ultima(page) == ["play", "somnoliento"]
    _limpiar(page)
    page.locator("ipsis-chat >> #rw-input").press_sequentially("a")
    assert _llamadas(page)[0] == ["play", "despertar"]
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
    assert _ultima(page) == ["play", "atento"]

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
    page.add_init_script("window.__avatar = []; document.addEventListener('rag:avatar', "
                         "e => window.__avatar.push(e.detail));")
    page.goto(base)
    page.evaluate("window.RagChat.abrir()")
    _esperar(page, "window.RagChat.avatar.estado().listo")
    assert page.evaluate("window.__avatar[0]") == {"estado": "listo", "nombre": "folio"}
    for evento in EVENTOS:
        assert page.evaluate(f"window.RagChat.avatar.disparar('{evento}')")
    assert not [e for e in page.evaluate("window.__avatar") if e.get("estado") == "error"]
    assert not errores, errores
    page.close()
