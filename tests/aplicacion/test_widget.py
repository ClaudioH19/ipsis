from __future__ import annotations


from apoyo import leer_proyecto
from ipsis.cli import main
from ipsis.aplicacion.widget import (
    aplicar_preset,
    generar_vista_previa,
    listar_presets,
    validar_tema,
)


def test_catalogo_de_presets_es_estable():
    assert list(listar_presets()) == ["clasico", "minimal", "editorial", "contraste"]


def test_aplicar_preset_preserva_css_extra_y_escribe_yaml_valido(tmp_path):
    ruta = tmp_path / "styles.yaml"
    ruta.write_text("css_extra: '.marca{display:block}'\n", encoding="utf-8")

    tema = aplicar_preset("editorial", str(ruta))
    persistido = leer_proyecto(ruta)

    assert tema == persistido
    assert persistido["preset"] == "editorial"
    assert persistido["colores"]["acento"] == "#8b2f3c"
    assert persistido["css_extra"] == ".marca{display:block}"


def test_preset_contraste_desactiva_animaciones(tmp_path):
    tema = aplicar_preset("contraste", str(tmp_path / "styles.yaml"))

    assert tema["animaciones"]["activadas"] is False
    assert tema["colores"]["texto"] == "#000000"


def test_preset_editorial_abre_citas_y_minimal_es_compacto(tmp_path):
    editorial = aplicar_preset("editorial", str(tmp_path / "editorial.yaml"))
    minimal = aplicar_preset("minimal", str(tmp_path / "minimal.yaml"))

    assert editorial["presentacion"]["citas"] == "lista"
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
    ruta = tmp_path / "styles.yaml"

    assert main(["widget", "theme", "list"]) == 0
    assert "minimal:" in capsys.readouterr().out
    assert main([
        "widget", "theme", "apply", "minimal", "--path", str(ruta)
    ]) == 0

    assert leer_proyecto(ruta)["preset"] == "minimal"


def test_vista_previa_incluye_estados_y_cita_sin_api(tmp_path):
    estilos = tmp_path / "styles.yaml"
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
    estilos = tmp_path / "styles.yaml"
    salida = tmp_path / "mockup.html"
    aplicar_preset("minimal", str(estilos))

    assert main([
        "widget", "theme", "preview", "--path", str(estilos),
        "--output", str(salida),
    ]) == 0
    assert salida.is_file()


# --- ubicación, snippet y /config (P12.5) -------------------------------------------------------
def test_ubicacion_por_defecto_y_validacion():
    import pytest

    from ipsis.aplicacion.widget import ubicacion_widget

    assert ubicacion_widget({}) == {"posicion": "abajo-derecha", "desplazamiento_x": 24, "desplazamiento_y": 24,
                                    "z_index": 2147483000, "tamano": "normal", "lanzador": "burbuja"}
    assert ubicacion_widget({"ubicacion": {"posicion": "incrustado", "lanzador": "oculto"}})["lanzador"] == "oculto"
    for malo, mensaje in [({"posicion": "centro"}, "placement.position"), ({"tamano": "enorme"}, "placement.size"),
                          ({"desplazamiento_x": -1}, "placement.offset_x"), ({"z_index": "alto"}, "placement.z_index"),
                          ({"color": "rojo"}, "desconocidas")]:
        with pytest.raises(ValueError, match=mensaje):
            validar_tema({"ubicacion": malo})


def test_forma_margen_anterior_sigue_ubicando_el_widget():
    from ipsis.aplicacion.widget import ubicacion_widget

    u = ubicacion_widget({"forma": {"margen": "40px"}})
    assert (u["desplazamiento_x"], u["desplazamiento_y"]) == (40, 40)
    assert ubicacion_widget({"forma": {"margen": "40px"}, "ubicacion": {"desplazamiento_x": 8}})["desplazamiento_x"] == 8


def test_las_citas_nunca_se_ocultan():
    import pytest

    from ipsis.aplicacion.widget import citas_presentacion

    assert [citas_presentacion(v) for v in ("acordeon", "lista", "abiertas", "ocultas", None)] == \
        ["acordeon", "lista", "lista", "acordeon", "acordeon"]
    with pytest.raises(ValueError, match="siempre se muestran"):
        validar_tema({"presentacion": {"citas": "invisibles"}})


def test_snippet_usa_la_ubicacion_y_escapa(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "styles.yaml").write_text(
        "placement:\n  position: top-left\n  launcher: tab\n", encoding="utf-8")
    assert main(["widget", "snippet", "--api", "https://asistente.ejemplo.cl/"]) == 0
    salida = capsys.readouterr().out.strip()
    assert salida.startswith('<script src="https://asistente.ejemplo.cl/widget.js" data-api="https://asistente.ejemplo.cl"')
    assert 'data-posicion="arriba-izquierda"' in salida and 'data-lanzador="pestana"' in salida
    assert main(["widget", "snippet", "--component", "--key", 'a"b']) == 0
    componente = capsys.readouterr().out
    assert "<ipsis-chat" in componente and 'widget-key="a&quot;b"' in componente


def test_config_trae_microcopia_del_tono_y_ubicacion(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    assert main(["personality", "tone", "apply", "serious"]) == 0
    from ipsis.servicio.api import crear_app

    cfg = TestClient(crear_app()).get("/config").json()
    assert cfg["citas"] == "acordeon" and cfg["ubicacion"]["posicion"] == "abajo-derecha"
    assert set(cfg["microcopia"]) == {"welcome", "waiting", "citations_hint", "network_error", "rate_limit_error",
                                      "service_error"}
    assert cfg["microcopia"]["waiting"][0] == "Buscando"  # tono serio
    assert all(len(v) == 5 for v in cfg["microcopia"].values())
    assert "{" not in " ".join(sum(cfg["microcopia"].values(), []))  # variables reemplazadas
    assert cfg["interfaz"]["fuentes_varias"] == "{n} fuentes del documento"  # plantilla del widget


# --- ipsis widget style: cada valor, por consola ----------------------------------------------
def test_estilo_mostrar_y_cambiar_por_consola(tmp_path, monkeypatch, capsys):
    from pathlib import Path

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    capsys.readouterr()
    assert main(["widget", "style", "show", "--section", "colors"]) == 0
    salida = capsys.readouterr().out
    assert "colors.accent = #2563eb" in salida and "shape." not in salida

    assert main(["widget", "style", "set", "colors.accent=#0ea5e9", "shape.panel_radius=10px",
                 "animations.enabled=false", "placement.offset_x=40"]) == 0
    tema = leer_proyecto(Path("config/styles.yaml"))
    assert tema["colores"]["acento"] == "#0ea5e9" and tema["forma"]["radio_panel"] == "10px"
    assert tema["animaciones"]["activadas"] is False and tema["ubicacion"]["desplazamiento_x"] == 40


def test_estilo_rechaza_erratas_tipos_y_css_peligroso(tmp_path, monkeypatch, capsys):
    from pathlib import Path

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    antes = Path("config/styles.yaml").read_text(encoding="utf-8")
    capsys.readouterr()
    for malo, mensaje in (("colors.acent=#fff", "clave desconocida"), ("colorss.accent=#fff", "sección desconocida"),
                          ("accent=#fff", "seccion.clave=valor"), ("colors.accent=red;x", "no permitidos"),
                          ("animations.enabled=quizas", "true o false"),
                          ("placement.offset_x=mucho", "entero")):
        assert main(["widget", "style", "set", malo]) == 1, malo
        assert mensaje in capsys.readouterr().out, malo
    assert Path("config/styles.yaml").read_text(encoding="utf-8") == antes  # nada se escribió
