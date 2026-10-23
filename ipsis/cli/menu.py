"""Menú de la terminal: ``ipsis`` sin argumentos (o ``ipsis help``).

Agrupa los comandos por tarea, con la descripción de cada uno (la misma de
``--help``) y ejemplos para empezar. Los grupos nombran comandos del registro: un
comando nuevo que no esté en ningún grupo aparece igual, al final (y una prueba
lo exige en un grupo).
"""
from __future__ import annotations

import os
import sys

from ipsis.recursos.mensajes import t

# Clave del título del grupo → comandos, en el orden de un proyecto nuevo.
GRUPOS: list[tuple[str, list[str]]] = [
    ("menu.group_start", ["init", "profile", "models", "doctor", "help"]),
    ("menu.group_documents", ["load", "sync", "prepare", "index"]),
    ("menu.group_ask", ["chat", "ask", "serve"]),
    ("menu.group_customize", ["configure", "personality", "widget"]),
    ("menu.group_quality", ["golden", "evaluate", "compare", "benchmark", "audit"]),
    ("menu.group_operate", ["deploy", "snapshot-config"]),
]

# Ejemplos: (clave de la explicación, comando).
EJEMPLOS: list[tuple[str, str]] = [
    ("menu.example_new", "ipsis init --profile medium --language es"),
    ("menu.example_load", "ipsis load ./docs"),
    ("menu.example_inventory", "ipsis load ./inventario.xlsx"),
    ("menu.example_index", "ipsis index"),
    ("menu.example_chat", "ipsis chat"),
    ("menu.example_demo", "ipsis serve --demo --open"),
    ("menu.example_serve", "ipsis serve --mode development --open"),
]


def _color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"


def _estilo(texto: str, codigo: str) -> str:
    return f"\033[{codigo}m{texto}\033[0m" if _color() else texto


def descripciones() -> dict[str, str]:
    """Nombre de cada comando registrado → su descripción traducida."""
    from ipsis.cli import registro_de_comandos

    return {e.nombre: t(e.ayuda) for e in registro_de_comandos()}


def texto_menu() -> str:
    from ipsis import __version__

    desc = descripciones()
    ancho = max(len(n) for n in desc) + 2
    lineas = [f" {_estilo('ipsis', '1')} {__version__} · {t('cli.description')}", ""]
    vistos: set[str] = set()
    for clave, nombres in GRUPOS:
        presentes = [n for n in nombres if n in desc]
        if not presentes:
            continue
        lineas.append(" " + _estilo(t(clave), "1"))
        for n in presentes:
            lineas.append(f"   {_estilo(n.ljust(ancho), '36')}{desc[n]}")
            vistos.add(n)
        lineas.append("")
    resto = [n for n in desc if n not in vistos]
    if resto:
        lineas.append(" " + _estilo(t("menu.group_other"), "1"))
        lineas += [f"   {_estilo(n.ljust(ancho), '36')}{desc[n]}" for n in resto]
        lineas.append("")
    lineas.append(" " + _estilo(t("menu.examples"), "1"))
    for clave, comando in EJEMPLOS:
        lineas.append(f"   {_estilo('$', '2')} {comando}")
        lineas.append(f"     {_estilo(t(clave), '2')}")
    lineas += ["", " " + t("menu.footer"), " " + t("terminal.partial_help")]
    from ipsis.recursos.instalacion import INSTALAR

    lineas += ["", " " + t("terminal.install", command=INSTALAR), " " + t("terminal.update"), " " + t("terminal.no_activation")]
    return "\n".join(lineas)


def imprimir_menu() -> None:
    print(texto_menu())


__all__ = ["EJEMPLOS", "GRUPOS", "descripciones", "imprimir_menu", "texto_menu"]
