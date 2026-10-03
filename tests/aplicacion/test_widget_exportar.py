from __future__ import annotations

from rag.cli import main
from rag.aplicacion.widget import exportar_widget


def test_exporta_web_component_y_snippet(tmp_path):
    salida = exportar_widget(
        str(tmp_path / "publico"), api="https://api.example/rag/", posicion="abajo-izquierda"
    )

    widget = (salida / "widget.js").read_text(encoding="utf-8")
    snippet = (salida / "snippet.html").read_text(encoding="utf-8")
    assert 'customElements.define("rag-extractivo-chat"' in widget
    assert "rag:respuesta" in widget
    assert '<rag-extractivo-chat api="https://api.example/rag"' in snippet
    assert 'posicion="abajo-izquierda"' in snippet
    assert '<script src="./widget.js"></script>' in snippet


def test_exportacion_escapa_la_url_en_el_snippet(tmp_path):
    salida = exportar_widget(str(tmp_path), api='https://example.test/?x="mal"')

    snippet = (salida / "snippet.html").read_text(encoding="utf-8")
    assert '"mal"' not in snippet
    assert "&quot;mal&quot;" in snippet


def test_cli_exporta_widget(tmp_path):
    salida = tmp_path / "dist"

    assert main(["widget", "exportar", str(salida), "--api", "https://api.test"]) == 0
    assert (salida / "widget.js").is_file()
    assert (salida / "snippet.html").is_file()
