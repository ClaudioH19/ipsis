from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

raiz = Path(__file__).resolve().parents[2]
salida = raiz / ".cache/plan-v4"
env = dict(os.environ, PYTHONUTF8="1", TEMP=str(salida / "tmp"), TMP=str(salida / "tmp"))
consulta = raiz / "tests/datos/banco_consultas/medir.py"
conversaciones = raiz / "tests/datos/banco_conversaciones/medir.py"
limite = time.monotonic() + 1200
while True:
    try:
        d = json.loads((salida / "despues-conversaciones.json").read_text(encoding="utf-8"))
        assert all(set(d[p]) == {"es", "en", "pt"} for p in ("light", "medium"))
        break
    except (OSError, ValueError, AssertionError):
        if time.monotonic() > limite:
            raise TimeoutError("El primer intento no terminó")
        time.sleep(5)
time.sleep(2)
previo = salida / "intento-1"
previo.mkdir(exist_ok=True)
for nombre in ("consultas", "universal", "conversaciones"):
    shutil.copy2(salida / f"despues-{nombre}.json", previo / f"despues-{nombre}.json")
shutil.copy2(salida / "metadata.json", previo / "metadata.json")
h = hashlib.sha256()
for p in sorted((raiz / "ipsis").rglob("*")):
    if p.is_file() and p.suffix in {".py", ".yaml"}:
        h.update(p.relative_to(raiz).as_posix().encode()); h.update(b"\0"); h.update(p.read_bytes())
meta = json.loads((salida / "metadata.json").read_text(encoding="utf-8"))
meta["initial_after_code"] = meta["after_code"]
meta["after_code"] = "sha256:" + h.hexdigest()
meta["optimization"] = "reuse query-content cache; cache normalized stopwords by stemmer and effective word list"
(salida / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for banco in ("consultas", "universal", "conversaciones"):
    script = conversaciones if banco == "conversaciones" else consulta
    args = [str(script), str(salida / f"despues-{banco}.json"), "light,medium", "es,en,pt"]
    if banco == "universal":
        args.append("banco_universal")
    comando = "import runpy,sys; runpy.run_path(sys.argv[1])['_importar_codigo'](); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    print(f"MEDIR FINAL {banco}", flush=True)
    subprocess.run([sys.executable, "-c", comando, str(consulta), *args], cwd=raiz,
                   env={**env, "IPSIS_CODIGO": str(raiz)}, check=True)
print("SUITE COMPLETA", flush=True)
subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "--basetemp", str(raiz / ".cache/pytest-plan-v4-completa"),
                "--junitxml", str(salida / "pruebas.xml")], cwd=raiz, env=env, check=True)
print("VALIDACIÓN FINAL COMPLETA", flush=True)
