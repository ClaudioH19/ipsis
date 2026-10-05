"""Avatares del widget: definiciones ``.avatar.json`` de @bible-strong/avatar-web.

Este módulo revisa lo que se puede revisar sin ejecutar JavaScript (tamaño,
JSON sin claves duplicadas, campos obligatorios, ``expressions.neutral``,
formato de las claves y colores). La validación completa contra el esquema la
hace la propia librería (``herramientas/avatar``, P12.9).

Los avatares incluidos viven en ``ipsis/recursos/avatares/``; los importados por
el proyecto, en ``config/avatars/``. Con el mismo nombre, manda el del
proyecto.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

from ipsis.configuracion import rutas
from ipsis.configuracion.personalidad import CLAVE_SEMANTICA, EVENTOS
from ipsis.recursos.mensajes import t

LIMITE_BYTES = 256 * 1024  # el mismo límite que parseAvatarDefinition
REQUERIDOS = ("schema", "schemaVersion", "body", "colors", "expressions", "expressionOrder", "animations",
              "animationOrder")
SUFIJO = ".avatar.json"


class AvatarInvalido(ValueError):
    def __init__(self, errores: list[str]) -> None:
        super().__init__("; ".join(errores))
        self.errores = errores


@dataclass(frozen=True)
class Avatar:
    nombre: str
    origen: str  # "incluido" | "proyecto"
    ruta: Path | None
    expresiones: tuple[str, ...]
    animaciones: tuple[str, ...]


@dataclass(frozen=True)
class MapaEventos:
    """Para cada evento: la clave efectiva y si es la pedida o un respaldo."""

    claves: dict[str, str]
    respaldos: dict[str, str] = field(default_factory=dict)  # evento → clave pedida que el avatar no tiene


def _sin_duplicadas(pares: list[tuple[str, Any]]) -> dict:
    claves = [k for k, _ in pares]
    if len(claves) != len(set(claves)):
        repetidas = sorted({k for k in claves if claves.count(k) > 1})
        raise ValueError(t("app.duplicate_keys", keys=repetidas))
    return dict(pares)


def validar_definicion(contenido: bytes) -> dict:
    """La definición como dict; ``AvatarInvalido`` con todos los problemas encontrados."""
    if len(contenido) > LIMITE_BYTES:
        raise AvatarInvalido([t("app.avatar_too_big", size=len(contenido), maximum=LIMITE_BYTES)])
    try:
        datos = json.loads(contenido.decode("utf-8"), object_pairs_hook=_sin_duplicadas)
    except (UnicodeDecodeError, ValueError) as e:
        raise AvatarInvalido([t("app.avatar_bad_json", error=e)]) from e
    if not isinstance(datos, dict):
        raise AvatarInvalido([t("app.avatar_not_object")])
    errores = [t("app.avatar_missing_field", field=c) for c in REQUERIDOS if c not in datos]
    expresiones = datos.get("expressions") if isinstance(datos.get("expressions"), dict) else {}
    animaciones = datos.get("animations") if isinstance(datos.get("animations"), dict) else {}
    if "expressions" in datos and "neutral" not in expresiones:
        errores.append(t("app.avatar_no_neutral"))
    for tipo, claves in ((t("app.avatar_expression"), expresiones), (t("app.avatar_animation"), animaciones)):
        for clave in claves:
            if not re.fullmatch(CLAVE_SEMANTICA, clave) or len(clave) > 64:
                errores.append(t("app.avatar_key_pattern", kind=tipo, key=clave, pattern=CLAVE_SEMANTICA))
    if len(expresiones) > 128:
        errores.append(t("app.avatar_too_many_expressions", n=len(expresiones)))
    if len(animaciones) > 64:
        errores.append(t("app.avatar_too_many_animations", n=len(animaciones)))
    colores = datos.get("colors") if isinstance(datos.get("colors"), dict) else {}
    for clave in ("body", "eyes"):
        if "colors" in datos and not re.fullmatch(r"#[0-9a-f]{6}", str(colores.get(clave, ""))):
            errores.append(t("app.avatar_color", key=clave))
    if errores:
        raise AvatarInvalido(errores)
    return datos


def _carpeta_incluidos():
    return files("ipsis.recursos").joinpath("avatares")


def _candidatos() -> dict[str, tuple[str, Any]]:
    """nombre → (origen, recurso); los del proyecto tapan a los incluidos."""
    salida: dict[str, tuple[str, Any]] = {}
    incluidos = _carpeta_incluidos()
    if incluidos.is_dir():
        for recurso in incluidos.iterdir():
            if recurso.name.endswith(SUFIJO):
                salida[recurso.name.removesuffix(SUFIJO)] = ("incluido", recurso)
    propios = Path(rutas.AVATARES)
    if propios.is_dir():
        for ruta in propios.glob(f"*{SUFIJO}"):
            salida[ruta.name.removesuffix(SUFIJO)] = ("proyecto", ruta)
    return salida


def cargar_avatar(nombre: str) -> tuple[Avatar, dict]:
    """El avatar ``nombre`` y su definición validada."""
    if not re.fullmatch(CLAVE_SEMANTICA, nombre or ""):
        raise AvatarInvalido([t("app.avatar_bad_name", name=nombre)])
    candidatos = _candidatos()
    if nombre not in candidatos:
        disponibles = ", ".join(sorted(candidatos)) or t("app.avatar_none_yet")
        raise FileNotFoundError(t("app.avatar_missing", name=nombre, available=disponibles))
    origen, recurso = candidatos[nombre]
    datos = validar_definicion(recurso.read_bytes())
    ruta = recurso if isinstance(recurso, Path) else None
    return Avatar(nombre, origen, ruta, tuple(datos["expressions"]), tuple(datos["animations"])), datos


def listar_avatares() -> list[Avatar | tuple[str, str, str]]:
    """Avatares válidos; los inválidos aparecen como (nombre, origen, error)."""
    salida: list = []
    for nombre, (origen, _) in sorted(_candidatos().items()):
        try:
            salida.append(cargar_avatar(nombre)[0])
        except (AvatarInvalido, OSError) as e:
            salida.append((nombre, origen, str(e)))
    return salida


def importar_avatar(archivo: str | Path, nombre: str | None = None) -> Avatar:
    """Valida ``archivo`` y lo copia a ``config/avatars/<nombre>.avatar.json``."""
    import os

    origen = Path(archivo)
    nombre = nombre or origen.name.removesuffix(SUFIJO).removesuffix(".json").lower()
    if not re.fullmatch(CLAVE_SEMANTICA, nombre):
        raise AvatarInvalido([t("app.avatar_name_rules", name=nombre)])
    contenido = origen.read_bytes()
    validar_definicion(contenido)
    destino = Path(rutas.AVATARES) / f"{nombre}{SUFIJO}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    temporal.write_bytes(contenido)
    os.replace(temporal, destino)
    return cargar_avatar(nombre)[0]


def mapa_eventos(avatar: Avatar | None, sobrescrituras: dict[str, str]) -> MapaEventos:
    """Clave efectiva de cada evento: la sobrescrita, la sugerida o su respaldo en cadena."""
    disponibles = set(avatar.expresiones + avatar.animaciones) if avatar is not None else set()
    claves: dict[str, str] = {}
    respaldos: dict[str, str] = {}

    def resolver(evento: str, vistos: frozenset[str] = frozenset()) -> str:
        sugerida, respaldo = EVENTOS[evento]
        pedida = sobrescrituras.get(evento, sugerida)
        if pedida in disponibles:
            return pedida
        if respaldo in EVENTOS and respaldo not in vistos:
            return resolver(respaldo, vistos | {evento})
        return "neutral"

    for evento in EVENTOS:
        claves[evento] = resolver(evento)
        pedida = sobrescrituras.get(evento, EVENTOS[evento][0])
        if claves[evento] != pedida:
            respaldos[evento] = pedida
    return MapaEventos(claves, respaldos)


def con_colores(datos: dict, cuerpo: str | None, ojos: str | None) -> dict:
    """La definición con los colores del proyecto (sin tocar el archivo original)."""
    colores = dict(datos.get("colors") or {})
    if cuerpo:
        colores["body"] = cuerpo
    if ojos:
        colores["eyes"] = ojos
    return {**datos, "colors": colores}


__all__ = ["Avatar", "AvatarInvalido", "LIMITE_BYTES", "MapaEventos", "cargar_avatar", "con_colores",
           "importar_avatar", "listar_avatares", "mapa_eventos", "validar_definicion"]
