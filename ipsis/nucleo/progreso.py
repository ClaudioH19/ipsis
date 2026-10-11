"""Eventos de trabajo sin depender de una interfaz ni alterar sus resultados.

El observador vive en el contexto de la operación: una consulta HTTP o una
sesión paralela no heredan los avisos de la terminal. Sin observador no hay IO.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_observador: ContextVar[Callable[..., None] | None] = ContextVar("ipsis_progreso", default=None)


def informar(etapa: str, **datos) -> None:
    observador = _observador.get()
    if observador is not None:
        observador(etapa, **datos)


@contextmanager
def observar_progreso(observador: Callable[..., None]) -> Iterator[None]:
    token = _observador.set(observador)
    try:
        yield
    finally:
        _observador.reset(token)
