"""Grupo web: temas y exportación del widget embebible."""
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


class ComandoTemaListar(Comando):
    nombre = "listar"
    ayuda = "Muestra los presets disponibles."

    def ejecutar(self, args: argparse.Namespace) -> int:
        for nombre, descripcion in listar_presets().items():
            print(f"{nombre}: {descripcion}")
        return 0


class ComandoTemaAplicar(Comando):
    nombre = "aplicar"
    ayuda = "Aplica un preset a estilos.yaml."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("preset", help="Nombre del preset visual.")
        parser.add_argument("--ruta", default="configuracion/estilos.yaml", help="Archivo de estilos a modificar.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            aplicar_preset(args.preset, args.ruta)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"No se pudo aplicar el preset: {exc}")
            return 1
        print(f"Preset {args.preset!r} aplicado en {args.ruta}")
        print("Vista activa: inicia el servicio y abre /widget/demo.html")
        return 0


class ComandoTemaVistaPrevia(Comando):
    nombre = "vista-previa"
    ayuda = "Genera un mockup HTML sin iniciar la API."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--ruta", default="configuracion/estilos.yaml",
                            help="Archivo de estilos que se desea previsualizar.")
        parser.add_argument("--salida", default=".ipsis/widget-vista-previa.html", help="Archivo HTML de salida.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            salida = generar_vista_previa(args.salida, args.ruta)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"No se pudo generar la vista previa: {exc}")
            return 1
        print(f"Vista previa escrita en {salida.resolve()}")
        return 0


class ComandoWidgetExportar(Comando):
    nombre = "exportar"
    ayuda = "Copia widget.js y genera un snippet de integración."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("carpeta", help="Directorio donde escribir los archivos.")
        parser.add_argument("--api", default="http://127.0.0.1:8000",
                            help="URL pública de la API que consultará el widget.")
        parser.add_argument("--posicion", default="abajo-derecha",
                            choices=["abajo-derecha", "abajo-izquierda", "arriba-derecha", "arriba-izquierda",
                                     "incrustado"],
                            help="Esquina donde se mostrará el botón.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            salida = exportar_widget(args.carpeta, api=args.api, posicion=args.posicion)
        except (OSError, ValueError) as exc:
            print(f"No se pudo exportar el widget: {exc}")
            return 1
        print(f"Widget exportado en {salida}")
        print(f"Snippet listo en {salida / 'snippet.html'}")
        return 0


class ComandoWidgetSnippet(Comando):
    nombre = "snippet"
    ayuda = "Imprime el código para pegar el widget en tu sitio, según estilos.yaml::ubicacion."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--api", default="http://127.0.0.1:8000",
                            help="URL pública del servicio (p. ej. https://asistente.tu-dominio.cl).")
        parser.add_argument("--componente", action="store_true",
                            help="Usa el Web Component <ipsis-chat> en vez de los data-* del <script>.")
        parser.add_argument("--clave", default=None, help="Clave pública del widget (claves_widget), si usas.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            print(snippet_widget(args.api, componente=args.componente, clave_widget=args.clave))
        except ValueError as e:
            print(f"Error: configuracion/estilos.yaml: {e}")
            return 1
        return 0


class ComandoEstiloMostrar(Comando):
    nombre = "mostrar"
    ayuda = "Muestra cada valor de estilo del widget (colores, tipografía, forma, ubicación…)."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--seccion", choices=SECCIONES_EDITABLES, default=None, help="Solo una sección.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            valores = estilo_plano()
        except (OSError, yaml.YAMLError) as exc:
            print(f"No se pudo leer configuracion/estilos.yaml: {exc}")
            return 1
        for clave, valor in valores:
            if args.seccion is None or clave.startswith(args.seccion + "."):
                print(f"{clave} = {str(valor).lower() if isinstance(valor, bool) else valor}")
        print("Para cambiar: ipsis widget estilo cambiar seccion.clave=valor")
        return 0


class ComandoEstiloCambiar(Comando):
    nombre = "cambiar"
    ayuda = "Cambia valores de estilo del widget, p. ej. colores.acento=#0ea5e9 forma.radio_panel=10px."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("asignaciones", nargs="+", metavar="seccion.clave=valor",
                            help="Uno o más cambios (ver 'ipsis widget estilo mostrar').")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            cambiar_estilo(args.asignaciones)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"No se cambió nada: {exc}")
            return 1
        print(f"Estilo actualizado en configuracion/estilos.yaml ({len(args.asignaciones)} cambio(s)).")
        print("El servicio lo aplica sin reiniciar; para verlo: ipsis widget tema vista-previa")
        return 0


def grupo_widget() -> Grupo:
    tema = Grupo("tema", "Administra presets visuales.", "Operación sobre el tema visual.",
                 [ComandoTemaListar(), ComandoTemaAplicar(), ComandoTemaVistaPrevia()])
    estilo = Grupo("estilo", "Muestra o cambia cada valor de estilo.", "Operación sobre el estilo.",
                   [ComandoEstiloMostrar(), ComandoEstiloCambiar()])
    return Grupo("widget", "Configura y exporta el widget embebible.", "Operación sobre el widget.",
                 [tema, estilo, ComandoWidgetExportar(), ComandoWidgetSnippet()])




class ComandoDesplegarPreparar(Comando):
    nombre = "preparar"
    ayuda = "Genera una carpeta lista para copiar a un servidor (Docker, compose y Caddy opcional)."

    def registrar(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--destino", default="dist", help="Carpeta de salida (por defecto: dist).")
        parser.add_argument("--dominio", default=None, help="Dominio del servicio para HTTPS con Caddy.")
        parser.add_argument("--wheel", default=None, help="Wheel de ipsis a instalar en la imagen.")
        parser.add_argument("--forzar", action="store_true", help="Regenera una carpeta preparada antes.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        from ipsis.aplicacion.despliegue import DespliegueInvalido, preparar_despliegue

        try:
            resumen = preparar_despliegue(args.destino, dominio=args.dominio, wheel=args.wheel, forzar=args.forzar)
        except (DespliegueInvalido, OSError) as exc:
            print(f"No se pudo preparar el despliegue: {exc}")
            return 1
        print(f"Despliegue preparado en {resumen.destino} (perfil {resumen.perfil}, dominio {resumen.dominio}):"
              f" {len(resumen.archivos)} archivos.")
        for aviso in resumen.avisos:
            print(f"  Aviso: {aviso}")
        print(f"Siguiente paso: lee {resumen.destino / 'LEEME_despliegue.md'} y copia la carpeta al servidor.")
        return 0


def grupo_desplegar() -> Grupo:
    return Grupo("desplegar", "Prepara el despliegue en un servidor propio.", "Operación de despliegue.",
                 [ComandoDesplegarPreparar()])


__all__ = ["ComandoDesplegarPreparar", "ComandoTemaAplicar", "ComandoTemaListar", "ComandoTemaVistaPrevia", "ComandoWidgetExportar",
           "ComandoWidgetSnippet", "grupo_desplegar",
           "grupo_widget"]
