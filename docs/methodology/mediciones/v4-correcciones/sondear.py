"""Sondeo reproducible de conversaciones con diagnóstico completo, sin red."""
from pathlib import Path
import json
import os
import runpy
import sys

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
os.environ.update(PYTHONUTF8="1", IPSIS_ONNX_THREADS="2", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
temporal = RAIZ / ".cache/v4-correcciones/tmp"
temporal.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = os.environ["TMP"] = str(temporal)

from ipsis.consulta.motor import Motor

diagnosticos = []
consultar = Motor.consultar


def registrar(self, pregunta, sesion, **kwargs):
    resultado = consultar(self, pregunta, sesion, **kwargs)
    diagnosticos.append({"pregunta": pregunta, "sesion": sesion, "diagnostico": resultado.diagnostico})
    return resultado


Motor.consultar = registrar
modulo = runpy.run_path(str(RAIZ / "tests/datos/banco_conversaciones/medir.py"))
medir = modulo["medir_idioma"]
perfil, idioma, nombre = sys.argv[1:4]
if len(sys.argv) > 4:
    ids = set(sys.argv[4].split(","))
    cargar = medir.__globals__["cargar"]
    medir.__globals__["cargar"] = lambda idioma: [c for c in cargar(idioma) if c["id"] in ids]
resultado = medir(idioma, perfil)
resultado["diagnosticos"] = diagnosticos
destino = Path(__file__).resolve().parent / f"{nombre}-{perfil}-{idioma}.json"
destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(resultado["resumen"], ensure_ascii=False), flush=True)
for turno in resultado["turnos"]:
    if turno["respuesta"]:
        print(turno["conversacion"], turno["turno"], turno["correcta"], turno["estado"], turno["tramo_lector"], flush=True)
