"""Captura árboles y mide bancos con código congelado, sin descargas."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

RAIZ = Path(__file__).resolve().parents[4]
SALIDA = Path(__file__).resolve().parent
CACHE = RAIZ / ".cache/v4-continuacion"


def capturar(nombre, origen=RAIZ, memoria_final=False):
    destino = CACHE / nombre
    if destino.exists():
        raise FileExistsError(destino)
    def copiar(origen, salida):
        if Path(origen).suffix in {".gz", ".tsv", ".part"}:
            os.link(origen, salida)
            return salida
        return shutil.copy2(origen, salida)
    shutil.copytree(origen / "ipsis", destino / "ipsis", copy_function=copiar,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if memoria_final:
        for archivo in ("consulta/seguimiento.py", "consulta/etapas/verificacion.py"):
            shutil.copy2(RAIZ / "ipsis" / archivo, destino / "ipsis" / archivo)
    h = hashlib.sha256()
    with zipfile.ZipFile(SALIDA / f"{nombre}-code.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((destino / "ipsis").rglob("*")):
            if p.is_file() and p.suffix in {".py", ".yaml", ".js"}:
                relativa = p.relative_to(destino).as_posix()
                h.update(relativa.encode()); h.update(b"\0"); h.update(p.read_bytes())
                z.write(p, relativa)
    (SALIDA / f"{nombre}-codigo.json").write_text(json.dumps({
        "sha256_py_yaml_js": h.hexdigest(), "codigo": str(destino),
        "recursos": "Recursos locales congelados de F2; archivos grandes enlazados sin modificar.",
    }, indent=2) + "\n", encoding="utf-8")
    print(nombre, h.hexdigest(), flush=True)


def medir(nombre, bancos):
    temporal = CACHE / "tmp"
    temporal.mkdir(parents=True, exist_ok=True)
    codigo = CACHE / nombre
    consulta = RAIZ / "tests/datos/banco_consultas/medir.py"
    env = dict(os.environ, PYTHONUTF8="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               TEMP=str(temporal), TMP=str(temporal), IPSIS_CODIGO=str(codigo))
    for banco in bancos.split(","):
        script = (RAIZ / "tests/datos/banco_conversaciones/medir.py") if banco == "conversaciones" else consulta
        args = [str(script), str(SALIDA / f"{nombre}-{banco}.json"), "light,medium", "es,en,pt"]
        if banco == "universal":
            args.append("banco_universal")
        print("MEDIR", nombre, banco, flush=True)
        subprocess.run([sys.executable, str(SALIDA / "medir_con_auditoria.py"), str(consulta), *args],
                       cwd=RAIZ, env=env, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("accion", choices=["capturar", "medir"])
    parser.add_argument("nombre")
    parser.add_argument("--bancos", default="consultas,universal,conversaciones")
    parser.add_argument("--desde")
    parser.add_argument("--memoria-final", action="store_true")
    args = parser.parse_args()
    capturar(args.nombre, CACHE / args.desde if args.desde else RAIZ, args.memoria_final) if args.accion == "capturar" else medir(args.nombre, args.bancos)
