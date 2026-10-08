"""Paquetes de idioma: todo texto y patrón que depende del idioma.

Cada idioma soportado tiene un YAML en ``ipsis/recursos/idiomas/<código>.yaml``.
Un proyecto puede sobrescribir cualquier clave en ``config/language.yaml``;
la fusión es profunda para objetos y reemplaza listas completas.

Una variante regional (``pt-br``) usa el paquete de su idioma. Un idioma sin
paquete funciona con un respaldo: solo las reglas universales
(sin stopwords, números, meses ni conectores propios), términos sin stem y
los mensajes e interfaz de ``en``. ``ipsis doctor`` lo advierte.
"""
from __future__ import annotations

import functools
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ipsis.configuracion import rutas
from ipsis.recursos.mensajes import t


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Marcadores(_Estricto):
    excepcion: list[str] = Field(default_factory=list)
    condicion: list[str] = Field(default_factory=list)


class Conversacional(_Estricto):
    """Cómo se reconoce una pregunta conversacional; las respuestas son del tono."""

    categorias: list[str] = Field(default_factory=list)
    patrones: dict[str, list[str]] = Field(default_factory=dict)


class Mensajes(_Estricto):
    """Textos estructurales del idioma. Los que varían con el tono (abstención,
    conectores de apertura, complemento, condición y excepción) viven en
    ``ipsis/recursos/tonos/``."""

    sin_seccion: str
    cita_breve: str  # {documento}
    cita_completa: str  # {documento}, {seccion}
    # Encabezado del texto que se embebe (``texto_embebido``): cambiarlo exige reindexar.
    cabecera_embebido: str = "Documento: {documento} | Sección: {seccion}"
    conectores: dict[str, list[str]] = Field(default_factory=dict)  # secuencia, contraste_version


class GoldenInstrucciones(_Estricto):
    """Textos de ``ipsis golden template`` (ver docs/guide/golden.md).

    ``nota_*`` admiten ``{terminos}`` (términos clave de la sección),
    ``{documento}`` y ``{par}``. ``conversacionales`` son tres preguntas ya
    completas.
    """

    leeme: str
    nota_respondible: str
    nota_trampa: str
    conversacionales: list[str] = Field(min_length=3, max_length=3)


class Intencion(_Estricto):
    """Una relación que se pregunta (``ipsis.lenguaje.consultas``): patrones que la
    reconocen en la pregunta y pistas que suelen estar en la oración que responde.
    En minúsculas y sin tildes; los patrones son expresiones regulares."""

    patrones: list[str] = Field(min_length=1)
    pistas: list[str] = Field(default_factory=list)
    ejemplos: list[str] = Field(default_factory=list)
    # Formas compatibles para admitir el respaldo semántico. No reconocen
    # una intención por sí solas ni eliminan términos de la pregunta.
    respaldo_patrones: list[str] = Field(default_factory=list)


class UmbralesIntencion(_Estricto):
    similitud: float = Field(ge=0.0, le=1.0)
    margen: float = Field(ge=0.0, le=2.0)
    habilitadas: list[str] | None = None


class BordesRespuesta(_Estricto):
    unidades_cantidad: list[str] = Field(default_factory=list)
    prefijos_cantidad: list[str] = Field(default_factory=list)
    referencias_cantidad: list[str] = Field(default_factory=list)
    limites_actor: list[str] = Field(default_factory=list)


IDIOMA_RESPALDO = "en"
_CODIGO = r"^[a-z]{2,3}(-[a-z0-9]{2,8})*$"  # ISO 639 con subetiquetas opcionales (pt-br, zh-hant)


class PaqueteIdioma(_Estricto):
    codigo: str = Field(min_length=2)
    nombre: str = Field(min_length=1)
    stemmer: str | None = None
    stopwords: list[str] = Field(default_factory=list)
    numeros: dict[str, int] = Field(default_factory=dict)
    ordinales: dict[str, int] = Field(default_factory=dict)
    meses: list[str] = Field(default_factory=list)
    dias_semana: dict[str, list[str]] = Field(default_factory=dict)  # ISO: 1=lunes … 7=domingo
    unidades_tiempo: dict[str, list[str]] = Field(default_factory=dict)
    calificadores_plazo: dict[str, list[str]] = Field(default_factory=dict)
    referencias_documento: dict[str, list[str]] = Field(default_factory=dict)
    conectores_rango: dict[str, list[str]] = Field(default_factory=dict)  # claves: y (lista), a (rango)
    conectores_fecha: list[str] = Field(default_factory=list)
    conectores_fecha_relativa: list[str] = Field(default_factory=list)
    marcadores: Marcadores = Field(default_factory=Marcadores)
    # En orden: gana la primera cuyo patrón aparece en la pregunta.
    intenciones: dict[str, Intencion] = Field(default_factory=dict)
    respaldo_intencion: dict[str, UmbralesIntencion] = Field(default_factory=dict)
    bordes_respuesta: BordesRespuesta = Field(default_factory=BordesRespuesta)
    # Cómo empieza una pregunta de seguimiento («y», «entonces»; ipsis.consulta.seguimiento).
    seguimiento: list[str] = Field(default_factory=list)
    # Grupos de sinónimos con sus formas comunes (ipsis.lenguaje.consultas.sinonimos_presentes):
    # solo reemplazan una palabra de la pregunta que no está en el corpus.
    sinonimos: list[list[str]] = Field(default_factory=list)
    sinonimos_dominio: list[list[str]] = Field(default_factory=list)
    # Palabras que nunca son término foco: verbos de apoyo («hacer», «tener») y
    # unidades («días», «veces»). Dicen cómo se pregunta, no de qué se habla.
    genericas: list[str] = Field(default_factory=list)
    # Solo la memoria de temas las ignora; conservan su peso en selección/foco.
    genericas_memoria: list[str] = Field(default_factory=list)
    # Sufijos de sustantivos derivados que el stemmer deja («signatur», «assinatur»;
    # ipsis.lenguaje.consultas.equivalentes): para el foco, «signature» cuenta como «sign».
    sufijos_derivados: list[str] = Field(default_factory=list)
    conversacional: Conversacional = Field(default_factory=Conversacional)
    mensajes: Mensajes
    interfaz: dict[str, str] = Field(default_factory=dict)
    # Contracciones obligatorias al insertar variables en un texto fijo
    # (en español: «de el» -> «del»).
    contracciones: dict[str, str] = Field(default_factory=dict)
    golden_instrucciones: GoldenInstrucciones | None = None
    respaldo: bool = False  # True: no hay paquete para este idioma (ver docstring del módulo)
    # Textos de config/language.yaml anteriores a los tonos, ya traducidos a
    # situaciones de tono (``ipsis.lenguaje.tonos.extraer_legado``).
    plantillas_legado: dict[str, list[str]] = Field(default_factory=dict)


def _carpeta_paquetes():
    return files("ipsis.recursos").joinpath("idiomas")


def idiomas_disponibles() -> list[str]:
    """Códigos de idioma con paquete incluido en la instalación."""
    return sorted(
        recurso.name.removesuffix(".yaml")
        for recurso in _carpeta_paquetes().iterdir()
        if recurso.name.endswith(".yaml")
    )


def _fusionar(base: dict[str, Any], cambios: dict[str, Any]) -> dict[str, Any]:
    salida = deepcopy(base)
    for clave, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = _fusionar(salida[clave], valor)
        else:
            salida[clave] = deepcopy(valor)
    return salida


def validar_codigo_idioma(codigo: str) -> str:
    """El código tiene forma de idioma (``es``, ``pt-br``); no exige que haya paquete."""
    import re

    if not re.fullmatch(_CODIGO, codigo or ""):
        raise ValueError(t("core.invalid_language_code", code=codigo))
    return codigo


@functools.lru_cache(maxsize=None)
def _paquete_base(codigo: str) -> dict[str, Any]:
    if codigo not in idiomas_disponibles():
        validar_codigo_idioma(codigo)
        base = codigo.split("-")[0]
        if base in idiomas_disponibles():  # variante regional (pt-br): el paquete de su idioma
            return {**_paquete_base(base), "codigo": codigo}
        respaldo = _paquete_base(IDIOMA_RESPALDO)
        return {"codigo": codigo, "nombre": codigo, "stemmer": None, "respaldo": True,
                **{clave: respaldo[clave] for clave in ("mensajes", "interfaz", "golden_instrucciones")
                   if clave in respaldo}}
    texto = _carpeta_paquetes().joinpath(f"{codigo}.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(texto) or {}


def cargar_paquete(codigo: str, proyecto: str | Path | None = None) -> PaqueteIdioma:
    """Paquete del idioma ``codigo``, con las sobrescrituras del proyecto si existen."""
    from ipsis.lenguaje.tonos import extraer_legado

    datos = _paquete_base(codigo)
    legado: dict[str, list[str]] = {}
    if proyecto is not None:
        ruta = Path(proyecto) / rutas.IDIOMA
        if ruta.is_file():
            propios, legado = extraer_legado(yaml.safe_load(ruta.read_text(encoding="utf-8")) or {})
            datos = _fusionar(datos, propios)
    paquete = PaqueteIdioma.model_validate({**datos, "plantillas_legado": legado})
    if proyecto is not None:
        from ipsis.configuracion.archivos import leer

        dominio = leer(Path(proyecto) / rutas.DOMINIO, "dominio")
        grupos = dominio.get("sinonimos") or []
        if not isinstance(grupos, list) or any(
            not isinstance(g, list) or len(g) < 2 or any(not isinstance(f, str) or not f.strip() for f in g)
            for g in grupos
        ):
            raise ValueError("domain.yaml: synonyms must contain groups of at least two nonempty strings")
        paquete.sinonimos_dominio = grupos
    return paquete


__all__ = ["IDIOMA_RESPALDO", "PaqueteIdioma", "cargar_paquete", "idiomas_disponibles", "validar_codigo_idioma"]
