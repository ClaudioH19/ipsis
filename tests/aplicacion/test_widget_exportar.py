from __future__ import annotations

from ipsis.cli import main
from ipsis.aplicacion.widget import exportar_widget


def test_exporta_web_component_y_snippet(tmp_path):
    salida = exportar_widget(
        str(tmp_path / "publico"), api="https://api.example/ipsis/", posicion="bottom-left"
    )

    widget = (salida / "widget.js").read_text(encoding="utf-8")
    snippet = (salida / "snippet.html").read_text(encoding="utf-8")
    assert 'customElements.define("ipsis-chat"' in widget
    assert "ipsis:answer" in widget
    assert '<ipsis-chat api="https://api.example/ipsis"' in snippet
    assert 'position="bottom-left"' in snippet
    assert '<script src="./widget.js"></script>' in snippet


def test_exportacion_escapa_la_url_en_el_snippet(tmp_path):
    salida = exportar_widget(str(tmp_path), api='https://example.test/?x="mal"')

    snippet = (salida / "snippet.html").read_text(encoding="utf-8")
    assert '"mal"' not in snippet
    assert "&quot;mal&quot;" in snippet


def test_cli_exporta_widget(tmp_path):
    salida = tmp_path / "dist"

    assert main(["widget", "export", str(salida), "--api", "https://api.test"]) == 0
    assert (salida / "widget.js").is_file()
    assert (salida / "snippet.html").is_file()
