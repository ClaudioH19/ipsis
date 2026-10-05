"""Tests de lo que el servicio necesita para sostener un frontend (Etapa
Plugin, Tarea A: CORS, autenticación de widget, límite de peticiones) y de
los endpoints del widget (Tarea B: ``/config``, ``/widget.js``,
``/widget/demo.html``).

A propósito, NINGUNO de estos tests requiere el corpus real ni el índice
Qdrant: usan ``TestClient(app)`` SIN el context manager (``with``), que en
FastAPI/Starlette es lo que dispara el evento ``startup`` -- así corren
siempre, en cualquier máquina, sin depender de que ``ipsis indexar``
se haya corrido antes (a diferencia de ``tests/integracion/test_caracterizacion.py``, que sí lo
necesita y se salta si falta). Esto es posible porque la seguridad de borde
(clave de widget + límite de peticiones) se resuelve como una dependencia de
FastAPI que corre ANTES que el cuerpo de la ruta -- ver
``ipsis/servicio/api.py::_verificar_seguridad`` -- y ``/config``/``/widget.js``/
``/widget/demo.html`` tampoco tocan el índice.

Los tests de autenticación y límite de peticiones reemplazan los atributos
de ``app.state.servicio`` con ``monkeypatch``. El estado pertenece a esta
instancia de aplicación; ``crear_app`` produce otro estado y otro *token
bucket* para cada aplicación."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ipsis.servicio.api import app
from ipsis.servicio.seguridad import NOMBRE_CABECERA_CLAVE_WIDGET, LimitadorPeticiones

client = TestClient(app)  # SIN 'with': no dispara startup (no requiere corpus/índice)
estado = app.state.servicio


@pytest.fixture(autouse=True)
def _aislar_seguridad(monkeypatch: pytest.MonkeyPatch):
    """Cada test de este archivo arranca con autenticación DESACTIVADA (sin
    claves) y un limitador propio con capacidad amplia -- los tests que
    quieren probar lo contrario lo configuran ellos mismos con
    ``monkeypatch``, que restaura el valor original al terminar."""
    monkeypatch.setattr(estado, "claves_widget", [])
    monkeypatch.setattr(estado, "limitador", LimitadorPeticiones(capacidad=1000, tasa_por_segundo=1000.0))
    yield


def _consultar(pregunta: str = "hola", **kwargs):
    return client.post("/consultar", json={"pregunta": pregunta, "id_sesion": "test-seguridad"}, **kwargs)


# ---------------------------------------------------------------------------
# CORS: cors_origenes está VACÍO por defecto (config/assistant.yaml, corregido
# en esta tanda) -- CUALQUIER origen cuenta como "no listado".
# ---------------------------------------------------------------------------

def test_origen_no_listado_preflight_es_rechazado():
    """Una petición preflight (OPTIONS, la que dispara el navegador antes de
    un POST entre orígenes) desde un origen no permitido recibe 400 de
    CORSMiddleware -- 'Disallowed CORS origin'. No requiere /consultar real:
    /health basta (CORS se aplica a nivel de middleware, antes de la ruta)."""
    r = client.options(
        "/health",
        headers={
            "Origin": "https://sitio-no-autorizado.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 400
    assert "disallowed" in r.text.lower()


def test_origen_no_listado_no_recibe_cabecera_de_permiso():
    """En una petición normal (no preflight), el servidor SÍ responde, pero
    sin 'Access-Control-Allow-Origin' -- es el navegador quien bloquea la
    lectura de la respuesta del lado del cliente. Con cors_origenes=[] (el
    valor por defecto de fábrica, ya corregido en esta tanda) esto vale para
    CUALQUIER origen."""
    r = client.get("/health", headers={"Origin": "https://cualquier-sitio.test"})
    assert r.status_code == 200  # el servidor igual responde...
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers.keys()}  # ...pero sin permiso CORS


# ---------------------------------------------------------------------------
# Autenticación de widget (clave pública por sitio)
# ---------------------------------------------------------------------------

def test_sin_claves_configuradas_no_exige_autenticacion(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(estado, "claves_widget", [])
    r = _consultar()  # "hola" -> conversacional, no necesita el índice
    assert r.status_code == 200
    assert r.json()["estado"] == "conversacional"


def test_clave_invalida_no_pasa(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(estado, "claves_widget", ["clave-correcta"])
    r = _consultar(headers={NOMBRE_CABECERA_CLAVE_WIDGET: "clave-incorrecta"})
    assert r.status_code == 401


def test_clave_ausente_no_pasa_cuando_hay_claves_configuradas(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(estado, "claves_widget", ["clave-correcta"])
    r = _consultar()  # sin cabecera
    assert r.status_code == 401


def test_clave_valida_si_pasa(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(estado, "claves_widget", ["clave-correcta", "clave-de-otro-sitio"])
    r = _consultar(headers={NOMBRE_CABECERA_CLAVE_WIDGET: "clave-correcta"})
    assert r.status_code == 200
    assert r.json()["estado"] == "conversacional"


# ---------------------------------------------------------------------------
# Límite de peticiones (token bucket)
# ---------------------------------------------------------------------------

def test_limite_de_peticiones_dispara_despues_de_n_llamadas(monkeypatch: pytest.MonkeyPatch):
    """Con una capacidad de 3 y recarga despreciable, las primeras 3
    peticiones se admiten y la 4ª se rechaza con 429 + Retry-After --
    criterio de cierre 2 del encargo, verificado contra el endpoint HTTP
    real (no solo contra LimitadorPeticiones en aislamiento, ver
    tests/servicio/test_seguridad.py)."""
    monkeypatch.setattr(estado, "claves_widget", [])
    monkeypatch.setattr(estado, "limitador", LimitadorPeticiones(capacidad=3, tasa_por_segundo=1e-9))

    for n in range(3):
        r = _consultar()
        assert r.status_code == 200, f"la petición {n + 1}/3 debía admitirse"

    r = _consultar()
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_limite_es_por_identificador_clave_mas_ip(monkeypatch: pytest.MonkeyPatch):
    """Dos claves distintas no comparten el mismo bucket -- agotar la de una
    no afecta a la otra (mismo cliente HTTP, misma IP, distinta clave)."""
    monkeypatch.setattr(estado, "claves_widget", ["clave-a", "clave-b"])
    monkeypatch.setattr(estado, "limitador", LimitadorPeticiones(capacidad=1, tasa_por_segundo=1e-9))

    r1 = _consultar(headers={NOMBRE_CABECERA_CLAVE_WIDGET: "clave-a"})
    assert r1.status_code == 200
    r2 = _consultar(headers={NOMBRE_CABECERA_CLAVE_WIDGET: "clave-a"})
    assert r2.status_code == 429  # clave-a ya agotó su bucket

    r3 = _consultar(headers={NOMBRE_CABECERA_CLAVE_WIDGET: "clave-b"})
    assert r3.status_code == 200  # clave-b tiene el suyo propio, intacto


def test_seguridad_se_resuelve_antes_que_lo_conversacional(monkeypatch: pytest.MonkeyPatch):
    """La clave inválida rechaza incluso un saludo (que de otro modo se
    resolvería sin tocar el índice) -- confirma que la dependencia de
    FastAPI corre ANTES que el cuerpo de la ruta, no que 'hola' sea un caso
    especial exento de autenticación."""
    monkeypatch.setattr(estado, "claves_widget", ["clave-correcta"])
    r = _consultar(pregunta="hola", headers={NOMBRE_CABECERA_CLAVE_WIDGET: "clave-mala"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# /config -- textos del servidor para el widget
# ---------------------------------------------------------------------------

def test_config_devuelve_los_textos_del_dominio():
    r = client.get("/config")
    assert r.status_code == 200
    body = r.json()
    assert body["nombre_asistente"]
    assert body["descripcion_dominio"]
    assert body["saludo"]
    assert body["preset"] in {"clasico", "minimal", "editorial", "contraste"}
    assert body["densidad"] in {"comoda", "compacta"}
    assert body["citas"] in {"acordeon", "abiertas", "ocultas"}
    assert isinstance(body["mostrar_etiqueta_estado"], bool)
    # el saludo real del paquete de idioma, con las variables ya
    # sustituidas (nunca la plantilla cruda con '{nombre_asistente}' sin
    # rellenar) -- misma función que responde un "hola" real.
    assert "{" not in body["saludo"]
    assert body["interfaz"]["placeholder"]
    assert body["interfaz"]["error_red"]


def test_config_no_exige_clave_de_widget(monkeypatch: pytest.MonkeyPatch):
    """Decisión de diseño (documentada en el informe de esta tanda, no solo
    en el código): '/config' entrega texto de PRESENTACIÓN, no datos del
    corpus -- se deja sin autenticar a propósito para que el widget pueda
    mostrar el nombre/saludo del asistente incluso antes de tener una clave
    válida a mano."""
    monkeypatch.setattr(estado, "claves_widget", ["clave-necesaria-solo-para-consultar"])
    r = client.get("/config")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# /widget.js y /widget/demo.html
# ---------------------------------------------------------------------------

def test_widget_js_responde_200_con_tipo_javascript():
    r = client.get("/widget.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"].lower()
    assert "attachShadow" in r.text  # confirma que es el widget real, no un placeholder


def test_widget_js_no_usa_innerhtml_en_ningun_punto():
    """Chequeo estático barato (no reemplaza una revisión manual, pero
    atrapa la regresión más peligrosa): el archivo entero no debe contener
    ``.innerHTML`` -- todo texto que venga de la API se asigna con
    ``textContent`` (ver ``agregarMensajeAsistente``/``agregarCitas`` en
    ``ipsis/servicio/estaticos/widget.js``)."""
    texto = client.get("/widget.js").text
    assert ".innerHTML" not in texto, "el widget no debe usar innerHTML en ningún punto (política de este proyecto)"


def test_widget_demo_html_solo_en_desarrollo_o_con_rag_demo():
    from ipsis.aplicacion.modo import ModoServicio
    from ipsis.servicio.api import crear_app

    assert client.get("/widget/demo.html").status_code == 404  # producción por defecto
    for modo in (ModoServicio(modo="desarrollo", demo=True), ModoServicio(demo=True)):
        r = TestClient(crear_app(modo=modo)).get("/widget/demo.html")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"].lower()
        assert "/widget.js" in r.text


# ---------------------------------------------------------------------------
# Diseño del widget: chequeos estáticos de lo que no debe perderse al
# repintarlo. No reemplazan una revisión visual en un navegador.
# ---------------------------------------------------------------------------

def test_widget_js_dibuja_los_cuatro_estados_distinto():
    """Los cuatro estados tienen su propia clase y ninguna es idéntica a
    otra. Si el widget los pintara iguales, se perdería la diferencia entre
    'esto lo dice el documento' y 'esto es lo más parecido que encontré',
    que es la mitad de la honestidad del sistema."""
    texto = client.get("/widget.js").text
    reglas = {}
    for estado in ("ok", "relacionado", "sin_respuesta", "conversacional"):
        marca = ".rw-msg-" + estado + "{"
        assert marca in texto, f"falta la clase del estado {estado}"
        inicio = texto.index(marca)
        reglas[estado] = texto[inicio:inicio + 200]
    assert len(set(reglas.values())) == 4, "dos estados comparten exactamente el mismo estilo"


def test_widget_js_usa_svg_y_no_emoji_para_los_iconos():
    """Un emoji se dibuja distinto en cada sistema operativo y trae su
    propio color; un SVG hereda `currentColor` y se ve igual en todas
    partes. Los iconos se construyen con createElementNS, no con
    innerHTML."""
    texto = client.get("/widget.js").text
    assert "createElementNS" in texto
    assert "\U0001f4ac" not in texto, "quedó un emoji como icono"


def test_widget_js_tiene_indicador_de_espera():
    """Entre que se envía la pregunta y llega la respuesta el widget no debe
    quedarse mudo: hay un indicador de 'escribiendo' que se muestra y se
    retira en el `finally` de la petición."""
    texto = client.get("/widget.js").text
    assert "mostrarEscribiendo" in texto and "ocultarEscribiendo" in texto


def test_widget_js_conserva_las_garantias_de_accesibilidad():
    """Foco atrapado, cierre con Escape y roles ARIA: no deben perderse al
    repintar el widget."""
    texto = client.get("/widget.js").text
    for marca in ('"role", INCRUSTADO ? "region" : "dialog"', 'aria-modal', '"Escape"', 'aria-live'):
        assert marca in texto, f"falta {marca}"
