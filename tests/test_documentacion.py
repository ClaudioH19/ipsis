"""La guía de uso documenta todos los comandos de la CLI."""
from __future__ import annotations

import argparse
from pathlib import Path

GUIA = Path(__file__).resolve().parents[1] / "docs" / "guia" / "uso.md"


def _comandos(parser, ruta=()):
    for accion in parser._actions:
        if isinstance(accion, argparse._SubParsersAction):
            for nombre, sub in accion.choices.items():
                if any(isinstance(a, argparse._SubParsersAction) for a in sub._actions):
                    yield from _comandos(sub, ruta + (nombre,))
                else:
                    yield ruta + (nombre,)


def test_cada_comando_aparece_en_la_guia_de_uso():
    from rag.cli import construir_parser

    guia = GUIA.read_text(encoding="utf-8")
    faltan = [" ".join(c) for c in _comandos(construir_parser()) if f"rag {' '.join(c)}" not in guia]
    assert not faltan, f"documenta en docs/guia/uso.md: {faltan}"


def test_los_enlaces_relativos_de_la_documentacion_existen():
    import re

    raiz = GUIA.parents[2]
    archivos = [raiz / "README.md", raiz / "CHANGELOG.md", *sorted((raiz / "docs").rglob("*.md")),
                *sorted((raiz / "ejemplos").rglob("*.md")), raiz / "herramientas" / "avatar" / "LEEME.md"]
    rotos = []
    for archivo in archivos:
        if not archivo.is_file() or "node_modules" in archivo.parts:
            continue
        texto = re.sub(r"```.*?```", "", archivo.read_text(encoding="utf-8"), flags=re.S)
        for destino in re.findall(r"\]\(([^)\s]+)\)", texto):
            if re.match(r"^[a-z]+:|^#|^mailto:", destino):
                continue
            ruta = destino.split("#")[0]
            if ruta and not (archivo.parent / ruta).exists():
                rotos.append(f"{archivo.relative_to(raiz)} → {destino}")
    assert not rotos, rotos
