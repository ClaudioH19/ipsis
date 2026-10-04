"""Elección de la variante de cada situación del tono.

Dentro de una consulta del motor la elección es determinista por
``(id_sesion, turno, situación, semilla)`` y no repite, en turnos seguidos de
una misma sesión, la variante usada antes en esa situación: la conversación
suena natural y sigue siendo reproducible. Fuera de una consulta (``/config``,
pruebas o funciones sueltas) depende solo de la semilla, como antes.

Cada variante elegida queda registrada como ``<tono>.<situación>.<n>`` para el
diagnóstico y el registro de consultas.
"""
from __future__ import annotations

import threading
import zlib
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


def _inicio(semilla: str, n: int) -> int:
    return zlib.crc32(semilla.encode("utf-8")) % n


class SelectorVariantes:
    """Memoria por sesión, acotada (LRU) y solo en memoria: guarda turnos e índices, nunca texto.

    Con varios procesos (workers) cada uno tiene la suya: es variedad, no corrección.
    """

    def __init__(self, tono: str = "cordial", *, fija: bool = False, max_sesiones: int = 1024) -> None:
        self.tono = tono
        self.fija = fija  # siempre la primera variante (``tono.variedad: fija``)
        self.max_sesiones = max_sesiones
        self._sesiones: OrderedDict[str, dict] = OrderedDict()
        self._candado = threading.Lock()

    def _sesion(self, id_sesion: str) -> dict:
        datos = self._sesiones.pop(id_sesion, None) or {"turno": 0, "ultimas": {}}
        self._sesiones[id_sesion] = datos
        while len(self._sesiones) > self.max_sesiones:
            self._sesiones.popitem(last=False)
        return datos

    def nuevo_turno(self, id_sesion: str) -> int:
        with self._candado:
            datos = self._sesion(id_sesion)
            datos["turno"] += 1
            return datos["turno"]

    def elegir(self, situacion: str, opciones: list[str], *, id_sesion: str, turno: int, semilla: str = "",
               evitar: frozenset[str] = frozenset()) -> int:
        """Índice de la variante para esta situación, sesión y turno."""
        n = len(opciones)
        with self._candado:
            ultimas = self._sesion(id_sesion)["ultimas"]
            if self.fija:
                orden = list(range(n))
            else:
                base = _inicio(f"{id_sesion}|{turno}|{situacion}|{semilla}", n)
                orden = [(base + i) % n for i in range(n)]
            prohibido = ultimas.get(situacion) if n > 1 and not self.fija else None
            elegido = next((i for i in orden if opciones[i] not in evitar and i != prohibido),
                           next((i for i in orden if opciones[i] not in evitar), orden[0]))
            ultimas[situacion] = elegido
            return elegido


@dataclass
class _Consulta:
    selector: SelectorVariantes
    id_sesion: str
    turno: int
    usadas: list[str] = field(default_factory=list)


_ACTUAL: ContextVar[_Consulta | None] = ContextVar("rag_variantes", default=None)


@contextmanager
def en_consulta(selector: SelectorVariantes, id_sesion: str):
    """Abre el contexto de elección para una consulta del motor."""
    consulta = _Consulta(selector, id_sesion, selector.nuevo_turno(id_sesion))
    marca = _ACTUAL.set(consulta)
    try:
        yield consulta
    finally:
        _ACTUAL.reset(marca)


def elegir(situacion: str, opciones: list[str], semilla: str = "", evitar: set[str] | None = None) -> str:
    """La variante de ``situacion`` que corresponde ahora ("" si no hay opciones)."""
    if not opciones:
        return ""
    evitar = frozenset(evitar or ())
    consulta = _ACTUAL.get()
    if consulta is None:
        base = _inicio(semilla, len(opciones))
        orden = [(base + i) % len(opciones) for i in range(len(opciones))]
        return opciones[next((i for i in orden if opciones[i] not in evitar), orden[0])]
    indice = consulta.selector.elegir(situacion, opciones, id_sesion=consulta.id_sesion, turno=consulta.turno,
                                      semilla=semilla, evitar=evitar)
    consulta.usadas.append(f"{consulta.selector.tono}.{situacion}.{indice + 1}")
    return opciones[indice]


def usadas() -> tuple[str | None, list[str]]:
    """Tono y ``plantilla_id`` elegidos en la consulta en curso."""
    consulta = _ACTUAL.get()
    return (consulta.selector.tono, list(consulta.usadas)) if consulta is not None else (None, [])


__all__ = ["SelectorVariantes", "elegir", "en_consulta", "usadas"]
