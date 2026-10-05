"""Grupo corpus: cargar documentos e indexarlos."""
from __future__ import annotations

import argparse
from pathlib import Path

from ipsis.aplicacion.corpus import ErrorConfiguracion, archivos_de_ruta, cargar_documentos, indexar_proyecto
from ipsis.cli.base import Comando
from ipsis.recursos.mensajes import t


class ComandoCargar(Comando):
    nombre = "load"
    ayuda = "load.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("ruta", metavar="path", help=t("load.arg_path"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            archivos = archivos_de_ruta(Path(args.ruta))
        except FileNotFoundError as e:
            print(t("cli.error", error=e))
            return 1
        if not archivos:
            print(t("load.nothing", path=args.ruta))
            return 1

        try:
            resultado = cargar_documentos(archivos)
        except (FileNotFoundError, ValueError) as e:
            print(t("cli.error", error=e))
            return 1

        for d in resultado:
            if d.ya_existia:
                print(t("load.duplicate", file=d.archivo, doc_id=d.doc_id))
                continue
            print(t("load.added", file=d.archivo, doc_id=d.doc_id, title=d.doc_titulo))
            for a in d.advertencias:
                print(t("load.warning", warning=a))
            if d.homonimo_de:
                print(t("load.homonym", doc_id=d.homonimo_de))
        print(t("load.done", n=sum(1 for d in resultado if not d.ya_existia)))
        print(t("load.next"))
        return 0


class ComandoIndexar(Comando):
    nombre = "index"
    ayuda = "index.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--corpus", default="documents", help=t("index.opt_corpus"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            resumen = indexar_proyecto(args.corpus)
        except ErrorConfiguracion as e:
            print(t("index.config_error", error=e))
            print(t("index.run_doctor"))
            return 1
        except Exception as e:  # noqa: BLE001 -- se reporta con contexto, no se oculta
            print(t("index.failed", error=e))
            return 1

        print(t("index.parsed", n=resumen.n_documentos))
        for d in resumen.documentos:
            print(t("index.document", doc_id=d.doc_id, blocks=d.n_bloques, chars=d.n_caracteres))
        print(t("index.chunks", n=resumen.n_chunks))
        if resumen.errores_validacion:
            print(t("index.validation_errors", n=len(resumen.errores_validacion)))
            for e in resumen.errores_validacion[:20]:
                print(t("index.validation_error", error=e))
        for a in resumen.advertencias:
            print(t("index.warning", warning=a))
        print(t("index.indexed", collection=resumen.nombre_coleccion, terms=resumen.n_vocab_bm25,
                entities=resumen.n_entidades_inventario))
        print(t("index.time", seconds=resumen.tiempo_seg))
        print(t("index.next"))
        return 0


__all__ = ["ComandoCargar", "ComandoIndexar"]
