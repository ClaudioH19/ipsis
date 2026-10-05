"""Grupo modelos: ver, descargar, verificar y exportar los modelos ONNX del perfil."""
from __future__ import annotations

import argparse

from ipsis.aplicacion.modelos import (
    ExportacionFallida,
    ExportacionNoDisponible,
    SinProyecto,
    descargar_modelos,
    exportar_modelo,
    listar_modelos,
    verificar_modelos,
)
from ipsis.aplicacion.proyecto import PerfilInvalido
from ipsis.cli.base import Comando, Grupo
from ipsis.recursos.mensajes import t


def _accion_descargar() -> str:
    return t("cli.action", action=t("models.download_action"))


def _rol(rol: str) -> str:
    return t(f"models.role_{rol}")


def _mb(n: int) -> str:
    return f"{n / 1_000_000:,.0f} MB".replace(",", ".")


def _sin_proyecto(e: SinProyecto) -> int:
    print(t("cli.error_dot", error=e))
    print(t("cli.action", action=t("models.no_project_action")))
    return 1


def _licencia(licencia: str, atribucion: str | None) -> str:
    return t("models.license_attribution", license=licencia, attribution=atribucion) if atribucion else licencia


class ComandoModelosListar(Comando):
    nombre = "list"
    ayuda = "models.list_help"

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            r = listar_modelos()
        except SinProyecto as e:
            return _sin_proyecto(e)
        print(t("models.profile", profile=r.perfil))
        for m in r.modelos:
            print(t("models.model", role=_rol(m.rol), model=m.id_hf))
            print(t("models.license", license=_licencia(m.licencia, m.atribucion)))
            print(t("models.parameters", millions=m.parametros / 1e6))
            print(t("models.onnx", file=m.archivo))
            print(t("models.cached", size=_mb(m.bytes_en_disco)) if m.en_cache else t("models.missing"))
        if any(not m.en_cache for m in r.modelos):
            print()
            print(_accion_descargar())
        return 0


class ComandoModelosDescargar(Comando):
    nombre = "download"
    ayuda = "models.download_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--profile", dest="perfil", default=None, help=t("models.opt_profile"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            r = descargar_modelos(args.perfil,
                                  avisar=lambda rol, id_hf: print(t("models.downloading", role=_rol(rol), model=id_hf)))
        except PerfilInvalido as e:
            print(t("cli.error", error=e))
            return 1
        except SinProyecto as e:
            return _sin_proyecto(e)
        for m in r.modelos:
            clave = "models.downloaded" if m.estado == "descargado" else "models.available"
            print(t(clave, role=_rol(m.rol), model=m.id_hf))
            print(t("models.license_short", license=_licencia(m.licencia, m.atribucion)))
        if r.error:
            print(t("cli.error", error=r.error))
            return 1
        print(t("models.ready", profile=r.perfil, path=r.cache))
        return 0


# Estado de la verificación → clave de su etiqueta en el catálogo.
_ETIQUETAS = {"ok": "models.state_ok", "falta": "models.state_missing", "no_carga": "models.state_not_loading",
              "inferencia_fallida": "models.state_failed"}


class ComandoModelosVerificar(Comando):
    nombre = "verify"
    ayuda = "models.verify_help"

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            r = verificar_modelos()
        except SinProyecto as e:
            return _sin_proyecto(e)
        print(t("models.profile", profile=r.perfil))
        for m in r.modelos:
            print(t("models.verify_row", role=_rol(m.rol), model=m.id_hf, state=t(_ETIQUETAS[m.estado])))
            if m.mensaje:
                print(t("models.verify_message", message=m.mensaje))
        if r.ok:
            print(t("models.verified"))
            return 0
        print(t("models.incomplete"))
        if any(m.estado == "falta" for m in r.modelos):
            print(_accion_descargar())
        if any(m.estado not in ("falta", "ok") for m in r.modelos):
            print(t("cli.action", action=t("models.redownload")))
        return 1


class ComandoModelosExportar(Comando):
    nombre = "export"
    ayuda = "models.export_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("id_hf", metavar="model", help=t("models.arg_model"))
        parser.add_argument("--int8", action="store_true", help=t("models.opt_int8"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            r = exportar_modelo(args.id_hf, int8=args.int8)
        except ExportacionNoDisponible as e:
            print(t("models.export_missing", missing=", ".join(e.faltantes)))
            print(t("cli.action", action=e.instalar))
            return 1
        except FileExistsError as e:
            print(t("cli.error", error=e))
            return 1
        except ExportacionFallida as e:
            print(t("models.export_failed", model=args.id_hf, error=e))
            print(t("models.export_hint"))
            return 1
        print(t("models.exported", path=r.onnx))
        if r.int8:
            print(t("models.exported_int8", path=r.int8))
        print(t("models.not_adopted"))
        return 0


def grupo_modelos() -> Grupo:
    return Grupo("models", "models.help",
                 [ComandoModelosListar(), ComandoModelosDescargar(), ComandoModelosVerificar(),
                  ComandoModelosExportar()])


__all__ = ["ComandoModelosDescargar", "ComandoModelosExportar", "ComandoModelosListar",
           "ComandoModelosVerificar", "grupo_modelos"]
