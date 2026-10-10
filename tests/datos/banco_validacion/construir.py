"""Construye el banco de validación con las reglas del banco universal.

Fuentes: ``<idioma>/corpus/*.md`` y ``<idioma>/casos.yaml``. Derivados
(versionados): ``<idioma>/banco.jsonl`` y ``<idioma>/manifiesto.json``.

    python tests/datos/banco_validacion/construir.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
IDIOMAS = ("es", "en", "pt")


def _universal():
    ruta = RAIZ.parent / "banco_universal" / "construir.py"
    spec = importlib.util.spec_from_file_location("banco_universal_construir", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def construir(idioma: str) -> tuple[str, str]:
    return _universal().construir(idioma, raiz=RAIZ, dataset="validacion")


def escribir() -> None:
    for idioma in IDIOMAS:
        manifiesto, casos = construir(idioma)
        (RAIZ / idioma / "manifiesto.json").write_bytes(manifiesto.encode("utf-8"))
        (RAIZ / idioma / "banco.jsonl").write_bytes(casos.encode("utf-8"))


if __name__ == "__main__":
    escribir()
