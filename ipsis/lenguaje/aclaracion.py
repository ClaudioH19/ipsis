"""¿La pregunta necesita aclaración antes de leer?

«¿Cuánto es?», «¿Quién lo aprueba?» o «Quem aprova?» no dicen de qué se habla. Sin
conversación que aporte el tema, cualquier oración con una cifra o con «aprueba»
parece responderlas: el lector la encuentra y la política no tiene con qué
rechazarla. Lo correcto es pedir el tema.

Reglas deterministas (sin modelo), sobre la pregunta ya interpretada (un seguimiento
trae el tema de la conversación y no las dispara):

- **sin tema:** no queda ninguna palabra de contenido (fuera stopwords, palabras de la
  relación de la intención y genéricas): «¿Cuántos días son?», «How much is it?»;
- **pronombre sin antecedente:** queda una sola palabra de contenido y la pregunta tiene
  un pronombre anafórico del paquete («lo», «it», «isso»): «¿Quién lo aprueba?»;
- **tema que no acota:** queda una sola palabra de contenido, la pregunta es corta
  (hasta ``PALABRAS_CORTA`` palabras) y esa palabra está en candidatos de dos o más
  documentos, o de ninguno con más de una palabra: «¿Cuánto dura?» (la garantía, el
  préstamo, el viaje), «¿Cuánto tarda?» en un corpus sin «tarda». «¿Bitcoin?» sigue
  el camino normal y queda fuera de dominio.

Una pregunta con una sola palabra pero larga («cuando empieza la compra?») no se toca:
la forma de la relación ya acota la respuesta. Se probó usar la categoría gramatical
del léxico (solo verbos = sin tema) y se descartó: el stemmer junta «tarda» y «tarde»,
y «aprueba» no coincide con el lema «aprobar».
"""
from __future__ import annotations

from ipsis.lenguaje.texto import terminos

PALABRAS_CORTA = 3


def motivo_aclaracion(pregunta: str, paquete, estadisticas=None, candidatos=()) -> str | None:
    """``"sin_tema"``, ``"pronombre"``, ``"varios_documentos"``, ``"tema_desconocido"`` o ``None``."""
    if paquete is None:
        return None
    from ipsis.lenguaje.consultas import comprender, plano, terminos_de_contenido, terminos_genericos

    relacion = comprender(pregunta, paquete).terminos_relacion
    genericos = terminos_genericos(paquete)
    contenido = list(dict.fromkeys(
        t for t in terminos_de_contenido(pregunta, paquete, estadisticas, sin_genericas=False)
        if t not in relacion and t not in genericos))
    if not contenido:
        return "sin_tema"
    if len(contenido) > 1:
        return None
    palabras = plano(pregunta).split()
    pronombres = {plano(p) for p in getattr(paquete, "pronombres_anaforicos", ()) or ()}
    if pronombres.intersection(palabras):
        return "pronombre"
    if len(palabras) > PALABRAS_CORTA:
        return None
    documentos = {c.chunk.doc_id for c in candidatos if contenido[0] in terminos(c.chunk.texto_fuente, paquete)}
    if len(documentos) >= 2 or (not documentos and len(palabras) > 1):
        # Sin documentos y de una palabra («¿Bitcoin?») decide la política: fuera de dominio.
        return "varios_documentos" if documentos else "tema_desconocido"
    return None


__all__ = ["PALABRAS_CORTA", "motivo_aclaracion"]
