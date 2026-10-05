"""Tonos de respuesta: linter, paquetes, migración y sobrescrituras (P12.1)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ipsis.lenguaje.tonos import (
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
    ("no_answer", "No está en los\ndocumentos.", "una sola línea"),
    ("no_answer", "No está. " * 30, "caracteres"),
    ("no_answer", "No está en los 3 documentos.", "dígitos"),
    ("no_answer", "Mira en https://otro.sitio", "URLs"),
    ("no_answer", "No está en los <b>documentos</b>.", "HTML"),
    ("no_answer", "No está en los **documentos**.", "Markdown"),
    ("no_answer", "No está en los documentos 😅", "emojis"),
    ("no_answer", "NO ESTÁ en los documentos.", "mayúsculas"),
    ("no_answer", "No está {assistant_name}.", "no permitidas"),
    ("missing_focus", "No encontré eso. Esto es lo más cercano:", "le falta"),
    ("missing_focus", "No encontré «{termino!r}». Esto es lo más cercano:", "formato"),
    ("opening", "Esto dice el documento.", "«:»"),
    ("no_answer", "No está, obviamente.", "prohibida"),
    ("no_answer", "No está en {", "llaves"),
])
def test_cada_regla_del_linter(situacion, texto, error):
    errores = errores_plantilla(situacion, texto, prohibidas("es"))
    assert any(error in e for e in errores), errores


def test_variables_y_texto_valido_no_dan_error():
    assert errores_plantilla("missing_focus", "No hay nada sobre «{term}». Esto es lo más cercano:") == []
    assert errores_plantilla("greeting", "Hola, soy {assistant_name}, de {domain_description}.") == []
    # Las variables no cuentan como Markdown aunque lleven guion bajo.
    assert errores_plantilla("capability", "Busco en {domain_description}.") == []


def test_errores_de_conjunto_completitud_minimo_y_repeticiones():
    base = {s: [f"Texto {s.replace('_', ' ')} variante {chr(97 + i)}" + (":" if SITUACIONES[s].dos_puntos else ".")
                for i in range(5)] for s in SITUACIONES}
    base["missing_focus"] = [f"Nada sobre «{{term}}» {chr(97 + i)}:" for i in range(5)]
    base["premise_not_found"] = [f"No hay {{entity}} {chr(97 + i)}." for i in range(5)]
    assert errores_tono(base) == []
    incompleto = {k: v for k, v in base.items() if k != "farewell"}
    assert any("faltan situaciones" in e for e in errores_tono(incompleto))
    corto = {**base, "farewell": base["farewell"][:4]}
    assert any("al menos 5" in e for e in errores_tono(corto))
    repetida = {**base, "farewell": [base["farewell"][0]] * 5}
    assert any("repite otra variante" in e for e in errores_tono(repetida))
    cruzada = {**base, "waiting": [base["farewell"][0]] + base["waiting"][1:]}
    assert any("repite una variante de farewell" in e for e in errores_tono(cruzada))


# --- paquetes ---------------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_los_tonos_incluidos_pasan_el_linter(idioma):
    for tono in tonos_disponibles(idioma):
        datos = _base(idioma, tono)
        assert errores_tono(datos["situations"], prohibidas(idioma)) == [], (idioma, tono)
        assert set(datos["situations"]) == set(SITUACIONES)


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_los_tonos_incluidos_son_neutros(idioma):
    """Sin regionalismos, formas con género ni saludos que dependan de la hora."""
    from ipsis.lenguaje.tonos import regionalismos_en

    for tono in tonos_disponibles(idioma):
        assert regionalismos_en(_base(idioma, tono)["situations"], idioma) == [], (idioma, tono)


def test_cordial_conserva_como_primera_variante_los_textos_anteriores():
    """Migración exacta: con el tono por defecto, las respuestas de siempre siguen ahí."""
    es = cargar_tono("es")
    assert es.variantes("no_answer")[0] == "No encontré esa información en los documentos disponibles."
    assert es.variantes("opening")[:4] == ["Esto es lo que dice el documento:", "Encontré esto en el documento:",
                                            "El documento lo plantea así:", "Según el texto cargado:"]
    assert es.variantes("welcome")[0] == "Hola, ¿en qué puedo ayudarte?"
    assert cargar_tono("en").variantes("no_answer")[0] == \
        "I couldn't find that information in the available documents."
    assert cargar_tono("pt").variantes("farewell")[0] == "Até logo."


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
        "conversacional": {"respuestas": {"saludo": "Hola."}, "patrones": {"greeting": ["^hola"]}},
        "interfaz": {"saludo": "Buenas.", "placeholder": "Escribe"},
    })
    assert plantillas == {"no_answer": ["Nada."], "welcome": ["Buenas."], "opening": ["Dice:"],
                          "greeting": ["Hola."]}
    assert propios == {"mensajes": {"sin_seccion": "(—)", "conectores": {"secuencia": ["Uno"]}},
                       "conversacional": {"patrones": {"greeting": ["^hola"]}}, "interfaz": {"placeholder": "Escribe"}}


def test_personalidad_yaml_sobrescribe_y_se_valida(tmp_path: Path):
    (tmp_path / "config").mkdir()
    ruta = tmp_path / "config" / "personality.yaml"
    ruta.write_text("tono:\n  plantillas:\n    no_answer: Eso no está en el manual.\n", encoding="utf-8")
    tono = cargar_tono("es", proyecto=tmp_path, sobrescrituras={"no_answer": ["Legado."]})
    assert tono.variantes("no_answer") == ["Eso no está en el manual."]  # personalidad gana al legado
    ruta.write_text("tono:\n  plantillas:\n    opening: [Sin dos puntos]\n", encoding="utf-8")
    with pytest.raises(TonoInvalido, match="opening"):
        cargar_tono("es", proyecto=tmp_path)


def test_el_motor_usa_el_tono_y_la_sobrescritura_del_proyecto(tmp_path: Path, monkeypatch):
    from ipsis.consulta.etapas.redaccion import cargar_plantillas
    from ipsis.lenguaje.paquete import cargar_paquete

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "personality.yaml").write_text(
        "tono:\n  plantillas:\n    no_answer: Eso no está en el manual.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    plantillas = cargar_plantillas(cargar_paquete("es"), {"nombre_asistente": "Ana", "descripcion_dominio": "el manual"})
    assert plantillas["tono"] == "cordial"
    assert plantillas["abstencion"]["generico"] == ["Eso no está en el manual."]
    assert plantillas["conectores"]["secuencia"] == ["Primero", "Luego", "Por último"]  # estructural, del idioma
    assert len(plantillas["conectores"]["opening"]) == 5
    assert all("Ana" in r or "manual" in r for r in plantillas["conversacional"]["respuestas"]["capability"])
