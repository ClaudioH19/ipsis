"""Evalúa el banco universal con un perfil y resume por categoría.

Mide el estado actual del software; no ajusta nada. v2 publica fuentes y no decide
«ok» (ADR 0012): la prueba lenta comprueba que ningún caso salga «ok». La calidad de la
recuperación se vigila con ``tests/datos/banco_general``."""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
IDIOMAS = ("es", "en", "pt")
GRUPOS = ("exacta", "parafrasis", "trampa_mismo_tema", "fuera_de_dominio", "premisa_falsa", "ambigua")


def resumir(artefacto) -> dict:
    """Resumen compacto de ``reporte.cobertura`` (las métricas de
    ``ipsis.evaluacion.metricas``): por grupo, casos, ok, relacionado,
    abstenciones, falsos ok y ok con la respuesta literal."""
    cobertura = artefacto.reporte.cobertura
    grupos = {}
    for nombre in GRUPOS:
        g = cobertura.por_grupo[nombre]
        grupos[nombre] = {"n": g.n, "ok": g.directas, "relacionado": g.relacionadas, "abstiene": g.abstenciones,
                          "falsos_ok": g.falsos_ok, "ok_literal": g.directas - g.directas_sin_literal
                          if nombre in ("exacta", "parafrasis") else 0}
    return {"grupos": grupos, "falsos_ok": sorted(f.caso_id for f in cobertura.casos if f.falso_ok),
            "directas_sin_literal": sorted(f.caso_id for f in cobertura.casos if f.directa_sin_literal)}


def evaluar_artefacto(idioma: str, perfil: str):
    """Proyecto temporal ``ipsis init --profile --language`` con el corpus del idioma."""
    from ipsis.aplicacion.evaluacion import evaluar_backend_activo
    from ipsis.cli import main
    from ipsis.evaluacion.banco import cargar_banco

    from ipsis.lenguaje.entidades import configurar_idioma, configurar_perfil, idioma_activo, perfil_activo

    manifiesto = RAIZ / idioma / "manifiesto.json"
    cargar_banco(manifiesto)  # valida el banco antes de indexar
    anterior = Path.cwd()
    # ``ipsis index`` fija el idioma y el perfil de dominio del proceso: se
    # restauran para no contaminar a quien llame después (p. ej. otras pruebas).
    idioma_previo, perfil_previo = idioma_activo(), perfil_activo()
    with tempfile.TemporaryDirectory(prefix=f"rag_universal_{idioma}_{perfil}_") as temporal:
        try:
            os.chdir(temporal)
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", "--profile", perfil, "--language", idioma]) == 0
                assert main(["load", str(RAIZ / idioma / "corpus")]) == 0
                assert main(["index"]) == 0
                artefacto = evaluar_backend_activo(str(manifiesto))
        finally:
            os.chdir(anterior)
            configurar_idioma(idioma_previo)
            configurar_perfil(perfil_previo)
    return artefacto
