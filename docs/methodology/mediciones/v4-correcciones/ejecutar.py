"""Congela una ronda nueva y mide los tres bancos sin alterar las anteriores."""
from pathlib import Path
import os
import runpy
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[4]
SALIDA = Path(__file__).resolve().parent
CACHE = RAIZ / ".cache/v4-correcciones"
anterior = SALIDA.parent / "v4"
nombre, bancos = sys.argv[1:3]
idiomas = sys.argv[3] if len(sys.argv) > 3 else "es,en,pt"
capturar = runpy.run_path(str(anterior / "ejecutar.py"))["capturar"]
capturar.__globals__.update(SALIDA=SALIDA, CACHE=CACHE)
capturar(nombre)
temporal = CACHE / "tmp"
temporal.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, PYTHONUTF8="1", IPSIS_ONNX_THREADS="2", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
           TEMP=str(temporal), TMP=str(temporal), IPSIS_CODIGO=str(CACHE / nombre))
consulta = RAIZ / "tests/datos/banco_consultas/medir.py"
for banco in bancos.split(","):
    script = RAIZ / "tests/datos/banco_conversaciones/medir.py" if banco == "conversaciones" else consulta
    args = [str(script), str(SALIDA / f"{nombre}-{banco}.json"), "light,medium", idiomas]
    if banco == "universal":
        args.append("banco_universal")
    print("MEDIR", nombre, banco, flush=True)
    with (SALIDA / f"{nombre}-{banco}.log").open("w", encoding="utf-8") as log:
        subprocess.run([sys.executable, str(anterior / "medir_con_auditoria.py"), str(consulta), *args],
                       cwd=RAIZ, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    print((SALIDA / f"{nombre}-{banco}.log").read_text(encoding="utf-8"), flush=True)
