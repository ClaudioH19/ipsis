"""Mide el banco de conversaciones: cada conversación en una sesión propia,
turno a turno, sobre el corpus del banco de consultas del mismo idioma.

    python tests/datos/banco_conversaciones/medir.py <salida.json> [light,medium] [es,en,pt]

Por turno registra si heredó tema (``pregunta_interpretada`` en el
diagnóstico), el estado y si la respuesta muestra el texto literal esperado.
El resumen por perfil e idioma cuenta:

- herencia correcta sobre los turnos con ``hereda``; heredó sin deber
  (``herencia_indebida``: el peligro de un cambio de tema) y no heredó
  debiendo (``herencia_perdida``);
- respuestas correctas sobre los turnos con ``respuesta`` (directa y con el
  literal en la respuesta completa y en una evidencia); QA se mide aparte;
- directas indebidas: turnos con ``directa: false`` que terminaron en
  respuesta directa.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent
CORPUS = RAIZ.parent / "banco_consultas"
IDIOMAS = ("es", "en", "pt")


def cargar(idioma: str) -> list[dict]:
    return yaml.safe_load((RAIZ / idioma / "conversaciones.yaml").read_text(encoding="utf-8"))


def _literal(resultado, esperado: str) -> bool:
    return esperado in resultado.mensaje_usuario and any(esperado in e.texto for e in resultado.evidencias)


def medir_idioma(idioma: str, perfil: str) -> dict:
    from ipsis.aplicacion.consulta import construir_motor_del_proyecto
    from ipsis.cli import main
    from ipsis.lenguaje.entidades import configurar_idioma, configurar_perfil, idioma_activo, perfil_activo

    previo = (idioma_activo(), perfil_activo())
    anterior = Path.cwd()
    turnos = []
    with tempfile.TemporaryDirectory(prefix=f"conversaciones_{idioma}_{perfil}_", ignore_cleanup_errors=True) as tmp:
        motor = None
        try:
            os.chdir(tmp)
            with contextlib.redirect_stdout(io.StringIO()):
                assert main(["init", "--profile", perfil, "--language", idioma]) == 0
                assert main(["load", str(CORPUS / idioma / "corpus")]) == 0
                assert main(["index"]) == 0
            motor = construir_motor_del_proyecto()
            for conversacion in cargar(idioma):
                sesion = f"conversacion:{conversacion['id']}"
                for n, turno in enumerate(conversacion["turnos"], start=1):
                    r = motor.consultar(turno["pregunta"], sesion)
                    heredo = bool(r.diagnostico.get("pregunta_interpretada"))
                    directa = r.estado.value == "respuesta_directa"
                    exacta = ((r.diagnostico.get("contrato_http") or {}).get("respuesta_exacta") or {}).get("texto")
                    turnos.append({
                        "conversacion": conversacion["id"], "turno": n, "pregunta": turno["pregunta"],
                        "estado": r.estado.value, "heredo": heredo,
                        "interpretada": r.diagnostico.get("pregunta_interpretada"),
                        "hereda": turno.get("hereda"), "directa_esperada": turno.get("directa"),
                        "respuesta": turno.get("respuesta"),
                        "correcta": bool(turno.get("respuesta")) and directa and _literal(r, turno["respuesta"]),
                        "directa": directa,
                        "mensaje": r.mensaje_usuario,
                        "tramo_lector": exacta,
                        "tramo_qa_correcto": (turno["respuesta"] in exacta
                                               if directa and turno.get("respuesta") and exacta is not None else None),
                        "conversacion_diagnostico": r.diagnostico.get("conversacion"),
                    })
        finally:
            if motor is not None:
                motor.cerrar()
            os.chdir(anterior)
            configurar_idioma(previo[0])
            configurar_perfil(previo[1])
    return {"criterio_respuesta": "respuesta_completa_conversaciones_v2", "turnos": turnos, "resumen": resumir(turnos)}


def resumir(turnos: list[dict]) -> dict:
    con_hereda = [t for t in turnos if t["hereda"] is not None]
    con_respuesta = [t for t in turnos if t["respuesta"]]
    sin_directa = [t for t in turnos if t["directa_esperada"] is False]
    tramos = [t for t in turnos if t.get("tramo_qa_correcto") is not None]
    return {
        "herencia_correcta": sum(t["heredo"] == t["hereda"] for t in con_hereda), "con_hereda": len(con_hereda),
        "herencia_indebida": sum(t["heredo"] and t["hereda"] is False for t in con_hereda),
        "herencia_perdida": sum(not t["heredo"] and t["hereda"] is True for t in con_hereda),
        "respuestas_correctas": sum(t["correcta"] for t in con_respuesta), "con_respuesta": len(con_respuesta),
        "directas_indebidas": sum(t["directa"] for t in sin_directa), "sin_directa": len(sin_directa),
        "tramos_qa_evaluados": len(tramos), "tramos_qa_sin_literal": sum(not t["tramo_qa_correcto"] for t in tramos),
    }


def main_cli(argv: list[str]) -> None:
    salida = Path(argv[0])
    perfiles = (argv[1] if len(argv) > 1 else "light,medium").split(",")
    idiomas = (argv[2] if len(argv) > 2 else ",".join(IDIOMAS)).split(",")
    resultado: dict = {}
    for perfil in perfiles:
        for idioma in idiomas:
            medido = medir_idioma(idioma, perfil)
            resultado.setdefault(perfil, {})[idioma] = medido
            print(perfil, idioma, json.dumps(medido["resumen"], ensure_ascii=False), flush=True)
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main_cli(sys.argv[1:])
