"""Resuelve exclusivamente los selectores del árbol de comandos al aceptar una línea."""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher


class ComandoAmbiguo(ValueError):
    def __init__(self, palabra, opciones):
        self.palabra, self.opciones = palabra, opciones
        super().__init__(palabra)


def _cercano(palabra, opciones):
    if palabra in opciones or palabra.startswith("-") or len(palabra) < 2:
        return palabra
    prefijos = sorted(n for n in opciones if n.startswith(palabra))
    if len(prefijos) == 1:
        return prefijos[0]
    if prefijos:
        raise ComandoAmbiguo(palabra, prefijos)
    if len(palabra) < 3:
        return palabra
    candidatos = sorted(((SequenceMatcher(None, palabra, n).ratio(), n) for n in opciones), reverse=True)
    if not candidatos or candidatos[0][0] < .75:
        return palabra
    similares = [n for score, n in candidatos if candidatos[0][0] - score < .08]
    if len(similares) > 1:
        raise ComandoAmbiguo(palabra, sorted(similares))
    return candidatos[0][1]


def resolver(argv, parser, *, propios=(), excluir=()):
    """Devuelve argv y cambios. Nunca corrige argumentos ni nombres de opciones."""
    salida, cambios = list(argv), []
    actual = parser
    for i, palabra in enumerate(salida):
        accion = next((a for a in actual._actions if isinstance(a, argparse._SubParsersAction)), None)
        if accion is None or palabra.startswith("-"):
            break
        opciones = {n: p for n, p in accion.choices.items() if n not in excluir or i > 0}
        if i == 0:
            opciones.update({n: None for n in propios})
        elegido = _cercano(palabra, opciones)
        if elegido not in opciones:
            break
        if elegido != palabra:
            salida[i] = elegido
            cambios.append((palabra, elegido))
        actual = opciones[elegido]
        if actual is None:
            break
    return salida, cambios


def informar_cambios(cambios):
    from ipsis.recursos.mensajes import t

    if cambios:
        print(t("terminal.interpreted", command=", ".join(f"{a} → {b}" for a, b in cambios)))


def informar_ambiguedad(error):
    from ipsis.recursos.mensajes import t

    print(t("terminal.ambiguous", command=error.palabra, choices=", ".join(error.opciones)))
