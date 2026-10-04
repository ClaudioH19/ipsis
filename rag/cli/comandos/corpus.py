"""Grupo corpus: cargar documentos e indexarlos."""
from __future__ import annotations

import argparse
from pathlib import Path

from rag.aplicacion.corpus import ErrorConfiguracion, archivos_de_ruta, cargar_documentos, indexar_proyecto
from rag.cli.base import Comando


class ComandoCargar(Comando):
    nombre = "cargar"
    ayuda = "Copia un archivo o carpeta al corpus y lo cataloga."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("ruta", help="Archivo o carpeta con .docx/.pdf/.md/.txt")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            archivos = archivos_de_ruta(Path(args.ruta))
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return 1
        if not archivos:
            print(f"No se encontró ningún archivo soportado en {args.ruta!r} "
                  f"(soportados: .docx, .pdf, .md, .markdown, .txt).")
            return 1

        try:
            resultado = cargar_documentos(archivos)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}")
            return 1

        for d in resultado:
            if d.ya_existia:
                print(f"  = {d.archivo}: ya estaba cargado como doc_id={d.doc_id!r} (mismo contenido, se omite)")
                continue
            print(f"  + {d.archivo}: doc_id={d.doc_id!r}, título={d.doc_titulo!r}")
            for a in d.advertencias:
                print(f"      [!] {a}")
            if d.homonimo_de:
                print(f"      [!] ya había un documento con ese nombre ({d.homonimo_de!r}) y otro contenido: este se "
                      "agregó aparte y ambos se indexan. Si lo reemplaza, marca 'vigente: false' en la entrada "
                      f"de {d.homonimo_de!r} en documentos/catalogo.yaml y ejecuta 'rag indexar'.")
        n_nuevos = sum(1 for d in resultado if not d.ya_existia)
        print(f"{n_nuevos} documento(s) nuevo(s) agregado(s) al catálogo (documentos/catalogo.yaml).")
        print("Siguiente paso: 'rag indexar'.")
        return 0


class ComandoIndexar(Comando):
    nombre = "indexar"
    ayuda = "Parsea, fragmenta, vectoriza y persiste el índice."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--corpus", default="documentos",
                            help="Carpeta con los documentos a indexar (por defecto: 'documentos').")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            resumen = indexar_proyecto(args.corpus)
        except ErrorConfiguracion as e:
            print(f"Error de configuración: {e}")
            print("Corré 'rag doctor' para un diagnóstico completo.")
            return 1
        except Exception as e:  # noqa: BLE001 -- se reporta con contexto, no se oculta
            print(f"Error indexando: {e}")
            return 1

        print(f"Documentos parseados: {resumen.n_documentos}")
        for d in resumen.documentos:
            print(f"  - {d.doc_id}: {d.n_bloques} bloques, {d.n_caracteres} caracteres")
        print(f"Chunks generados: {resumen.n_chunks}")
        if resumen.errores_validacion:
            print(f"Errores de validación de ingesta: {len(resumen.errores_validacion)}")
            for e in resumen.errores_validacion[:20]:
                print(f"  ! {e}")
        for a in resumen.advertencias:
            print(f"  [!] {a}")
        print(f"Indexado en la colección {resumen.nombre_coleccion!r}: "
              f"BM25 ({resumen.n_vocab_bm25} términos), "
              f"inventario de entidades ({resumen.n_entidades_inventario} valores).")
        print(f"Tiempo total: {resumen.tiempo_seg:.1f}s")
        print("Siguiente paso: 'rag servir' (o 'rag preguntar \"...\"' si ya está sirviendo).")
        return 0


__all__ = ["ComandoCargar", "ComandoIndexar"]
