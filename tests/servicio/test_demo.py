"""La página de prueba comparte servicio y tema, conservando el acceso al panel."""
from fastapi.testclient import TestClient

from ipsis.aplicacion.modo import ModoServicio
from ipsis.servicio.api import crear_app


def test_demo_habilitada_no_habilita_admin_y_renderiza_idioma():
    cliente = TestClient(crear_app(modo=ModoServicio(demo=True)))
    html = cliente.get("/widget/demo.html").text
    assert "Explora tus documentos" in html
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
