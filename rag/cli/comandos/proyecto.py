"""Grupo proyecto: crear y configurar el proyecto del cliente."""
from __future__ import annotations

import argparse

from rag.aplicacion.proyecto import ProyectoExistente, actualizar_dominio, inicializar_proyecto
from rag.cli.base import Comando


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
                            help="Código del paquete de idioma: textos, patrones y reglas (por defecto: 'es').")
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
            print(f"  {clave} = {nuevo[clave]!r}")
        return 0


__all__ = ["ComandoConfigurar", "ComandoInit"]
