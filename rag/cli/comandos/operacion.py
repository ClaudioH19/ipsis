"""Grupo operación: diagnóstico y configuración efectiva."""
from __future__ import annotations

import argparse

from rag.aplicacion.diagnostico import ejecutar_diagnostico
from rag.aplicacion.proyecto import guardar_snapshot
from rag.cli.base import Comando


class ComandoDoctor(Comando):
    nombre = "doctor"
    ayuda = "Diagnóstico: configuración, índice, modelos, Qdrant."

    def ejecutar(self, args: argparse.Namespace) -> int:
        hay_fallas = False
        for r in ejecutar_diagnostico():
            marca = "OK  " if r.ok else "FALLA"
            print(f"[{marca}] {r.nombre}: {r.mensaje}")
            if not r.ok:
                hay_fallas = True
                if r.comando_sugerido:
                    print(f"        -> corré: {r.comando_sugerido}")
        print()
        print("Todo listo." if not hay_fallas else "Hay puntos por resolver (ver '-> corré:' arriba).")
        return 1 if hay_fallas else 0


class ComandoSnapshotConfig(Comando):
    nombre = "snapshot-config"
    ayuda = "Escribe la configuración efectiva con defaults resueltos."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--salida", default=".rag/configuracion-efectiva.yaml",
                            help="Ruta del snapshot (por defecto: .rag/configuracion-efectiva.yaml).")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            ruta = guardar_snapshot(args.salida)
        except Exception as e:  # noqa: BLE001 -- CLI debe dar un error accionable
            print(f"Error generando snapshot de configuración: {e}")
            return 1
        print(f"Snapshot de configuración efectiva escrito en {ruta}")
        return 0


__all__ = ["ComandoDoctor", "ComandoSnapshotConfig"]
