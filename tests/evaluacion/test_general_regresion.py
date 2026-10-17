"""La suite normal también comprueba la regresión real cuando hay modelos."""
import json
import importlib.util
from pathlib import Path

import pytest

from ipsis.configuracion.perfiles import cargar_perfil_instalacion

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "tests/datos/banco_general"


def general():
    spec = importlib.util.spec_from_file_location("regresion_general", RAIZ / "herramientas/evaluacion/general.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def perfil_con_modelos(nombre):
    ids = [m for m in cargar_perfil_instalacion(nombre).modelos.model_dump().values() if m]
    return pytest.param(nombre, marks=pytest.mark.modelos(*ids))


@pytest.mark.slow
@pytest.mark.parametrize("perfil", [perfil_con_modelos(p) for p in ("light", "medium")])
def test_regresion_documental_real(perfil, tmp_path, monkeypatch):
    monkeypatch.setenv("IPSIS_ONNX_THREADS", "2")
    m = general()
    # La línea base se midió el 2026-10-10 con la cascada de v1 y fragmentos de tamaño fijo; hoy los valores por defecto son
    # v2 y la preparación estructural (ADR 0009), y esta regresión protege el camino anterior.
    actual = m.ejecutar([perfil], [], [BANCO / c / "manifiesto.json" for c in ("bueno", "medio", "malo")],
                       tmp_path / "reportes", condiciones={"pipeline": "v1", "recuperacion": {"preparacion": {"modo": "legacy"}}})
    base = json.loads((BANCO / "linea_base.json").read_text(encoding="utf-8"))
    assert not actual["fallos"], actual["fallos"]
    assert len(actual["resultados"]) == 3
    assert not m.comparar(actual, base)
