"""Patrón Command de la CLI.

Cada comando es una clase que registra sus opciones en ``argparse`` y, al
ejecutarse, llama a un caso de uso de ``rag.aplicacion`` y presenta el
resultado. No contiene lógica de negocio: si un comando necesita algo nuevo,
eso se escribe en ``rag/aplicacion/``.
"""
from __future__ import annotations

import argparse
from abc import ABC, abstractmethod


class Comando(ABC):
    """Una acción de la CLI: ``rag <nombre> …``."""

    nombre: str = ""
    ayuda: str = ""

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        """Declara argumentos y opciones; todas con ``help``."""

    @abstractmethod
    def ejecutar(self, args: argparse.Namespace) -> int:
        """Corre el caso de uso y devuelve el código de salida."""


class Grupo:
    """Comando con subcomandos (``rag golden importar``, ``rag widget tema …``)."""

    def __init__(self, nombre: str, ayuda: str, ayuda_subcomandos: str, comandos: list) -> None:
        self.nombre = nombre
        self.ayuda = ayuda
        self.ayuda_subcomandos = ayuda_subcomandos
        self.comandos = comandos


def registrar(subparsers, elemento: Comando | Grupo) -> None:
    """Agrega un comando o un grupo (recursivo) a ``subparsers``."""
    parser = subparsers.add_parser(elemento.nombre, help=elemento.ayuda)
    if isinstance(elemento, Grupo):
        destino = f"{elemento.nombre.replace('-', '_')}_comando"
        hijos = parser.add_subparsers(dest=destino, required=True, help=elemento.ayuda_subcomandos)
        for comando in elemento.comandos:
            registrar(hijos, comando)
        return
    elemento.registrar(parser)
    parser.set_defaults(comando_cli=elemento)


__all__ = ["Comando", "Grupo", "registrar"]
