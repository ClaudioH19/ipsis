"""Reglas deterministas de extracción de entidades.

Cada función de extracción recibe el texto de un chunk (o de una pregunta) y
devuelve una lista de entidades con offset **relativo al texto recibido**,
de modo que la validación "toda entidad debe encontrarse literalmente en
texto" sea directa: ``texto[offset:offset+len(texto_entidad)]``
debe ser igual a ``texto_entidad``.

Ninguna de estas reglas usa modelos: son regex + normalización de superficie.
El campo `valor_norm` es la forma canónica con la que se comparan entidades
entre pregunta, evidencia e inventario del índice — por eso es
intencionalmente literal y no requiere NLU.
"""
from __future__ import annotations

import functools
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from typing import Iterable

@dataclass(frozen=True)
class Entidad:
    tipo: str
    texto: str
    valor_norm: str
    offset: int

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# DECIMAL: "3,9", "2.5". Coma y punto normalizan igual ("3.9"), de modo que la
# pregunta y el documento coinciden aunque usen convenciones distintas. Los
# números con varios separadores ("1.000.000", "12.03.2024") no se toman
# como decimales: los lookarounds impiden recortar un trozo de ellos.
# Una escala propia (p.ej. notas de 1,0 a 7,0) se declara en el perfil.
# ---------------------------------------------------------------------------
_RE_DECIMAL = re.compile(r"(?<![\d.,])(\d{1,6})[,.](\d{1,3})(?![.,]?\d)")


def extraer_decimales(texto: str) -> list[Entidad]:
    out = []
    for m in _RE_DECIMAL.finditer(texto):
        valor = f"{m.group(1)}.{m.group(2)}"
        out.append(Entidad("decimal", m.group(0), valor, m.start(0)))
    return out


# ---------------------------------------------------------------------------
# PORCENTAJE
# ---------------------------------------------------------------------------
# El lookbehind impide que "12,5%" se lea como "5%": un porcentaje parcial
# respaldaría en falso una pregunta por otra cifra.
_RE_PORCENTAJE = re.compile(r"(?<![\d.,])(\d{1,3})(?:[,.](\d{1,3}))?\s?%")


def extraer_porcentajes(texto: str) -> list[Entidad]:
    out = []
    for m in _RE_PORCENTAJE.finditer(texto):
        numero = m.group(1) if m.group(2) is None else f"{m.group(1)}.{m.group(2)}"
        out.append(Entidad("porcentaje", m.group(0), f"{numero}_pct", m.start(0)))
    return out


# ---------------------------------------------------------------------------
# FECHA NUMÉRICA (universal): dd/mm/aaaa, dd-mm-aaaa, dd.mm.aaaa o aaaa-mm-dd.
# Se normaliza a ISO (aaaa-mm-dd) para comparar fechas escritas distinto.
# ---------------------------------------------------------------------------
_RE_FECHA_DMA = re.compile(r"(?<![\d/.-])(\d{1,2})([/.-])(\d{1,2})\2(\d{4})(?![\d/-]|\.\d)")
_RE_FECHA_ISO = re.compile(r"(?<![\d/.-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d/-]|\.\d)")


def _fecha_iso(anio: str, mes: str, dia: str) -> str | None:
    m, d = int(mes), int(dia)
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    return f"{anio}-{m:02d}-{d:02d}"


def extraer_fechas_numericas(texto: str) -> list[Entidad]:
    out = []
    for m in _RE_FECHA_DMA.finditer(texto):
        valor = _fecha_iso(m.group(4), m.group(3), m.group(1))
        if valor:
            out.append(Entidad("fecha", m.group(0), valor, m.start(0)))
    for m in _RE_FECHA_ISO.finditer(texto):
        valor = _fecha_iso(m.group(1), m.group(2), m.group(3))
        if valor:
            out.append(Entidad("fecha", m.group(0), valor, m.start(0)))
    return out


# ---------------------------------------------------------------------------
# MONTO (universal): número junto a un símbolo de moneda o a un código ISO
# 4217 frecuente. «12.500» y «12,500» con grupos de tres dígitos se leen como
# miles; cualquier otro separador, como decimal.
# ---------------------------------------------------------------------------
_CODIGOS_MONEDA = (
    "USD|EUR|GBP|JPY|CNY|CHF|CAD|AUD|CLP|CLF|ARS|MXN|COP|PEN|BRL|UYU|BOB|PYG"
)
_NUMERO = r"\d{1,3}(?:[.,\u00a0 ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_RE_MONTO_ANTES = re.compile(
    rf"(?:R\$|US\$|[$€£¥]|\b(?:{_CODIGOS_MONEDA})\b)\s?({_NUMERO})(?!\d|[.,]\d)"
)
_RE_MONTO_DESPUES = re.compile(rf"(?<![\d.,])({_NUMERO})\s?(?:[€£¥]|\b(?:{_CODIGOS_MONEDA})\b)")


def _normalizar_monto(numero: str) -> str:
    limpio = numero.replace("\u00a0", " ")
    if re.fullmatch(r"\d{1,3}(?:[., ]\d{3})+", limpio):
        return re.sub(r"[., ]", "", limpio)
    entero_decimal = re.fullmatch(r"(\d{1,3}(?:[., ]\d{3})+)([.,])(\d{1,2})", limpio)
    if entero_decimal:
        return re.sub(r"[., ]", "", entero_decimal.group(1)) + "." + entero_decimal.group(3)
    return limpio.replace(",", ".")


def extraer_montos(texto: str) -> list[Entidad]:
    out = []
    vistos: set[int] = set()
    for patron in (_RE_MONTO_ANTES, _RE_MONTO_DESPUES):
        for m in patron.finditer(texto):
            if m.start(0) in vistos:
                continue
            vistos.add(m.start(0))
            out.append(Entidad("monto", m.group(0), f"monto_{_normalizar_monto(m.group(1))}", m.start(0)))
    return out


# ---------------------------------------------------------------------------
# REGLAS DEL IDIOMA: plazos, fechas con nombres y referencias a partes del
# documento. La ESTRUCTURA es común (número + unidad, día + mes + año, palabra
# + número); las PALABRAS vienen del paquete de idioma. Así un idioma nuevo
# solo agrega listas al YAML, no código.
#
# valor_norm no depende del idioma:
#   plazo      30_dia, 5_dia_habiles, 2_semana
#   fecha      2024-03-15, --03-15 (sin año), 2_dow5_m01 (2.º viernes de enero)
#   referencia articulo_13, articulo_13_y_14 (lista), articulo_20_a_23 (rango)
# ---------------------------------------------------------------------------

_ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _romano_a_entero(texto: str) -> int | None:
    total, previo = 0, 0
    for c in reversed(texto.upper()):
        valor = _ROMANOS.get(c)
        if valor is None:
            return None
        total = total - valor if valor < previo else total + valor
        previo = max(previo, valor)
    return total or None


def _alternativas(palabras) -> str:
    """Alternancia regex, de la más larga a la más corta (para no recortar)."""
    unicas = sorted({p for p in palabras if p}, key=len, reverse=True)
    return "|".join(re.escape(p) for p in unicas) or r"(?!x)x"


def _inverso(mapa: dict[str, list[str]]) -> dict[str, str]:
    return {forma.casefold(): canon for canon, formas in mapa.items() for forma in formas}


@dataclass(frozen=True)
class _ReglasIdioma:
    numeros: dict[str, int]
    ordinales: dict[str, int]
    meses: dict[str, int]
    dias: dict[str, str]
    unidades: dict[str, str]
    calificadores: dict[str, str]
    referencias: dict[str, str]
    conectores_rango: dict[str, str]
    plazo: re.Pattern
    fecha_relativa: re.Pattern
    fecha_dia_mes: re.Pattern
    fecha_mes_dia: re.Pattern
    referencia: re.Pattern


@functools.lru_cache(maxsize=32)
def _compilar(clave: str) -> _ReglasIdioma:
    datos = json.loads(clave)
    numeros = {k.casefold(): v for k, v in datos["numeros"].items()}
    ordinales = {k.casefold(): v for k, v in datos["ordinales"].items()}
    meses = {m.casefold(): i for i, m in enumerate(datos["meses"], start=1)}
    dias = _inverso(datos["dias_semana"])
    unidades = _inverso(datos["unidades_tiempo"])
    calificadores = _inverso(datos["calificadores_plazo"])
    referencias = _inverso(datos["referencias_documento"])
    conectores_rango = _inverso(datos["conectores_rango"])
    con_fecha = _alternativas(datos["conectores_fecha"])
    con_relativa = _alternativas(datos["conectores_fecha_relativa"])

    numero = rf"(\d{{1,3}}|{_alternativas(numeros)})"
    calif = _alternativas(calificadores)
    mes = _alternativas(meses)
    anio = r"(\d{4})"
    dia = r"(\d{1,2})"
    flags = re.IGNORECASE
    return _ReglasIdioma(
        numeros=numeros, ordinales=ordinales, meses=meses, dias=dias, unidades=unidades,
        calificadores=calificadores, referencias=referencias, conectores_rango=conectores_rango,
        plazo=re.compile(
            rf"\b{numero}\s+(?:({calif})\s+)?({_alternativas(unidades)})(?:\s+({calif}))?\b", flags
        ),
        fecha_relativa=re.compile(
            rf"\b({_alternativas(ordinales)})\s+({_alternativas(dias)})\s+(?:(?:{con_relativa})\s+)?({mes})\b",
            flags,
        ),
        fecha_dia_mes=re.compile(
            rf"\b{dia}\s+(?:(?:{con_fecha})\s+)?({mes})(?:,?\s+(?:(?:{con_fecha})\s+)?{anio})?\b", flags
        ),
        fecha_mes_dia=re.compile(
            rf"\b({mes})\s+{dia}(?:st|nd|rd|th)?(?:,?\s+{anio})?\b", flags
        ),
        referencia=re.compile(
            rf"\b({_alternativas(referencias)})\s+(\d{{1,3}}|[IVXLC]+\b)"
            rf"(?:\s+({_alternativas(conectores_rango)})\s+(\d{{1,3}}))?\b",
            flags,
        ),
    )


def _reglas(paquete) -> _ReglasIdioma | None:
    if paquete is None:
        return None
    clave = json.dumps({
        "numeros": paquete.numeros, "ordinales": paquete.ordinales, "meses": paquete.meses,
        "dias_semana": paquete.dias_semana, "unidades_tiempo": paquete.unidades_tiempo,
        "calificadores_plazo": paquete.calificadores_plazo,
        "referencias_documento": paquete.referencias_documento,
        "conectores_rango": paquete.conectores_rango, "conectores_fecha": paquete.conectores_fecha,
        "conectores_fecha_relativa": paquete.conectores_fecha_relativa,
    }, sort_keys=True, ensure_ascii=False)
    return _compilar(clave)


def _numero(token: str, reglas: _ReglasIdioma) -> int | None:
    return int(token) if token.isdigit() else reglas.numeros.get(token.casefold())


def extraer_plazos(texto: str, paquete=None) -> list[Entidad]:
    reglas = _reglas(paquete if paquete is not None else idioma_activo())
    if reglas is None:
        return []
    out = []
    for m in reglas.plazo.finditer(texto):
        num = _numero(m.group(1), reglas)
        if num is None:
            continue
        valor = f"{num}_{reglas.unidades[m.group(3).casefold()]}"
        calif = m.group(2) or m.group(4)
        if calif:
            valor += f"_{reglas.calificadores[calif.casefold()]}"
        out.append(Entidad("plazo", m.group(0), valor, m.start(0)))
    return out


def extraer_fechas(texto: str, paquete=None) -> list[Entidad]:
    reglas = _reglas(paquete if paquete is not None else idioma_activo())
    if reglas is None:
        return []
    out = []
    for m in reglas.fecha_relativa.finditer(texto):
        ordinal = reglas.ordinales[m.group(1).casefold()]
        dia = reglas.dias[m.group(2).casefold()]
        mes = reglas.meses[m.group(3).casefold()]
        out.append(Entidad("fecha", m.group(0), f"{ordinal}_dow{dia}_m{mes:02d}", m.start(0)))
    ocupados = {e.offset for e in out}
    for patron, g_dia, g_mes, g_anio in ((reglas.fecha_dia_mes, 1, 2, 3), (reglas.fecha_mes_dia, 2, 1, 3)):
        for m in patron.finditer(texto):
            if m.start(0) in ocupados:
                continue
            dia, mes = int(m.group(g_dia)), reglas.meses[m.group(g_mes).casefold()]
            if not 1 <= dia <= 31:
                continue
            valor = f"{m.group(g_anio)}-{mes:02d}-{dia:02d}" if m.group(g_anio) else f"--{mes:02d}-{dia:02d}"
            out.append(Entidad("fecha", m.group(0), valor, m.start(0)))
            ocupados.add(m.start(0))
    return out


def extraer_articulos(texto: str, paquete=None) -> list[Entidad]:
    """Referencias a partes del documento: artículo, anexo, capítulo, etc."""
    reglas = _reglas(paquete if paquete is not None else idioma_activo())
    if reglas is None:
        return []
    out = []
    for m in reglas.referencia.finditer(texto):
        canon = reglas.referencias[m.group(1).casefold()]
        n1 = m.group(2)
        if not n1.isdigit():
            if _romano_a_entero(n1) is None or not n1.isupper():
                continue
            n1 = n1.lower()
        valor = f"{canon}_{n1}"
        if m.group(3) and m.group(4):
            valor += f"_{reglas.conectores_rango[m.group(3).casefold()]}_{m.group(4)}"
        out.append(Entidad("articulo", m.group(0), valor, m.start(0)))
    return out


# ---------------------------------------------------------------------------
# Idioma activo: igual que el perfil de dominio, se fija al arrancar
# (configurar_idioma) o por consulta (usar_idioma). Sin idioma activo solo
# corren las reglas universales.
# ---------------------------------------------------------------------------
_idioma_activo = None
_SIN_IDIOMA_CONTEXTUAL = object()
_idioma_contextual: ContextVar = ContextVar("rag_idioma_contextual", default=_SIN_IDIOMA_CONTEXTUAL)


def configurar_idioma(paquete) -> None:
    global _idioma_activo
    _idioma_activo = paquete


def idioma_activo():
    contextual = _idioma_contextual.get()
    return _idioma_activo if contextual is _SIN_IDIOMA_CONTEXTUAL else contextual


@contextmanager
def usar_idioma(paquete):
    token = _idioma_contextual.set(paquete)
    try:
        yield
    finally:
        _idioma_contextual.reset(token)


# ---------------------------------------------------------------------------
# Universales: no dependen del idioma.
EXTRACTORES = [
    extraer_decimales,
    extraer_porcentajes,
    extraer_fechas_numericas,
    extraer_montos,
]
# Dependen del paquete de idioma activo.
EXTRACTORES_IDIOMA = [
    extraer_plazos,
    extraer_fechas,
    extraer_articulos,
]

# Nombres de tipo que produce cada extractor GENERICO de arriba (mismo orden
# conceptual que EXTRACTORES, pero como nombres -- lo usa tipos_con_regla()
# para no hardcodear en ningun otro modulo cuales tipos vienen del nucleo).
TIPOS_GENERICOS = {"decimal", "porcentaje", "plazo", "fecha", "monto", "articulo"}


# ---------------------------------------------------------------------------
# Perfil de dominio activo: las entidades
# ESPECIFICAS de un dominio (saberes, organismos, practicas, semanas
# relativas... lo que antes eran extraer_saberes/extraer_semanas/
# extraer_organismos/extraer_practicas en este mismo modulo) ya NO viven
# aqui -- se declaran en configuracion/dominio.yaml y las interpreta
# ipsis/lenguaje/dominio.py. Este modulo solo necesita saber que existe un objeto con
# .extraer_entidades_extra(texto), configurado UNA VEZ al arrancar el
# proceso (la CLI de indexación y el arranque del servicio).
# Sin perfil configurado (None, el valor por defecto), extraer_entidades
# sigue funcionando con solo las reglas GENERICAS de arriba -- nunca falla
# por falta de perfil.
# ---------------------------------------------------------------------------
_perfil_activo = None
_SIN_PERFIL_CONTEXTUAL = object()
_perfil_contextual: ContextVar = ContextVar(
    "rag_perfil_contextual",
    default=_SIN_PERFIL_CONTEXTUAL,
)


def configurar_perfil(perfil) -> None:
    """Fija el perfil de dominio activo para todo el proceso. Se llama una
    sola vez al arrancar (nunca por peticion): la ingesta, el servicio y la
    CLI cargan su perfil con ipsis/lenguaje/dominio.py::cargar_perfil y lo registran
    aqui antes de procesar el primer documento o la primera consulta."""
    global _perfil_activo
    _perfil_activo = perfil


def perfil_activo():
    """El perfil configurado actualmente (o None si no se configuro
    ninguno)."""
    contextual = _perfil_contextual.get()
    return _perfil_activo if contextual is _SIN_PERFIL_CONTEXTUAL else contextual


@contextmanager
def usar_perfil(perfil):
    """Activa un perfil solo para la consulta/contexto actual."""
    token = _perfil_contextual.set(perfil)
    try:
        yield
    finally:
        _perfil_contextual.reset(token)


def tipos_con_regla() -> set[str]:
    """Tipos de entidad con una regla de extraccion DETERMINISTA disponible:
    los genericos del nucleo (TIPOS_GENERICOS, los que cubre EXTRACTORES) mas
    los que aporta el perfil de dominio activo, si hay uno configurado (ver
    ipsis/lenguaje/dominio.py::PerfilDominio.tipos_aportados). Sin perfil activo,
    devuelve solo los genericos -- nunca falla por falta de perfil, mismo
    criterio que extraer_entidades. Asi ningun modulo de evaluacion
    necesita conocer los tipos de un perfil en particular."""
    tipos = set(TIPOS_GENERICOS)
    perfil = perfil_activo()
    if perfil is not None:
        tipos |= perfil.tipos_aportados()
    return tipos


def extraer_entidades(texto: str) -> list[dict]:
    """Corre las reglas GENERICAS del nucleo mas las del perfil de dominio
    activo (si hay uno configurado, ver configurar_perfil), y devuelve
    entidades como dicts, ordenadas por offset.

    Garantiza la invariante de validacion de ingesta:
    texto[offset:offset+len(texto_ent)] == texto_ent para cada entidad.
    """
    entidades: list[Entidad] = []
    for extractor in EXTRACTORES:
        entidades.extend(extractor(texto))
    paquete = idioma_activo()
    if paquete is not None:
        for extractor in EXTRACTORES_IDIOMA:
            entidades.extend(extractor(texto, paquete))
    perfil = perfil_activo()
    if perfil is not None:
        entidades.extend(perfil.extraer_entidades_extra(texto))
    entidades.sort(key=lambda e: e.offset)
    # valida la invariante antes de devolver (falla temprano si una regla se desalinea)
    for e in entidades:
        extraido = texto[e.offset:e.offset + len(e.texto)]
        assert extraido == e.texto, (
            f"Offset desalineado para entidad {e.tipo!r}: "
            f"esperado {e.texto!r}, encontrado {extraido!r}"
        )
    return [e.to_dict() for e in entidades]


# ---------------------------------------------------------------------------
# Marcadores léxicos (tiene_excepcion / tiene_condicion, sección 3.4)
# ---------------------------------------------------------------------------

def tiene_marcador(texto: str, marcadores: Iterable[str]) -> bool:
    texto_low = texto.lower()
    return any(m.lower() in texto_low for m in marcadores)
