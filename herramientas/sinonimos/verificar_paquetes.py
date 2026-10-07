"""Comprueba wheel y sdist en una copia limpia, sin red ni build/ previo."""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def verificar() -> tuple[Path, Path]:
    from setuptools.build_meta import build_sdist, build_wheel

    base = RAIZ / ".cache/sinonimos/paquetes"
    base.mkdir(parents=True, exist_ok=True)
    trabajo = Path(tempfile.mkdtemp(prefix="revision-", dir=base))
    fuente = trabajo / "src"
    fuente.mkdir()
    # build/lib puede contener paquetes de versiones antiguas del repositorio.
    # Se copia la fuente actual, no se borra el build/ compartido del usuario.
    for nombre in ["pyproject.toml", "MANIFEST.in", "README.md", "LICENSE"]:
        shutil.copy2(RAIZ / nombre, fuente / nombre)
    ignorar = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(RAIZ / "ipsis", fuente / "ipsis", ignore=ignorar)
    shutil.copytree(RAIZ / "herramientas/sinonimos", fuente / "herramientas/sinonimos", ignore=ignorar)
    dist = trabajo / "dist"
    dist.mkdir()
    anterior = Path.cwd()
    try:
        os.chdir(fuente)
        with (trabajo / "build.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
            wheel = dist / build_wheel(str(dist))
            sdist = dist / build_sdist(str(dist))
    finally:
        os.chdir(anterior)
    recursos = RAIZ / "ipsis/recursos/sinonimos"
    esperados = {"ipsis/recursos/sinonimos/" + p.relative_to(recursos).as_posix(): p.read_bytes()
                 for p in recursos.rglob("*") if p.is_file()}
    with zipfile.ZipFile(wheel) as archivo:
        assert not any(n.startswith("rag/") for n in archivo.namelist()), "Old build artifacts included"
        assert not any(n.startswith("herramientas/") for n in archivo.namelist()), "Originals must not be in wheel"
        presentes = {n for n in archivo.namelist() if n.startswith("ipsis/recursos/sinonimos/")}
        assert presentes == set(esperados), "Missing or unexpected synonym resources in wheel"
        for nombre, datos in esperados.items():
            assert archivo.read(nombre) == datos, f"Wheel resource differs: {nombre}"
    originales = RAIZ / "herramientas/sinonimos/datos"
    with tarfile.open(sdist) as archivo:
        prefijo = archivo.getnames()[0].split("/")[0] + "/"
        for nombre, datos in esperados.items():
            contenido = archivo.extractfile(prefijo + nombre)
            assert contenido is not None and contenido.read() == datos, f"Sdist resource differs: {nombre}"
        for p in originales.rglob("*"):
            if p.is_file():
                contenido = archivo.extractfile(prefijo + "herramientas/sinonimos/datos/" + p.relative_to(originales).as_posix())
                assert contenido is not None and contenido.read() == p.read_bytes(), f"Sdist source differs: {p.name}"
    # Esta copia no tiene .cache ni acceso automático a la red: reproduce
    # la situación de otro clon con los archivos que se van a distribuir.
    prueba = subprocess.run([sys.executable, "-X", "utf8", "herramientas/sinonimos/construir.py", "all", "--check"],
                            cwd=fuente, capture_output=True, text=True, encoding="utf-8", timeout=1200)
    assert prueba.returncode == 0, f"Offline rebuild in clean copy failed: {prueba.stdout}\n{prueba.stderr}"
    print(f"Verified {len(esperados)} synonym resources in wheel/sdist and all original sources in sdist")
    print("Offline rebuild in clean source copy passed, without .cache")
    print(f"Wheel: {wheel}")
    print(f"Sdist: {sdist}")
    return wheel, sdist


if __name__ == "__main__":
    verificar()
