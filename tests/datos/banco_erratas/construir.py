"""Construye el banco de erratas (diseño y validación) con las reglas del banco universal.

Fuentes: ``<conjunto>/<idioma>/casos.yaml`` (de generar.py) y su corpus. Derivados
(versionados): ``banco.jsonl`` y ``manifiesto.json``.

    python tests/datos/banco_erratas/construir.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
IDIOMAS = ("es", "en", "pt")
CONJUNTOS = ("diseno", "validacion")


def _universal():
    ruta = RAIZ.parent / "banco_universal" / "construir.py"
    spec = importlib.util.spec_from_file_location("banco_universal_construir", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def construir(conjunto: str, idioma: str) -> tuple[str, str]:
    return _universal().construir(idioma, raiz=RAIZ / conjunto, dataset=f"erratas_{conjunto}")


def escribir() -> None:
    for conjunto in CONJUNTOS:
        for idioma in IDIOMAS:
            manifiesto, casos = construir(conjunto, idioma)
            carpeta = RAIZ / conjunto / idioma
            (carpeta / "manifiesto.json").write_bytes(manifiesto.encode("utf-8"))
            (carpeta / "banco.jsonl").write_bytes(casos.encode("utf-8"))


if __name__ == "__main__":
    escribir()
