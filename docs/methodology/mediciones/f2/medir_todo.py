from pathlib import Path
import os
import subprocess
import sys

raiz = Path(__file__).resolve().parents[2]
salida = raiz / ".cache/plan-v4"
env = dict(os.environ, PYTHONUTF8="1", TEMP=str(salida / "tmp"), TMP=str(salida / "tmp"))
consulta = raiz / "tests/datos/banco_consultas/medir.py"
conversaciones = raiz / "tests/datos/banco_conversaciones/medir.py"
jobs = [("antes", "universal", salida / "base"), ("antes", "conversaciones", salida / "base"),
        ("despues", "consultas", raiz), ("despues", "universal", raiz), ("despues", "conversaciones", raiz)]
for momento, banco, codigo in jobs:
    destino = salida / f"{momento}-{banco}.json"
    script = conversaciones if banco == "conversaciones" else consulta
    args = [str(script), str(destino), "light,medium", "es,en,pt"]
    if banco == "universal":
        args.append("banco_universal")
    # También las conversaciones usan exactamente el árbol de código indicado.
    comando = "import runpy,sys; runpy.run_path(sys.argv[1])['_importar_codigo'](); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    print(f"MEDIR {momento} {banco}", flush=True)
    subprocess.run([sys.executable, "-c", comando, str(consulta), *args],
                   cwd=raiz, env={**env, "IPSIS_CODIGO": str(codigo)}, check=True)
print("MEDICIONES COMPLETAS", flush=True)
