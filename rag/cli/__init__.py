"""CLI pública: ``rag <comando> ...``.

Este módulo solo arma el parser raíz con los comandos de ``rag/cli/comandos/``
(patrón Command, ver ``base.py``), interpreta ``argv`` y despacha. La CLI solo
importa ``rag.aplicacion``, ``rag.nucleo`` y ``rag.recursos``; la lógica vive
en ``rag/aplicacion/``. Importar este paquete no crea ni abre nada.
"""
from __future__ import annotations

import argparse
import sys

from rag.cli.base import Comando, Grupo, registrar
from rag.cli.comandos.consulta import ComandoPreguntar, ComandoServir
from rag.cli.comandos.corpus import ComandoCargar, ComandoIndexar
from rag.cli.comandos.evaluacion import ComandoBenchmark, ComandoCalibrar, ComandoComparar, ComandoEvaluar
from rag.cli.comandos.golden import grupo_golden
from rag.cli.comandos.modelos import grupo_modelos
from rag.cli.comandos.operacion import ComandoAuditar, ComandoDoctor, ComandoSnapshotConfig
from rag.cli.comandos.personalidad import grupo_personalidad
from rag.cli.comandos.proyecto import ComandoConfigurar, ComandoInit, grupo_perfil
from rag.cli.comandos.web import grupo_desplegar, grupo_widget


def registro_de_comandos() -> list[Comando | Grupo]:
    """Registro explícito, en el orden en que aparecen en ``rag --help``."""
    init, cargar, indexar = ComandoInit(), ComandoCargar(), ComandoIndexar()
    return [
        init, cargar, ComandoConfigurar(), grupo_perfil(), grupo_modelos(), grupo_personalidad(), indexar,
        ComandoServir(init, cargar, indexar), ComandoPreguntar(),
        ComandoDoctor(), ComandoAuditar(), ComandoSnapshotConfig(),
        ComandoEvaluar(), ComandoCalibrar(), ComandoComparar(), ComandoBenchmark(main),
        grupo_golden(), grupo_widget(), grupo_desplegar(),
    ]


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag", description="Chatbot RAG extractivo sobre tus documentos.")
    from rag import __version__

    parser.add_argument("--version", action="version", version=f"rag-extractivo {__version__}")
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    for elemento in registro_de_comandos():
        registrar(subcomandos, elemento)
    return parser


def _asegurar_salida_no_crashea() -> None:
    """La consola de Windows suele usar cp1252 (o cp437), que no puede
    codificar caracteres fuera de esa página: un solo símbolo decorativo en un
    ``print()`` mataba el comando con un ``UnicodeEncodeError`` justo en la
    ruta que más importa mostrar. Se reemplaza por el carácter de repuesto
    (``errors="replace"``): un defecto cosmético, nunca un traceback. La salida
    de la CLI ya usa marcadores ASCII como ``[!]``; esto es solo un respaldo."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass  # streams sin `reconfigure` (p.ej. redirigidos a algo atípico): se deja tal cual


def main(argv: list[str] | None = None) -> int:
    from rag.aplicacion.proyecto import migrar_proyecto_activo

    _asegurar_salida_no_crashea()
    args = construir_parser().parse_args(argv)
    for cambio in migrar_proyecto_activo():
        print(f"[migración] {cambio}")
    try:
        return args.comando_cli.ejecutar(args)
    except KeyboardInterrupt:
        return 130


__all__ = ["construir_parser", "main", "registro_de_comandos"]
