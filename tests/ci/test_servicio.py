"""La comprobación de arranque no acepta un HTTP 200 con una respuesta vacía."""
import importlib.util
from pathlib import Path

import pytest

_ruta = Path(__file__).resolve().parents[2] / "herramientas/ci/comprobar_servicio.py"
_spec = importlib.util.spec_from_file_location("comprobar_servicio_ci", _ruta)
_modulo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_modulo)
validar_conversacion = _modulo.validar_conversacion
validar_fuentes = _modulo.validar_fuentes
PASO_DOCUMENTAL = _modulo.PASO_DOCUMENTAL


@pytest.mark.parametrize("respuesta", [
    {}, {"status": "conversational", "conversational_category": "greeting", "answer": ""},
    {"status": "related", "answer": "Hola"},
    {"status": "conversational", "conversational_category": "greeting", "answer": "Hola", "fragments": [{}]},
])
def test_rechaza_conversaciones_incorrectas(respuesta):
    with pytest.raises(RuntimeError):
        validar_conversacion(respuesta, "greeting")


def test_exige_dato_del_corpus_y_offsets_reales():
    fuente = {"doc_title": "Inventario", "text": PASO_DOCUMENTAL, "offset_start": 3,
              "offset_end": 3 + len(PASO_DOCUMENTAL)}
    respuesta = {"status": "related", "response_mode": "ranked_sources", "fragments": [fuente]}
    validar_fuentes(respuesta)
    fuente["offset_end"] += 1
    with pytest.raises(RuntimeError, match="Offsets"):
        validar_fuentes(respuesta)
    fuente["text"] = "Un documento ajeno"
    with pytest.raises(RuntimeError, match="dato conocido"):
        validar_fuentes(respuesta)
