"""Grupo proyecto: crear y configurar el proyecto del cliente."""
from __future__ import annotations

import argparse

from rag.aplicacion.proyecto import (
    PerfilInvalido,
    ProyectoExistente,
    actualizar_dominio,
    cambiar_perfil,
    idioma_con_respaldo,
    inicializar_proyecto,
    resumen_perfil,
)
from rag.cli.base import Comando, Grupo


_NOTA_RESPALDO = ("  Nota: no hay un paquete para {idioma!r}: se usan las reglas universales, términos sin stem "
                  "y los textos en inglés (tradúcelos en configuracion/idioma.yaml).")


class ComandoInit(Comando):
    nombre = "init"
    ayuda = "Crea la configuración de un dominio nuevo."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--nombre-asistente", dest="nombre_asistente", default=None,
                            help="Nombre visible del asistente (por defecto: 'Asistente documental').")
        parser.add_argument("--descripcion-dominio", dest="descripcion_dominio", default=None,
                            help="Descripción corta del dominio, p.ej. 'el manual de mi equipo' "
                                 "(por defecto: 'los documentos cargados').")
        parser.add_argument("--idioma", default=None,
                            help="Código del idioma (por defecto: 'es'). es, en y pt tienen paquete propio; otro código "
                                 "usa las reglas universales, sin stem, y los textos en inglés.")
        parser.add_argument("--perfil", choices=["light", "medium", "heavy"], default=None,
                            help="Perfil de instalación: light (sin modelos extra), medium o heavy "
                                 "(por defecto: medium).")
        parser.add_argument("--force", action="store_true",
                            help="Reinicia configuracion/asistente.yaml si ya existe.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            inicio = inicializar_proyecto(args.nombre_asistente, args.descripcion_dominio, args.idioma,
                                          args.perfil, forzar=args.force)
        except ProyectoExistente as e:
            print(f"Ya existe {e} -- usa 'rag configurar clave=valor' para modificarlo, "
                  f"o 'rag init --force' para reiniciarlo desde los valores por defecto.")
            return 1
        except ValueError as e:
            print(f"Error: {e}")
            return 1

        nuevo = inicio.nuevo
        if inicio.creo_estilos:
            print("configuracion/estilos.yaml creado: ahí se cambia TODO el diseño del widget "
                  "(colores, tipografía, formas, sombras y animaciones), sin tocar código.")
        print(f"Dominio inicializado en {inicio.ruta_asistente}:")
        print(f"  nombre_asistente = {nuevo['nombre_asistente']!r}")
        print(f"  descripcion_dominio = {nuevo['descripcion_dominio']!r}")
        print(f"  idioma = {nuevo['idioma']!r}, perfil = {nuevo['perfil']!r}")
        if idioma_con_respaldo(nuevo["idioma"]):
            print(_NOTA_RESPALDO.format(idioma=nuevo["idioma"]))
        print(f"Corpus vacío listo en documentos/ (catálogo en {inicio.ruta_catalogo}).")
        if inicio.creo_motor:
            print("configuracion/motor.yaml creado con umbrales genéricos de partida. "
                  "La calibración se realiza al final, después de estabilizar la infraestructura.")
        else:
            print("configuracion/motor.yaml ya existía -- no se tocó.")
        if inicio.creo_dominio:
            print("configuracion/dominio.yaml creado: reglas y categorías propias de tu dominio (opcional).")
        else:
            print("configuracion/dominio.yaml ya existía -- no se tocó.")
        print("Siguiente paso: 'rag cargar <archivo|carpeta>', después 'rag indexar'.")
        return 0


class ComandoConfigurar(Comando):
    nombre = "configurar"
    ayuda = "Modifica configuracion/asistente.yaml (clave=valor)."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("pares", nargs="+",
                            help="Uno o más pares clave=valor, p.ej. nombre_asistente='Mi asistente' "
                                 "cors_origenes=https://mi-sitio.cl (varias claves separadas por espacio, "
                                 "varios valores de una lista separados por coma dentro del mismo valor).")

    def ejecutar(self, args: argparse.Namespace) -> int:
        pares: dict[str, str] = {}
        for par in args.pares:
            if "=" not in par:
                print(f"Error: {par!r} no tiene la forma 'clave=valor'.")
                return 1
            clave, _, valor = par.partition("=")
            pares[clave.strip()] = valor.strip()

        try:
            nuevo = actualizar_dominio(pares)
        except ValueError as e:
            print(f"Error: {e}")
            return 1

        print("configuracion/asistente.yaml actualizado:")
        for clave in pares:
            valor = nuevo
            for parte in clave.split("."):  # claves anidadas: registro.activo
                valor = valor[parte]
            print(f"  {clave} = {valor!r}")
        if "idioma" in pares and idioma_con_respaldo(nuevo["idioma"]):
            print(_NOTA_RESPALDO.format(idioma=nuevo["idioma"]))
        return 0


def _mostrar_indice(indice, perfil: str) -> None:
    if indice.estado == "compatible":
        print(f"Índice: compatible (construido con {indice.modelo_indice}).")
    elif indice.estado == "sin_indice":
        print(f"Índice: todavía no existe; el próximo 'rag indexar' lo construirá para {perfil} "
              f"({indice.modelo_requerido}).")
    else:
        print(f"Índice: incompatible: se construyó con {indice.modelo_indice} y el perfil {perfil} "
              f"necesita {indice.modelo_requerido}.")
        print("  Acción: rag indexar")


def _mostrar_calibracion(calibracion, cambio: bool = False) -> None:
    if calibracion.estado == "sin_calibracion":
        print("Calibración: no hay (rigen los umbrales del perfil).")
    elif calibracion.estado == "vigente":
        print("Calibración: vigente (sus umbrales están activos).")
    elif calibracion.estado == "no_habilitada":
        print(f"Calibración: guardada solo para auditoría, no se aplica ({calibracion.motivo}).")
    else:
        prefijo = "La calibración anterior ya no corresponde al perfil activo" if cambio else "Calibración: obsoleta"
        print(f"{prefijo} ({calibracion.motivo}). Rigen los umbrales del perfil; el archivo se conserva.")
        print("  Acción: rag calibrar --aplicar (si tienes un golden set importado)")


class ComandoPerfilMostrar(Comando):
    nombre = "mostrar"
    ayuda = "Muestra el perfil activo, sus modelos, su presupuesto y si el índice y la calibración le sirven."

    def ejecutar(self, args: argparse.Namespace) -> int:
        r = resumen_perfil()
        print(f"Perfil activo: {r.perfil} ({r.descripcion})" if r.descripcion else f"Perfil activo: {r.perfil}")
        print(f"Presupuesto p95: {r.presupuesto_p95_ms} ms")
        print("Modelos:")
        for rol in ("denso", "reranker", "lector"):
            print(f"  {rol + ':':9} {r.modelos.get(rol) or '—'}")
        _mostrar_indice(r.indice, r.perfil)
        _mostrar_calibracion(r.calibracion)
        return 0


class ComandoPerfilCambiar(Comando):
    nombre = "cambiar"
    ayuda = "Cambia el perfil activo e indica si hay que reindexar o recalibrar (no ejecuta nada costoso)."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("perfil", help="Perfil de instalación destino: light, medium o heavy.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            cambio = cambiar_perfil(args.perfil)
        except PerfilInvalido as e:
            print(f"Error: {e}")
            return 1
        except ValueError as e:  # ajustes_perfil del proyecto inválidos para el destino
            print(f"Error: los ajustes_perfil de configuracion/motor.yaml no son válidos para {args.perfil}: {e}")
            return 1
        if not cambio.cambio_real:
            print(f"El perfil {cambio.nuevo} ya está activo. No se realizaron cambios.")
            return 0
        print(f"Perfil cambiado: {cambio.anterior} → {cambio.nuevo}")
        indice = cambio.indice
        if indice.estado == "compatible":
            print("El índice actual sigue siendo compatible: no es necesario reindexar.")
        elif indice.estado == "sin_indice":
            print(f"Todavía no hay índice: el próximo 'rag indexar' lo construirá para {cambio.nuevo}.")
        else:
            print(f"El modelo denso cambió: {indice.modelo_indice} → {indice.modelo_requerido}. "
                  "Hay que reconstruir el índice (el anterior se conserva).")
            print("  Acción: rag indexar")
        if cambio.calibracion.estado in ("obsoleta", "no_habilitada"):
            _mostrar_calibracion(cambio.calibracion, cambio=True)
        return 0


def grupo_perfil() -> Grupo:
    return Grupo("perfil", "Muestra o cambia el perfil de instalación (light, medium o heavy).",
                 "Operación sobre el perfil.", [ComandoPerfilMostrar(), ComandoPerfilCambiar()])


__all__ = ["ComandoConfigurar", "ComandoInit", "ComandoPerfilCambiar", "ComandoPerfilMostrar", "grupo_perfil"]
