"""CLI pública: ``ipsis <comando> ...``.

Este módulo solo arma el parser raíz con los comandos de ``ipsis/cli/comandos/``
(patrón Command, ver ``base.py``), interpreta ``argv`` y despacha. La CLI solo
importa ``ipsis.aplicacion``, ``ipsis.nucleo`` y ``ipsis.recursos``; la lógica vive
en ``ipsis/aplicacion/``. Importar este paquete no crea ni abre nada.
"""
from __future__ import annotations

import argparse
import sys

from ipsis.cli.base import Comando, Grupo, registrar
from ipsis.cli.comandos.chat import ComandoAyuda, ComandoChat
from ipsis.cli.comandos.consulta import ComandoPreguntar, ComandoServir
from ipsis.cli.comandos.corpus import ComandoCargar, ComandoIndexar
from ipsis.cli.comandos.evaluacion import ComandoBenchmark, ComandoCalibrar, ComandoComparar, ComandoEvaluar
from ipsis.cli.comandos.golden import grupo_golden
from ipsis.cli.comandos.modelos import grupo_modelos
from ipsis.cli.comandos.operacion import ComandoAuditar, ComandoDoctor, ComandoSnapshotConfig
from ipsis.cli.comandos.personalidad import grupo_personalidad
from ipsis.cli.comandos.proyecto import ComandoConfigurar, ComandoInit, grupo_perfil
from ipsis.cli.comandos.web import grupo_desplegar, grupo_widget


def registro_de_comandos() -> list[Comando | Grupo]:
    """Registro explícito, en el orden en que aparecen en ``ipsis --help``."""
    init, cargar, indexar = ComandoInit(), ComandoCargar(), ComandoIndexar()
    return [
        init, cargar, ComandoConfigurar(), grupo_perfil(), grupo_modelos(), grupo_personalidad(), indexar,
        ComandoServir(init, cargar, indexar), ComandoChat(), ComandoPreguntar(),
        ComandoDoctor(), ComandoAuditar(), ComandoSnapshotConfig(),
        ComandoEvaluar(), ComandoCalibrar(), ComandoComparar(), ComandoBenchmark(main),
        grupo_golden(), grupo_widget(), grupo_desplegar(), ComandoAyuda(),
    ]


def construir_parser() -> argparse.ArgumentParser:
    from ipsis import __version__
    from ipsis.recursos.mensajes import t

    from ipsis.recursos.instalacion import INSTALAR

    parser = argparse.ArgumentParser(prog="ipsis", description=t("cli.description"),
                                     epilog=t("terminal.install", command=INSTALAR) + "\n" + t("terminal.update") + "\n" + t("terminal.no_activation"),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--version", action="version", version=f"ipsis {__version__}")
    subcomandos = parser.add_subparsers(dest="comando", required=True, metavar="<command>",
                                        help=t("cli.subcommand"))
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
    from ipsis.aplicacion.proyecto import migrar_proyecto_activo
    from ipsis.recursos.mensajes import t

    _asegurar_salida_no_crashea()
    if not (sys.argv[1:] if argv is None else argv):
        # «ipsis» solo, como «claude»: en una terminal real abre el modo interactivo
        # (Folio, autocompletado y menú de opciones); en un script imprime el menú.
        from ipsis.cli.terminal import terminal_real

        if terminal_real():
            from ipsis.cli.comandos.chat import ComandoChat

            return ComandoChat().ejecutar(argparse.Namespace(diagnostico=False))
        from ipsis.cli.menu import imprimir_menu

        imprimir_menu()
        return 0
    args = construir_parser().parse_args(argv)
    for cambio in migrar_proyecto_activo():
        print(t("cli.migration", change=cambio))
    try:
        from ipsis.cli.progreso import COMANDOS, actividad

        if args.comando not in COMANDOS:
            return args.comando_cli.ejecutar(args)
        with actividad(COMANDOS[args.comando]) as trabajo:
            codigo = args.comando_cli.ejecutar(args)
            trabajo.codigo = codigo
            return codigo
    except KeyboardInterrupt:
        return 130


__all__ = ["construir_parser", "main", "registro_de_comandos"]
