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
from collections import OrderedDict
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


def terminos_de_contenido(pregunta: str, paquete, estadisticas=None, *, sin_genericas: bool = True) -> list[str]:
    """Los términos de contenido de la pregunta sin las palabras de su relación
    que no están en el corpus («empieza» en «¿cuándo empieza la compra?»: la
    respuesta dice «Una vez aprobado…»). Una palabra de la relación que sí está
    («até» en «Até quando posso pedir o reembolso?» y en su respuesta) se queda:
    ayuda a la cobertura. Sin ``estadisticas`` se quitan todas. Si la relación
    fuera todo lo que hay, se dejan los términos completos.

    Memoizado: la selección lo pide para cada oración que puntúa, con la misma
    pregunta, paquete y estadísticas."""
    df = getattr(estadisticas, "df", None)
    clave = (pregunta, id(paquete), id(estadisticas), id(df), len(df) if df is not None else -1, sin_genericas)
    if clave in _CONTENIDO:
        _CONTENIDO.move_to_end(clave)
        return list(_CONTENIDO[clave][1])
    salida = _terminos_de_contenido(pregunta, paquete, estadisticas, sin_genericas)
    # Guarda paquete y estadísticas junto al resultado para que sus id no se reutilicen.
    _CONTENIDO[clave] = ((paquete, estadisticas), tuple(salida))
    if len(_CONTENIDO) > 64:
        _CONTENIDO.popitem(last=False)
    return salida


_CONTENIDO: OrderedDict = OrderedDict()


def _terminos_de_contenido(pregunta: str, paquete, estadisticas, sin_genericas: bool) -> list[str]:
    from ipsis.lenguaje.lexico import terminos_pregunta

    tq = terminos_pregunta(pregunta, paquete)
    sinonimos = sinonimos_presentes(pregunta, paquete, estadisticas) if estadisticas is not None else {}
    if sinonimos:
        # «necesita» no está y «requieren» sí: cuenta el sinónimo, no la ausencia.
        from ipsis.lenguaje.texto import terminos

        reemplazos = {terminos(p, paquete)[0]: [r for f in formas for r in terminos(f, paquete)]
                      for p, formas in sinonimos.items()}
        tq = list(dict.fromkeys(r for t in tq for r in reemplazos.get(t, [t])))
    relacion = comprender(pregunta, paquete).terminos_relacion
    df = getattr(estadisticas, "df", None)
    quitar = {t for t in relacion if df is None or df.get(t, 0) == 0}
    sin_relacion = [t for t in tq if t not in quitar]
    if not sin_genericas:
        return sin_relacion or tq
    # «hace» en «¿desde cuándo se hace la compra?» no es contenido: con IDF alto
    # llevaba a «Para hacer un reclamo…» por encima de las oraciones de la compra.
    # Para ``s_oov`` y ``s_cov`` se dejan (``sin_genericas=False``): sin «meses», lo
    # ausente del corpus pesaría más de lo que pesa en la pregunta.
    genericos = terminos_genericos(paquete)
    return [t for t in sin_relacion if t not in genericos] or sin_relacion or tq


def sinonimos_presentes(pregunta: str, paquete, estadisticas) -> dict[str, list[str]]:
    """Para cada palabra de la pregunta que no está en el corpus («necesita»), las
    formas de sus sinónimos que sí están («requieren»), según los grupos del
    paquete (``sinonimos``). Una palabra que ya está en el corpus nunca se toca, y
    tampoco las de la relación («empieza» en «¿cuándo empieza la compra?»): de
    esas se encargan las pistas, y «inicia» traería oraciones de otro tema."""
    grupos = _grupos_por_raiz(paquete)
    df = getattr(estadisticas, "df", None)
    if not grupos or df is None:
        return {}
    # La misma pregunta se mide en cada oración que se puntúa: se calcula una vez.
    clave = (pregunta, id(paquete), id(df), len(df))
    if clave in _PRESENTES:
        _PRESENTES.move_to_end(clave)
        return {k: list(v) for k, v in _PRESENTES[clave][1].items()}
    salida = _sinonimos_presentes(pregunta, paquete, grupos, df)
    _PRESENTES[clave] = ((paquete, df), salida)
    if len(_PRESENTES) > 64:
        _PRESENTES.popitem(last=False)
    return {k: list(v) for k, v in salida.items()}


# Guarda el paquete y el df junto al resultado para que sus id no se reutilicen.
_PRESENTES: OrderedDict = OrderedDict()


def _sinonimos_presentes(pregunta, paquete, grupos, df) -> dict[str, list[str]]:
    from ipsis.lenguaje.lexico import terminos_pregunta
    from ipsis.lenguaje.texto import terminos

    contenido = set(terminos_pregunta(pregunta, paquete)) - comprender(pregunta, paquete).terminos_relacion
    salida: dict[str, list[str]] = {}
    for palabra in plano(pregunta).split():
        raices = terminos(palabra, paquete)
        if len(raices) != 1 or raices[0] not in contenido or df.get(raices[0], 0) > 0:
            continue
        presentes = [f for grupo in grupos.get(raices[0], ()) for f, rs in grupo
                     if any(df.get(r, 0) > 0 for r in rs)]
        if presentes:
            salida[palabra] = list(dict.fromkeys(presentes))
    return salida


def terminos_genericos(paquete) -> frozenset[str]:
    """Los términos (stems) de ``genericas`` del paquete: nunca son foco."""
    palabras = getattr(paquete, "genericas", None) or []
    if not palabras:
        return frozenset()
    guardado = _GENERICOS.get(id(paquete))
    if guardado is not None and guardado[0] is paquete:
        return guardado[1]
    from ipsis.lenguaje.texto import terminos

    salida = frozenset(r for p in palabras for r in terminos(plano(p), paquete))
    _GENERICOS[id(paquete)] = (paquete, salida)
    return salida


_GENERICOS: dict[int, tuple[object, frozenset[str]]] = {}


def equivalentes(terminos_oracion: list[str], paquete) -> list[str]:
    """Los términos de la oración más lo que equivale a ellos, para ver si un término
    foco está:

    - su raíz sin sufijo derivado: «Who signs the Resolution?» se responde con
      «…for signature» («signatur» → «sign»; la raíz que queda tiene 3 letras o más);
    - las raíces de su grupo de sinónimos: «Above what amount do you need a
      Resolution?» se responde con «…require a Resolution» («need» sí está en el
      corpus, en otra acepción, así que la pregunta no se expande)."""
    sufijos = getattr(paquete, "sufijos_derivados", None) or []
    extra = [t[: -len(s)] for t in terminos_oracion for s in sufijos
             if t.endswith(s) and len(t) - len(s) >= 3]
    grupos = _grupos_por_raiz(paquete)
    extra += [r for t in terminos_oracion for grupo in grupos.get(t, ()) for _, rs in grupo for r in rs]
    return terminos_oracion + extra


# id(paquete) → (paquete, raíz → grupos de (forma, raíces)): se calcula una vez por paquete,
# no en cada oración que se puntúa. Guarda el paquete para que su id no se reutilice.
_GRUPOS: dict[int, tuple[object, dict[str, list[list[tuple[str, tuple[str, ...]]]]]]] = {}


def _grupos_por_raiz(paquete) -> dict[str, list[list[tuple[str, tuple[str, ...]]]]]:
    grupos = getattr(paquete, "sinonimos", None) or []
    if not grupos:
        return {}
    guardado = _GRUPOS.get(id(paquete))
    if guardado is not None and guardado[0] is paquete:
        return guardado[1]
    from ipsis.lenguaje.texto import terminos

    por_raiz: dict[str, list[list[tuple[str, tuple[str, ...]]]]] = {}
    for grupo in grupos:
        formas = [(plano(f), tuple(terminos(plano(f), paquete))) for f in grupo]
        for raiz in {r for _, rs in formas for r in rs}:
            por_raiz.setdefault(raiz, []).append(formas)
    _GRUPOS[id(paquete)] = (paquete, por_raiz)
    return por_raiz


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


__all__ = ["BONO_PISTA", "Comprension", "comprender", "peso_pista", "plano", "sinonimos_presentes",
           "equivalentes", "terminos_de_contenido", "terminos_genericos", "tiene_pista"]
