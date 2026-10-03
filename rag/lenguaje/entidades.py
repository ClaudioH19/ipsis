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

import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from typing import Iterable

NUMEROS_TEXTO = {
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "catorce": 14, "quince": 15,
    "veinte": 20, "veinticuatro": 24, "treinta": 30,
}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

ORDINALES = {
    "primer": 1, "primera": 1, "segundo": 2, "segunda": 2,
    "tercer": 3, "tercera": 3, "cuarto": 4, "cuarta": 4,
    "quinto": 5, "quinta": 5,
}


@dataclass(frozen=True)
class Entidad:
    tipo: str
    texto: str
    valor_norm: str
    offset: int

    def to_dict(self) -> dict:
        return asdict(self)


def _num_o_texto_a_int(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    token_norm = token.replace(",", "").replace(".", "")
    return NUMEROS_TEXTO.get(token_norm)


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
# PLAZO: "<numero|texto> día(s)/semana(s)/hora(s) [hábiles|corridos]"
# ---------------------------------------------------------------------------
_UNIDADES_PLAZO = r"(d[ií]as?|semanas?|horas?|minutos?|meses?)"
_RE_PLAZO = re.compile(
    rf"\b(\d{{1,3}}|{'|'.join(NUMEROS_TEXTO.keys())})\s+{_UNIDADES_PLAZO}"
    rf"(\s+(h[aá]biles|corridos))?",
    re.IGNORECASE,
)


def extraer_plazos(texto: str) -> list[Entidad]:
    out = []
    for m in _RE_PLAZO.finditer(texto):
        num = _num_o_texto_a_int(m.group(1))
        if num is None:
            continue
        unidad = m.group(2).lower()
        # normaliza plural/singular de la unidad a su forma singular
        unidad_norm = re.sub(r"s$", "", unidad).replace("í", "i").replace("á", "a")
        calif = m.group(4)
        valor = f"{num}_{unidad_norm}"
        if calif:
            valor += f"_{calif.lower().replace('á', 'a')}"
        out.append(Entidad("plazo", m.group(0), valor, m.start(0)))
    return out


# ---------------------------------------------------------------------------
# FECHA relativa: "<ordinal> <día semana> de <mes>" (patrón real del corpus:
# "segundo viernes de enero"); también fechas explícitas dd/mm/yyyy o "dd de mes".
# ---------------------------------------------------------------------------
_DIAS_SEMANA = ["lunes", "martes", "mi[eé]rcoles", "jueves", "viernes", "s[aá]bado", "domingo"]
_RE_FECHA_RELATIVA = re.compile(
    rf"\b({'|'.join(ORDINALES.keys())})\s+({'|'.join(_DIAS_SEMANA)})\s+de\s+({'|'.join(MESES)})\b",
    re.IGNORECASE,
)
_RE_FECHA_EXPLICITA = re.compile(
    rf"\b(\d{{1,2}})\s+de\s+({'|'.join(MESES)})(\s+de\s+(\d{{4}}))?\b",
    re.IGNORECASE,
)


def extraer_fechas(texto: str) -> list[Entidad]:
    out = []
    for m in _RE_FECHA_RELATIVA.finditer(texto):
        ordinal = ORDINALES.get(m.group(1).lower(), m.group(1).lower())
        dia = re.sub(r"[íÍ]", "i", m.group(2).lower()).replace("á", "a")
        mes = m.group(3).lower()
        out.append(Entidad("fecha", m.group(0), f"{ordinal}_{dia}_de_{mes}", m.start(0)))
    for m in _RE_FECHA_EXPLICITA.finditer(texto):
        dia = m.group(1)
        mes = m.group(2).lower()
        anio = m.group(4) or ""
        valor = f"{dia}_de_{mes}" + (f"_{anio}" if anio else "")
        out.append(Entidad("fecha", m.group(0), valor, m.start(0)))
    return out


# ---------------------------------------------------------------------------
# ARTICULO / ANEXO
#
# Defecto: "artículos 13 y 14" normalizaba como
# "articulo_13" -- el segundo número del rango/lista se descartaba
# silenciosamente porque el patrón original solo capturaba un dígito. Se
# agrega un segundo número opcional unido por "y" (lista) o "a" (rango),
# mismo precedente que ``_RE_SABER_RANGO``: el rango/lista completo queda en
# un único ``valor_norm`` (p.ej. "articulo_13_y_14", "articulo_13_a_15"), en
# vez de truncarse al primer elemento.
# ---------------------------------------------------------------------------
_RE_ARTICULO = re.compile(
    r"\b([Aa]rt[ií]culo)s?\s+(\d{1,3})(\s+(y|a)\s+(\d{1,3}))?\b"
)
_RE_ANEXO = re.compile(r"\b([Aa]nexo)\s+(\d{1,2})\b")
_RE_CAPITULO = re.compile(r"\b(CAP[IÍ]TULO)\s+([IVX]+)\b")


def extraer_articulos(texto: str) -> list[Entidad]:
    out = []
    for m in _RE_ARTICULO.finditer(texto):
        n1 = m.group(2)
        conector = m.group(4)
        n2 = m.group(5)
        valor = f"articulo_{n1}" if not n2 else f"articulo_{n1}_{conector}_{n2}"
        out.append(Entidad("articulo", m.group(0), valor, m.start(0)))
    for m in _RE_ANEXO.finditer(texto):
        out.append(Entidad("articulo", m.group(0), f"anexo_{m.group(2)}", m.start(0)))
    for m in _RE_CAPITULO.finditer(texto):
        out.append(Entidad("articulo", m.group(0), f"capitulo_{m.group(2).lower()}", m.start(0)))
    return out


# ---------------------------------------------------------------------------
EXTRACTORES = [
    extraer_decimales,
    extraer_porcentajes,
    extraer_plazos,
    extraer_fechas,
    extraer_articulos,
]

# Nombres de tipo que produce cada extractor GENERICO de arriba (mismo orden
# conceptual que EXTRACTORES, pero como nombres -- lo usa tipos_con_regla()
# para no hardcodear en ningun otro modulo cuales tipos vienen del nucleo).
TIPOS_GENERICOS = {"decimal", "porcentaje", "plazo", "fecha", "articulo"}


# ---------------------------------------------------------------------------
# Perfil de dominio activo: las entidades
# ESPECIFICAS de un dominio (saberes, organismos, practicas, semanas
# relativas... lo que antes eran extraer_saberes/extraer_semanas/
# extraer_organismos/extraer_practicas en este mismo modulo) ya NO viven
# aqui -- se declaran en configuracion/dominios/<nombre>/perfil.yaml y las interpreta
# rag/lenguaje/dominio.py. Este modulo solo necesita saber que existe un objeto con
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
    CLI cargan su perfil con rag/lenguaje/dominio.py::cargar_perfil y lo registran
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
    rag/lenguaje/dominio.py::PerfilDominio.tipos_aportados). Sin perfil activo,
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
