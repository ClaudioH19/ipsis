"""Evalúa el banco universal con un perfil y resume por categoría.

Mide el estado actual del software; no ajusta nada. ``linea_base.json``
guarda el resultado de referencia, y la prueba lenta falla si los falsos
``ok`` superan esa referencia (regresión), sin exigir que hoy sean cero.

Registrar la línea base (requiere los modelos de cada perfil en caché)::

    python tests/datos/banco_universal/linea_base.py light,medium
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
IDIOMAS = ("es", "en", "pt")
ARCHIVO = RAIZ / "linea_base.json"
ESTADOS_OK = {"respuesta_directa", "respuesta_parcial"}
GRUPOS = ("exacta", "parafrasis", "trampa_mismo_tema", "fuera_de_dominio", "premisa_falsa", "ambigua")


def grupo(caso) -> str:
    if caso.subtipo == "trampa_mismo_tema":
        return "trampa_mismo_tema"
    if caso.estado_esperado == "fuera_dominio":
        return "fuera_de_dominio"
    return caso.categoria.value


def resumir(banco, observaciones) -> dict:
    """Por grupo: casos, ok, relacionado, abstenciones, falsos ok y, en las
    respondibles con ok, cuántas muestran la respuesta literal."""
    por_id = {o.caso_id: o for o in observaciones}
    salida = {g: {"n": 0, "ok": 0, "relacionado": 0, "abstiene": 0, "falsos_ok": 0, "ok_literal": 0}
              for g in GRUPOS}
    falsos = []
    for caso in banco.casos:
        obs = por_id[caso.id]
        fila = salida[grupo(caso)]
        fila["n"] += 1
        if obs.estado in ESTADOS_OK:
            fila["ok"] += 1
            if caso.respondible:
                textos = [obs.respuesta] + [e.texto for e in obs.evidencias]
                fila["ok_literal"] += any(caso.respuesta_literal in t for t in textos)
            else:
                fila["falsos_ok"] += 1
                falsos.append(caso.id)
        elif obs.estado == "relacionado":
            fila["relacionado"] += 1
        else:
            fila["abstiene"] += 1
    return {"grupos": salida, "falsos_ok": sorted(falsos)}


def evaluar(idioma: str, perfil: str) -> dict:
    """Proyecto temporal ``rag init --perfil --idioma`` con el corpus del idioma."""
    from rag.aplicacion.evaluacion import evaluar_backend_activo
    from rag.cli import main
    from rag.evaluacion.banco import cargar_banco

    from rag.lenguaje.entidades import configurar_idioma, configurar_perfil, idioma_activo, perfil_activo

    manifiesto = RAIZ / idioma / "manifiesto.json"
    banco = cargar_banco(manifiesto)
    anterior = Path.cwd()
    # ``rag indexar`` fija el idioma y el perfil de dominio del proceso: se
    # restauran para no contaminar a quien llame después (p. ej. otras pruebas).
    idioma_previo, perfil_previo = idioma_activo(), perfil_activo()
    with tempfile.TemporaryDirectory(prefix=f"rag_universal_{idioma}_{perfil}_") as temporal:
        try:
            os.chdir(temporal)
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", "--perfil", perfil, "--idioma", idioma]) == 0
                assert main(["cargar", str(RAIZ / idioma / "corpus")]) == 0
                assert main(["indexar"]) == 0
                artefacto = evaluar_backend_activo(str(manifiesto))
        finally:
            os.chdir(anterior)
            configurar_idioma(idioma_previo)
            configurar_perfil(perfil_previo)
    return resumir(banco, artefacto.observaciones)


def registrar(perfiles: list[str]) -> dict:
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.is_file() else {}
    for perfil in perfiles:
        for idioma in IDIOMAS:
            datos.setdefault(perfil, {})[idioma] = evaluar(idioma, perfil)
    ARCHIVO.write_bytes((json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return datos


if __name__ == "__main__":
    registrar(sys.argv[1].split(",") if len(sys.argv) > 1 else ["light", "medium"])
