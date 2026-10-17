from __future__ import annotations

import pytest

from apoyo import leer_proyecto
from ipsis.lenguaje.tonos import CUOTAS_PAQUETE
from ipsis.cli import main
from ipsis.aplicacion.widget import (
    aplicar_preset,
    generar_vista_previa,
    listar_presets,
    validar_tema,
)


def test_catalogo_de_presets_es_estable():
    assert list(listar_presets()) == ["classic", "minimal", "editorial", "contrast", "search", "search_compact",
                                    "ocean", "forest", "midnight"]


@pytest.mark.parametrize("preset", list(listar_presets()))
def test_templates_de_busqueda_se_exportan_y_tienen_contexto_accesible(tmp_path, preset):
    ruta = tmp_path / "styles.yaml"
    aplicar_preset(preset, str(ruta))
    salida = generar_vista_previa(str(tmp_path / "preview.html"), str(ruta))
    contenido = salida.read_text(encoding="utf-8")
    assert '<ipsis-chat api="/__ipsis_preview__" position="embedded">' in contenido
    assert 'var configuracionEjemplo' in contenido and 'var respuestaEjemplo' in contenido
    assert '"response_mode": "ranked_sources"' in contenido
    assert '"chunk_id": "ejemplo-3"' in contenido
    assert 'data:text/css;charset=utf-8,' in contenido
    assert f'"preset": "{preset}"' in contenido


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


def test_personalizacion_de_resultados_y_contenido_llega_a_config(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from ipsis.aplicacion.widget import cambiar_estilo
    from ipsis.servicio.api import crear_app

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    cambiar_estilo(["presentation.result_layout=editorial", "presentation.show_result_numbers=false",
                    "presentation.show_section_path=false", "presentation.expand_context=true",
                    "presentation.show_suggestions=false", "content.title=Centro de ayuda",
                    "content.welcome_title=¿Qué necesitas revisar?", "colors.heading=#14532d",
                    "typography.heading_family=Georgia, serif", "shape.result_radius=4px"])
    cliente = TestClient(crear_app())
    cfg = cliente.get("/config").json()
    assert cfg["result_layout"] == "editorial" and cfg["expand_context"] is True
    assert cfg["show_result_numbers"] is cfg["show_section_path"] is cfg["show_suggestions"] is False
    assert cfg["widget_content"]["title"] == "Centro de ayuda"
    assert len(cfg["suggested_questions"]) == 6
    css = cliente.get("/styles.css").text
    assert '--rw-titulo:#14532d' in css and '--rw-fuente-titulo:Georgia, serif' in css
    assert '--rw-radio-resultado:4px' in css
    aplicar_preset("ocean")
    assert cliente.get("/config").json()["widget_content"]["title"] == "Centro de ayuda"


@pytest.mark.parametrize("cambios", [
    {"presentacion": {"diseno_resultados": "grid"}},
    {"presentacion": {"mostrar_numeros": "false"}},
    {"contenido": []}, {"contenido": {"titulo": 42}}, {"contenido": {"desconocido": "test"}},
])
def test_nuevas_opciones_invalidas_no_se_guardan(tmp_path, cambios):
    from ipsis.aplicacion.widget import actualizar_estilos

    ruta = str(tmp_path / "styles.yaml")
    aplicar_preset("forest", ruta)
    antes = (tmp_path / "styles.yaml").read_bytes()
    with pytest.raises(ValueError):
        actualizar_estilos(cambios, ruta)
    assert (tmp_path / "styles.yaml").read_bytes() == antes


def test_proyectos_anteriores_conservan_el_diseno_del_preset():
    from ipsis.aplicacion.widget import presentacion_publica

    assert presentacion_publica({"preset": "buscador"})["result_layout"] == "lines"
    assert presentacion_publica({"preset": "editorial"})["result_layout"] == "editorial"
    assert presentacion_publica({"preset": "buscador", "presentacion": {"diseno_resultados": "tarjetas"}})["result_layout"] == "cards"


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


def test_vista_previa_usa_widget_real_y_fuentes_de_ejemplo_sin_api(tmp_path):
    estilos = tmp_path / "styles.yaml"
    aplicar_preset("contraste", str(estilos))

    salida = generar_vista_previa(str(tmp_path / "preview.html"), str(estilos))
    html = salida.read_text(encoding="utf-8")

    assert 'window.fetch = function(url)' in html
    assert 'requestSubmit()' in html
    assert '"animations_enabled": false' in html
    assert '"source_blocks":' in html
    assert 'preset contrast' in html


def test_vista_previa_escapa_textos_personalizados(tmp_path):
    from ipsis.aplicacion.widget import cambiar_estilo

    ruta = str(tmp_path / "styles.yaml")
    cambiar_estilo(['content.title=</script><img src=x onerror=alert(1)>'], ruta)
    contenido = generar_vista_previa(str(tmp_path / "preview.html"), ruta).read_text(encoding="utf-8")
    assert '</script><img' not in contenido
    assert '\\u003c/script\\u003e' in contenido
    assert contenido.count('</script>') == 3


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
    assert 'data-position="top-left"' in salida and 'data-launcher="tab"' in salida
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
    assert cfg["citations"] == "accordion" and cfg["placement"]["position"] == "bottom-right"
    assert set(cfg["microcopy"]) == {"welcome", "waiting", "citations_hint", "network_error", "rate_limit_error",
                                      "service_error"}
    assert cfg["microcopy"]["waiting"][0] == "Buscando"  # tono serio
    assert all(len(v) == CUOTAS_PAQUETE[s] for s, v in cfg["microcopy"].items())
    assert "{" not in " ".join(sum(cfg["microcopy"].values(), []))  # variables reemplazadas
    assert cfg["interface"]["sources_many"] == "{n} fuentes consultadas"  # plantilla del widget


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


def test_alineacion_justificada_es_opcional_y_se_valida():
    from ipsis.aplicacion.widget import presentacion_publica

    assert presentacion_publica({})["text_align"] == "justify"  # por defecto, justificado
    assert presentacion_publica({"presentacion": {"alineacion": "inicio"}})["text_align"] == "start"
    validar_tema({"presentacion": {"alineacion": "justificada"}})
    with pytest.raises(ValueError, match="text_align"):
        validar_tema({"presentacion": {"alineacion": "centrada"}})


def test_el_widget_empieza_una_conversacion_nueva_en_cada_carga_de_pagina():
    """El servidor recuerda la conversación por session_id; el widget no guarda el
    historial visible, así que tampoco debe reusar la sesión entre cargas."""
    from pathlib import Path

    import ipsis.servicio

    js = (Path(ipsis.servicio.__file__).parent / "estaticos" / "widget.js").read_text(encoding="utf-8")
    assert "var ID_SESION = generarIdSesion();" in js
    assert "localStorage" not in js and "sessionStorage" not in js


def test_el_widget_muestra_las_alternativas_de_una_respuesta_sin_respuesta():
    """Postura proactiva (ADR 0008): ``alternatives`` de la API se pinta con sus
    citas, en una burbuja propia, sin la etiqueta de un estado relacionado."""
    from pathlib import Path

    import ipsis.servicio

    js = (Path(ipsis.servicio.__file__).parent / "estaticos" / "widget.js").read_text(encoding="utf-8")
    assert "alternativas: (r.alternatives || []).map(fragmentoInterno)" in js
    assert ".rw-msg-alternativas{" in js
    assert 'estadoResp === "sin_respuesta" ? (respuesta.alternativas || [])' in js
