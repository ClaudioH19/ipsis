"""Patrón Command de la CLI.

Cada comando es una clase que registra sus opciones en ``argparse`` y, al
ejecutarse, llama a un caso de uso de ``ipsis.aplicacion`` y presenta el
resultado. No contiene lógica de negocio: si un comando necesita algo nuevo,
eso se escribe en ``ipsis/aplicacion/``. Los textos (``ayuda`` y mensajes)
son claves del catálogo de ``ipsis/recursos/mensajes``.
"""
from __future__ import annotations

import argparse
from abc import ABC, abstractmethod

from ipsis.recursos.mensajes import t


class Comando(ABC):
    """Una acción de la CLI: ``ipsis <nombre> …``."""

    nombre: str = ""
    ayuda: str = ""  # clave del catálogo de mensajes

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        """Declara argumentos y opciones; todas con ``help``."""

    @abstractmethod
    def ejecutar(self, args: argparse.Namespace) -> int:
        """Corre el caso de uso y devuelve el código de salida."""


class Grupo:
    """Comando con subcomandos (``ipsis golden import``, ``ipsis widget theme …``)."""

    def __init__(self, nombre: str, ayuda: str, comandos: list) -> None:
        self.nombre = nombre
        self.ayuda = ayuda  # clave del catálogo de mensajes
        self.comandos = comandos


def registrar(subparsers, elemento: Comando | Grupo) -> None:
    """Agrega un comando o un grupo (recursivo) a ``subparsers``."""
    ayuda = t(elemento.ayuda)
    parser = subparsers.add_parser(elemento.nombre, help=ayuda, description=ayuda)
    if isinstance(elemento, Grupo):
        destino = f"{elemento.nombre.replace('-', '_')}_comando"
        hijos = parser.add_subparsers(dest=destino, required=True, metavar="<command>", help=t("cli.subcommand"))
        for comando in elemento.comandos:
            registrar(hijos, comando)
        return
    elemento.registrar(parser)
    parser.set_defaults(comando_cli=elemento)


__all__ = ["Comando", "Grupo", "registrar"]
