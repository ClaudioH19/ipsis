"""Grupo corpus: cargar documentos e indexarlos."""
from __future__ import annotations

import argparse
from pathlib import Path

from ipsis.aplicacion.corpus import (
    ErrorConfiguracion,
    archivos_de_ruta,
    avisos_de_ocr,
    cargar_documentos,
    indexar_proyecto,
)
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
            with avisos_de_ocr(print):  # el OCR cuenta qué página lee y con qué confianza
                resultado = cargar_documentos(archivos)
        except (FileNotFoundError, ValueError) as e:
            print(t("cli.error", error=e))
            return 1

        for d in resultado:
            if d.rechazo:
                print(t("load.rejected", file=d.archivo, reason=d.rechazo))
                continue
            if d.ya_existia:
                print(t("load.duplicate", file=d.archivo, doc_id=d.doc_id))
                continue
            print(t("load.added", file=d.archivo, doc_id=d.doc_id, title=d.doc_titulo))
            for a in d.advertencias:
                print(t("load.warning", warning=a))
            if d.homonimo_de:
                print(t("load.homonym", doc_id=d.homonimo_de))
        nuevos = sum(1 for d in resultado if not d.ya_existia and not d.rechazo)
        rechazados = sum(1 for d in resultado if d.rechazo)
        print(t("load.done", n=nuevos))
        if rechazados:
            print(t("load.rejected_summary", n=rechazados))
        if nuevos:
            print(t("load.next"))
        return 1 if rechazados else 0


class ComandoIndexar(Comando):
    nombre = "index"
    ayuda = "index.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--corpus", default="documents", help=t("index.opt_corpus"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            with avisos_de_ocr(print):
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


class ComandoSincronizar(Comando):
    nombre = "sync"
    ayuda = "sync.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--dry-run", action="store_true", help=t("sync.opt_dry_run"))
        parser.add_argument("--no-index", action="store_true", help=t("sync.opt_no_index"))
        parser.add_argument("--force", action="store_true", help=t("sync.opt_force"))
        parser.add_argument("--prune", action="store_true", help=t("sync.opt_prune"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        from ipsis.aplicacion.sincronizar import sincronizar

        carpeta = "documents"
        try:
            with avisos_de_ocr(print):
                r = sincronizar(solo_plan=args.dry_run, indexar=not args.no_index, forzar=args.force,
                                podar=args.prune, carpeta=carpeta)
        except ErrorConfiguracion as e:
            print(t("index.config_error", error=e))
            print(t("index.run_doctor"))
            return 1
        except Exception as e:  # noqa: BLE001 -- se reporta con contexto, no se oculta
            print(t("sync.failed", error=e))
            print(t("sync.lock_hint"))
            return 1
        plan = r.plan
        if plan.hay_cambios or plan.ignorados:
            print(t("sync.plan_header", folder=carpeta))
        for nuevo in plan.nuevos:
            print(t("sync.added", file=nuevo.name))
        for entrada, nuevo in plan.renombrados:
            print(t("sync.renamed", old=entrada["archivo"], new=nuevo.name, doc_id=entrada["doc_id"]))
        for entrada, _ in plan.modificados:
            print(t("sync.modified", file=entrada["archivo"]))
        for entrada in plan.retirados:
            print(t("sync.removed", file=entrada["archivo"], doc_id=entrada["doc_id"]))
        for entrada, nuevo in plan.reactivados:
            print(t("sync.reactivated", file=nuevo.name, doc_id=entrada["doc_id"]))
        for ignorado in plan.ignorados:
            print(t("sync.ignored", file=ignorado.as_posix(), folder=carpeta))
        print(t("sync.unchanged", n=plan.sin_cambios))
        for d in r.agregados:
            if d.rechazo:
                print(t("load.rejected", file=d.archivo, reason=d.rechazo))
            for a in d.advertencias:
                print(t("load.warning", warning=a))
        if args.dry_run:
            print(t("sync.dry_run"))
            return 0
        if r.version_nueva is not None:
            print(t("sync.version_bumped", old=r.version_anterior, new=r.version_nueva))
        if r.indexado:
            resumen = r.resumen_indice
            print(t("sync.indexed", docs=resumen.n_documentos, chunks=resumen.n_chunks, collection=resumen.nombre_coleccion))
            for a in resumen.advertencias:
                print(t("index.warning", warning=a))
        elif not plan.hay_cambios and not args.force:
            print(t("sync.nothing"))
        elif args.no_index:
            print(t("sync.catalog_only"))
        if r.podadas:
            print(t("sync.pruned", names=", ".join(r.podadas)))
        return 1 if any(d.rechazo for d in r.agregados) else 0


class ComandoPreparar(Comando):
    nombre = "prepare"
    ayuda = "prepare.help"

    def registrar(self, parser):
        parser.add_argument("--project", type=Path, default=Path.cwd(), help=t("prepare.project"))
        parser.add_argument("--output", type=Path, required=True, help=t("prepare.output"))
        parser.add_argument("--index", action="store_true", help=t("prepare.index"))

    def ejecutar(self, args):
        from ipsis.aplicacion.preparacion import preparar_proyecto

        try:
            r = preparar_proyecto(args.project, args.output, indexar=args.index)
        except (ValueError, OSError, RuntimeError) as exc:
            print(t("cli.error", error=exc))
            return 1
        print(t("prepare.done", documents=r.documentos, units=r.unidades, children=r.hijos))
        print(t("prepare.preview", path=r.vista_previa))
        print(t("prepare.project_done", path=r.proyecto))
        for aviso in r.advertencias:
            print(t("cli.warning", warning=aviso))
        return 0


__all__ = ["ComandoCargar", "ComandoIndexar", "ComandoPreparar", "ComandoSincronizar"]
