from __future__ import annotations

import yaml

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


# --- ubicación, snippet y /config (P12.5) -------------------------------------------------------
def test_ubicacion_por_defecto_y_validacion():
    import pytest

    from ipsis.aplicacion.widget import ubicacion_widget

    assert ubicacion_widget({}) == {"posicion": "abajo-derecha", "desplazamiento_x": 24, "desplazamiento_y": 24,
                                    "z_index": 2147483000, "tamano": "normal", "lanzador": "burbuja"}
    assert ubicacion_widget({"ubicacion": {"posicion": "incrustado", "lanzador": "oculto"}})["lanzador"] == "oculto"
    for malo, mensaje in [({"posicion": "centro"}, "posicion"), ({"tamano": "enorme"}, "tamano"),
                          ({"desplazamiento_x": -1}, "desplazamiento_x"), ({"z_index": "alto"}, "z_index"),
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
    (tmp_path / "configuracion").mkdir()
    (tmp_path / "configuracion" / "estilos.yaml").write_text(
        "ubicacion:\n  posicion: arriba-izquierda\n  lanzador: pestana\n", encoding="utf-8")
    assert main(["widget", "snippet", "--api", "https://asistente.ejemplo.cl/"]) == 0
    salida = capsys.readouterr().out.strip()
    assert salida.startswith('<script src="https://asistente.ejemplo.cl/widget.js" data-api="https://asistente.ejemplo.cl"')
    assert 'data-posicion="arriba-izquierda"' in salida and 'data-lanzador="pestana"' in salida
    assert main(["widget", "snippet", "--componente", "--clave", 'a"b']) == 0
    componente = capsys.readouterr().out
    assert "<ipsis-chat" in componente and 'widget-key="a&quot;b"' in componente


def test_config_trae_microcopia_del_tono_y_ubicacion(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--perfil", "light"]) == 0
    assert main(["personalidad", "tono", "aplicar", "serio"]) == 0
    from ipsis.servicio.api import crear_app

    cfg = TestClient(crear_app()).get("/config").json()
    assert cfg["citas"] == "acordeon" and cfg["ubicacion"]["posicion"] == "abajo-derecha"
    assert set(cfg["microcopia"]) == {"bienvenida", "esperando", "invitacion_citas", "error_red", "error_limite",
                                      "error_servicio"}
    assert cfg["microcopia"]["esperando"][0] == "Buscando"  # tono serio
    assert all(len(v) == 5 for v in cfg["microcopia"].values())
    assert "{" not in " ".join(sum(cfg["microcopia"].values(), []))  # variables reemplazadas
    assert cfg["interfaz"]["fuentes_varias"] == "{n} fuentes del documento"  # plantilla del widget


# --- ipsis widget estilo: cada valor, por consola ----------------------------------------------
def test_estilo_mostrar_y_cambiar_por_consola(tmp_path, monkeypatch, capsys):
    from pathlib import Path

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--perfil", "light"]) == 0
    capsys.readouterr()
    assert main(["widget", "estilo", "mostrar", "--seccion", "colores"]) == 0
    salida = capsys.readouterr().out
    assert "colores.acento = #2563eb" in salida and "forma." not in salida

    assert main(["widget", "estilo", "cambiar", "colores.acento=#0ea5e9", "forma.radio_panel=10px",
                 "animaciones.activadas=false", "ubicacion.desplazamiento_x=40"]) == 0
    tema = yaml.safe_load(Path("configuracion/estilos.yaml").read_text(encoding="utf-8"))
    assert tema["colores"]["acento"] == "#0ea5e9" and tema["forma"]["radio_panel"] == "10px"
    assert tema["animaciones"]["activadas"] is False and tema["ubicacion"]["desplazamiento_x"] == 40


def test_estilo_rechaza_erratas_tipos_y_css_peligroso(tmp_path, monkeypatch, capsys):
    from pathlib import Path

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--perfil", "light"]) == 0
    antes = Path("configuracion/estilos.yaml").read_text(encoding="utf-8")
    capsys.readouterr()
    for malo, mensaje in (("colores.acentto=#fff", "clave desconocida"), ("coloress.acento=#fff", "sección desconocida"),
                          ("acento=#fff", "seccion.clave=valor"), ("colores.acento=red;x", "no permitidos"),
                          ("animaciones.activadas=quizas", "true o false"),
                          ("ubicacion.desplazamiento_x=mucho", "entero")):
        assert main(["widget", "estilo", "cambiar", malo]) == 1, malo
        assert mensaje in capsys.readouterr().out, malo
    assert Path("configuracion/estilos.yaml").read_text(encoding="utf-8") == antes  # nada se escribió
