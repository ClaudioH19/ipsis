"""Grupo proyecto: crear y configurar el proyecto del cliente."""
from __future__ import annotations

import argparse

from ipsis.aplicacion.proyecto import (
    PerfilInvalido,
    ProyectoExistente,
    configurar,
    cambiar_perfil,
    idioma_con_respaldo,
    inicializar_proyecto,
    resumen_perfil,
)
from ipsis.cli.base import Comando, Grupo
from ipsis.recursos.mensajes import t


class ComandoInit(Comando):
    nombre = "init"
    ayuda = "init.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--assistant-name", dest="nombre_asistente", default=None, help=t("init.opt_name"))
        parser.add_argument("--domain-description", dest="descripcion_dominio", default=None,
                            help=t("init.opt_description"))
        parser.add_argument("--language", dest="idioma", default=None, help=t("init.opt_language"))
        parser.add_argument("--profile", dest="perfil", choices=["light", "medium"], default=None,
                            help=t("init.opt_profile"))
        parser.add_argument("--force", action="store_true", help=t("init.opt_force"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            inicio = inicializar_proyecto(args.nombre_asistente, args.descripcion_dominio, args.idioma,
                                          args.perfil, forzar=args.force)
        except ProyectoExistente as e:
            print(t("init.exists", path=e))
            return 1
        except ValueError as e:
            print(t("cli.error", error=e))
            return 1

        nuevo = inicio.nuevo
        if inicio.creo_estilos:
            print(t("init.styles_created"))
        print(t("init.done", path=inicio.ruta_asistente))
        print(t("init.name", value=nuevo["nombre_asistente"]))
        print(t("init.description", value=nuevo["descripcion_dominio"]))
        print(t("init.language_profile", language=nuevo["idioma"], profile=nuevo["perfil"]))
        if idioma_con_respaldo(nuevo["idioma"]):
            print(t("init.fallback_note", language=nuevo["idioma"]))
        print(t("init.corpus_ready", path=inicio.ruta_catalogo))
        print(t("init.engine_created" if inicio.creo_motor else "init.engine_kept"))
        print(t("init.domain_created" if inicio.creo_dominio else "init.domain_kept"))
        print(t("init.next"))
        return 0


class ComandoConfigurar(Comando):
    nombre = "configure"
    ayuda = "configure.help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("pares", nargs="+", metavar="key=value", help=t("configure.arg_pairs"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        pares: dict[str, str] = {}
        for par in args.pares:
            if "=" not in par:
                print(t("configure.bad_pair", pair=par))
                return 1
            clave, _, valor = par.partition("=")
            pares[clave.strip()] = valor.strip()

        try:
            nuevo = configurar(pares)
        except ValueError as e:
            print(t("cli.error", error=e))
            return 1

        print(t("configure.done"))
        for clave in pares:
            valor = nuevo
            for parte in clave.split("."):  # claves anidadas: query_log.enabled
                valor = valor[parte]
            print(t("configure.value", key=clave, value=valor))
        if "language" in pares and idioma_con_respaldo(nuevo["language"]):
            print(t("init.fallback_note", language=nuevo["language"]))
        return 0


def _mostrar_indice(indice, perfil: str) -> None:
    if indice.estado == "compatible":
        print(t("profile.index_compatible", model=indice.modelo_indice))
    elif indice.estado == "sin_indice":
        print(t("profile.index_missing", profile=perfil, model=indice.modelo_requerido))
    else:
        print(t("profile.index_incompatible", built=indice.modelo_indice, profile=perfil,
                needed=indice.modelo_requerido))
        print(t("cli.action", action="ipsis index"))


def _mostrar_calibracion(calibracion, cambio: bool = False) -> None:
    if calibracion.estado == "sin_calibracion":
        print(t("profile.calibration_none"))
    elif calibracion.estado == "vigente":
        print(t("profile.calibration_current"))
    elif calibracion.estado == "no_habilitada":
        print(t("profile.calibration_disabled", reason=calibracion.motivo))
    else:
        prefijo = t("profile.calibration_changed" if cambio else "profile.calibration_stale")
        print(t("profile.calibration_kept", prefix=prefijo, reason=calibracion.motivo))
        print(t("cli.action", action=t("profile.calibration_action")))


class ComandoPerfilMostrar(Comando):
    nombre = "show"
    ayuda = "profile.show_help"

    def ejecutar(self, args: argparse.Namespace) -> int:
        r = resumen_perfil()
        print(t("profile.active_described", profile=r.perfil, description=r.descripcion) if r.descripcion
              else t("profile.active", profile=r.perfil))
        print(t("profile.budget", ms=r.presupuesto_p95_ms))
        print(t("profile.models"))
        for rol, clave in (("denso", "role_dense"), ("reranker", "role_reranker"), ("lector", "role_reader")):
            print(f"  {t('profile.' + clave):9} {r.modelos.get(rol) or t('cli.none')}")
        _mostrar_indice(r.indice, r.perfil)
        _mostrar_calibracion(r.calibracion)
        return 0


class ComandoPerfilCambiar(Comando):
    nombre = "set"
    ayuda = "profile.set_help"

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("perfil", metavar="profile", help=t("profile.arg_profile"))

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            cambio = cambiar_perfil(args.perfil)
        except PerfilInvalido as e:
            print(t("cli.error", error=e))
            return 1
        except ValueError as e:  # ajustes del perfil del proyecto inválidos para el destino
            print(t("profile.invalid_overrides", profile=args.perfil, error=e))
            return 1
        if not cambio.cambio_real:
            print(t("profile.already_active", profile=cambio.nuevo))
            return 0
        print(t("profile.changed", old=cambio.anterior, new=cambio.nuevo))
        indice = cambio.indice
        if indice.estado == "compatible":
            print(t("profile.still_compatible"))
        elif indice.estado == "sin_indice":
            print(t("profile.no_index_yet", profile=cambio.nuevo))
        else:
            print(t("profile.dense_changed", old=indice.modelo_indice, new=indice.modelo_requerido))
            print(t("cli.action", action="ipsis index"))
        if cambio.calibracion.estado in ("obsoleta", "no_habilitada"):
            _mostrar_calibracion(cambio.calibracion, cambio=True)
        return 0


def grupo_perfil() -> Grupo:
    return Grupo("profile", "profile.help", [ComandoPerfilMostrar(), ComandoPerfilCambiar()])


__all__ = ["ComandoConfigurar", "ComandoInit", "ComandoPerfilCambiar", "ComandoPerfilMostrar", "grupo_perfil"]
