"""Comprensión determinista de la consulta: qué relación se pregunta y sobre qué.

En «¿cuándo empieza la compra?» se pregunta por el **inicio** (la relación)
de la **compra** (el tema). La recuperación y la selección léxica tratan las
dos partes igual, y eso falla de dos maneras:

- «empieza» no suele estar en la oración que responde («Una vez aprobado el
  formulario, se realizará la compra»): cuenta como término ausente del
  corpus, baja la cobertura y la respuesta queda en «relacionado»;
- entre muchas oraciones que hablan de la compra, nada favorece a la que dice
  *cuándo*.

Cada paquete de idioma declara sus intenciones (``intenciones`` en
``ipsis/recursos/idiomas/<idioma>.yaml``): patrones que las reconocen en la
pregunta y pistas que suelen aparecer en la oración que responde («una vez»,
«después de»). Con eso:

- las palabras de la relación no cuentan como contenido de la pregunta
  (``terminos_de_contenido``);
- entre oraciones que ya comparten tema con la pregunta, la que contiene una
  pista sube (``BONO_PISTA``), en la selección y en la ventana del lector QA.

No reescribe la pregunta ni inventa texto: la consulta original sigue siendo
la que se busca y la que se responde. Los patrones y las pistas se escriben
en minúsculas y sin tildes; se comparan como palabras completas.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Una oración que comparte tema con la pregunta y empieza con una pista de la
# intención («Una vez aprobado…») vale el doble en la selección; con la pista
# más adentro («…antes de emitir la orden»), la mitad de eso.
BONO_PISTA = 1.0
PALABRAS_INICIO = 4


@dataclass(frozen=True)
class Comprension:
    intencion: str | None = None
    relacion: str = ""  # el texto de la pregunta que la reconoció
    terminos_relacion: frozenset[str] = field(default_factory=frozenset)  # stems
    pistas: tuple[str, ...] = ()


def plano(texto: str) -> str:
    """Minúsculas, sin tildes ni signos, espacios simples: la forma en que se comparan."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", sin_tildes.lower()).split())


def _como_palabras(patron: str) -> str:
    return rf"(?<!\w)(?:{patron})(?!\w)"


def comprender(pregunta: str, paquete) -> Comprension:
    """La primera intención del paquete cuyo patrón aparece en la pregunta."""
    intenciones = getattr(paquete, "intenciones", None) or {}
    texto = plano(pregunta)
    for nombre, intencion in intenciones.items():
        for patron in intencion.patrones:
            encontrado = re.search(_como_palabras(patron), texto)
            if encontrado:
                from ipsis.lenguaje.texto import terminos

                # Solo las palabras escritas en los patrones son de la relación: en
                # «when does the purchase start» el patrón abarca «the purchase»,
                # que es el tema y no se quita.
                vocabulario = {p for patron_i in intencion.patrones for p in re.findall(r"[a-z]+", patron_i)}
                relacion = " ".join(p for p in encontrado.group(0).split() if p in vocabulario)
                return Comprension(
                    intencion=nombre,
                    relacion=encontrado.group(0),
                    terminos_relacion=frozenset(terminos(relacion, paquete)) if relacion else frozenset(),
                    pistas=tuple(plano(p) for p in intencion.pistas),
                )
    return Comprension()


def terminos_de_contenido(pregunta: str, paquete, estadisticas=None) -> list[str]:
    """Los términos de contenido de la pregunta sin las palabras de su relación
    que no están en el corpus («empieza» en «¿cuándo empieza la compra?»: la
    respuesta dice «Una vez aprobado…»). Una palabra de la relación que sí está
    («até» en «Até quando posso pedir o reembolso?» y en su respuesta) se queda:
    ayuda a la cobertura. Sin ``estadisticas`` se quitan todas. Si la relación
    fuera todo lo que hay, se dejan los términos completos."""
    from ipsis.lenguaje.lexico import terminos_pregunta

    tq = terminos_pregunta(pregunta, paquete)
    relacion = comprender(pregunta, paquete).terminos_relacion
    df = getattr(estadisticas, "df", None)
    quitar = {t for t in relacion if df is None or df.get(t, 0) == 0}
    sin_relacion = [t for t in tq if t not in quitar]
    return sin_relacion or tq


def peso_pista(texto: str, comprension: Comprension) -> float:
    """1 si la oración empieza con una pista de la intención (en sus primeras
    ``PALABRAS_INICIO`` palabras), 0,5 si la tiene más adentro, 0 si no tiene."""
    if not comprension.pistas:
        return 0.0
    texto = plano(texto)
    inicio = " ".join(texto.split()[:PALABRAS_INICIO])
    patrones = [_como_palabras(re.escape(p)) for p in comprension.pistas]
    if any(re.search(p, inicio) for p in patrones):
        return 1.0
    return 0.5 if any(re.search(p, texto) for p in patrones) else 0.0


def tiene_pista(texto: str, comprension: Comprension) -> bool:
    return peso_pista(texto, comprension) > 0


__all__ = ["BONO_PISTA", "Comprension", "comprender", "peso_pista", "plano", "terminos_de_contenido", "tiene_pista"]
