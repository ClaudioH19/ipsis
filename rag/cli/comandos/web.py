"""Grupo web: temas y exportación del widget embebible."""
from __future__ import annotations

import argparse

import yaml

from rag.aplicacion.widget import aplicar_preset, exportar_widget, generar_vista_previa, listar_presets, snippet_widget
from rag.cli.base import Comando, Grupo


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
        parser.add_argument("--salida", default=".rag/widget-vista-previa.html", help="Archivo HTML de salida.")

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
                            help="Usa el Web Component <rag-extractivo-chat> en vez de los data-* del <script>.")
        parser.add_argument("--clave", default=None, help="Clave pública del widget (claves_widget), si usas.")

    def ejecutar(self, args: argparse.Namespace) -> int:
        try:
            print(snippet_widget(args.api, componente=args.componente, clave_widget=args.clave))
        except ValueError as e:
            print(f"Error: configuracion/estilos.yaml: {e}")
            return 1
        return 0


def grupo_widget() -> Grupo:
    tema = Grupo("tema", "Administra presets visuales.", "Operación sobre el tema visual.",
                 [ComandoTemaListar(), ComandoTemaAplicar(), ComandoTemaVistaPrevia()])
    return Grupo("widget", "Configura y exporta el widget embebible.", "Operación sobre el widget.",
                 [tema, ComandoWidgetExportar(), ComandoWidgetSnippet()])


__all__ = ["ComandoTemaAplicar", "ComandoTemaListar", "ComandoTemaVistaPrevia", "ComandoWidgetExportar",
           "ComandoWidgetSnippet",
           "grupo_widget"]
