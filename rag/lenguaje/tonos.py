"""Tonos de respuesta: varias formulaciones fijas por situación y por idioma.

Un tono (``cordial``, ``formal``, ``directo``…) solo cambia cómo se enmarca
una respuesta, nunca su contenido: el texto del corpus va literal en su
propio bloque y las citas van debajo. Cada tono vive en
``rag/recursos/tonos/<idioma>/<tono>.yaml`` con 18 situaciones de al menos 5
variantes cada una; el linter de este módulo hace cumplir las reglas del
catálogo (``docs/guia/personalidad.md``).

Un proyecto puede sobrescribir situaciones en
``configuracion/personalidad.yaml::tono.plantillas``. Las sobrescrituras de
``configuracion/idioma.yaml`` anteriores a los tonos (``mensajes.sin_respuesta``,
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

from rag.configuracion.personalidad import TONOS  # la lista de tonos vive en la configuración

TONO_POR_DEFECTO = "cordial"
MINIMO_VARIANTES = 5
LARGO_MAXIMO = 200


@dataclass(frozen=True)
class Situacion:
    origen: str  # "motor" (redacción) o "widget" (microcopia)
    permitidas: frozenset[str] = frozenset()
    requeridas: frozenset[str] = frozenset()
    dos_puntos: bool = False  # introduce texto literal: debe terminar en «:»


_ASISTENTE = frozenset({"nombre_asistente", "descripcion_dominio"})
SITUACIONES: dict[str, Situacion] = {
    "saludo": Situacion("motor", _ASISTENTE),
    "agradecimiento": Situacion("motor", frozenset({"descripcion_dominio"})),
    "despedida": Situacion("motor"),
    "capacidad": Situacion("motor", _ASISTENTE),
    "apertura": Situacion("motor", dos_puntos=True),
    "complemento": Situacion("motor", dos_puntos=True),
    "condicion": Situacion("motor", dos_puntos=True),
    "excepcion": Situacion("motor", dos_puntos=True),
    "relacionado_intro": Situacion("motor", dos_puntos=True),
    "foco_ausente": Situacion("motor", frozenset({"termino"}), frozenset({"termino"}), dos_puntos=True),
    "sin_respuesta": Situacion("motor"),
    "premisa_no_encontrada": Situacion("motor", frozenset({"entidad"}), frozenset({"entidad"})),
    "bienvenida": Situacion("widget", frozenset({"nombre_asistente"})),
    "esperando": Situacion("widget"),
    "invitacion_citas": Situacion("widget"),
    "error_red": Situacion("widget"),
    "error_limite": Situacion("widget"),
    "error_servicio": Situacion("widget"),
}

# Claves de configuracion/idioma.yaml anteriores a los tonos → situación.
_LEGADO = {
    ("mensajes", "sin_respuesta"): "sin_respuesta",
    ("mensajes", "premisa_no_encontrada"): "premisa_no_encontrada",
    ("mensajes", "relacionado_intro"): "relacionado_intro",
    ("mensajes", "relacionado_foco_ausente"): "foco_ausente",
    ("interfaz", "saludo"): "bienvenida",
    ("interfaz", "esperando"): "esperando",
    ("interfaz", "error_red"): "error_red",
    ("interfaz", "error_limite"): "error_limite",
}
_CONECTORES_LEGADO = ("apertura", "complemento", "condicion", "excepcion")
_CONVERSACIONALES = ("saludo", "agradecimiento", "despedida", "capacidad")


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
        return [f"situación desconocida {situacion!r}"]
    regla = SITUACIONES[situacion]
    if not isinstance(texto, str) or not texto.strip():
        return ["vacía"]
    try:
        literal, campos = _campos(texto)
    except ValueError as e:
        return [f"llaves mal formadas: {e}"]
    errores = []
    if "\n" in texto:
        errores.append("debe ser una sola línea")
    if len(texto) > LARGO_MAXIMO:
        errores.append(f"tiene {len(texto)} caracteres (máximo {LARGO_MAXIMO})")
    if _DIGITOS.search(literal):
        errores.append("no puede tener dígitos (afirmaría un dato)")
    if _URL.search(literal):
        errores.append("no puede tener URLs")
    if _HTML.search(literal):
        errores.append("no puede tener HTML")
    if _MARKDOWN.search(literal):
        errores.append("no puede tener Markdown")
    if any(_es_emoji(c) for c in literal):
        errores.append("no puede tener emojis")
    # Solo para idiomas con signos de apertura (en y pt no los usan).
    if ("¡" in literal and literal.count("¡") != literal.count("!")) or \
            ("¿" in literal and literal.count("¿") != literal.count("?")):
        errores.append("los signos de apertura (¡ ¿) deben cerrarse (! ?)")
    if any(len(p) >= 4 and p.isupper() for p in re.findall(r"\w+", literal)):
        errores.append("no puede tener palabras enteras en mayúsculas")
    nombres = {c for c, _, _ in campos}
    if extra := sorted(nombres - regla.permitidas):
        errores.append(f"variables no permitidas: {extra} (permitidas: {sorted(regla.permitidas) or 'ninguna'})")
    if falta := sorted(regla.requeridas - nombres):
        errores.append(f"le falta {falta}")
    if any(formato or conversion for _, formato, conversion in campos):
        errores.append("las variables no admiten formato ni conversión")
    if regla.dos_puntos and not texto.rstrip().endswith(":"):
        errores.append("debe terminar en «:» porque introduce el texto del documento")
    minusculas = literal.casefold()
    for prohibida in prohibidas:
        if re.search(rf"\b{re.escape(prohibida.casefold())}\b", minusculas):
            errores.append(f"contiene una expresión prohibida: {prohibida!r}")
    return errores


def _normalizar(texto: str) -> str:
    return re.sub(r"[\W_]+", " ", texto.casefold()).strip()


def errores_tono(situaciones: dict[str, list[str]], prohibidas: tuple[str, ...] = (), *,
                 completo: bool = True, minimo: int = MINIMO_VARIANTES) -> list[str]:
    """Errores de un conjunto de situaciones. ``completo``: exige las 18 situaciones."""
    errores = []
    if completo and (faltan := [s for s in SITUACIONES if s not in situaciones]):
        errores.append(f"faltan situaciones: {faltan}")
    vistas: dict[str, str] = {}
    for situacion, textos in situaciones.items():
        if situacion not in SITUACIONES:
            errores.append(f"situación desconocida {situacion!r}")
            continue
        if not isinstance(textos, list) or len(textos) < minimo:
            errores.append(f"{situacion}: necesita al menos {minimo} variantes")
            continue
        propias: set[str] = set()
        for i, texto in enumerate(textos, start=1):
            errores += [f"{situacion}[{i}]: {e}" for e in errores_plantilla(situacion, texto, prohibidas)]
            clave = _normalizar(texto) if isinstance(texto, str) else ""
            if clave in propias:
                errores.append(f"{situacion}[{i}]: repite otra variante de la misma situación")
            elif clave in vistas and vistas[clave] != situacion:
                errores.append(f"{situacion}[{i}]: repite una variante de {vistas[clave]}")
            propias.add(clave)
            vistas.setdefault(clave, situacion)
    return errores


# --- carga ----------------------------------------------------------------------------------
def _raiz():
    return files("rag.recursos").joinpath("tonos")


def carpeta_idioma(idioma: str) -> str:
    """Carpeta de tonos para ``idioma``: la suya, la de su idioma base (``pt-br`` → ``pt``) o ``en``."""
    from rag.lenguaje.paquete import IDIOMA_RESPALDO

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
    return tuple(_reglas(idioma).get("prohibidas") or ())


def regionalismos_en(situaciones: dict[str, list[str]], idioma: str) -> list[str]:
    """Regionalismos, formas con género y saludos según la hora encontrados en
    ``situaciones``. Los tonos incluidos deben ser neutros (lo exige una prueba);
    en las sobrescrituras de un proyecto es un aviso (``avisos_neutralidad``)."""
    hallados = []
    for situacion, textos in situaciones.items():
        for i, texto in enumerate(textos, start=1):
            minusculas = _campos(texto)[0].casefold()
            for expresion in _reglas(idioma).get("regionalismos") or ():
                if re.search(rf"(?<!\w){re.escape(expresion.casefold())}(?!\w)", minusculas):
                    hallados.append(f"{situacion}[{i}]: {expresion!r}")
    return hallados


@functools.lru_cache(maxsize=None)
def _base(carpeta: str, tono: str) -> dict[str, Any]:
    recurso = _raiz().joinpath(carpeta, f"{tono}.yaml")
    if not recurso.is_file():
        raise TonoInvalido([f"no hay tono {tono!r} para el idioma {carpeta!r}; "
                            f"disponibles: {', '.join(tonos_disponibles(carpeta))}"])
    return yaml.safe_load(recurso.read_text(encoding="utf-8")) or {}


def extraer_legado(datos: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Separa de un ``idioma.yaml`` los textos que ahora son del tono.

    Devuelve los datos sin esas claves (lo que sigue validando el paquete de
    idioma) y las sobrescrituras de tono equivalentes.
    """
    import copy

    datos = copy.deepcopy(datos or {})
    plantillas: dict[str, list[str]] = {}

    def como_lista(valor) -> list[str]:
        return [valor] if isinstance(valor, str) else list(valor or [])

    for (seccion, clave), situacion in _LEGADO.items():
        if isinstance(datos.get(seccion), dict) and clave in datos[seccion]:
            plantillas[situacion] = como_lista(datos[seccion].pop(clave))
    conectores = (datos.get("mensajes") or {}).get("conectores")
    if isinstance(conectores, dict):
        for clave in _CONECTORES_LEGADO:
            if clave in conectores:
                plantillas[clave] = como_lista(conectores.pop(clave))
    respuestas = (datos.get("conversacional") or {}).pop("respuestas", None) \
        if isinstance(datos.get("conversacional"), dict) else None
    for categoria, valor in (respuestas or {}).items():
        if categoria in _CONVERSACIONALES:
            plantillas[categoria] = como_lista(valor)
    return datos, plantillas


def _sobrescrituras_personalidad(proyecto: str | Path | None) -> dict[str, list[str]]:
    if proyecto is None:
        return {}
    from rag.configuracion.personalidad import cargar_personalidad

    plantillas = cargar_personalidad(proyecto).tono.plantillas
    return {s: ([v] if isinstance(v, str) else list(v)) for s, v in plantillas.items()}


def cargar_tono(idioma: str, tono: str = TONO_POR_DEFECTO, *, proyecto: str | Path | None = None,
                sobrescrituras: dict[str, list[str]] | None = None) -> PaqueteTono:
    """El tono para ``idioma``, con las sobrescrituras del proyecto ya validadas.

    Orden: el paquete del tono ← ``sobrescrituras`` (las de ``idioma.yaml``
    anteriores a los tonos) ← ``personalidad.yaml::tono.plantillas``. Una
    sobrescritura puede traer una sola variante; debe cumplir las mismas
    reglas que el paquete.
    """
    carpeta = carpeta_idioma(idioma)
    datos = _base(carpeta, tono)
    situaciones = {s: list(v) for s, v in (datos.get("situaciones") or {}).items()}
    propias = {**(sobrescrituras or {}), **_sobrescrituras_personalidad(proyecto)}
    if propias:
        errores = errores_tono(propias, prohibidas(carpeta), completo=False, minimo=1)
        if errores:
            raise TonoInvalido([f"sobrescritura del proyecto: {e}" for e in errores])
        situaciones.update(propias)
    return PaqueteTono(tono=datos.get("tono", tono), idioma=carpeta, descripcion=datos.get("descripcion", ""),
                       situaciones=situaciones)


__all__ = [
    "LARGO_MAXIMO", "MINIMO_VARIANTES", "PaqueteTono", "SITUACIONES", "Situacion", "TONOS", "TONO_POR_DEFECTO",
    "TonoInvalido", "cargar_tono", "carpeta_idioma", "errores_plantilla", "errores_tono", "extraer_legado",
    "prohibidas", "regionalismos_en", "tonos_disponibles",
]
