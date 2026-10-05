"""Grupo golden: plantilla, importar, validar y exportar el golden del cliente."""
from __future__ import annotations

import argparse
from pathlib import Path

from ipsis.aplicacion.golden import (
    ErrorGolden,
    exportar_golden,
    generar_plantilla_golden,
    importar_golden,
    validar_golden,
)
from ipsis.cli.base import Comando, Grupo
from ipsis.recursos.mensajes import t


def _imprimir_errores(e: ErrorGolden) -> int:
    print(t("golden.failed"))
    for error in e.errores:
        print(t("cli.item", item=error))
    return 1


def _imprimir_resumen(resumen) -> None:
    for tipo in ("respondible", "sin_respuesta", "premisa_falsa", "ambigua", "conversacional"):
        if resumen.por_tipo.get(tipo):
            print(t("golden.type_row", type=tipo, n=resumen.por_tipo[tipo]))
    print(t("golden.split_row", dev=resumen.por_split.get("dev", 0), test=resumen.por_split.get("test", 0)))
    if resumen.avisos:
        print(t("golden.warnings"))
        for aviso in resumen.avisos:
            print(t("cli.item", item=aviso))


class ComandoGoldenPlantilla(Comando):
    nombre = "template"
    ayuda = "golden.template_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--n", type=int, default=40, help=t("golden.opt_n"))
        parser.add_argument("--force", action="store_true", help=t("golden.opt_force"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            ruta_csv, ruta_leeme, avisos = generar_plantilla_golden(n=args.n, forzar=args.force)
        except FileExistsError as e:
            print(t("golden.exists", path=e))
            print(t("golden.regenerate"))
            return 1
        except ErrorGolden as e:
            return _imprimir_errores(e)
        print(t("golden.template_written", csv=ruta_csv, readme=ruta_leeme))
        for aviso in avisos:
            print(t("cli.warning", warning=aviso))
        print(t("golden.template_next"))
        return 0


class ComandoGoldenImportar(Comando):
    nombre = "import"
    ayuda = "golden.import_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("archivo", metavar="file", help=t("golden.arg_file"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        if not Path(args.archivo).is_file():
            print(t("golden.no_file", path=args.archivo))
            return 1
        try:
            resumen = importar_golden(args.archivo)
        except ErrorGolden as e:
            return _imprimir_errores(e)
        print(t("golden.imported", path=resumen.manifiesto.parent, n=sum(resumen.por_tipo.values())))
        _imprimir_resumen(resumen)
        return 0


class ComandoGoldenValidar(Comando):
    nombre = "validate"
    ayuda = "golden.validate_help"

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            resumen = validar_golden()
        except ErrorGolden as e:
            return _imprimir_errores(e)
        print(t("golden.valid", n=sum(resumen.por_tipo.values())))
        _imprimir_resumen(resumen)
        return 0


class ComandoGoldenExportar(Comando):
    nombre = "export"
    ayuda = "golden.export_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--format", dest="formato", choices=["squad2", "csv"], required=True,
                            help=t("golden.opt_format"))
        parser.add_argument("--output", dest="salida", default=None, help=t("golden.opt_output"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            destino, avisos = exportar_golden(args.formato, args.salida)
        except ErrorGolden as e:
            return _imprimir_errores(e)
        print(t("golden.exported", format=args.formato, path=destino))
        for aviso in avisos:
            print(t("cli.warning", warning=aviso))
        return 0


def grupo_golden() -> Grupo:
    return Grupo("golden", "golden.help",
                 [ComandoGoldenPlantilla(), ComandoGoldenImportar(), ComandoGoldenValidar(), ComandoGoldenExportar()])


__all__ = ["ComandoGoldenExportar", "ComandoGoldenImportar", "ComandoGoldenPlantilla", "ComandoGoldenValidar",
           "grupo_golden"]
