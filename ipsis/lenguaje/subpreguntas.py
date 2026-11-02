"""División determinista de un mensaje con varias preguntas.

Un mensaje como «¿cuánto cuesta el P1? ¿y cuánto dura la garantía?» se buscaba entero: un solo vector, un solo ranking,
y un tema tapaba al otro. Aquí se decide **si hay más de una pregunta** y **dónde cortar**; el motor busca cada una por
separado y la interfaz las muestra agrupadas (ADR 0014).

Dos señales, de la más segura a la menos segura:

1. **Signos de interrogación.** Cada pieza que termina en ``?`` es una pregunta. Es puntuación, no vocabulario: vale para
   todo idioma y no necesita paquete. Lo que no es pregunta (un saludo, «gracias») se pega a la pregunta que sigue o,
   si va al final, a la última.
2. **Una pregunta que arranca dentro de otra**, sin signo propio: «¿cuánto cuesta el P1 y cuánto cuesta el P2?». Solo
   se corta antes de una palabra interrogativa del idioma, precedida de un enlace («y», «además») o de una coma, y solo
   si **las dos mitades** tienen contenido suficiente para buscarse solas. «¿Cómo y cuándo se paga?» o «¿qué es X y cómo
   se usa?» no se cortan: una mitad quedaría sin tema.

Ninguna palabra vive aquí. Las interrogativas, los enlaces y las expresiones de cortesía salen del paquete de idioma
(``varias_preguntas`` y ``conversacional`` en ``ipsis/recursos/idiomas/<idioma>.yaml``). Un idioma sin paquete solo usa
la primera señal.

No inventa texto ni reescribe: cada parte es un tramo de lo que escribió la persona. Dividir de nuevo una parte devuelve
la misma parte, y un mensaje con una sola pregunta se devuelve intacto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ipsis.lenguaje.texto import normalizar

# Contenido mínimo (términos que no son stopwords ni genéricos) para que una pieza se busque sola.
MIN_TERMINOS_PREGUNTA = 1  # separada por el signo de interrogación: la persona ya las separó
MIN_TERMINOS_UNION = 2  # separada solo por una palabra interrogativa: hay que estar seguro de que no es un sujeto elíptico

_CIERRES = ("?", "？")
_CORTE_SIGNOS = re.compile(r"(?<=[?？])|(?=¿)")
_PALABRA = re.compile(r"\w+")
_RECORTE = " \t\r\n,;:"


@dataclass(frozen=True)
class Division:
    """Las preguntas buscadas y, si hubo más que el tope, las que quedaron sin buscar."""

    partes: tuple[str, ...]
    omitidas: tuple[str, ...] = ()

    @property
    def multiple(self) -> bool:
        return len(self.partes) > 1


def _plano(palabra: str) -> str:
    return normalizar(palabra.casefold())


def _secuencias(valores) -> list[tuple[str, ...]]:
    """Expresiones del paquete como tuplas de palabras sin tildes, las más largas primero."""
    salida = {tuple(_plano(p) for p in _PALABRA.findall(str(v))) for v in valores or ()}
    return sorted((s for s in salida if s), key=lambda s: (-len(s), s))


def _coincide(palabras: list[str], i: int, secuencias: list[tuple[str, ...]]) -> int:
    """Largo de la expresión que empieza en ``palabras[i]`` (0 si ninguna)."""
    for s in secuencias:
        if tuple(palabras[i:i + len(s)]) == s:
            return len(s)
    return 0


def _terminos_propios(texto: str, paquete) -> int:
    """Cuántos términos de contenido tiene ``texto``: sin stopwords ni palabras genéricas del idioma."""
    from ipsis.lenguaje.lexico import terminos_pregunta
    from ipsis.lenguaje.lexico_base import terminos_genericos

    # Un objeto de idioma parcial (pruebas, respaldo) cuenta todas las palabras.
    completo = paquete if hasattr(paquete, "stopwords") else None
    return len(set(terminos_pregunta(texto, completo)) - set(terminos_genericos(paquete)))


def _es_cortesia(texto: str, paquete) -> bool:
    """Saludo, agradecimiento o despedida completos: no son una pregunta ni aportan tema."""
    limpio = texto.strip().strip("¡!¿?.,;: ")
    patrones = getattr(getattr(paquete, "conversacional", None), "patrones", None) or {}
    return bool(limpio) and any(re.fullmatch(p, limpio, re.IGNORECASE)
                                for categoria in ("greeting", "thanks", "farewell") for p in patrones.get(categoria, []))


def _preguntas_por_signos(texto: str, paquete) -> list[str]:
    """Las piezas que terminan en un signo de cierre, con lo demás pegado a la pregunta vecina."""
    piezas = [p.strip() for p in _CORTE_SIGNOS.split(texto) if p and p.strip()]
    preguntas: list[str] = []
    pendiente = ""
    for pieza in piezas:
        if pieza.endswith(_CIERRES):
            preguntas.append(f"{pendiente} {pieza}".strip())
            pendiente = ""
        elif _es_cortesia(pieza, paquete):
            continue
        else:
            pendiente = f"{pendiente} {pieza}".strip()
    if pendiente:
        if preguntas:
            preguntas[-1] = f"{preguntas[-1]} {pendiente}"
        else:
            preguntas.append(pendiente)
    # Una pieza sin tema propio («¿ok?») no es una pregunta: se une a la anterior (o a la siguiente si va primera).
    fusionadas: list[str] = []
    suelta = ""
    for pregunta in preguntas:
        pregunta = f"{suelta} {pregunta}".strip()
        if _terminos_propios(pregunta, paquete) < MIN_TERMINOS_PREGUNTA:
            if fusionadas:
                fusionadas[-1] = f"{fusionadas[-1]} {pregunta}"
                suelta = ""
            else:
                suelta = pregunta
            continue
        fusionadas.append(pregunta)
        suelta = ""
    if suelta:
        fusionadas.append(suelta)
    return fusionadas


def _cortar_por_interrogativas(texto: str, paquete) -> list[str]:
    """Corta una pregunta que contiene otra: «… y cuánto cuesta el P2». ``[texto]`` si no hay un corte seguro."""
    datos = getattr(paquete, "varias_preguntas", None)
    interrogativos = _secuencias(getattr(datos, "interrogativos", None))
    if not interrogativos:
        return [texto]
    enlaces = _secuencias(getattr(datos, "enlaces", None))
    marcas = list(_PALABRA.finditer(texto))
    palabras = [_plano(m.group()) for m in marcas]
    i = 1
    while i < len(palabras):
        largo = _coincide(palabras, i, interrogativos)
        if not largo:
            i += 1
            continue
        # El enlace («y», «además») que precede a la interrogativa; sin él, debe haber una coma o un punto y coma.
        inicio_corte, enlace = i, 0
        for secuencia in enlaces:
            if i - len(secuencia) >= 0 and tuple(palabras[i - len(secuencia):i]) == secuencia:
                enlace = len(secuencia)
                break
        if enlace:
            inicio_corte = i - enlace
        entre = texto[marcas[i - 1].end():marcas[i].start()]
        if not enlace and not re.search(r"[,;]", entre):
            i += largo
            continue
        izquierda = texto[:marcas[inicio_corte].start()].rstrip(_RECORTE)
        derecha = texto[marcas[i].start():]
        izq_palabras = palabras[:inicio_corte]
        tiene_interrogativa = any(_coincide(izq_palabras, k, interrogativos) for k in range(len(izq_palabras)))
        if (tiene_interrogativa and _terminos_propios(izquierda, paquete) >= MIN_TERMINOS_UNION
                and _terminos_propios(derecha, paquete) >= MIN_TERMINOS_UNION):
            abre = texto.lstrip().startswith("¿")
            cierra = texto.rstrip().endswith(_CIERRES)
            izquierda = izquierda + ("?" if cierra else "")
            derecha = ("¿" if abre and not derecha.startswith("¿") else "") + derecha
            return [izquierda] + _cortar_por_interrogativas(derecha, paquete)
        i += largo
    return [texto]


def _titulo(parte: str, paquete, *, quitar_enlace: bool) -> str:
    """La parte tal como se muestra y se guarda: sin el enlace que la unía a la anterior («¿Y cuánto…?») y con mayúscula."""
    parte = " ".join(parte.split())
    enlaces = _secuencias(getattr(getattr(paquete, "varias_preguntas", None), "enlaces", None))
    if quitar_enlace and enlaces:
        marcas = list(_PALABRA.finditer(parte))
        largo = _coincide([_plano(m.group()) for m in marcas], 0, enlaces)
        # Solo un enlace suelto («Y cuánto…»): «E-mail» o «Y2K» no empiezan con un «y/e» que quitar.
        if largo and len(marcas) > largo and parte[marcas[largo - 1].end():marcas[largo - 1].end() + 1].isspace():
            sin_enlace = ("¿" if parte.startswith("¿") else "") + parte[marcas[largo].start():]
            if _terminos_propios(sin_enlace, paquete) >= MIN_TERMINOS_PREGUNTA:
                parte = sin_enlace
    for i, c in enumerate(parte):
        if c.isalpha():
            return parte[:i] + c.upper() + parte[i + 1:]
    return parte


def dividir(pregunta: str, paquete=None, *, maximo: int = 3, unir: bool = True) -> Division:
    """Las preguntas de ``pregunta``: una sola (intacta) si no hay un corte seguro.

    ``maximo`` limita cuántas se buscan; el resto va a ``omitidas``, para que la interfaz lo diga en vez de perderlas
    en silencio. ``unir=False`` desactiva el corte por palabra interrogativa y deja solo los signos de interrogación.
    """
    normalizada = " ".join(str(pregunta).split())
    if maximo < 2 or not normalizada:
        return Division((normalizada,))
    piezas = _preguntas_por_signos(normalizada, paquete)
    if len(piezas) < 2:
        piezas = [normalizada]
    if unir:
        piezas = [parte for pieza in piezas for parte in _cortar_por_interrogativas(pieza, paquete)]
    if len(piezas) < 2:
        return Division((normalizada,))
    piezas = [_titulo(p, paquete, quitar_enlace=i > 0) for i, p in enumerate(piezas)]
    return Division(tuple(piezas[:maximo]), tuple(piezas[maximo:]))


__all__ = ["Division", "MIN_TERMINOS_PREGUNTA", "MIN_TERMINOS_UNION", "dividir"]
