"""Los reproductores de bancos distinguen prosa y QA y conservan el criterio."""
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

DATOS = Path(__file__).resolve().parents[1] / "datos"


def test_conversacion_evalua_prosa_con_evidencia_independientemente_del_qa():
    literal = runpy.run_path(str(DATOS / "banco_conversaciones/medir.py"))["_literal"]
    resultado = SimpleNamespace(mensaje_usuario="El plazo es dos días hábiles.",
                                evidencias=[SimpleNamespace(texto="El plazo es dos días hábiles.")],
                                diagnostico={"contrato_http": {"respuesta_exacta": {"texto": "dos"}}})
    assert literal(resultado, "dos días hábiles")
    resultado.mensaje_usuario = "El plazo no aparece."
    assert not literal(resultado, "dos días hábiles")


def test_comparador_de_consultas_no_mezcla_criterios():
    comparar = runpy.run_path(str(DATOS / "banco_consultas/medir.py"))["comparar"]
    anterior = {"medium": {"es": {"criterio_respuesta": "tramo_o_respuesta_v1"}}}
    nuevo = {"medium": {"es": {"criterio_respuesta": "respuesta_completa_v2"}}}
    with pytest.raises(ValueError, match="distintos criterios"):
        comparar(anterior, nuevo)
