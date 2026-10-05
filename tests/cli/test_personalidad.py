"""``ipsis personality``: tono y avatar desde la terminal (P12.4)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ipsis.cli import main
from apoyo import escribir_proyecto, leer_proyecto

PERSONALIDAD = Path("config/personality.yaml")


def _definicion(**cambios) -> dict:
    """Definición mínima con la forma que revisa Python (la librería valida el resto)."""
    expresion = {"head": {"x": 0, "y": 0, "z": 0}, "perspective": 1, "motion": {"eyes": "none", "body": "none"},
                 "eyes": {"spacing": 1, "left": {"width": 1, "height": 1, "x": 0, "y": 0, "angle": 0},
                          "right": {"width": 1, "height": 1, "x": 0, "y": 0, "angle": 0}}}
    paso = {"expression": "contento", "holdMs": 400, "transitionMs": 100, "transition": "smooth"}
    datos = {"schema": "bible-strong-avatar", "schemaVersion": 1, "name": "Prueba", "body": {},
             "colors": {"body": "#ffffff", "eyes": "#000000"},
             "expressions": {"neutral": expresion, "contento": expresion},
             "expressionOrder": ["neutral", "contento"],
             "animations": {"inactivo": {"playbackMode": "loop", "steps": [paso], "blink": {}},
                            "contento": {"playbackMode": "once", "steps": [paso], "blink": {}}},
             "animationOrder": ["inactivo", "contento"]}
    datos.update(cambios)
    return datos


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> Path:
    carpeta = tmp_path / "proyecto"
    carpeta.mkdir()
    monkeypatch.chdir(carpeta)
    assert main(["init", "--profile", "light"]) == 0
    capsys.readouterr()
    return carpeta


def _avatar(tmp_path: Path, nombre="prueba.avatar.json", texto: str | None = None) -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(texto if texto is not None else json.dumps(_definicion()), encoding="utf-8")
    return ruta


# --- archivo y mostrar ---------------------------------------------------------------------------
def test_init_crea_personalidad_por_defecto_y_mostrar_la_resume(proyecto, capsys):
    assert PERSONALIDAD.is_file() and PERSONALIDAD.read_text(encoding="utf-8").startswith("# Assistant personality")
    assert main(["personality", "show"]) == 0
    salida = capsys.readouterr().out
    assert "Tono: cordial (variedad rotativa" in salida
    assert "Avatar: folio -- ok" in salida  # Folio viene incluido


def test_sin_proyecto_pide_rag_init(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["personality", "show"]) == 1
    assert "Acción: ipsis init" in capsys.readouterr().out


# --- tono ---------------------------------------------------------------------------------------
def test_listar_aplicar_y_probar_tono(proyecto, capsys):
    assert main(["personality", "tone", "list"]) == 0
    salida = capsys.readouterr().out
    assert "* cordial" in salida and "  directo" in salida and salida.count("«") == 7

    assert main(["personality", "tone", "apply", "formal"]) == 0
    texto = PERSONALIDAD.read_text(encoding="utf-8")
    assert texto.startswith("# Assistant personality")  # conserva los comentarios
    assert leer_proyecto(PERSONALIDAD)["tono"]["activo"] == "formal"

    capsys.readouterr()
    assert main(["personality", "tone", "try", "--situation", "sin_respuesta"]) == 0
    lineas = capsys.readouterr().out.splitlines()
    assert lineas[0] == "sin_respuesta:" and len(lineas) == 6 and lineas[1].startswith("  1. Lamentablemente")


def test_probar_reemplaza_las_variables_del_proyecto(proyecto, capsys):
    assert main(["configure", "assistant_name=Ana"]) == 0
    capsys.readouterr()
    assert main(["personality", "tone", "try", "--tone", "serio", "--situation", "saludo"]) == 0
    salida = capsys.readouterr().out
    assert "Ana" in salida and "{" not in salida


@pytest.mark.parametrize("argumentos", [["tone", "apply", "turbo"], ["tone", "try", "--situation", "nada"],
                                         ["tone", "try", "--tone", "turbo"]])
def test_tono_invalido_no_escribe_nada(proyecto, capsys, argumentos):
    antes = PERSONALIDAD.read_bytes()
    assert main(["personality", *argumentos]) == 1
    assert "Error" in capsys.readouterr().out and PERSONALIDAD.read_bytes() == antes


def test_el_motor_usa_el_tono_activo_y_la_variedad_fija(proyecto):
    from ipsis.aplicacion.consulta import construir_motor  # noqa: F401 -- la ruta real del motor
    from ipsis.consulta.etapas.redaccion import cargar_plantillas
    from ipsis.consulta.motor import Motor
    from ipsis.lenguaje.paquete import cargar_paquete

    datos = leer_proyecto(PERSONALIDAD)
    datos["tono"].update(activo="directo", variedad="fija")
    escribir_proyecto(PERSONALIDAD, datos)
    plantillas = cargar_plantillas(cargar_paquete("es"), {"nombre_asistente": "A", "descripcion_dominio": "B"})
    assert plantillas["tono"] == "directo" and plantillas["abstencion"]["generico"][0].startswith("No está")
    motor = Motor(plantillas=plantillas)
    assert motor.selector_variantes.fija and motor.selector_variantes.tono == "directo"
    textos = {motor.consultar("hola", "s").mensaje_usuario for _ in range(3)}
    assert len(textos) == 1  # fija: siempre la primera variante


def test_plantilla_propia_invalida_es_error_en_validar_y_doctor(proyecto, capsys):
    datos = leer_proyecto(PERSONALIDAD)
    datos["tono"]["plantillas"] = {"apertura": ["Sin dos puntos"]}
    escribir_proyecto(PERSONALIDAD, datos)
    assert main(["personality", "validate"]) == 1
    assert "[ERROR]" in capsys.readouterr().out
    from ipsis.aplicacion.diagnostico import diagnosticar

    chequeo = diagnosticar().chequeo("personalidad")
    assert chequeo.estado.value == "error" and chequeo.acciones


def test_cambiar_el_tono_no_toca_indice_ni_calibracion(proyecto, capsys):
    from ipsis.aplicacion.diagnostico import diagnosticar

    antes = {c.clave: c.estado for c in diagnosticar().chequeos}
    assert main(["profile", "show"]) == 0
    perfil_antes = capsys.readouterr().out
    assert main(["personality", "tone", "apply", "animoso"]) == 0
    capsys.readouterr()
    assert main(["profile", "show"]) == 0
    assert capsys.readouterr().out == perfil_antes
    assert {c.clave: c.estado for c in diagnosticar().chequeos} == antes


def test_snapshot_incluye_la_personalidad(proyecto):
    assert main(["snapshot-config", "--output", "snapshot.yaml"]) == 0
    snapshot = yaml.safe_load(Path("snapshot.yaml").read_text(encoding="utf-8"))
    assert snapshot["personality"]["tone"]["active"] == "cordial"


# --- avatar -------------------------------------------------------------------------------------
def test_importar_aplicar_eventos_y_asignar(proyecto, tmp_path, capsys):
    assert main(["personality", "avatar", "import", str(_avatar(tmp_path)), "--name", "mi-avatar"]) == 0
    assert Path("config/avatars/mi-avatar.avatar.json").is_file()
    assert main(["personality", "avatar", "apply", "mi-avatar"]) == 0
    capsys.readouterr()
    assert main(["personality", "avatar", "events"]) == 0
    salida = capsys.readouterr().out
    assert "respuesta_ok           → contento" in salida
    assert "pensando               → inactivo  (pedida: 'pensando'" in salida  # respaldo en cadena
    assert main(["personality", "avatar", "assign", "pensando", "contento"]) == 0
    assert leer_proyecto(PERSONALIDAD)["avatar"]["eventos"] == {"pensando": "contento"}
    capsys.readouterr()
    assert main(["personality", "avatar", "assign", "pensando", "volar"]) == 1
    assert "no tiene la clave 'volar'" in capsys.readouterr().out
    assert main(["personality", "avatar", "assign", "bailar", "contento"]) == 1
    from ipsis.aplicacion.diagnostico import diagnosticar

    assert diagnosticar().chequeo("personalidad").estado.value == "aviso"  # faltan claves del mapa


@pytest.mark.parametrize(("texto", "error"), [
    ("x" * (256 * 1024 + 1), "256 KiB"),
    ('{"expressions": {"neutral": {}}, "expressions": {}}', "duplicadas"),
    (json.dumps(_definicion(expressions={"feliz": {}})), "neutral"),
    (json.dumps(_definicion(animations={"Mal_Nombre": {}})), "Mal_Nombre"),
    (json.dumps(_definicion(colors={"body": "#FFF", "eyes": "#000000"})), "colors.body"),
    ("{no es json", "JSON"),
], ids=["grande", "duplicadas", "sin-neutral", "clave-invalida", "color-invalido", "no-json"])
def test_importar_rechaza_definiciones_invalidas_sin_escribir(proyecto, tmp_path, capsys, texto, error):
    assert main(["personality", "avatar", "import", str(_avatar(tmp_path, texto=texto)), "--name", "x"]) == 1
    assert error in capsys.readouterr().out
    assert not Path("config/avatars/x.avatar.json").exists()


def test_aplicar_un_avatar_inexistente_falla(proyecto, capsys):
    antes = PERSONALIDAD.read_bytes()
    assert main(["personality", "avatar", "apply", "nadie"]) == 1
    assert "no hay un avatar 'nadie'" in capsys.readouterr().out and PERSONALIDAD.read_bytes() == antes


def test_colores_se_normalizan_y_validan(proyecto, capsys):
    assert main(["personality", "avatar", "colors", "--body", "#F5F1E8", "--eyes", "#1e293b"]) == 0
    colores = leer_proyecto(PERSONALIDAD)["avatar"]["colores"]
    assert colores == {"cuerpo": "#f5f1e8", "ojos": "#1e293b"}
    assert main(["personality", "avatar", "colors", "--eyes", "azul"]) == 1


def test_los_colores_se_aplican_sin_modificar_el_archivo(proyecto, tmp_path):
    from ipsis.aplicacion.avatar import cargar_avatar, con_colores

    main(["personality", "avatar", "import", str(_avatar(tmp_path)), "--name", "mi-avatar"])
    _, datos = cargar_avatar("mi-avatar")
    pintado = con_colores(datos, "#123456", None)
    assert pintado["colors"] == {"body": "#123456", "eyes": "#000000"}
    assert json.loads(Path("config/avatars/mi-avatar.avatar.json").read_text())["colors"]["body"] == "#ffffff"


# --- neutralidad de los textos propios: aviso, no error ----------------------------------------
def _textos_propios(plantillas: dict) -> None:
    ruta = Path("config/personality.yaml")
    datos = leer_proyecto(ruta)
    datos["tono"]["plantillas"] = plantillas
    escribir_proyecto(ruta, datos)


def test_texto_propio_no_neutro_es_aviso_en_validar_y_doctor(proyecto, capsys):
    from ipsis.aplicacion.diagnostico import Estado, diagnosticar

    _textos_propios({"despedida": ["Chao, nos vemos pronto."]})
    capsys.readouterr()
    assert main(["personality", "validate"]) == 0  # no bloquea
    salida = capsys.readouterr().out
    assert "[AVISO] texto propio no neutro: despedida[1]: 'chao'" in salida
    assert "Hay avisos (no bloquean)" in salida
    chequeo = diagnosticar(abrir_indice=False).chequeo("personalidad")
    assert chequeo.estado is Estado.AVISO and "chao" in chequeo.mensaje
    assert chequeo.acciones == ("revisa tono.plantillas en config/personality.yaml "
                                "(detalle: ipsis personality validate)",)


def test_texto_propio_neutro_no_avisa(proyecto, capsys):
    _textos_propios({"despedida": ["Hasta pronto."]})
    capsys.readouterr()
    assert main(["personality", "validate"]) == 0
    assert "[AVISO]" not in capsys.readouterr().out


def test_idioma_sin_reglas_propias_no_se_revisa(proyecto):
    from ipsis.aplicacion.personalidad import avisos_neutralidad

    datos = leer_proyecto(Path("config/assistant.yaml"))
    datos["idioma"] = "fr"
    escribir_proyecto(Path("config/assistant.yaml"), datos)
    _textos_propios({"despedida": ["Hey, à bientôt."]})  # «hey» está en la lista inglesa de respaldo
    assert avisos_neutralidad() == []
