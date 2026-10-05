"""Las guías de uso (inglés y español) documentan todos los comandos de la CLI."""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
GUIA = RAIZ / "docs" / "guide" / "usage.md"
GUIA_ES = RAIZ / "docs" / "es" / "guia" / "uso.md"


def _comandos(parser, ruta=()):
    for accion in parser._actions:
        if isinstance(accion, argparse._SubParsersAction):
            for nombre, sub in accion.choices.items():
                if any(isinstance(a, argparse._SubParsersAction) for a in sub._actions):
                    yield from _comandos(sub, ruta + (nombre,))
                else:
                    yield ruta + (nombre,)


@pytest.mark.parametrize("guia", [GUIA, GUIA_ES], ids=["en", "es"])
def test_cada_comando_aparece_en_la_guia_de_uso(guia):
    from ipsis.cli import construir_parser

    texto = guia.read_text(encoding="utf-8")
    faltan = [" ".join(c) for c in _comandos(construir_parser()) if f"ipsis {' '.join(c)}" not in texto]
    assert not faltan, f"documenta en {guia.relative_to(RAIZ)}: {faltan}"


def test_los_enlaces_relativos_de_la_documentacion_existen():
    import re

    raiz = RAIZ
    archivos = [raiz / "README.md", raiz / "README.es.md", raiz / "CHANGELOG.md", raiz / "CONTRIBUTING.md", raiz / "SECURITY.md",
                raiz / "CODE_OF_CONDUCT.md", raiz / ".github" / "PULL_REQUEST_TEMPLATE.md",
                raiz / "tests" / "datos" / "banco_universal" / "README.md", *sorted((raiz / "docs").rglob("*.md")),
                *sorted((raiz / "examples").rglob("*.md")), raiz / "herramientas" / "avatar" / "LEEME.md"]
    rotos = []
    for archivo in archivos:
        if not archivo.is_file() or "node_modules" in archivo.parts:
            continue
        texto = re.sub(r"```.*?```", "", archivo.read_text(encoding="utf-8"), flags=re.S)
        enlaces = re.findall(r"\]\(([^)\s]+)\)", texto) + re.findall(r'(?:src|srcset|href)="([^"]+)"', texto)
        for destino in enlaces:
            if re.match(r"^[a-z]+:|^#|^mailto:", destino):
                continue
            ruta = destino.split("#")[0]
            if ruta and not (archivo.parent / ruta).exists():
                rotos.append(f"{archivo.relative_to(raiz)} → {destino}")
    assert not rotos, rotos
