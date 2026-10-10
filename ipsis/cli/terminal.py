"""Terminal interactiva de ``ipsis``: Folio, autocompletado y menú de opciones.

Con ``prompt_toolkit`` (dependencia del paquete), al escribir ``/`` se despliega
un menú con los comandos y su descripción; tras ``/calibrate `` aparecen sus
opciones con su ayuda, y tras ``/load `` las rutas. Todo sale del parser de la
CLI: un comando nuevo aparece solo. Sin terminal real (o sin la librería) se usa
``input()``, igual que antes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ipsis.recursos.mensajes import t

# Folio, el avatar de ipsis, en caracteres (una hoja con cara).
FOLIO = (
    "╭──────╮",
    "│ ◕  ◕ │",
    "│  ‿   │",
    "│ ──── │",
    "╰──────╯",
)
HISTORIAL = Path.home() / ".ipsis_history"
PROPIOS = ("help", "diagnostics", "reload", "exit", "quit")


def terminal_real() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _resumen_proyecto() -> tuple[str, int] | None:
    """``(perfil · idioma, documentos)`` del proyecto de esta carpeta, o ``None``."""
    if not Path("config/assistant.yaml").is_file():
        return None
    try:
        from ipsis.aplicacion.panel import documentos
        from ipsis.configuracion.carga import cargar_dominio

        dominio = cargar_dominio()
        return f"{dominio.get('perfil', '-')} · {dominio.get('idioma', '-')}", len(documentos())
    except Exception:  # noqa: BLE001 -- el banner nunca impide abrir la terminal
        return None


def lineas_banner() -> list[str]:
    from ipsis import __version__

    proyecto = _resumen_proyecto()
    derecha = [f"ipsis {__version__}",
               t("terminal.project", profile=proyecto[0], n=proyecto[1]) if proyecto else t("terminal.no_project"),
               t("terminal.tips"), ""]
    return [f"  {folio}   {texto}".rstrip() for folio, texto in zip(FOLIO, derecha + [""])]


def imprimir_banner() -> None:
    texto = "\n".join(lineas_banner())
    try:
        from prompt_toolkit import print_formatted_text
        from prompt_toolkit.formatted_text import FormattedText

        print_formatted_text(FormattedText([("ansicyan", texto)]))
    except ImportError:
        print(texto)


# --- autocompletado desde el parser ---------------------------------------------------------
def _subcomandos(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for accion in parser._actions:  # noqa: SLF001 -- argparse no publica sus subparsers
        if isinstance(accion, argparse._SubParsersAction):  # noqa: SLF001
            return dict(accion.choices)
    return {}


def _ayudas_de_subcomandos(parser: argparse.ArgumentParser) -> dict[str, str]:
    for accion in parser._actions:  # noqa: SLF001
        if isinstance(accion, argparse._SubParsersAction):  # noqa: SLF001
            return {c.dest: c.help or "" for c in accion._choices_actions}  # noqa: SLF001
    return {}


def _opciones(parser: argparse.ArgumentParser) -> list[tuple[str, str]]:
    salida = []
    for accion in parser._actions:  # noqa: SLF001
        for opcion in accion.option_strings:
            if opcion.startswith("--") and opcion != "--help":
                salida.append((opcion, accion.help or ""))
    return salida


def candidatos(texto: str, parser: argparse.ArgumentParser) -> list[tuple[str, str, int]]:
    """``(completado, descripción, inicio)`` para lo escrito hasta el cursor. ``inicio`` es
    la posición (negativa) desde la que se reemplaza. Solo completa ``/comandos``."""
    if not texto.startswith("/"):
        return []
    partes = texto[1:].split()
    actual = "" if texto.endswith(" ") or not partes else partes[-1]
    previas = partes if texto.endswith(" ") else partes[:-1]
    if not previas:  # el nombre del comando
        ayudas = _ayudas_de_subcomandos(parser)
        nombres = {**{p: t(f"terminal.own_{p}") for p in PROPIOS}, **{n: ayudas.get(n, "") for n in ayudas}}
        nombres.pop("chat", None)
        return [("/" + n, d, -len(actual) - 1) for n, d in nombres.items() if n.startswith(actual)]
    nivel = parser
    for palabra in previas:
        hijos = _subcomandos(nivel)
        if palabra in hijos:
            nivel = hijos[palabra]
    if actual.startswith("-"):
        return [(o, d, -len(actual)) for o, d in _opciones(nivel) if o.startswith(actual)]
    subcomandos = _ayudas_de_subcomandos(nivel)
    if subcomandos:
        return [(n, d, -len(actual)) for n, d in subcomandos.items() if n.startswith(actual)]
    return [(o, d, 0) for o, d in _opciones(nivel)] if not actual else []

def crear_entrada(estado: dict):
    """Una función ``leer(prompt)`` con historial, menú de opciones y barra inferior;
    ``None`` si no hay terminal real o falta ``prompt_toolkit``."""
    if not terminal_real():
        return None
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion, PathCompleter
        from prompt_toolkit.document import Document
        from prompt_toolkit.history import FileHistory
    except ImportError:
        return None
    from ipsis.cli import construir_parser

    parser = construir_parser()
    rutas = PathCompleter(expanduser=True)

    class _Completador(Completer):
        def get_completions(self, documento, evento):
            texto = documento.text_before_cursor
            partes = texto[1:].split()
            if texto.startswith("/") and partes and partes[0] == "load" and (len(partes) > 1 or texto.endswith(" ")):
                ruta = "" if texto.endswith(" ") else partes[-1]
                yield from rutas.get_completions(Document(ruta, len(ruta)), evento)
                return
            for completado, descripcion, inicio in candidatos(texto, parser):
                yield Completion(completado, start_position=inicio, display_meta=descripcion)

    def barra():
        diag = t("terminal.on") if estado.get("diagnostico") else t("terminal.off")
        return t("terminal.toolbar", diagnostics=diag)

    try:
        historial = FileHistory(str(HISTORIAL))
    except OSError:
        historial = None
    sesion = PromptSession(completer=_Completador(), complete_while_typing=True, history=historial,
                           bottom_toolbar=barra)
    return lambda prompt: sesion.prompt("› ")


__all__ = ["FOLIO", "candidatos", "crear_entrada", "imprimir_banner", "lineas_banner", "terminal_real"]
