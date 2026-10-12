"""Grupo web: temas, estilo y exportación del widget embebible, y despliegue."""
from __future__ import annotations

import argparse

import yaml

from ipsis.aplicacion.widget import (
    SECCIONES_EDITABLES,
    aplicar_preset,
    cambiar_estilo,
    estilo_plano,
    exportar_widget,
    generar_vista_previa,
    listar_presets,
    snippet_widget,
)
from ipsis.cli.base import Comando, Grupo
from ipsis.recursos.mensajes import t


class ComandoTemaListar(Comando):
    nombre = "list"
    ayuda = "widget.theme_list_help"

    def ejecutar(self, args: argparse.Namespace) -> int:
        for nombre, descripcion in listar_presets().items():
            print(t("widget.preset_row", name=nombre, description=descripcion))
        return 0


class ComandoTemaAplicar(Comando):
    nombre = "apply"
    ayuda = "widget.theme_apply_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("preset", help=t("widget.arg_preset") + " " +
            t("widget.available_presets", names=", ".join(listar_presets())))
        parser.add_argument("--path", dest="ruta", default="config/styles.yaml", help=t("widget.opt_styles"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            aplicar_preset(args.preset, args.ruta)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(t("widget.preset_failed", error=exc))
            return 1
        print(t("widget.preset_applied", preset=args.preset, path=args.ruta))
        print(t("widget.preset_view"))
        return 0


class ComandoTemaVistaPrevia(Comando):
    nombre = "preview"
    ayuda = "widget.preview_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--path", dest="ruta", default="config/styles.yaml", help=t("widget.opt_preview_styles"))
        parser.add_argument("--output", dest="salida", default=".ipsis/widget-preview.html", help=t("widget.opt_html"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            salida = generar_vista_previa(args.salida, args.ruta)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(t("widget.preview_failed", error=exc))
            return 1
        print(t("widget.preview_written", path=salida.resolve()))
        return 0


class ComandoWidgetExportar(Comando):
    nombre = "export"
    ayuda = "widget.export_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("carpeta", metavar="folder", help=t("widget.arg_folder"))
        parser.add_argument("--api", default="http://127.0.0.1:8000", help=t("widget.opt_api"))
        parser.add_argument("--position", dest="posicion", default="bottom-right",
                            choices=["bottom-right", "bottom-left", "top-right", "top-left", "embedded"],
                            help=t("widget.opt_position"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            salida = exportar_widget(args.carpeta, api=args.api, posicion=args.posicion)
        except (OSError, ValueError) as exc:
            print(t("widget.export_failed", error=exc))
            return 1
        print(t("widget.exported", path=salida))
        print(t("widget.snippet_ready", path=salida / "snippet.html"))
        return 0


class ComandoWidgetSnippet(Comando):
    nombre = "snippet"
    ayuda = "widget.snippet_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--api", default="http://127.0.0.1:8000", help=t("widget.opt_service"))
        parser.add_argument("--component", dest="componente", action="store_true", help=t("widget.opt_component"))
        parser.add_argument("--key", dest="clave", default=None, help=t("widget.opt_key"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            print(snippet_widget(args.api, componente=args.componente, clave_widget=args.clave))
        except ValueError as e:
            print(t("widget.styles_error", error=e))
            return 1
        return 0


class ComandoEstiloMostrar(Comando):
    nombre = "show"
    ayuda = "widget.style_show_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--section", dest="seccion", choices=SECCIONES_EDITABLES, default=None,
                            help=t("widget.opt_section"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            valores = estilo_plano()
        except (OSError, yaml.YAMLError) as exc:
            print(t("widget.styles_unreadable", error=exc))
            return 1
        for clave, valor in valores:
            if args.seccion is None or clave.startswith(args.seccion + "."):
                print(t("widget.style_value", key=clave, value=str(valor).lower() if isinstance(valor, bool) else valor))
        print(t("widget.style_how"))
        return 0


class ComandoEstiloCambiar(Comando):
    nombre = "set"
    ayuda = "widget.style_set_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("asignaciones", nargs="+", metavar=t("widget.metavar_assignment"),
                            help=t("widget.arg_assignments"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            cambiar_estilo(args.asignaciones)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(t("widget.nothing_changed", error=exc))
            return 1
        print(t("widget.style_updated", n=len(args.asignaciones)))
        print(t("widget.style_live"))
        return 0


def grupo_widget() -> Grupo:
    tema = Grupo("theme", "widget.theme_help", [ComandoTemaListar(), ComandoTemaAplicar(), ComandoTemaVistaPrevia()])
    estilo = Grupo("style", "widget.style_help", [ComandoEstiloMostrar(), ComandoEstiloCambiar()])
    return Grupo("widget", "widget.help", [tema, estilo, ComandoWidgetExportar(), ComandoWidgetSnippet()])


class ComandoDesplegarPreparar(Comando):
    nombre = "prepare"
    ayuda = "deploy.prepare_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--target", dest="destino", default="dist", help=t("deploy.opt_target"))
        parser.add_argument("--domain", dest="dominio", default=None, help=t("deploy.opt_domain"))
        parser.add_argument("--wheel", default=None, help=t("deploy.opt_wheel"))
        parser.add_argument("--force", dest="forzar", action="store_true", help=t("deploy.opt_force"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        from ipsis.aplicacion.despliegue import DespliegueInvalido, preparar_despliegue

        try:
            resumen = preparar_despliegue(args.destino, dominio=args.dominio, wheel=args.wheel, forzar=args.forzar)
        except (DespliegueInvalido, OSError) as exc:
            print(t("deploy.failed", error=exc))
            return 1
        print(t("deploy.done", path=resumen.destino, profile=resumen.perfil, domain=resumen.dominio,
                n=len(resumen.archivos)))
        for aviso in resumen.avisos:
            print(t("cli.warning_indented", warning=aviso))
        print(t("deploy.next", path=resumen.destino / "DEPLOY.md"))
        return 0


def grupo_desplegar() -> Grupo:
    return Grupo("deploy", "deploy.help", [ComandoDesplegarPreparar()])


__all__ = ["ComandoDesplegarPreparar", "ComandoTemaAplicar", "ComandoTemaListar", "ComandoTemaVistaPrevia",
           "ComandoWidgetExportar", "ComandoWidgetSnippet", "grupo_desplegar", "grupo_widget"]
