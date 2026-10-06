"""Grupo personalidad: tono de las respuestas y avatar del widget."""
from __future__ import annotations

import argparse
import functools

from ipsis.aplicacion.avatar import AvatarInvalido
from ipsis.aplicacion.personalidad import (
    PersonalidadInvalida,
    SinProyecto,
    aplicar_avatar,
    aplicar_tono,
    asignar_evento,
    colores_avatar,
    importar_avatar,
    listar_avatares,
    listar_tonos,
    probar_tono,
    resumen_personalidad,
    validar_personalidad,
)
from ipsis.cli.base import Comando, Grupo
from ipsis.recursos.mensajes import t


def _errores_accionables(funcion):
    """Errores esperables → mensaje y salida 1, sin traceback."""

    @functools.wraps(funcion)
    def envoltura(self, args):
        try:
            return funcion(self, args)
        except SinProyecto as e:
            print(t("cli.error_dot", error=e))
            print(t("cli.action", action="ipsis init"))
        except PersonalidadInvalida as e:
            print(t("personality.invalid"))
            for error in e.errores:
                print(t("cli.item", item=error))
        except AvatarInvalido as e:
            print(t("personality.avatar_invalid"))
            for error in e.errores:
                print(t("cli.item", item=error))
        except FileNotFoundError as e:
            print(t("cli.error", error=e))
        return 1

    return envoltura


def _color(valor: str | None) -> str:
    return valor or t("personality.avatar_color")


class ComandoPersonalidadMostrar(Comando):
    nombre = "show"
    ayuda = "personality.show_help"

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        r = resumen_personalidad()
        a, c = r.avatar, r.config.avatar
        print(t("personality.tone", tone=r.tono, variety=r.variedad, language=r.idioma_tonos))
        print(t("personality.own_situations", situations=", ".join(r.sobrescritas) or t("cli.none")))
        print(t("personality.avatar_message", name=a.nombre, state=a.estado, message=a.mensaje) if a.mensaje
              else t("personality.avatar", name=a.nombre, state=a.estado))
        print(t("personality.placement", placement=c.ubicacion, size=c.tamano,
                launcher=t("cli.yes" if c.en_lanzador else "cli.no")))
        print(t("personality.gaze", mode=t("personality.gaze_follow" if c.mirada.activa else "personality.gaze_fixed"),
                eyes=c.mirada.amplitud_ojos, head=c.mirada.amplitud_cabeza, dead=c.mirada.zona_muerta,
                idle=c.inactividad_min))
        print(t("personality.colors", body=_color(c.colores.cuerpo), eyes=_color(c.colores.ojos)))
        if a.respaldos:
            print(t("personality.fallbacks", n=len(a.respaldos)))
        return 0


class ComandoPersonalidadValidar(Comando):
    nombre = "validate"
    ayuda = "personality.validate_help"

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        errores, avisos = validar_personalidad()
        for error in errores:
            print(t("personality.error_line", error=error))
        for aviso in avisos:
            print(t("personality.warning_line", warning=aviso))
        if errores:
            print(t("personality.not_valid"))
            return 1
        print(t("personality.valid_warnings" if avisos else "personality.valid"))
        return 0


class ComandoTonoListar(Comando):
    nombre = "list"
    ayuda = "tone.list_help"

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        for tono in listar_tonos():
            print(t("tone.row", mark="*" if tono.activo else " ", tone=tono.tono, description=tono.descripcion))
            print(t("tone.example", example=tono.ejemplo))
        return 0


class ComandoTonoAplicar(Comando):
    nombre = "apply"
    ayuda = "tone.apply_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("tono", metavar="tone", help=t("tone.arg_tone"))

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        aplicar_tono(args.tono)
        print(t("tone.applied", tone=args.tono))
        return 0


class ComandoTonoProbar(Comando):
    nombre = "try"
    ayuda = "tone.try_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--tone", dest="tono", default=None, help=t("tone.opt_tone"))
        parser.add_argument("--situation", dest="situacion", default=None, help=t("tone.opt_situation"))

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        for situacion, variantes in probar_tono(args.tono, args.situacion).items():
            print(t("tone.situation", situation=situacion))
            for i, texto in enumerate(variantes, start=1):
                print(t("tone.variant", i=i, text=texto))
        return 0


class ComandoAvatarListar(Comando):
    nombre = "list"
    ayuda = "avatar.list_help"

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        avatares, activo = listar_avatares()
        if not avatares:
            print(t("avatar.none"))
        for a in avatares:
            if isinstance(a, tuple):
                nombre, origen, error = a
                print(t("avatar.invalid_row", mark="*" if nombre == activo else " ", name=nombre, origin=origen,
                        error=error))
            else:
                print(t("avatar.row", mark="*" if a.nombre == activo else " ", name=a.nombre, origin=a.origen,
                        animations=len(a.animaciones), expressions=len(a.expresiones)))
        if activo not in {a.nombre if not isinstance(a, tuple) else a[0] for a in avatares}:
            print(t("avatar.unavailable", name=activo))
        return 0


class ComandoAvatarImportar(Comando):
    nombre = "import"
    ayuda = "avatar.import_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("archivo", metavar="file", help=t("avatar.arg_file"))
        parser.add_argument("--name", dest="nombre", default=None, help=t("avatar.opt_name"))

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        avatar = importar_avatar(args.archivo, args.nombre)
        print(t("avatar.imported", name=avatar.nombre, animations=len(avatar.animaciones),
                expressions=len(avatar.expresiones)))
        return 0


class ComandoAvatarAplicar(Comando):
    nombre = "apply"
    ayuda = "avatar.apply_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("nombre", metavar="name", help=t("avatar.arg_name"))

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        aplicar_avatar(args.nombre)
        print(t("avatar.applied", name=args.nombre))
        return 0


class ComandoAvatarEventos(Comando):
    nombre = "events"
    ayuda = "avatar.events_help"

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        a = resumen_personalidad().avatar
        if a.estado != "ok":
            print(t("avatar.state", name=a.nombre, state=a.estado, message=a.mensaje))
            return 0
        for evento, clave in a.claves.items():
            nota = t("avatar.fallback_note", requested=a.respaldos[evento]) if evento in a.respaldos else ""
            print(t("avatar.event", event=evento, key=clave, note=nota))
        return 0


class ComandoAvatarAsignar(Comando):
    nombre = "assign"
    ayuda = "avatar.assign_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("evento", metavar="event", help=t("avatar.arg_event"))
        parser.add_argument("clave", metavar="key", help=t("avatar.arg_key"))

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        asignar_evento(args.evento, args.clave)
        print(t("avatar.assigned", event=args.evento, key=args.clave))
        return 0


class ComandoAvatarColores(Comando):
    nombre = "colors"
    ayuda = "avatar.colors_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--body", dest="cuerpo", default=None, help=t("avatar.opt_body"))
        parser.add_argument("--eyes", dest="ojos", default=None, help=t("avatar.opt_eyes"))

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        colores = colores_avatar(args.cuerpo, args.ojos).avatar.colores
        print(t("avatar.colors", body=_color(colores.cuerpo), eyes=_color(colores.ojos)))
        return 0


def grupo_personalidad() -> Grupo:
    tono = Grupo("tone", "tone.help", [ComandoTonoListar(), ComandoTonoAplicar(), ComandoTonoProbar()])
    avatar = Grupo("avatar", "avatar.help",
                   [ComandoAvatarListar(), ComandoAvatarImportar(), ComandoAvatarAplicar(), ComandoAvatarEventos(),
                    ComandoAvatarAsignar(), ComandoAvatarColores()])
    return Grupo("personality", "personality.help",
                 [ComandoPersonalidadMostrar(), ComandoPersonalidadValidar(), tono, avatar])


__all__ = ["grupo_personalidad"]
