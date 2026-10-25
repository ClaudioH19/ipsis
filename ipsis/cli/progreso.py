"""Trabajo visible y medido; avisos en stderr, resultados en stdout.

En una terminal usa una línea animada con la fase real y el tiempo; fuera
de ella conserva avisos sencillos sin escapes ni hilos de refresco.
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar

from ipsis.nucleo.progreso import observar_progreso
from ipsis.recursos.mensajes import catalogo, t

_activa: ContextVar[Actividad | None] = ContextVar("ipsis_actividad", default=None)
COMANDOS = {
    "load": "load", "index": "index", "doctor": "doctor", "audit": "audit",
    "evaluate": "evaluate", "benchmark": "benchmark",
    "ask": "query", "models": "models", "deploy": "deploy",
}


def consola_animada() -> bool:
    return (sys.stderr.isatty() and sys.stdout.isatty()
            and os.environ.get("TERM") != "dumb")


class Actividad:
    def __init__(self, clave: str) -> None:
        self.titulo = t(f"progress.{clave}")
        self.inicio = time.perf_counter()
        self.codigo = 0
        self.ultima_etapa = None
        self.progreso = None
        self.consola = None
        self.tarea = None

    def empezar(self) -> None:
        if consola_animada():
            from rich.console import Console
            from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
            from rich.text import Text

            self.consola = Console(stderr=True, highlight=False)
            self.progreso = Progress(SpinnerColumn(style="cyan"), TextColumn("{task.description}"),
                                     TimeElapsedColumn(), console=self.consola, transient=True,
                                     refresh_per_second=8)
            self.tarea = self.progreso.add_task(Text(self.titulo), total=None)
            self.progreso.start()
        self._linea(f"... {self.titulo}", "cyan")

    def _linea(self, texto: str, estilo: str = "dim") -> None:
        if self.consola is not None:
            from rich.text import Text

            self.consola.print(Text(texto, style=estilo))
        else:
            print(texto, file=sys.stderr, flush=True)

    def actualizar(self, etapa: str, **datos) -> None:
        clave = f"progress.stage_{etapa}"
        texto = t(clave, **datos) if clave in catalogo("en") else t("progress.stage_other", stage=etapa)
        if etapa != self.ultima_etapa:
            self._linea(f"  {texto}")
        self.ultima_etapa = etapa
        if self.progreso is not None:
            from rich.text import Text

            self.progreso.update(self.tarea, description=Text(texto), refresh=True)

    def terminar(self) -> None:
        if self.progreso is not None:
            self.progreso.stop()
        clave = "cancelled" if self.codigo == 130 else "done" if self.codigo == 0 else "failed"
        estilo = "green" if self.codigo == 0 else "yellow" if self.codigo == 130 else "red"
        self._linea(t(f"progress.{clave}", task=self.titulo,
                      seconds=time.perf_counter() - self.inicio), estilo)


@contextmanager
def actividad(clave: str):
    anterior = _activa.get()
    if anterior is not None:
        yield anterior
        return
    actual = Actividad(clave)
    token = _activa.set(actual)
    try:
        actual.empezar()
        with observar_progreso(actual.actualizar):
            yield actual
    except KeyboardInterrupt:
        actual.codigo = 130
        raise
    except BaseException:
        actual.codigo = 1
        raise
    finally:
        try:
            actual.terminar()
        finally:
            _activa.reset(token)
