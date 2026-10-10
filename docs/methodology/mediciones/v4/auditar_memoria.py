"""Inspecciona los términos de tema en los seguimientos perdidos (light)."""
from pathlib import Path
import json
import os
import runpy
import sys

RAIZ = Path(__file__).resolve().parents[4]
SALIDA = Path(__file__).resolve().parent
os.environ["IPSIS_CODIGO"] = str(RAIZ / ".cache/v4-continuacion/f4-v2")
temporal = RAIZ / ".cache/v4-continuacion/tmp"
os.environ["TEMP"] = os.environ["TMP"] = str(temporal)
runpy.run_path(str(RAIZ / "tests/datos/banco_consultas/medir.py"))["_importar_codigo"]()

from ipsis.consulta.seguimiento import MemoriaConversacion
from ipsis.lenguaje.consultas import terminos_de_contenido, terminos_genericos

original = MemoriaConversacion.resolver
registros = []


def resolver(self, pregunta, sesion, paquete, est):
    conversacion = self._sesiones.get(sesion)
    tema = conversacion.tema if conversacion else None
    propios = terminos_de_contenido(pregunta, paquete, est)
    con_tema = [t for t in propios if est.df.get(t, 0) and t not in terminos_genericos(paquete)]
    r = original(self, pregunta, sesion, paquete, est)
    if tema is not None and not r.seguimiento:
        registros.append({"sesion": sesion, "pregunta": pregunta, "accion": r.accion,
                          "nucleo": [est.superficie.get(t,t) for t in tema.nucleo],
                          "propios": [est.superficie.get(t,t) for t in con_tema],
                          "ausentes": [est.superficie.get(t,t) for t in con_tema if t not in tema.vocabulario()]})
    return r


MemoriaConversacion.resolver = resolver
medir = runpy.run_path(str(RAIZ / "tests/datos/banco_conversaciones/medir.py"))["medir_idioma"]
idioma = sys.argv[1] if len(sys.argv) > 1 else "es"
resultado = medir(idioma, "light")
preguntas = {t["pregunta"] for t in resultado["turnos"] if t["hereda"] is True and not t["heredo"]}
registros = [r for r in registros if r["pregunta"] in preguntas]
(SALIDA / f"auditoria-memoria-{idioma}.json").write_text(json.dumps(registros, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(registros, ensure_ascii=False, indent=2), flush=True)
