"""Alias que el propio corpus define: siglas, glosario y «en adelante».

Un reglamento escribe «Práctica Profesional I (P1): primera práctica profesional del
plan…» y después solo dice «la P1»; quien pregunta dice «la primera práctica». Al indexar
se extraen esos grupos de nombres equivalentes de cada corpus (nunca de una lista escrita
a mano), y al consultar sirven para buscar con todas las formas y para reconocer en la
oración o en el título de su sección («Evaluación de la P1») lo que la pregunta nombró de
otra manera.

Los ordinales (clase cerrada por idioma, ``ordinales`` del paquete) se normalizan a
«#n»: «primera» = «I» = «1». Si la pregunta trae un ordinal junto a un término de un
grupo («tercera práctica») y la oración habla de otro ordinal, no es lo preguntado.
"""
from __future__ import annotations

import re

from ipsis.lenguaje.texto import terminos

ROMANOS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
# Ordinales del paquete que no numeran un elemento de una serie («last Monday» usa 5 para «último»).
NO_SERIALES = {"last", "ultimo", "ultima", "último", "última", "ultimo"}


def _ordinales(paquete) -> dict[str, int]:
    return {k: v for k, v in (getattr(paquete, "ordinales", None) or {}).items() if k.lower() not in NO_SERIALES}
_PALABRA = re.compile(r"[^\W_]+")
# «Nombre Largo (SIGLA)»: la sigla en mayúsculas (y dígitos), el nombre con mayúscula inicial.
_SIGLA = re.compile(r"([A-ZÁÉÍÓÚÑÇ][^()\n:;.,]{2,80}?)\s+\(([A-Z][A-Z0-9]{1,7})\)")
_ADELANTE = {"es": r"en adelante,?\s+(?:el|la|los|las)\s+([A-ZÁÉÍÓÚÑ]\w+)",
             "en": r"hereinafter,?\s+(?:the\s+)?([A-Z]\w+)",
             "pt": r"doravante,?\s+(?:o|a|os|as)\s+([A-ZÁÉÍÓÚÇ]\w+)"}
_CORTE_DEFINICION = {"es": r",|\.|;|:|\s(?:que|en el que|en la que|el cual|la cual)\s",
                     "en": r",|\.|;|:|\s(?:which|that|in which|who)\s",
                     "pt": r",|\.|;|:|\s(?:que|em que|no qual|na qual)\s"}


_DEFINICION = re.compile(r"^\s*[A-ZÁÉÍÓÚÑÇ][^:\n]{1,80}\([A-Z][A-Z0-9]{1,7}\)\s*:")


def es_definicion(linea: str) -> bool:
    """«Práctica Profesional I (P1): primera práctica…»: la línea del glosario que define
    un término. Nombra el término con todas sus formas y por eso atrae a cualquier pregunta
    sobre él, pero solo responde «¿qué es la P1?»."""
    return bool(_DEFINICION.match(linea or ""))


def pide_definicion(pregunta: str, paquete) -> bool:
    from ipsis.lenguaje.consultas import plano

    texto = " " + plano(pregunta or "").lower().strip(" ¿?¡!")
    return any(re.search(p, texto.strip()) or re.search(p, texto) for p in
               getattr(paquete, "patrones_definicion", None) or [])


def _idioma(paquete) -> str:
    return (getattr(paquete, "codigo", "") or "").split("-")[0]


def _limpiar_nombre(nombre: str) -> str:
    """Sin las palabras en minúscula que la expresión arrastra al inicio («de Módulo…»)."""
    palabras = nombre.split()
    while palabras and not palabras[0][:1].isupper():
        palabras.pop(0)
    return " ".join(palabras)


def bolsa(texto: str, paquete) -> frozenset[str]:
    """Raíces de contenido de un texto; ordinales y números romanos como «#n»."""
    ordinales = _ordinales(paquete)
    stop = set(getattr(paquete, "stopwords", ()) or ())
    salida: set[str] = set()
    for palabra in _PALABRA.findall(texto or ""):
        baja = palabra.lower()
        if baja in ordinales:
            salida.add(f"#{ordinales[baja]}")
        elif palabra in ROMANOS:
            salida.add(f"#{ROMANOS[palabra]}")
        elif baja not in stop and not palabra.isdigit():
            salida.update(terminos(baja, paquete)[:1])
    return frozenset(salida)


def extraer_alias(textos, paquete) -> list[list[str]]:
    """Grupos de formas equivalentes que el corpus define, unidos por sigla."""
    idioma = _idioma(paquete)
    adelante = _ADELANTE.get(idioma)
    corte = _CORTE_DEFINICION.get(idioma, r",|\.|;|:")
    por_sigla: dict[str, set[str]] = {}
    for texto in textos:
        for linea in (texto or "").splitlines():
            for m in _SIGLA.finditer(linea):
                nombre, sigla = _limpiar_nombre(m.group(1).strip()), m.group(2)
                if len(bolsa(nombre, paquete) - {"#1", "#2", "#3", "#4", "#5", "#6"}) == 0:
                    continue
                formas = por_sigla.setdefault(sigla, {sigla})
                formas.add(nombre)
                resto = linea[m.end():]
                if resto.startswith(":"):  # glosario: «Término (SIGLA): definición…»
                    definicion = re.split(corte, resto[1:].strip(), maxsplit=1)[0].strip()
                    # Solo una definición nominal corta y específica: «primera práctica profesional
                    # del plan», nunca «unidad» o «académico de la Escuela» (una sola raíz genérica).
                    if 2 <= len(definicion.split()) <= 7 and len(bolsa(definicion, paquete)) >= 3:
                        formas.add(definicion)
                if adelante:
                    m_adelante = re.search(adelante, linea[m.start():])
                    if m_adelante:
                        formas.add(m_adelante.group(1))
    return [sorted(f) for _, f in sorted(por_sigla.items()) if len(f) >= 2]


class Alias:
    """Grupos de un corpus listos para consultar."""

    def __init__(self, grupos: list[list[str]], paquete) -> None:
        self.paquete = paquete
        self.grupos = [list(g) for g in grupos]
        self.siglas = [{f for f in g if f.isupper() or re.fullmatch(r"[A-Z][A-Z0-9]+", f)} for g in self.grupos]
        # Formas de dos raíces o más (las de una sola, como «Sistema», solo cuentan en la oración).
        self.bolsas = [[bolsa(f, paquete) for f in g if f not in s] for g, s in zip(self.grupos, self.siglas)]
        self.raices = [frozenset().union(*b) if b else frozenset() for b in self.bolsas]
        self.cabezas = frozenset().union(*(r for r in self.raices)) - {f"#{n}" for n in range(1, 10)} \
            if self.raices else frozenset()

    def _ordinal(self, raices: frozenset[str]) -> set[str]:
        return {r for r in raices if r.startswith("#")}

    def mencionados(self, pregunta: str) -> list[int]:
        """Grupos que la pregunta nombra: por sigla («P2»); con una forma que tiene ordinal, el
        mismo ordinal y otra raíz («primera práctica» → «Práctica Profesional I»); sin ordinal,
        dos raíces («coordinación de prácticas»); o el referente que el corpus definió con «en
        adelante» («el Comité»)."""
        palabras = set(_PALABRA.findall(pregunta or ""))
        q = bolsa(pregunta, self.paquete) | self.ordinales_ligados(pregunta)
        orden_q = self._ordinal(q)
        salida = []
        for i, (siglas, bolsas) in enumerate(zip(self.siglas, self.bolsas)):
            if siglas & palabras:
                salida.append(i)
                continue
            for b in bolsas:
                comun, orden_b = b & q, self._ordinal(b)
                if orden_b:
                    nombra = orden_b == orden_q and len(comun - orden_b) >= 1
                else:
                    nombra = len(comun) >= 2 or (len(b) == 1 and comun == b)
                if nombra:
                    salida.append(i)
                    break
        return salida

    def presentes(self, texto: str) -> list[int]:
        """Grupos que el texto (oración, título de sección) nombra con alguna de sus formas."""
        palabras = set(_PALABRA.findall(texto or ""))
        t = bolsa(texto, self.paquete)
        salida = []
        for i, (grupo, siglas) in enumerate(zip(self.grupos, self.siglas)):
            if siglas & palabras or any(
                    len(b) >= 1 and b <= t for b in (bolsa(f, self.paquete) for f in grupo if f not in siglas)):
                salida.append(i)
        return salida

    def ordinales_ligados(self, texto: str) -> set[str]:
        """Ordinales del texto pegados a un término de algún grupo («tercera práctica»,
        «práctica 1»): los de «la primera semana» no cuentan."""
        ordinales = _ordinales(self.paquete)
        palabras = _PALABRA.findall(texto or "")
        salida = set()
        for i, palabra in enumerate(palabras):
            baja = palabra.lower()
            n = ordinales.get(baja) or ROMANOS.get(palabra) or (int(palabra) if palabra.isdigit() and len(palabra) == 1
                                                                 else None)
            if not n:
                continue
            vecinas = [p for p in palabras[max(0, i - 3):i] + palabras[i + 1:i + 4]]
            if any(set(terminos(v.lower(), self.paquete)[:1]) & self.cabezas for v in vecinas):
                salida.add(f"#{n}")
        return salida

    def expansion(self, grupos: list[int]) -> list[str]:
        return [f for i in grupos for f in self.grupos[i]]


# id(estadísticas), id(paquete) → (estadísticas, paquete, Alias).
_CACHE: dict[tuple[int, int], tuple[object, object, Alias]] = {}


def alias_del_indice(estadisticas, paquete) -> Alias | None:
    """Los alias del índice abierto (``None`` si el índice no los trae)."""
    grupos = getattr(estadisticas, "alias", None)
    if not grupos or paquete is None:
        return None
    clave = (id(estadisticas), id(paquete))
    guardado = _CACHE.get(clave)
    if guardado is None or guardado[0] is not estadisticas or guardado[1] is not paquete:
        _CACHE.clear()
        guardado = (estadisticas, paquete, Alias(grupos, paquete))
        _CACHE[clave] = guardado
    return guardado[2]


__all__ = ["Alias", "alias_del_indice", "bolsa", "es_definicion", "extraer_alias", "pide_definicion"]
