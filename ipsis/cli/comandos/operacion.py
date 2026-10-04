"""Grupo operación: diagnóstico y configuración efectiva."""
from __future__ import annotations

import argparse

from ipsis.aplicacion.diagnostico import Estado, ProyectoNoEncontrado, diagnosticar
from ipsis.aplicacion.proyecto import guardar_snapshot
from ipsis.aplicacion.registro import FechaInvalida, SinRegistro, auditar_registro, interpretar_fecha
from ipsis.cli.base import Comando


# ASCII: la salida redirigida en Windows puede ser cp1252.
MARCAS = {Estado.OK: "[OK]", Estado.AVISO: "[AVISO]", Estado.ERROR: "[ERROR]", Estado.NO_EVALUADO: "[--]"}


class ComandoDoctor(Comando):
    nombre = "doctor"
    ayuda = "Diagnóstico de solo lectura: configuración, perfil, idioma, modelos, índice, calibración, golden y CORS."

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            reporte = diagnosticar()
        except ProyectoNoEncontrado:
            print("No se encontró un proyecto RAG en esta carpeta.")
            print("  Acción: ipsis init")
            return 1
        print("Diagnóstico del proyecto\n")
        for c in reporte.chequeos:
            print(f"{MARCAS[c.estado]:9} {c.nombre}: {c.mensaje}")
            for detalle in c.detalles:
                print(f"            {detalle}")
            for accion in c.acciones:
                print(f"            Acción: {accion}")
        errores, avisos = len(reporte.errores), len(reporte.avisos)
        print()
        print(f"{errores} error{'es' if errores != 1 else ''}, {avisos} aviso{'s' if avisos != 1 else ''}. "
              + ("El proyecto puede funcionar." if reporte.listo else "El proyecto no está listo."))
        if reporte.acciones:
            print("Acciones:")
            for accion in reporte.acciones:
                print(f"  {accion}")
        return 0 if reporte.listo else 1


class ComandoAuditar(Comando):
    nombre = "auditar"
    ayuda = "Revisa el registro de consultas: estados, reglas y si cada evidencia sigue siendo literal."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--desde", default=None,
                            help="Solo consultas desde esta fecha (AAAA-MM-DD o ISO 8601; UTC si no trae zona).")
        parser.add_argument("--hasta", default=None, help="Solo consultas hasta esta fecha, inclusive.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            desde = interpretar_fecha(args.desde) if args.desde else None
            hasta = interpretar_fecha(args.hasta, fin_del_dia=True) if args.hasta else None
            r = auditar_registro(desde=desde, hasta=hasta)
        except FechaInvalida as e:
            print(f"No se pudo auditar: {e}")
            return 2
        except SinRegistro as e:
            print(f"No hay registro de consultas ({e}). Está apagado por defecto, por privacidad.")
            print("  Acción: ipsis configurar registro.activo=true (y reinicia 'ipsis servir')")
            return 1
        rango = ""
        if r.desde or r.hasta:
            rango = (f", rango {r.desde.isoformat() if r.desde else '…'} a {r.hasta.isoformat() if r.hasta else '…'}"
                     f"; {r.fuera_de_rango} fuera del rango")
        print(f"Registro: {r.ruta} ({r.consultas} consultas{rango})")
        if r.sin_fecha:
            print(f"Líneas sin fecha legible (excluidas del rango): {', '.join(map(str, r.sin_fecha))}")
        print("Estados: " + (", ".join(f"{k} {v}" for k, v in r.por_estado.most_common()) or "—"))
        print("Reglas:  " + (", ".join(f"{k} {v}" for k, v in r.por_regla.most_common()) or "—"))
        print("Tonos:   " + (", ".join(f"{k} {v}" for k, v in r.por_tono.most_common()) or "—"))
        print(f"Evidencias verificadas contra el corpus vigente: {r.evidencias}, con problemas: {len(r.problemas)}")
        for p in r.problemas:
            print(f"  línea {p.linea}: {p.doc_id} offsets {p.offset_inicio}-{p.offset_fin}: {p.motivo}: {p.detalle}")
        if r.lineas_invalidas:
            print(f"Líneas ilegibles: {', '.join(map(str, r.lineas_invalidas))}")
        if r.ok:
            print("Todas las evidencias registradas siguen siendo literales.")
            return 0
        print("Hay evidencias que ya no coinciden con el corpus: el documento cambió desde la consulta o el "
              "registro se editó.")
        return 1


class ComandoSnapshotConfig(Comando):
    nombre = "snapshot-config"
    ayuda = "Escribe la configuración efectiva con defaults resueltos."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--salida", default=".ipsis/configuracion-efectiva.yaml",
                            help="Ruta del snapshot (por defecto: .ipsis/configuracion-efectiva.yaml).")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            ruta = guardar_snapshot(args.salida)
        except Exception as e:  # noqa: BLE001 -- CLI debe dar un error accionable
            print(f"Error generando snapshot de configuración: {e}")
            return 1
        print(f"Snapshot de configuración efectiva escrito en {ruta}")
        return 0


__all__ = ["ComandoAuditar", "ComandoDoctor", "ComandoSnapshotConfig"]
