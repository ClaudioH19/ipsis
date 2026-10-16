"""Fichas multimedia: un YAML por audio o video en ``media/`` (plan multimedia, M0.1).

Una ficha es metadata escrita por una persona: título, descripción, palabras clave y capítulos. ipsis no abre ni
analiza el archivo de audio o video: lo que se busca y se muestra es ese texto, literal
(ADR 0001, ``docs/plan/multimedia.md``). Esta capa solo lee y valida; no indexa ni sirve archivos.

El ``id`` de una ficha es el nombre de su archivo sin ``.yaml`` (``induccion-matricula.yaml``). Un archivo inválido no
impide leer los demás: sus errores quedan en ``LecturaFichas.errores`` bajo su ``id``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml

from ipsis.configuracion import rutas
from ipsis.recursos.mensajes import t

TIPOS = ("video", "audio")
CLAVES = ("title", "kind", "url", "file", "description", "keywords", "language", "version", "duration", "active",
          "chapters", "transcript")
CLAVES_CAPITULO = ("at", "title", "description")

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_IDIOMA = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
_MINUTOS = re.compile(r"^(\d{1,3}):([0-5]\d)$")  # MM:SS (los minutos pueden pasar de 59: «75:30»)
_HORAS = re.compile(r"^(\d{1,3}):([0-5]\d):([0-5]\d)$")  # HH:MM:SS


@dataclass(frozen=True)
class Capitulo:
    segundos: int
    titulo: str
    descripcion: str = ""


@dataclass(frozen=True)
class Ficha:
    id: str
    titulo: str
    tipo: str  # video | audio
    descripcion: str
    url: str | None = None  # https://… (uno de url o archivo)
    archivo: str | None = None  # ruta relativa a media/, siempre dentro de files/
    palabras_clave: tuple[str, ...] = ()
    idioma: str | None = None
    version: str | None = None
    duracion: int | None = None  # segundos
    vigente: bool = True
    capitulos: tuple[Capitulo, ...] = ()


@dataclass
class LecturaFichas:
    fichas: list[Ficha] = field(default_factory=list)  # ordenadas por id
    errores: dict[str, list[str]] = field(default_factory=dict)  # id → mensajes (en el idioma de la interfaz)


def a_segundos(valor) -> int | None:
    """``"14:32"`` o ``"01:14:32"`` → segundos; ``None`` si no es un tiempo.

    YAML 1.1 lee ``14:32`` sin comillas como el entero 872 (base 60), que ya son los segundos: se acepta. Un
    ``06:45`` sin comillas llega como texto. Un booleano no es un tiempo.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if valor >= 0 else None
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if (m := _HORAS.match(texto)):
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    if (m := _MINUTOS.match(texto)):
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def _texto(valor) -> str | None:
    """El texto en una sola línea (YAML plegado deja saltos); ``None`` si no es un texto no vacío."""
    if not isinstance(valor, str):
        return None
    limpio = " ".join(valor.split())
    return limpio or None


def _ruta_de_archivo(valor) -> str | None:
    """``files/video.mp4`` normalizado; ``None`` si sale de ``files/`` (absoluta, con «..», «\\» o fuera de la carpeta)."""
    if not isinstance(valor, str) or not valor.strip() or "\\" in valor:
        return None
    ruta = PurePosixPath(valor.strip())
    if ruta.is_absolute() or ".." in ruta.parts or len(ruta.parts) < 2 or ruta.parts[0] != "files":
        return None
    return ruta.as_posix()


def _capitulos(valor, duracion: int | None, errores: list[str]) -> tuple[Capitulo, ...]:
    if not isinstance(valor, list):
        errores.append(t("media.invalid_chapters"))
        return ()
    capitulos: list[Capitulo] = []
    anterior = -1
    for n, entrada in enumerate(valor, start=1):
        if not isinstance(entrada, dict):
            errores.append(t("media.chapter_not_object", n=n))
            continue
        for clave in sorted(str(k) for k in entrada if k not in CLAVES_CAPITULO):
            errores.append(t("media.unknown_key", key=f"chapters[{n}].{clave}"))
        segundos = a_segundos(entrada.get("at"))
        if segundos is None:
            errores.append(t("media.invalid_time", field=f"chapters[{n}].at"))
        elif segundos <= anterior:
            errores.append(t("media.chapter_order", n=n))
        elif duracion is not None and segundos >= duracion:
            errores.append(t("media.chapter_after_duration", n=n))
        titulo = _texto(entrada.get("title"))
        if titulo is None:
            errores.append(t("media.invalid_text", field=f"chapters[{n}].title"))
        descripcion = entrada.get("description")
        if descripcion is not None and _texto(descripcion) is None:
            errores.append(t("media.invalid_text", field=f"chapters[{n}].description"))
        if segundos is not None and titulo is not None:
            capitulos.append(Capitulo(segundos, titulo, _texto(descripcion) or ""))
            anterior = segundos
    return tuple(capitulos)


def validar_ficha(id_ficha: str, datos) -> tuple[Ficha | None, list[str]]:
    """Valida el contenido de una ficha. Devuelve ``(ficha, [])`` o ``(None, errores)``; no mira el disco."""
    errores: list[str] = []
    if not _ID.match(id_ficha):
        errores.append(t("media.invalid_id", id=id_ficha))
    if not isinstance(datos, dict):
        return None, [*errores, t("media.not_object")]
    for clave in sorted(str(k) for k in datos if k not in CLAVES):
        errores.append(t("media.unknown_key", key=clave))
    if "transcript" in datos:
        errores.append(t("media.transcript_unsupported"))

    titulo = _texto(datos.get("title"))
    if titulo is None:
        errores.append(t("media.required", field="title") if "title" not in datos
                       else t("media.invalid_text", field="title"))
    tipo = datos.get("kind")
    if tipo not in TIPOS:
        errores.append(t("media.invalid_kind"))
    descripcion = _texto(datos.get("description"))
    if descripcion is None:
        errores.append(t("media.required", field="description") if "description" not in datos
                       else t("media.invalid_text", field="description"))

    url, archivo = datos.get("url"), datos.get("file")
    if (url is None) == (archivo is None):
        errores.append(t("media.source_exactly_one"))
    if url is not None and not (isinstance(url, str) and url.strip().startswith("https://")
                                and len(url.strip()) > len("https://")):
        errores.append(t("media.url_not_https"))
    archivo_normalizado = _ruta_de_archivo(archivo) if archivo is not None else None
    if archivo is not None and archivo_normalizado is None:
        errores.append(t("media.file_outside"))

    claves = datos.get("keywords")
    palabras: tuple[str, ...] = ()
    if claves is not None:
        validas = [_texto(c) for c in claves] if isinstance(claves, list) else [None]
        if None in validas:
            errores.append(t("media.invalid_keywords"))
        else:
            palabras = tuple(validas)

    idioma = datos.get("language")
    if idioma is not None and not (isinstance(idioma, str) and _IDIOMA.match(idioma.strip().lower())):
        errores.append(t("media.invalid_language"))
    version = datos.get("version")
    if version is not None and (isinstance(version, bool) or not isinstance(version, (str, int, float))
                                or (isinstance(version, str) and not version.strip())):
        errores.append(t("media.invalid_version"))
    duracion = None
    if datos.get("duration") is not None:
        duracion = a_segundos(datos["duration"])
        if duracion is None:
            errores.append(t("media.invalid_time", field="duration"))
    vigente = datos.get("active", True)
    if not isinstance(vigente, bool):
        errores.append(t("media.invalid_active"))
    capitulos = _capitulos(datos["chapters"], duracion, errores) if datos.get("chapters") is not None else ()

    if errores:
        return None, errores
    return Ficha(
        id=id_ficha, titulo=titulo, tipo=tipo, descripcion=descripcion, url=url.strip() if url else None,
        archivo=archivo_normalizado, palabras_clave=palabras,
        idioma=idioma.strip().lower() if isinstance(idioma, str) else None,
        version=str(version).strip() if version is not None else None, duracion=duracion, vigente=vigente,
        capitulos=capitulos), []


def leer_fichas(carpeta: str | Path = rutas.MEDIA) -> LecturaFichas:
    """Lee y valida ``<carpeta>/*.yaml``. Sin carpeta no hay fichas ni errores. Un archivo ``file:`` debe existir."""
    base = Path(carpeta)
    lectura = LecturaFichas()
    if not base.is_dir():
        return lectura
    for ruta in sorted(base.glob("*.yaml")):
        id_ficha = ruta.stem
        try:
            datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
            lectura.errores[id_ficha] = [t("media.unreadable", error=str(error).splitlines()[0] if str(error) else
                                           type(error).__name__)]
            continue
        ficha, errores = validar_ficha(id_ficha, datos)
        if ficha is not None and ficha.archivo is not None and not (base / ficha.archivo).is_file():
            ficha, errores = None, [t("media.file_missing", file=ficha.archivo)]
        if ficha is None:
            lectura.errores[id_ficha] = errores
        else:
            lectura.fichas.append(ficha)
    return lectura


__all__ = ["CLAVES", "Capitulo", "Ficha", "LecturaFichas", "TIPOS", "a_segundos", "leer_fichas", "validar_ficha"]
