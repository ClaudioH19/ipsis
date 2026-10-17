"""La página de prueba comparte servicio y tema, conservando el acceso al panel."""
from fastapi.testclient import TestClient

from ipsis.aplicacion.modo import ModoServicio
from ipsis.servicio.api import crear_app


def test_demo_habilitada_no_habilita_admin_y_renderiza_idioma():
    cliente = TestClient(crear_app(modo=ModoServicio(demo=True)))
    html = cliente.get("/widget/demo.html").text
    assert "Encuentra lo que necesitas" in html
    assert '<ipsis-chat mode="embedded"' in html and 'href="/styles.css"' in html
    assert "{{" not in html and "[[" not in html
    assert '/admin/panel' not in html
    assert cliente.get("/admin/status").status_code == 404


def test_demo_y_panel_se_enlazan_sin_publicar_token():
    token = "t" * 48
    cliente = TestClient(crear_app(modo=ModoServicio(demo=True, token_admin=token)), base_url="https://testserver")
    html = cliente.get("/widget/demo.html").text
    assert 'href="/admin/panel"' in html and token not in html
    panel = cliente.get("/admin/panel").text
    assert 'href="/widget/demo.html"' in panel and "[[DEMO_LINK]]" not in panel
    assert token not in panel


def test_raiz_redirige_a_widget_o_panel_y_respeta_desactivacion():
    for modo, destino in [(ModoServicio(demo=True), "/widget/demo.html"),
                          (ModoServicio(token_admin="a" * 40), "/admin/panel")]:
        respuesta = TestClient(crear_app(modo=modo)).get("/", follow_redirects=False)
        assert respuesta.status_code == 307 and respuesta.headers["location"] == destino
    cliente = TestClient(crear_app(modo=ModoServicio(modo="desarrollo", demo=False)))
    assert cliente.get("/").status_code == 404
    assert cliente.get("/widget/demo.html").status_code == 404


def test_v2_publica_banco_y_cortesia_sin_filtrar_preguntas_documentales(tmp_path, monkeypatch):
    from ipsis.cli import main
    from ipsis.lenguaje.paquete import cargar_paquete
    from tests.consulta.test_motor_v2 import motor

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    m = motor(idioma=cargar_paquete("es"), opciones={"corregir_erratas": False})
    m.plantillas["conversacional"] = m.idioma.conversacional.model_dump()
    cliente = TestClient(crear_app(m, modo=ModoServicio(demo=True)))
    cfg = cliente.get("/config").json()
    assert sum(map(len, cfg["assistant_messages"].values())) >= 100
    assert len(cfg["default_questions"]) >= 100
    assert cfg["interface"]["voice_help"] == "Cómo buscar" and cfg["animations_enabled"] is True
    for pregunta in ("hola", "gracias", "adiós", "¿Qué puedes hacer?"):
        r = cliente.post("/ask", json={"question": pregunta, "session_id": "misma"})
        assert r.status_code == 200
        assert r.json()["status"] == "conversational" and not r.json()["fragments"]
    assert not m.retriever.consultas
    r = cliente.post("/ask", json={"question": "hola, cuánto pesa la evaluación", "session_id": "misma"})
    assert r.status_code == 200 and r.json()["response_mode"] == "ranked_sources"
    assert r.json()["fragments"] and len(m.retriever.consultas) == 1
