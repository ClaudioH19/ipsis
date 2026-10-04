"""El tono solo enmarca: con otras plantillas, los estados, las reglas y la
literalidad de ``ipsis evaluar`` son idénticos (P12.2)."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1] / "datos" / "banco_universal"
GRIEGAS = ["alfa", "beta", "gamma", "delta", "épsilon"]

pytestmark = [pytest.mark.slow, pytest.mark.modelos("intfloat/multilingual-e5-small")]


def _otro_tono() -> dict[str, list[str]]:
    """Plantillas distintas a ``cordial`` para todas las situaciones del motor, válidas para el linter."""
    from ipsis.lenguaje.tonos import SITUACIONES

    plantillas = {}
    for situacion, regla in SITUACIONES.items():
        if regla.origen != "motor":
            continue
        variables = " ".join(f"{{{v}}}" for v in sorted(regla.requeridas))
        final = ":" if regla.dos_puntos else "."
        nombre = situacion.replace("_", " ")
        plantillas[situacion] = [f"Plantilla {nombre} {g} {variables}".rstrip() + final for g in GRIEGAS]
    return plantillas


def _por_caso(artefacto) -> dict[str, tuple]:
    return {o.caso_id: (o.estado, o.regla, o.respuesta_exacta) for o in artefacto.observaciones}


def test_otro_tono_no_cambia_estados_reglas_ni_literalidad(tmp_path: Path):
    from ipsis.aplicacion.evaluacion import evaluar_backend_activo
    from ipsis.cli import main
    from ipsis.lenguaje.entidades import configurar_idioma, configurar_perfil, idioma_activo, perfil_activo

    manifiesto = RAIZ / "es" / "manifiesto.json"
    anterior, idioma_previo, perfil_previo = Path.cwd(), idioma_activo(), perfil_activo()
    try:
        os.chdir(tmp_path)
        with contextlib.redirect_stdout(io.StringIO()):
            assert main(["init", "--perfil", "light", "--idioma", "es"]) == 0
            assert main(["cargar", str(RAIZ / "es" / "corpus")]) == 0
            assert main(["indexar"]) == 0
        cordial = evaluar_backend_activo(str(manifiesto))
        Path("configuracion/personalidad.yaml").write_text(
            yaml.safe_dump({"tono": {"plantillas": _otro_tono()}}, allow_unicode=True), encoding="utf-8")
        otro = evaluar_backend_activo(str(manifiesto))
    finally:
        os.chdir(anterior)
        configurar_idioma(idioma_previo)
        configurar_perfil(perfil_previo)

    assert cordial.tono == otro.tono == "cordial"  # el nombre del tono no cambia; sí sus textos
    assert any("Plantilla" in o.respuesta for o in otro.observaciones)  # las plantillas nuevas se usaron
    assert _por_caso(cordial) == _por_caso(otro)
    # Por caso: estado, regla, falso ok, directa sin literal, señales, tramo y evidencia.
    assert cordial.reporte.cobertura.model_dump() == otro.reporte.cobertura.model_dump()
