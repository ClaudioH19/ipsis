"""Completa unidades y relaciones alrededor de un span QA, sin redactar texto."""
from __future__ import annotations

import re


def _alternativas(valores) -> str:
    return "|".join(re.escape(v) for v in sorted(set(valores), key=lambda v: (-len(v), v)))


def completar_tramo(pregunta: str, texto: str, inicio: int, fin: int, paquete) -> tuple[int, int]:
    """Bordes literales de una cantidad o del actor y su acción actual.

    Solo completa un span que el lector ya escogió: no cambia el actor ni
    busca otra cifra. Una relación se extiende únicamente si su verbo está
    después del actor escogido; nunca reemplaza el actor por toda la cita.
    """
    bordes = getattr(paquete, "bordes_respuesta", None)
    if bordes is None or inicio >= fin:
        return inicio, fin
    unidades = [u for grupo in paquete.unidades_tiempo.values() for u in grupo]
    unidades += bordes.unidades_cantidad
    if unidades:
        numeros = r"\d+(?:[.,]\d+)*" + ("|" + _alternativas(paquete.numeros) if paquete.numeros else "")
        prefijos = _alternativas(bordes.prefijos_cantidad)
        calificadores = _alternativas(v for grupo in paquete.calificadores_plazo.values() for v in grupo)
        referencias = _alternativas(bordes.referencias_cantidad)
        calificador_previo = rf"(?:(?:{calificadores})\s+)?" if calificadores else ""
        patron = rf"(?<!\w)(?:{numeros})\s+{calificador_previo}(?:{_alternativas(unidades)})(?!\w)"
        if prefijos:
            patron = rf"(?:(?:{prefijos})\s+)?" + patron
        if calificadores:
            patron += rf"(?:\s+(?:{calificadores})(?!\w))?"
        if referencias:
            patron += rf"(?:\s+(?:{referencias})\s+[^.;!?\n]+)?"
        for cantidad in re.finditer(patron, texto, re.I):
            if cantidad.start() <= inicio < fin <= cantidad.end():
                return cantidad.start(), cantidad.end()

    from ipsis.lenguaje.consultas import comprender, equivalentes, terminos_de_contenido
    from ipsis.lenguaje.texto import terminos

    comprension = comprender(pregunta, paquete)
    if comprension.intencion != "responsable":
        return inicio, fin
    propios = set(terminos_de_contenido(pregunta, paquete))
    # El verbo de la pregunta («redacta»), no el de la pregunta anterior
    # («firma»), es el que permite completar la relación.
    accion = re.search(r"\w+", texto[fin:])
    if accion is None or not propios.intersection(equivalentes(terminos(accion.group(), paquete), paquete)):
        return inicio, fin
    fin_accion = fin + accion.end()
    limite = len(texto)
    for patron in bordes.limites_actor:
        corte = re.search(patron, texto[fin_accion:], re.I)
        if corte:
            limite = min(limite, fin_accion + corte.start())
    while limite > fin and texto[limite - 1] in " \t\n.,;":
        limite -= 1
    return inicio, max(fin, limite)
