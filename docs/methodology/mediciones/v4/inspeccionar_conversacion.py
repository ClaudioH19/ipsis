"""Reproduce una conversación concreta para revisar pasajes y tramos del lector."""
from pathlib import Path
import json
import os
import runpy
import sys

RAIZ = Path(__file__).resolve().parents[4]
SALIDA = Path(__file__).resolve().parent
codigo, conversacion, perfil = sys.argv[1:4]
idioma = conversacion.split("-", 1)[0]
os.environ["IPSIS_CODIGO"] = str(RAIZ / ".cache/v4-continuacion" / codigo)
os.environ["IPSIS_ONNX_THREADS"] = "2"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TEMP"] = os.environ["TMP"] = str(RAIZ / ".cache/v4-continuacion/tmp")
runpy.run_path(str(RAIZ / "tests/datos/banco_consultas/medir.py"))["_importar_codigo"]()
modulo = runpy.run_path(str(RAIZ / "tests/datos/banco_conversaciones/medir.py"))
medir = modulo["medir_idioma"]
cargar = medir.__globals__["cargar"]
medir.__globals__["cargar"] = lambda idioma: [c for c in cargar(idioma) if c["id"] == conversacion]
r = medir(idioma, perfil)
archivo = SALIDA / f"inspeccion-{codigo}-{conversacion}-{perfil}.json"
archivo.write_text(json.dumps(r, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(r, ensure_ascii=False, indent=2), flush=True)
