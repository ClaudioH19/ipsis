from __future__ import annotations

import yaml

from rag.cli import main
from rag.aplicacion.widget import (
    aplicar_preset,
    generar_vista_previa,
    listar_presets,
    validar_tema,
)


def test_catalogo_de_presets_es_estable():
    assert list(listar_presets()) == ["clasico", "minimal", "editorial", "contraste"]


def test_aplicar_preset_preserva_css_extra_y_escribe_yaml_valido(tmp_path):
    ruta = tmp_path / "estilos.yaml"
    ruta.write_text("css_extra: '.marca{display:block}'\n", encoding="utf-8")

    tema = aplicar_preset("editorial", str(ruta))
    persistido = yaml.safe_load(ruta.read_text(encoding="utf-8"))

    assert tema == persistido
    assert persistido["preset"] == "editorial"
    assert persistido["colores"]["acento"] == "#8b2f3c"
    assert persistido["css_extra"] == ".marca{display:block}"


def test_preset_contraste_desactiva_animaciones(tmp_path):
    tema = aplicar_preset("contraste", str(tmp_path / "estilos.yaml"))

    assert tema["animaciones"]["activadas"] is False
    assert tema["colores"]["texto"] == "#000000"


def test_preset_editorial_abre_citas_y_minimal_es_compacto(tmp_path):
    editorial = aplicar_preset("editorial", str(tmp_path / "editorial.yaml"))
    minimal = aplicar_preset("minimal", str(tmp_path / "minimal.yaml"))

    assert editorial["presentacion"]["citas"] == "abiertas"
    assert minimal["presentacion"]["densidad"] == "compacta"


def test_preset_no_hereda_valores_del_preset_anterior(tmp_path):
    ruta_encadenada = tmp_path / "encadenada.yaml"
    aplicar_preset("minimal", str(ruta_encadenada))
    editorial_encadenado = aplicar_preset("editorial", str(ruta_encadenada))
    editorial_limpio = aplicar_preset("editorial", str(tmp_path / "limpia.yaml"))

    assert editorial_encadenado == editorial_limpio


def test_validacion_rechaza_inyeccion_en_valor_css():
    try:
        validar_tema({"colores": {"acento": "red;} body{display:none"}})
    except ValueError as exc:
        assert "caracteres CSS" in str(exc)
    else:
        raise AssertionError("debió rechazar el valor CSS")


def test_cli_lista_y_aplica_preset(tmp_path, capsys):
    ruta = tmp_path / "estilos.yaml"

    assert main(["widget", "tema", "listar"]) == 0
    assert "minimal:" in capsys.readouterr().out
    assert main([
        "widget", "tema", "aplicar", "minimal", "--ruta", str(ruta)
    ]) == 0

    assert yaml.safe_load(ruta.read_text(encoding="utf-8"))["preset"] == "minimal"


def test_vista_previa_incluye_estados_y_cita_sin_api(tmp_path):
    estilos = tmp_path / "estilos.yaml"
    aplicar_preset("contraste", str(estilos))

    salida = generar_vista_previa(str(tmp_path / "preview.html"), str(estilos))
    html = salida.read_text(encoding="utf-8")

    assert "Respuesta directa" in html
    assert "Información relacionada" in html
    assert "sin_respuesta" in html
    assert "conversacional" in html
    assert "El filtro de sedimentos se cambia cada 6 meses." in html
    assert "preset contraste" in html


def test_cli_genera_vista_previa(tmp_path):
    estilos = tmp_path / "estilos.yaml"
    salida = tmp_path / "mockup.html"
    aplicar_preset("minimal", str(estilos))

    assert main([
        "widget", "tema", "vista-previa", "--ruta", str(estilos),
        "--salida", str(salida),
    ]) == 0
    assert salida.is_file()
