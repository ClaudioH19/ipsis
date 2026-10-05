"""Grupo operación: diagnóstico y configuración efectiva."""
from __future__ import annotations

import argparse

from ipsis.aplicacion.diagnostico import Estado, ProyectoNoEncontrado, diagnosticar
from ipsis.aplicacion.proyecto import guardar_snapshot
from ipsis.aplicacion.registro import FechaInvalida, SinRegistro, auditar_registro, interpretar_fecha
from ipsis.cli.base import Comando
from ipsis.recursos.mensajes import t


# Estado del chequeo → clave de su marca (ASCII: la salida redirigida en Windows puede ser cp1252).
MARCAS = {Estado.OK: "doctor.mark_ok", Estado.AVISO: "doctor.mark_warning", Estado.ERROR: "doctor.mark_error",
          Estado.NO_EVALUADO: "doctor.mark_skipped"}


def _cuenta(clave: str, n: int) -> str:
    return t(f"{clave}_one") if n == 1 else t(f"{clave}_many", n=n)


class ComandoDoctor(Comando):
    nombre = "doctor"
    ayuda = "doctor.help"

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            reporte = diagnosticar()
        except ProyectoNoEncontrado:
            print(t("doctor.no_project"))
            print(t("cli.action", action="ipsis init"))
            return 1
        print(t("doctor.title"))
        for c in reporte.chequeos:
            print(f"{t(MARCAS[c.estado]):9} {c.nombre}: {c.mensaje}")
            for detalle in c.detalles:
                print(t("doctor.detail", detail=detalle))
            for accion in c.acciones:
                print(t("doctor.check_action", action=accion))
        print()
        print(t("doctor.summary", errors=_cuenta("doctor.errors", len(reporte.errores)),
                warnings=_cuenta("doctor.warnings", len(reporte.avisos)),
                verdict=t("doctor.ready" if reporte.listo else "doctor.not_ready")))
        if reporte.acciones:
            print(t("doctor.actions"))
            for accion in reporte.acciones:
                print(t("doctor.action_item", action=accion))
        return 0 if reporte.listo else 1


def _conteo(contador) -> str:
    return ", ".join(f"{k} {v}" for k, v in contador.most_common()) or t("cli.none")


class ComandoAuditar(Comando):
    nombre = "audit"
    ayuda = "audit.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--from", dest="desde", default=None, help=t("audit.opt_from"))
        parser.add_argument("--to", dest="hasta", default=None, help=t("audit.opt_to"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            desde = interpretar_fecha(args.desde) if args.desde else None
            hasta = interpretar_fecha(args.hasta, fin_del_dia=True) if args.hasta else None
            r = auditar_registro(desde=desde, hasta=hasta)
        except FechaInvalida as e:
            print(t("audit.failed", error=e))
            return 2
        except SinRegistro as e:
            print(t("audit.no_log", path=e))
            print(t("cli.action", action=t("audit.enable")))
            return 1
        rango = ""
        if r.desde or r.hasta:
            rango = t("audit.range", start=r.desde.isoformat() if r.desde else "…",
                      end=r.hasta.isoformat() if r.hasta else "…", outside=r.fuera_de_rango)
        print(t("audit.log", path=r.ruta, n=r.consultas, range=rango))
        if r.sin_fecha:
            print(t("audit.undated", lines=", ".join(map(str, r.sin_fecha))))
        print(t("audit.statuses", values=_conteo(r.por_estado)))
        print(t("audit.rules", values=_conteo(r.por_regla)))
        print(t("audit.tones", values=_conteo(r.por_tono)))
        print(t("audit.checked", n=r.evidencias, problems=len(r.problemas)))
        for p in r.problemas:
            print(t("audit.problem", line=p.linea, doc_id=p.doc_id, start=p.offset_inicio, end=p.offset_fin,
                    reason=p.motivo, detail=p.detalle))
        if r.lineas_invalidas:
            print(t("audit.unreadable", lines=", ".join(map(str, r.lineas_invalidas))))
        if r.ok:
            print(t("audit.ok"))
            return 0
        print(t("audit.mismatch"))
        return 1


class ComandoSnapshotConfig(Comando):
    nombre = "snapshot-config"
    ayuda = "snapshot.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--output", dest="salida", default=".ipsis/effective-config.yaml",
                            help=t("snapshot.opt_output"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            ruta = guardar_snapshot(args.salida)
        except Exception as e:  # noqa: BLE001 -- CLI debe dar un error accionable
            print(t("snapshot.failed", error=e))
            return 1
        print(t("snapshot.done", path=ruta))
        return 0


__all__ = ["ComandoAuditar", "ComandoDoctor", "ComandoSnapshotConfig"]
