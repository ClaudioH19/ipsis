import json
import shutil
import subprocess
from pathlib import Path

import pytest


RAIZ = Path(__file__).resolve().parents[1]


def test_ejemplo_html_carga_el_web_component_configurable():
    html = (RAIZ / "ejemplos/html/index.html").read_text(encoding="utf-8")
    config = (RAIZ / "ejemplos/html/config.js").read_text(encoding="utf-8")

    assert "<rag-extractivo-chat" in html
    assert 'setAttribute("api"' in html
    assert 'api: "http://127.0.0.1:8000"' in config


def test_ejemplo_react_declara_build_y_conecta_eventos():
    paquete = json.loads((RAIZ / "ejemplos/react/package.json").read_text(encoding="utf-8"))
    fuente = (RAIZ / "ejemplos/react/src/main.jsx").read_text(encoding="utf-8")

    assert paquete["scripts"]["build"] == "vite build"
    assert "rag:respuesta" in fuente
    assert "rag:error" in fuente
    assert 'React.createElement("rag-extractivo-chat"' in fuente


def test_ejemplo_wordpress_es_plugin_y_escapa_atributos():
    fuente = (RAIZ / "ejemplos/wordpress/rag-extractivo-widget.php").read_text(encoding="utf-8")

    assert "Plugin Name: rag-extractivo Widget" in fuente
    assert "add_shortcode('rag_extractivo'" in fuente
    assert "esc_url($api)" in fuente
    assert fuente.count("esc_attr(") >= 4


@pytest.mark.skipif(shutil.which("php") is None, reason="PHP no está instalado")
def test_ejemplo_wordpress_tiene_sintaxis_php_valida():
    resultado = subprocess.run(
        ["php", "-l", str(RAIZ / "ejemplos/wordpress/rag-extractivo-widget.php")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
