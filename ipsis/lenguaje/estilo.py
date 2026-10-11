"""¿La pregunta está escrita de manera coloquial?

Solo mira la forma de escribir, nunca el vocabulario ni los documentos: empieza
en minúscula (en español, además, sin «¿») o trae una abreviatura informal del
paquete («q», «pa», «pra», «u», «ur»). Quien escribe así suele usar palabras que
los documentos no usan, y el filtro de foco le cuesta respuestas correctas: la
política relaja el foco para estas preguntas cuando el lector está casi seguro
(``ipsis.consulta.etapas.politica.foco_exigido``).
"""
from __future__ import annotations

import re

_PALABRA = re.compile(r"[^\W\d_]+")


def es_coloquial(pregunta: str, paquete) -> bool:
    texto = (pregunta or "").strip()
    if not texto or paquete is None:
        return False
    primera = next((c for c in texto if c.isalpha() or c in "¿¡"), "")
    abrevia = set(getattr(paquete, "abreviaturas_informales", ()) or ())
    if abrevia and any(p in abrevia for p in _PALABRA.findall(texto.lower())):
        return True
    if not primera or not primera.isalpha() or not primera.islower():
        return False
    # En español la pregunta formal abre con «¿»; empezar con minúscula y sin él es apurado.
    return getattr(paquete, "codigo", "").split("-")[0] != "es" or "¿" not in texto


__all__ = ["es_coloquial"]
