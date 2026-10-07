"""Mediciones consecutivas con iguales recursos; registra salida y procedencia."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

RAIZ = Path(__file__).resolve().parents[4]
SALIDA = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONUTF8="1", IPSIS_ONNX_THREADS="2", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
deadline = time.monotonic() + 3600
while not (SALIDA / "f4-final-conversaciones.json").exists():
    if time.monotonic() > deadline:
        raise TimeoutError("F4 no terminó")
    time.sleep(5)

jobs = [
    ["docs/methodology/mediciones/v4/ejecutar.py", "medir", "f1", "--bancos", "conversaciones"],
    ["docs/methodology/mediciones/v4/ejecutar.py", "medir", "final"],
    ["tests/datos/banco_universal/medir_latencia.py", str(RAIZ / ".cache/v4-continuacion/antes"),
     str(RAIZ / ".cache/v4-continuacion/final"), str(SALIDA / "pareadas"), "3"],
]
for n, job in enumerate(jobs, 1):
    print("EJECUTAR", " ".join(job), flush=True)
    with (SALIDA / f"pipeline-{n}.log").open("w", encoding="utf-8") as log:
        p = subprocess.Popen([sys.executable, *job], cwd=RAIZ, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        for linea in p.stdout:
            print(linea, end="", flush=True)
            log.write(linea); log.flush()
        if p.wait():
            raise RuntimeError(f"Falló {job}; salida en pipeline-{n}.log")
print("BANCOS Y LATENCIA COMPLETOS", flush=True)
