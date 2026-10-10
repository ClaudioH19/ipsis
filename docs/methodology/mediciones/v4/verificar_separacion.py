"""Reevalúa la separación de palabras genéricas; conserva la ronda que falló G3."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import time

RAIZ = Path(__file__).resolve().parents[4]
SALIDA = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONUTF8="1", IPSIS_ONNX_THREADS="2", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
deadline = time.monotonic() + 3600
while not (SALIDA / "pareadas-f1/resumen.json").exists():
    if time.monotonic() > deadline:
        raise TimeoutError("No terminó la ronda F1 anterior")
    time.sleep(5)

shutil.copy2(SALIDA / "intenciones-dev-test.json", SALIDA / "intenciones-antes-separacion.json")
jobs = [
    ["docs/methodology/mediciones/v4/calibrar_intenciones.py"],
    ["docs/methodology/mediciones/v4/ejecutar.py", "capturar", "corregido"],
    ["docs/methodology/mediciones/v4/ejecutar.py", "medir", "corregido"],
    ["tests/datos/banco_universal/medir_latencia.py", str(RAIZ / ".cache/v4-continuacion/antes"),
     str(RAIZ / ".cache/v4-continuacion/corregido"), str(SALIDA / "pareadas-corregidas"), "3"],
    ["tests/datos/banco_universal/medir_latencia.py", str(RAIZ / ".cache/v4-continuacion/f1"),
     str(RAIZ / ".cache/v4-continuacion/corregido"), str(SALIDA / "pareadas-f1-corregidas"), "3"],
]
for n, job in enumerate(jobs, 1):
    print("EJECUTAR", " ".join(job), flush=True)
    with (SALIDA / f"separacion-{n}.log").open("w", encoding="utf-8") as log:
        p = subprocess.Popen([sys.executable, *job], cwd=RAIZ, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        for linea in p.stdout:
            print(linea, end="", flush=True)
            log.write(linea); log.flush()
        if p.wait():
            raise RuntimeError(f"Falló {job}; salida en separacion-{n}.log")
    if n == 1:
        prev, actual = (json.loads((SALIDA / p).read_text(encoding="utf-8")) for p in
                        ("intenciones-antes-separacion.json", "intenciones-dev-test.json"))
        for idioma, ajustes in actual["idiomas"].items():
            assert all(ajustes[k] == prev["idiomas"][idioma][k] for k in ("tau", "delta", "habilitadas")), idioma
print("SEPARACIÓN REEVALUADA", flush=True)
