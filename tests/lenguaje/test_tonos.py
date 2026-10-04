"""Tonos de respuesta: linter, paquetes, migración y sobrescrituras (P12.1)."""
from __future__ import annotations

from pathlib import Path

import pytest

from rag.lenguaje.tonos import (
    SITUACIONES,
    TonoInvalido,
    _base,
    cargar_tono,
    errores_plantilla,
    errores_tono,
    extraer_legado,
    prohibidas,
    tonos_disponibles,
)


# --- el linter rechaza cada infracción ------------------------------------------------------
@pytest.mark.parametrize(("situacion", "texto", "error"), [
    ("sin_respuesta", "No está en los\ndocumentos.", "una sola línea"),
    ("sin_respuesta", "No está. " * 30, "caracteres"),
    ("sin_respuesta", "No está en los 3 documentos.", "dígitos"),
    ("sin_respuesta", "Mira en https://otro.sitio", "URLs"),
    ("sin_respuesta", "No está en los <b>documentos</b>.", "HTML"),
    ("sin_respuesta", "No está en los **documentos**.", "Markdown"),
    ("sin_respuesta", "No está en los documentos 😅", "emojis"),
    ("sin_respuesta", "NO ESTÁ en los documentos.", "mayúsculas"),
    ("sin_respuesta", "No está {nombre_asistente}.", "no permitidas"),
    ("foco_ausente", "No encontré eso. Esto es lo más cercano:", "le falta"),
    ("foco_ausente", "No encontré «{termino!r}». Esto es lo más cercano:", "formato"),
    ("apertura", "Esto dice el documento.", "«:»"),
    ("sin_respuesta", "No está, obviamente.", "prohibida"),
    ("sin_respuesta", "No está en {", "llaves"),
])
def test_cada_regla_del_linter(situacion, texto, error):
    errores = errores_plantilla(situacion, texto, prohibidas("es"))
    assert any(error in e for e in errores), errores


def test_variables_y_texto_valido_no_dan_error():
    assert errores_plantilla("foco_ausente", "No hay nada sobre «{termino}». Esto es lo más cercano:") == []
    assert errores_plantilla("saludo", "Hola, soy {nombre_asistente}, de {descripcion_dominio}.") == []
    # Las variables no cuentan como Markdown aunque lleven guion bajo.
    assert errores_plantilla("capacidad", "Busco en {descripcion_dominio}.") == []


def test_errores_de_conjunto_completitud_minimo_y_repeticiones():
    base = {s: [f"Texto {s.replace('_', ' ')} variante {chr(97 + i)}" + (":" if SITUACIONES[s].dos_puntos else ".")
                for i in range(5)] for s in SITUACIONES}
    base["foco_ausente"] = [f"Nada sobre «{{termino}}» {chr(97 + i)}:" for i in range(5)]
    base["premisa_no_encontrada"] = [f"No hay {{entidad}} {chr(97 + i)}." for i in range(5)]
    assert errores_tono(base) == []
    incompleto = {k: v for k, v in base.items() if k != "despedida"}
    assert any("faltan situaciones" in e for e in errores_tono(incompleto))
    corto = {**base, "despedida": base["despedida"][:4]}
    assert any("al menos 5" in e for e in errores_tono(corto))
    repetida = {**base, "despedida": [base["despedida"][0]] * 5}
    assert any("repite otra variante" in e for e in errores_tono(repetida))
    cruzada = {**base, "esperando": [base["despedida"][0]] + base["esperando"][1:]}
    assert any("repite una variante de despedida" in e for e in errores_tono(cruzada))


# --- paquetes ---------------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_los_tonos_incluidos_pasan_el_linter(idioma):
    for tono in tonos_disponibles(idioma):
        datos = _base(idioma, tono)
        assert errores_tono(datos["situaciones"], prohibidas(idioma)) == [], (idioma, tono)
        assert set(datos["situaciones"]) == set(SITUACIONES)


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_los_tonos_incluidos_son_neutros(idioma):
    """Sin regionalismos, formas con género ni saludos que dependan de la hora."""
    from rag.lenguaje.tonos import regionalismos_en

    for tono in tonos_disponibles(idioma):
        assert regionalismos_en(_base(idioma, tono)["situaciones"], idioma) == [], (idioma, tono)


def test_cordial_conserva_como_primera_variante_los_textos_anteriores():
    """Migración exacta: con el tono por defecto, las respuestas de siempre siguen ahí."""
    es = cargar_tono("es")
    assert es.variantes("sin_respuesta")[0] == "No encontré esa información en los documentos disponibles."
    assert es.variantes("apertura")[:4] == ["Esto es lo que dice el documento:", "Encontré esto en el documento:",
                                            "El documento lo plantea así:", "Según el texto cargado:"]
    assert es.variantes("bienvenida")[0] == "Hola, ¿en qué puedo ayudarte?"
    assert cargar_tono("en").variantes("sin_respuesta")[0] == \
        "I couldn't find that information in the available documents."
    assert cargar_tono("pt").variantes("despedida")[0] == "Até logo."


def test_idioma_sin_carpeta_de_tonos_usa_en_y_la_variante_regional_su_base():
    assert cargar_tono("ru").idioma == "en"
    assert cargar_tono("pt-br").idioma == "pt"


def test_tono_inexistente_lista_los_disponibles():
    with pytest.raises(TonoInvalido, match="disponibles: cordial"):
        cargar_tono("es", "inexistente")


# --- sobrescrituras ---------------------------------------------------------------------------
def test_legado_de_idioma_yaml_se_traduce_a_situaciones():
    propios, plantillas = extraer_legado({
        "mensajes": {"sin_respuesta": "Nada.", "sin_seccion": "(—)",
                     "conectores": {"apertura": ["Dice:"], "secuencia": ["Uno"]}},
        "conversacional": {"respuestas": {"saludo": "Hola."}, "patrones": {"saludo": ["^hola"]}},
        "interfaz": {"saludo": "Buenas.", "placeholder": "Escribe"},
    })
    assert plantillas == {"sin_respuesta": ["Nada."], "bienvenida": ["Buenas."], "apertura": ["Dice:"],
                          "saludo": ["Hola."]}
    assert propios == {"mensajes": {"sin_seccion": "(—)", "conectores": {"secuencia": ["Uno"]}},
                       "conversacional": {"patrones": {"saludo": ["^hola"]}}, "interfaz": {"placeholder": "Escribe"}}


def test_personalidad_yaml_sobrescribe_y_se_valida(tmp_path: Path):
    (tmp_path / "configuracion").mkdir()
    ruta = tmp_path / "configuracion" / "personalidad.yaml"
    ruta.write_text("tono:\n  plantillas:\n    sin_respuesta: Eso no está en el manual.\n", encoding="utf-8")
    tono = cargar_tono("es", proyecto=tmp_path, sobrescrituras={"sin_respuesta": ["Legado."]})
    assert tono.variantes("sin_respuesta") == ["Eso no está en el manual."]  # personalidad gana al legado
    ruta.write_text("tono:\n  plantillas:\n    apertura: [Sin dos puntos]\n", encoding="utf-8")
    with pytest.raises(TonoInvalido, match="apertura"):
        cargar_tono("es", proyecto=tmp_path)


def test_el_motor_usa_el_tono_y_la_sobrescritura_del_proyecto(tmp_path: Path, monkeypatch):
    from rag.consulta.etapas.redaccion import cargar_plantillas
    from rag.lenguaje.paquete import cargar_paquete

    (tmp_path / "configuracion").mkdir()
    (tmp_path / "configuracion" / "personalidad.yaml").write_text(
        "tono:\n  plantillas:\n    sin_respuesta: Eso no está en el manual.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    plantillas = cargar_plantillas(cargar_paquete("es"), {"nombre_asistente": "Ana", "descripcion_dominio": "el manual"})
    assert plantillas["tono"] == "cordial"
    assert plantillas["abstencion"]["generico"] == ["Eso no está en el manual."]
    assert plantillas["conectores"]["secuencia"] == ["Primero", "Luego", "Por último"]  # estructural, del idioma
    assert len(plantillas["conectores"]["apertura"]) == 5
    assert all("Ana" in r or "manual" in r for r in plantillas["conversacional"]["respuestas"]["capacidad"])
