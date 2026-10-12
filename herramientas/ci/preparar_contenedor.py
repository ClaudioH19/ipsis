"""Proyecto pequeño real, indexado con light y desplegado desde el wheel actual."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

FUENTE = "# Inventario de prueba\n\nEl producto CI-001 tiene 17 unidades disponibles.\n"


def preparar(salida: Path, wheels: Path):
    from ipsis.cli import main

    paquetes = list(wheels.resolve().glob("ipsis-*.whl"))
    if len(paquetes) != 1:
        raise ValueError("Se requiere exactamente un wheel de ipsis del commit actual")
    salida = salida.resolve()
    proyecto = salida / "proyecto"
    proyecto.mkdir(parents=True, exist_ok=False)
    anterior = Path.cwd()
    try:
        os.chdir(proyecto)
        fuente = proyecto / "inventario.md"
        fuente.write_text(FUENTE, encoding="utf-8")
        for comando in (["init", "--profile", "light", "--language", "es"],
                        ["models", "download"], ["load", str(fuente)], ["index"],
                        ["deploy", "prepare", "--target", str(salida / "deploy"), "--wheel", str(paquetes[0])]):
            if main(comando) != 0:
                raise RuntimeError(f"Falló la preparación: {' '.join(comando)}")
    finally:
        os.chdir(anterior)
    return salida / "deploy"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, required=True)
    args = parser.parse_args()
    preparar(args.output, args.wheels)
