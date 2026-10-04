"""Grupo personalidad: tono de las respuestas y avatar del widget."""
from __future__ import annotations

import argparse
import functools

from rag.aplicacion.avatar import AvatarInvalido
from rag.aplicacion.personalidad import (
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
from rag.cli.base import Comando, Grupo


def _errores_accionables(funcion):
    """Errores esperables → mensaje y salida 1, sin traceback."""

    @functools.wraps(funcion)
    def envoltura(self, args):
        try:
            return funcion(self, args)
        except SinProyecto as e:
            print(f"Error: {e}.\n  Acción: rag init")
        except PersonalidadInvalida as e:
            print("Error: la personalidad no es válida; no se cambió nada:")
            for error in e.errores:
                print(f"  - {error}")
        except AvatarInvalido as e:
            print("Error: el avatar no es válido; no se cambió nada:")
            for error in e.errores:
                print(f"  - {error}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
        return 1

    return envoltura


class ComandoPersonalidadMostrar(Comando):
    nombre = "mostrar"
    ayuda = "Tono y avatar activos, y cómo se resuelve cada evento del avatar."

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        r = resumen_personalidad()
        a, c = r.avatar, r.config.avatar
        print(f"Tono: {r.tono} (variedad {r.variedad}; textos de '{r.idioma_tonos}')")
        print(f"  Situaciones propias del proyecto: {', '.join(r.sobrescritas) or '—'}")
        print(f"Avatar: {a.nombre} -- {a.estado}" + (f" ({a.mensaje})" if a.mensaje else ""))
        print(f"  Ubicación: {c.ubicacion}; tamaño: {c.tamano} px; en el lanzador: {'sí' if c.en_lanzador else 'no'}")
        print(f"  Mirada: {'sigue el puntero' if c.mirada.activa else 'fija'} (ojos {c.mirada.amplitud_ojos}, "
              f"cabeza {c.mirada.amplitud_cabeza}°, zona muerta {c.mirada.zona_muerta} px); "
              f"inactividad: {c.inactividad_min} min")
        print(f"  Colores: cuerpo {c.colores.cuerpo or 'del avatar'}, ojos {c.colores.ojos or 'del avatar'}")
        if a.respaldos:
            print(f"  Eventos con respaldo: {len(a.respaldos)} (detalle: rag personalidad avatar eventos)")
        return 0


class ComandoPersonalidadValidar(Comando):
    nombre = "validar"
    ayuda = "Revisa personalidad.yaml, las plantillas propias y el avatar. Sale con 1 si hay errores."

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        errores, avisos = validar_personalidad()
        for error in errores:
            print(f"[ERROR] {error}")
        for aviso in avisos:
            print(f"[AVISO] {aviso}")
        if errores:
            print("La personalidad no es válida: el motor no arrancará hasta corregirla.")
            return 1
        print("Personalidad válida." + (" Hay avisos (no bloquean)." if avisos else ""))
        return 0


class ComandoTonoListar(Comando):
    nombre = "listar"
    ayuda = "Tonos disponibles para el idioma del proyecto, con un ejemplo de cada uno."

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        for t in listar_tonos():
            print(f"{'*' if t.activo else ' '} {t.tono:9} {t.descripcion}")
            print(f"            «{t.ejemplo}»")
        return 0


class ComandoTonoAplicar(Comando):
    nombre = "aplicar"
    ayuda = "Activa un tono. No pide reindexar ni recalibrar."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("tono", help="cordial, formal, serio, animoso, cercano, empatico o directo.")

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        aplicar_tono(args.tono)
        print(f"Tono activo: {args.tono}. Reinicia 'rag servir' (o espera la recarga en caliente) para verlo.")
        return 0


class ComandoTonoProbar(Comando):
    nombre = "probar"
    ayuda = "Imprime las variantes de un tono, con las variables del proyecto."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--tono", default=None, help="Tono a probar (por defecto, el activo).")
        parser.add_argument("--situacion", default=None, help="Una sola situación (p. ej. sin_respuesta).")

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        for situacion, variantes in probar_tono(args.tono, args.situacion).items():
            print(f"{situacion}:")
            for i, texto in enumerate(variantes, start=1):
                print(f"  {i}. {texto}")
        return 0


class ComandoAvatarListar(Comando):
    nombre = "listar"
    ayuda = "Avatares incluidos e importados."

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        avatares, activo = listar_avatares()
        if not avatares:
            print("No hay avatares todavía. Importa uno con 'rag personalidad avatar importar <archivo.avatar.json>'.")
        for a in avatares:
            if isinstance(a, tuple):
                nombre, origen, error = a
                print(f"{'*' if nombre == activo else ' '} {nombre} ({origen}) -- inválido: {error}")
            else:
                print(f"{'*' if a.nombre == activo else ' '} {a.nombre} ({a.origen}): "
                      f"{len(a.animaciones)} animaciones, {len(a.expresiones)} expresiones")
        if activo not in {a.nombre if not isinstance(a, tuple) else a[0] for a in avatares}:
            print(f"  El avatar activo ({activo}) no está disponible: el widget muestra el ícono.")
        return 0


class ComandoAvatarImportar(Comando):
    nombre = "importar"
    ayuda = "Valida un .avatar.json (exportado del Studio) y lo copia a configuracion/avatares/."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("archivo", help="Definición exportada desde avatars.bible-strong.app.")
        parser.add_argument("--nombre", default=None, help="Nombre en el proyecto (minúsculas y guiones).")

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        avatar = importar_avatar(args.archivo, args.nombre)
        print(f"Avatar importado: {avatar.nombre} ({len(avatar.animaciones)} animaciones, "
              f"{len(avatar.expresiones)} expresiones). Actívalo con 'rag personalidad avatar aplicar {avatar.nombre}'.")
        return 0


class ComandoAvatarAplicar(Comando):
    nombre = "aplicar"
    ayuda = "Usa un avatar en el widget."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("nombre", help="Nombre del avatar (ver 'rag personalidad avatar listar').")

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        aplicar_avatar(args.nombre)
        print(f"Avatar activo: {args.nombre}.")
        return 0


class ComandoAvatarEventos(Comando):
    nombre = "eventos"
    ayuda = "Cada evento del widget y la animación o expresión del avatar que dispara."

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        a = resumen_personalidad().avatar
        if a.estado != "ok":
            print(f"Avatar {a.nombre}: {a.estado} ({a.mensaje}).")
            return 0
        for evento, clave in a.claves.items():
            nota = f"  (pedida: {a.respaldos[evento]!r}, no existe; respaldo)" if evento in a.respaldos else ""
            print(f"  {evento:22} → {clave}{nota}")
        return 0


class ComandoAvatarAsignar(Comando):
    nombre = "asignar"
    ayuda = "Asigna a un evento una animación o expresión del avatar."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("evento", help="Evento (ver 'rag personalidad avatar eventos').")
        parser.add_argument("clave", help="Animación o expresión del avatar.")

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        asignar_evento(args.evento, args.clave)
        print(f"{args.evento} → {args.clave}")
        return 0


class ComandoAvatarColores(Comando):
    nombre = "colores"
    ayuda = "Colores del cuerpo y de los ojos del avatar (no modifica su archivo)."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--cuerpo", default=None, help="Color #rrggbb del cuerpo.")
        parser.add_argument("--ojos", default=None, help="Color #rrggbb de los ojos.")

    @_errores_accionables
    def ejecutar(self, args: argparse.Namespace) -> int:
        colores = colores_avatar(args.cuerpo, args.ojos).avatar.colores
        print(f"Colores del avatar: cuerpo {colores.cuerpo or 'del avatar'}, ojos {colores.ojos or 'del avatar'}.")
        return 0


def grupo_personalidad() -> Grupo:
    tono = Grupo("tono", "Tono de las respuestas.", "Operación sobre el tono.",
                 [ComandoTonoListar(), ComandoTonoAplicar(), ComandoTonoProbar()])
    avatar = Grupo("avatar", "Avatar del widget.", "Operación sobre el avatar.",
                   [ComandoAvatarListar(), ComandoAvatarImportar(), ComandoAvatarAplicar(), ComandoAvatarEventos(),
                    ComandoAvatarAsignar(), ComandoAvatarColores()])
    return Grupo("personalidad", "Tono de las respuestas y avatar del widget (solo presentación).",
                 "Operación sobre la personalidad.",
                 [ComandoPersonalidadMostrar(), ComandoPersonalidadValidar(), tono, avatar])


__all__ = ["grupo_personalidad"]
