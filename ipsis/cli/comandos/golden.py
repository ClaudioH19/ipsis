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


def _imprimir_errores(e: ErrorGolden) -> int:
    print("No se pudo completar la operación con el golden:")
    for error in e.errores:
        print(f"  - {error}")
    return 1


def _imprimir_resumen(resumen) -> None:
    for tipo in ("respondible", "sin_respuesta", "premisa_falsa", "ambigua", "conversacional"):
        if resumen.por_tipo.get(tipo):
            print(f"  {tipo:15} {resumen.por_tipo[tipo]}")
    print(f"  dev / test      {resumen.por_split.get('dev', 0)} / {resumen.por_split.get('test', 0)}")
    if resumen.avisos:
        print("Avisos:")
        for aviso in resumen.avisos:
            print(f"  - {aviso}")


class ComandoGoldenPlantilla(Comando):
    nombre = "plantilla"
    ayuda = "Genera golden/golden.csv y golden/README.txt para completar."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--n", type=int, default=40, help="Filas a generar (por defecto: 40).")
        parser.add_argument("--force", action="store_true", help="Reemplaza golden/golden.csv si ya existe.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            ruta_csv, ruta_leeme, avisos = generar_plantilla_golden(n=args.n, forzar=args.force)
        except FileExistsError as e:
            print(f"{e} ya existe y puede tener preguntas escritas: no se sobrescribió.")
            print("Usa 'ipsis golden plantilla --force' para regenerarla desde cero.")
            return 1
        except ErrorGolden as e:
            return _imprimir_errores(e)
        print(f"Plantilla escrita en {ruta_csv} (instrucciones en {ruta_leeme}).")
        for aviso in avisos:
            print(f"Aviso: {aviso}")
        print("Complétala y luego ejecuta: ipsis golden importar golden/golden.csv")
        return 0


class ComandoGoldenImportar(Comando):
    nombre = "importar"
    ayuda = "Valida el golden y escribe golden/bank/."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("archivo", help="golden.csv, un .jsonl o un SQuAD 2.0 (.json).")

    def ejecutar(self, args: argparse.Namespace) -> int:
        if not Path(args.archivo).is_file():
            print(f"No existe el archivo {args.archivo}.")
            return 1
        try:
            resumen = importar_golden(args.archivo)
        except ErrorGolden as e:
            return _imprimir_errores(e)
        print(f"Golden importado en {resumen.manifiesto.parent} ({sum(resumen.por_tipo.values())} casos):")
        _imprimir_resumen(resumen)
        return 0


class ComandoGoldenValidar(Comando):
    nombre = "validar"
    ayuda = "Revisa el banco contra el corpus actual (solo lectura)."

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            resumen = validar_golden()
        except ErrorGolden as e:
            return _imprimir_errores(e)
        print(f"Banco válido para el corpus actual ({sum(resumen.por_tipo.values())} casos):")
        _imprimir_resumen(resumen)
        return 0


class ComandoGoldenExportar(Comando):
    nombre = "exportar"
    ayuda = "Exporta el banco a SQuAD 2.0 o CSV."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--formato", choices=["squad2", "csv"], required=True, help="Formato de salida.")
        parser.add_argument("--salida", default=None,
                            help="Archivo de salida (por defecto: golden/exportado.squad2.json o "
                                 "golden/exportado.csv).")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            destino, avisos = exportar_golden(args.formato, args.salida)
        except ErrorGolden as e:
            return _imprimir_errores(e)
        print(f"Banco exportado en formato {args.formato} a {destino}.")
        for aviso in avisos:
            print(f"Aviso: {aviso}")
        return 0


def grupo_golden() -> Grupo:
    return Grupo("golden", "Golden set del cliente: plantilla, importar, validar y exportar.",
                 "Operación sobre el golden.",
                 [ComandoGoldenPlantilla(), ComandoGoldenImportar(), ComandoGoldenValidar(), ComandoGoldenExportar()])


__all__ = ["ComandoGoldenExportar", "ComandoGoldenImportar", "ComandoGoldenPlantilla", "ComandoGoldenValidar",
           "grupo_golden"]
