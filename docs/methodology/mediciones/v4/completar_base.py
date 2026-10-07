"""Completa F1 con la métrica corregida, después de terminar la ronda final."""
from pathlib import Path
import os
import subprocess
import sys
import time

RAIZ = Path(__file__).resolve().parents[4]
SALIDA = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONUTF8="1", IPSIS_ONNX_THREADS="2", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
deadline = time.monotonic() + 3600
while not (SALIDA / "pareadas/resumen.json").exists():
    if time.monotonic() > deadline:
        raise TimeoutError("No terminó la medición anterior; revisar pipeline-3.log")
    time.sleep(5)

jobs = [
    ["docs/methodology/mediciones/v4/ejecutar.py", "medir", "f1", "--bancos", "consultas,universal"],
    ["tests/datos/banco_universal/medir_latencia.py", str(RAIZ / ".cache/v4-continuacion/f1"),
     str(RAIZ / ".cache/v4-continuacion/final"), str(SALIDA / "pareadas-f1"), "3"],
]
for n, job in enumerate(jobs, 1):
    print("EJECUTAR", " ".join(job), flush=True)
    with (SALIDA / f"base-{n}.log").open("w", encoding="utf-8") as log:
        p = subprocess.Popen([sys.executable, *job], cwd=RAIZ, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        for linea in p.stdout:
            print(linea, end="", flush=True)
            log.write(linea); log.flush()
        if p.wait():
            raise RuntimeError(f"Falló {job}; salida en base-{n}.log")
print("BASE F1 COMPLETA", flush=True)
