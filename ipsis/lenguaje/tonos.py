"""Tonos de respuesta: varias formulaciones fijas por situación y por idioma.

Un tono (``cordial``, ``formal``, ``direct``…) solo cambia cómo se enmarca
una respuesta, nunca su contenido: el texto del corpus va literal en su
propio bloque y las citas van debajo. Cada tono vive en
``ipsis/recursos/tonos/<idioma>/<tono>.yaml`` con 18 situaciones; cada paquete
incluido cumple ``CUOTAS_PAQUETE`` (más variantes donde más se repiten) y las
de un proyecto, al menos una. El linter de este módulo hace cumplir las reglas del
catálogo (``docs/guide/personality.md``).

Un proyecto puede sobrescribir situaciones en
``config/personality.yaml::tono.plantillas``. Las sobrescrituras de
``config/language.yaml`` anteriores a los tonos (``mensajes.sin_respuesta``,
``conectores.apertura``…) se siguen aceptando y se traducen aquí.
"""
from __future__ import annotations

import functools
import re
import string
import unicodedata
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from ipsis.recursos.mensajes import t
from ipsis.configuracion.personalidad import TONOS, VARIABLES_ANTERIORES  # viven en la configuración

TONO_POR_DEFECTO = "cordial"
MINIMO_VARIANTES = 5
LARGO_MAXIMO = 200
# Dos variantes de una situación son casi iguales si comparten casi todas sus
# palabras o si, con varias palabras, solo cambian una: rellenan sin variar.
PARECIDO_MAXIMO = 0.8
PALABRAS_MINIMAS_PARECIDO = 4


@dataclass(frozen=True)
class Situacion:
    origen: str  # "motor" (redacción) o "widget" (microcopia)
    permitidas: frozenset[str] = frozenset()
    requeridas: frozenset[str] = frozenset()
    dos_puntos: bool = False  # introduce texto literal: debe terminar en «:»


_ASISTENTE = frozenset({"assistant_name", "domain_description"})
SITUACIONES: dict[str, Situacion] = {
    "greeting": Situacion("motor", _ASISTENTE),
    "thanks": Situacion("motor", frozenset({"domain_description"})),
    "farewell": Situacion("motor"),
    "capability": Situacion("motor", _ASISTENTE),
    "opening": Situacion("motor", dos_puntos=True),
    "addition": Situacion("motor", dos_puntos=True),
    "condition": Situacion("motor", dos_puntos=True),
    "exception": Situacion("motor", dos_puntos=True),
    "related_intro": Situacion("motor", dos_puntos=True),
    "missing_focus": Situacion("motor", frozenset({"term"}), frozenset({"term"}), dos_puntos=True),
    "no_answer": Situacion("motor"),
    "premise_not_found": Situacion("motor", frozenset({"entity"}), frozenset({"entity"})),
    "welcome": Situacion("widget", frozenset({"assistant_name"})),
    "waiting": Situacion("widget"),
    "citations_hint": Situacion("widget"),
    "network_error": Situacion("widget"),
    "rate_limit_error": Situacion("widget"),
    "service_error": Situacion("widget"),
}

# Variantes que debe traer cada situación en los paquetes incluidos: más
# donde el usuario las ve en casi toda respuesta (~150 por paquete).
_FRECUENTES = ("opening", "addition", "no_answer", "related_intro")
CUOTAS_PAQUETE: dict[str, int] = {
    s: 12 if s in _FRECUENTES else 7 if SITUACIONES[s].origen == "widget" else 8 for s in SITUACIONES
}

# Claves de config/language.yaml anteriores a los tonos → situación.
_LEGADO = {
    ("mensajes", "sin_respuesta"): "no_answer",
    ("mensajes", "premisa_no_encontrada"): "premise_not_found",
    ("mensajes", "relacionado_intro"): "related_intro",
    ("mensajes", "relacionado_foco_ausente"): "missing_focus",
    ("interfaz", "saludo"): "welcome",
    ("interfaz", "esperando"): "waiting",
    ("interfaz", "error_red"): "network_error",
    ("interfaz", "error_limite"): "rate_limit_error",
}
def _variables_actuales(texto):
    if isinstance(texto, str):
        for anterior, actual in VARIABLES_ANTERIORES.items():
            texto = texto.replace("{" + anterior + "}", "{" + actual + "}")
    return texto


# Claves anteriores (conectores y respuestas conversacionales) → situación.
_CONECTORES_LEGADO = {"apertura": "opening", "complemento": "addition", "condicion": "condition",
                      "excepcion": "exception"}
_CONVERSACIONALES = {"saludo": "greeting", "agradecimiento": "thanks", "despedida": "farewell",
                     "capacidad": "capability", "greeting": "greeting", "thanks": "thanks",
                     "farewell": "farewell", "capability": "capability"}


class PaqueteTono(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tono: str
    idioma: str  # carpeta de la que salió (``en`` si el idioma del proyecto usa el respaldo)
    descripcion: str
    situaciones: dict[str, list[str]]

    def variantes(self, situacion: str) -> list[str]:
        return list(self.situaciones[situacion])


class TonoInvalido(ValueError):
    def __init__(self, errores: list[str]) -> None:
        super().__init__("; ".join(errores))
        self.errores = errores


# --- linter ---------------------------------------------------------------------------------
_DIGITOS = re.compile(r"\d")
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_HTML = re.compile(r"<[^>]*>")
_MARKDOWN = re.compile(r"[*_`#]|\[[^\]]*\]\(")


def _campos(texto: str) -> tuple[str, list[tuple[str, str | None, str | None]]]:
    """Texto literal (sin variables) y las variables con su formato y conversión."""
    literal, campos = [], []
    for parte, campo, formato, conversion in string.Formatter().parse(texto):
        literal.append(parte)
        if campo is not None:
            campos.append((campo, formato, conversion))
    return "".join(literal), campos


def _es_emoji(caracter: str) -> bool:
    return unicodedata.category(caracter) == "So" or 0x1F000 <= ord(caracter) <= 0x1FAFF


def errores_plantilla(situacion: str, texto: str, prohibidas: tuple[str, ...] = ()) -> list[str]:
    """Infracciones de una plantilla a las reglas de su situación."""
    if situacion not in SITUACIONES:
        return [t("lint.unknown_situation", situation=situacion)]
    regla = SITUACIONES[situacion]
    if not isinstance(texto, str) or not texto.strip():
        return [t("lint.empty")]
    try:
        literal, campos = _campos(texto)
    except ValueError as e:
        return [t("lint.bad_braces", error=e)]
    errores = []
    if "\n" in texto:
        errores.append(t("lint.one_line"))
    if len(texto) > LARGO_MAXIMO:
        errores.append(t("lint.too_long", length=len(texto), maximum=LARGO_MAXIMO))
    if _DIGITOS.search(literal):
        errores.append(t("lint.digits"))
    if _URL.search(literal):
        errores.append(t("lint.urls"))
    if _HTML.search(literal):
        errores.append(t("lint.html_tags"))
    if _MARKDOWN.search(literal):
        errores.append(t("lint.markdown"))
    if any(_es_emoji(c) for c in literal):
        errores.append(t("lint.emojis"))
    # Solo para idiomas con signos de apertura (en y pt no los usan).
    if ("¡" in literal and literal.count("¡") != literal.count("!")) or \
            ("¿" in literal and literal.count("¿") != literal.count("?")):
        errores.append(t("lint.opening_marks"))
    if any(len(p) >= 4 and p.isupper() for p in re.findall(r"\w+", literal)):
        errores.append(t("lint.capitals"))
    nombres = {c for c, _, _ in campos}
    if extra := sorted(nombres - regla.permitidas):
        errores.append(t("lint.variables_not_allowed", extra=extra,
                          allowed=sorted(regla.permitidas) or t("lint.none_allowed")))
    if falta := sorted(regla.requeridas - nombres):
        errores.append(t("lint.missing_variables", missing=falta))
    if any(formato or conversion for _, formato, conversion in campos):
        errores.append(t("lint.variable_format"))
    if regla.dos_puntos and not texto.rstrip().endswith(":"):
        errores.append(t("lint.colon"))
    minusculas = literal.casefold()
    for prohibida in prohibidas:
        if re.search(rf"\b{re.escape(prohibida.casefold())}\b", minusculas):
            errores.append(t("lint.forbidden", expression=prohibida))
    return errores


def _normalizar(texto: str) -> str:
    return re.sub(r"[\W_]+", " ", texto.casefold()).strip()


def _palabras(texto: str) -> list[str]:
    try:
        literal = _campos(texto)[0]
    except ValueError:
        literal = texto
    return re.findall(r"\w+", literal.casefold())


def _distancia(a: list[str], b: list[str]) -> int:
    """Distancia de edición entre dos secuencias de palabras."""
    fila = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        diagonal, fila[0] = fila[0], i
        for j, y in enumerate(b, start=1):
            diagonal, fila[j] = fila[j], min(fila[j] + 1, fila[j - 1] + 1, diagonal + (x != y))
    return fila[-1]


def casi_iguales(a: str, b: str) -> bool:
    """Las frases cortas («Si:», «Salvo:») son legítimas aunque cambien una palabra."""
    pa, pb = _palabras(a), _palabras(b)
    if min(len(pa), len(pb)) < PALABRAS_MINIMAS_PARECIDO:
        return False
    union = set(pa) | set(pb)
    if len(set(pa) & set(pb)) / len(union) >= PARECIDO_MAXIMO:
        return True
    return min(len(pa), len(pb)) > PALABRAS_MINIMAS_PARECIDO and _distancia(pa, pb) <= 1


def errores_tono(situaciones: dict[str, list[str]], prohibidas: tuple[str, ...] = (), *,
                 completo: bool = True, minimo: int | dict[str, int] = MINIMO_VARIANTES,
                 parecidas: bool = True) -> list[str]:
    """Errores de un conjunto de situaciones. ``completo``: exige las 18 situaciones.

    ``minimo``: variantes por situación, un número para todas o por situación
    (``CUOTAS_PAQUETE`` para los paquetes incluidos). ``parecidas``: rechaza
    variantes casi iguales; es una regla de calidad de los paquetes incluidos,
    no de las sobrescrituras de un proyecto (que antes eran válidas)."""
    errores = []
    if completo and (faltan := [s for s in SITUACIONES if s not in situaciones]):
        errores.append(t("lint.missing_situations", missing=faltan))
    vistas: dict[str, str] = {}
    for situacion, textos in situaciones.items():
        if situacion not in SITUACIONES:
            errores.append(t("lint.unknown_situation", situation=situacion))
            continue
        requeridas = minimo.get(situacion, MINIMO_VARIANTES) if isinstance(minimo, dict) else minimo
        if not isinstance(textos, list) or len(textos) < requeridas:
            errores.append(t("lint.min_variants", situation=situacion, minimum=requeridas))
            continue
        propias: set[str] = set()
        for i, texto in enumerate(textos, start=1):
            errores += [f"{situacion}[{i}]: {e}" for e in errores_plantilla(situacion, texto, prohibidas)]
            clave = _normalizar(texto) if isinstance(texto, str) else ""
            if clave in propias:
                errores.append(t("lint.repeats_own", situation=situacion, index=i))
            elif clave in vistas and vistas[clave] != situacion:
                errores.append(t("lint.repeats_other", situation=situacion, index=i, other=vistas[clave]))
            elif parecidas and isinstance(texto, str) and (parecida := next(
                    (j for j, previo in enumerate(textos[:i - 1], start=1)
                     if isinstance(previo, str) and casi_iguales(previo, texto)), None)):
                errores.append(t("lint.near_duplicate", situation=situacion, index=i, other=parecida))
            propias.add(clave)
            vistas.setdefault(clave, situacion)
    return errores


# --- carga ----------------------------------------------------------------------------------
def _raiz():
    return files("ipsis.recursos").joinpath("tonos")


def carpeta_idioma(idioma: str) -> str:
    """Carpeta de tonos para ``idioma``: la suya, la de su idioma base (``pt-br`` → ``pt``) o ``en``."""
    from ipsis.lenguaje.paquete import IDIOMA_RESPALDO

    disponibles = {r.name for r in _raiz().iterdir() if r.is_dir()}
    for candidato in (idioma, idioma.split("-")[0]):
        if candidato in disponibles:
            return candidato
    return IDIOMA_RESPALDO


def tonos_disponibles(idioma: str) -> list[str]:
    carpeta = _raiz().joinpath(carpeta_idioma(idioma))
    presentes = {r.name.removesuffix(".yaml") for r in carpeta.iterdir() if r.name.endswith(".yaml")}
    return [t for t in TONOS if t in presentes]


@functools.lru_cache(maxsize=None)
def _reglas(idioma: str) -> dict:
    recurso = _raiz().joinpath(carpeta_idioma(idioma), "_reglas.yaml")
    return yaml.safe_load(recurso.read_text(encoding="utf-8")) or {}


def prohibidas(idioma: str) -> tuple[str, ...]:
    """Expresiones que ningún tono puede usar (insultos, culpar al usuario…)."""
    return tuple(_reglas(idioma).get("forbidden") or ())


def regionalismos_en(situaciones: dict[str, list[str]], idioma: str) -> list[str]:
    """Regionalismos, formas con género y saludos según la hora encontrados en
    ``situaciones``. Los tonos incluidos deben ser neutros (lo exige una prueba);
    en las sobrescrituras de un proyecto es un aviso (``avisos_neutralidad``)."""
    hallados = []
    for situacion, textos in situaciones.items():
        for i, texto in enumerate(textos, start=1):
            minusculas = _campos(texto)[0].casefold()
            for expresion in _reglas(idioma).get("regionalisms") or ():
                if re.search(rf"(?<!\w){re.escape(expresion.casefold())}(?!\w)", minusculas):
                    hallados.append(f"{situacion}[{i}]: {expresion!r}")
    return hallados


@functools.lru_cache(maxsize=None)
def _base(carpeta: str, tono: str) -> dict[str, Any]:
    recurso = _raiz().joinpath(carpeta, f"{tono}.yaml")
    if not recurso.is_file():
        raise TonoInvalido([t("lint.no_tone", tone=tono, language=carpeta,
                              available=", ".join(tonos_disponibles(carpeta)))])
    return yaml.safe_load(recurso.read_text(encoding="utf-8")) or {}


def extraer_legado(datos: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Separa de un ``language.yaml`` los textos que ahora son del tono.

    Devuelve los datos sin esas claves (lo que sigue validando el paquete de
    idioma) y las sobrescrituras de tono equivalentes.
    """
    import copy

    datos = copy.deepcopy(datos or {})
    plantillas: dict[str, list[str]] = {}

    def como_lista(valor) -> list[str]:
        return [_variables_actuales(v) for v in ([valor] if isinstance(valor, str) else list(valor or []))]

    for (seccion, clave), situacion in _LEGADO.items():
        if isinstance(datos.get(seccion), dict) and clave in datos[seccion]:
            plantillas[situacion] = como_lista(datos[seccion].pop(clave))
    conectores = (datos.get("mensajes") or {}).get("conectores")
    if isinstance(conectores, dict):
        for clave, situacion in _CONECTORES_LEGADO.items():
            if clave in conectores:
                plantillas[situacion] = como_lista(conectores.pop(clave))
    respuestas = (datos.get("conversacional") or {}).pop("respuestas", None) \
        if isinstance(datos.get("conversacional"), dict) else None
    for categoria, valor in (respuestas or {}).items():
        if categoria in _CONVERSACIONALES:
            plantillas[_CONVERSACIONALES[categoria]] = como_lista(valor)
    return datos, plantillas


def _sobrescrituras_personalidad(proyecto: str | Path | None) -> dict[str, list[str]]:
    if proyecto is None:
        return {}
    from ipsis.configuracion.personalidad import cargar_personalidad

    plantillas = cargar_personalidad(proyecto).tono.plantillas
    return {s: ([v] if isinstance(v, str) else list(v)) for s, v in plantillas.items()}


def cargar_tono(idioma: str, tono: str = TONO_POR_DEFECTO, *, proyecto: str | Path | None = None,
                sobrescrituras: dict[str, list[str]] | None = None) -> PaqueteTono:
    """El tono para ``idioma``, con las sobrescrituras del proyecto ya validadas.

    Orden: el paquete del tono ← ``sobrescrituras`` (las de ``language.yaml``
    anteriores a los tonos) ← ``personality.yaml::tono.plantillas``. Una
    sobrescritura puede traer una sola variante; debe cumplir las mismas
    reglas que el paquete.
    """
    carpeta = carpeta_idioma(idioma)
    datos = _base(carpeta, tono)
    situaciones = {s: list(v) for s, v in (datos.get("situations") or {}).items()}
    propias = {**(sobrescrituras or {}), **_sobrescrituras_personalidad(proyecto)}
    if propias:
        errores = errores_tono(propias, prohibidas(carpeta), completo=False, minimo=1, parecidas=False)
        if errores:
            raise TonoInvalido([f"sobrescritura del proyecto: {e}" for e in errores])
        situaciones.update(propias)
    return PaqueteTono(tono=datos.get("tone", tono), idioma=carpeta, descripcion=datos.get("description", ""),
                       situaciones=situaciones)


__all__ = [
    "CUOTAS_PAQUETE", "LARGO_MAXIMO", "MINIMO_VARIANTES", "PaqueteTono", "SITUACIONES", "Situacion", "TONOS", "TONO_POR_DEFECTO",
    "TonoInvalido", "cargar_tono", "carpeta_idioma", "casi_iguales", "errores_plantilla", "errores_tono", "extraer_legado",
    "prohibidas", "regionalismos_en", "tonos_disponibles",
]
