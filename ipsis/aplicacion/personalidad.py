"""Casos de uso de ``ipsis personalidad``: tono de las respuestas y avatar del widget.

Todo cambio se valida completo (esquema, linter de plantillas y avatar) antes
de escribir ``configuracion/personalidad.yaml``; si no pasa, no se escribe
nada. Es presentación: no toca índice, calibración ni umbrales.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ipsis.configuracion import rutas
from ipsis.configuracion.personalidad import EVENTOS, HEX, TONOS, PersonalidadConfig


class SinProyecto(RuntimeError):
    """No hay proyecto en la carpeta actual."""


class PersonalidadInvalida(ValueError):
    def __init__(self, errores: list[str]) -> None:
        super().__init__("; ".join(errores))
        self.errores = errores


@dataclass(frozen=True)
class EstadoAvatar:
    nombre: str
    estado: str  # "ok" | "falta" | "invalido" | "desactivado"
    mensaje: str = ""
    expresiones: tuple[str, ...] = ()
    animaciones: tuple[str, ...] = ()
    respaldos: dict[str, str] = field(default_factory=dict)  # evento → clave pedida que no tiene
    claves: dict[str, str] = field(default_factory=dict)  # evento → clave efectiva


@dataclass(frozen=True)
class ResumenPersonalidad:
    tono: str
    variedad: str
    idioma_tonos: str  # carpeta de tonos que usa el proyecto (en si el idioma usa el respaldo)
    sobrescritas: list[str]
    config: PersonalidadConfig
    avatar: EstadoAvatar


@dataclass(frozen=True)
class TonoDisponible:
    tono: str
    descripcion: str
    ejemplo: str
    activo: bool


def _exigir_proyecto() -> None:
    if not Path(rutas.MOTOR).is_file():
        raise SinProyecto("no hay un proyecto en esta carpeta")


def _idioma() -> str:
    from ipsis.configuracion.carga import cargar_dominio

    return cargar_dominio().get("idioma", "es")


def _config() -> PersonalidadConfig:
    from ipsis.configuracion.personalidad import cargar_personalidad

    try:
        return cargar_personalidad()
    except Exception as e:  # noqa: BLE001 -- YAML o esquema inválido
        raise PersonalidadInvalida([f"{rutas.PERSONALIDAD}: {_breve(e)}"]) from e


def _breve(error: Exception) -> str:
    errores = getattr(error, "errors", None)
    if callable(errores):
        try:
            return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in errores()[:4])
        except Exception:  # noqa: BLE001
            pass
    return str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__


def estado_avatar(config: PersonalidadConfig) -> EstadoAvatar:
    from ipsis.aplicacion.avatar import AvatarInvalido, cargar_avatar, mapa_eventos

    nombre = config.avatar.definicion
    if not config.avatar.activo:
        return EstadoAvatar(nombre, "desactivado", "el widget muestra el ícono")
    try:
        avatar, _ = cargar_avatar(nombre)
    except FileNotFoundError as e:
        return EstadoAvatar(nombre, "falta", f"{e}; el widget muestra el ícono")
    except AvatarInvalido as e:
        return EstadoAvatar(nombre, "invalido", f"{e}; el widget muestra el ícono")
    mapa = mapa_eventos(avatar, config.avatar.eventos)
    return EstadoAvatar(nombre, "ok", "", avatar.expresiones, avatar.animaciones, mapa.respaldos, mapa.claves)


def _validar_tono(config: PersonalidadConfig) -> list[str]:
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.lenguaje.tonos import TonoInvalido, cargar_tono, tonos_disponibles

    idioma = _idioma()
    if config.tono.activo not in tonos_disponibles(idioma):
        return [f"el tono {config.tono.activo!r} no existe para el idioma {idioma!r}"]
    try:
        legado = cargar_paquete(idioma, proyecto=Path.cwd()).plantillas_legado
        plantillas = {s: ([v] if isinstance(v, str) else list(v)) for s, v in config.tono.plantillas.items()}
        cargar_tono(idioma, config.tono.activo, sobrescrituras={**legado, **plantillas})
    except TonoInvalido as e:
        return list(e.errores)
    return []


def _escribir(datos: dict) -> PersonalidadConfig:
    """Valida todo lo que ``datos`` cambia y recién entonces escribe."""
    from ipsis.configuracion.personalidad import guardar_personalidad

    try:
        config = PersonalidadConfig.model_validate(datos)
    except Exception as e:  # noqa: BLE001
        raise PersonalidadInvalida([_breve(e)]) from e
    if errores := _validar_tono(config):
        raise PersonalidadInvalida(errores)
    guardar_personalidad(config)
    return config


def resumen_personalidad() -> ResumenPersonalidad:
    from ipsis.lenguaje.tonos import carpeta_idioma

    _exigir_proyecto()
    config = _config()
    return ResumenPersonalidad(config.tono.activo, config.tono.variedad, carpeta_idioma(_idioma()),
                               sorted(config.tono.plantillas), config, estado_avatar(config))


def validar_personalidad() -> tuple[list[str], list[str]]:
    """(errores, avisos). Un error impide arrancar el motor; un aviso, no."""
    _exigir_proyecto()
    try:
        config = _config()
    except PersonalidadInvalida as e:
        return e.errores, []
    errores = _validar_tono(config)
    avatar = estado_avatar(config)
    avisos = [] if errores else avisos_neutralidad(config)
    if avatar.estado in ("falta", "invalido"):
        avisos.append(f"avatar {avatar.nombre!r}: {avatar.mensaje}")
    for evento, pedida in avatar.respaldos.items():
        avisos.append(f"al avatar le falta {pedida!r} (evento {evento}): usa {avatar.claves[evento]!r}")
    return errores, avisos


PREFIJO_NEUTRALIDAD = "texto propio no neutro"


def avisos_neutralidad(config: PersonalidadConfig | None = None) -> list[str]:
    """Regionalismos, formas con género o saludos según la hora en los textos propios
    del proyecto (``tono.plantillas``). Es un aviso, no un error: los tonos incluidos
    son neutros, pero un sitio local puede querer hablar como su región."""
    from ipsis.lenguaje.tonos import carpeta_idioma, regionalismos_en

    config = config or _config()
    propias = {s: ([v] if isinstance(v, str) else list(v)) for s, v in config.tono.plantillas.items()}
    idioma = carpeta_idioma(_idioma().lower())
    # Solo con reglas del propio idioma: las de respaldo (en) darían falsos avisos en otro idioma.
    if not propias or idioma != _idioma().lower().split("-")[0]:
        return []
    return [f"{PREFIJO_NEUTRALIDAD}: {hallado} (los tonos incluidos lo evitan; cámbialo si tu público es de "
            "varios países)" for hallado in regionalismos_en(propias, idioma)]


# --- tono -------------------------------------------------------------------------------------
def listar_tonos() -> list[TonoDisponible]:
    from ipsis.lenguaje.tonos import cargar_tono, tonos_disponibles

    _exigir_proyecto()
    idioma, activo = _idioma(), _config().tono.activo
    salida = []
    for tono in tonos_disponibles(idioma):
        paquete = cargar_tono(idioma, tono)
        salida.append(TonoDisponible(tono, paquete.descripcion, paquete.variantes("sin_respuesta")[0], tono == activo))
    return salida


def aplicar_tono(tono: str) -> PersonalidadConfig:
    _exigir_proyecto()
    if tono not in TONOS:
        raise PersonalidadInvalida([f"tono desconocido {tono!r}; disponibles: {', '.join(TONOS)}"])
    datos = _config().model_dump(mode="json")
    datos["tono"]["activo"] = tono
    return _escribir(datos)


def probar_tono(tono: str | None = None, situacion: str | None = None) -> dict[str, list[str]]:
    """Variantes de cada situación con las variables del proyecto ya reemplazadas."""
    from ipsis.configuracion.carga import cargar_dominio
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.lenguaje.tonos import SITUACIONES, cargar_tono

    _exigir_proyecto()
    config = _config()
    tono = tono or config.tono.activo
    if tono not in TONOS:
        raise PersonalidadInvalida([f"tono desconocido {tono!r}; disponibles: {', '.join(TONOS)}"])
    if situacion is not None and situacion not in SITUACIONES:
        raise PersonalidadInvalida([f"situación desconocida {situacion!r}; válidas: {', '.join(SITUACIONES)}"])
    dominio = cargar_dominio()
    idioma = dominio.get("idioma", "es")
    legado = cargar_paquete(idioma, proyecto=Path.cwd()).plantillas_legado
    propias = config.tono.plantillas if tono == config.tono.activo else {}
    paquete = cargar_tono(idioma, tono, sobrescrituras={
        **legado, **{s: ([v] if isinstance(v, str) else list(v)) for s, v in propias.items()}})
    variables = {"nombre_asistente": dominio.get("nombre_asistente", ""),
                 "descripcion_dominio": dominio.get("descripcion_dominio", ""),
                 "termino": "…", "entidad": "…"}
    elegidas = [situacion] if situacion else list(SITUACIONES)
    return {s: [v.format(**variables) for v in paquete.variantes(s)] for s in elegidas}


# --- avatar -----------------------------------------------------------------------------------
def listar_avatares():
    from ipsis.aplicacion.avatar import listar_avatares as listar

    _exigir_proyecto()
    return listar(), _config().avatar.definicion


def importar_avatar(archivo: str, nombre: str | None = None):
    from ipsis.aplicacion.avatar import importar_avatar as importar

    _exigir_proyecto()
    return importar(archivo, nombre)


def aplicar_avatar(nombre: str) -> PersonalidadConfig:
    from ipsis.aplicacion.avatar import cargar_avatar

    _exigir_proyecto()
    cargar_avatar(nombre)  # FileNotFoundError o AvatarInvalido antes de escribir
    datos = _config().model_dump(mode="json")
    datos["avatar"]["definicion"] = nombre
    return _escribir(datos)


def asignar_evento(evento: str, clave: str) -> PersonalidadConfig:
    _exigir_proyecto()
    if evento not in EVENTOS:
        raise PersonalidadInvalida([f"evento desconocido {evento!r}; válidos: {', '.join(EVENTOS)}"])
    config = _config()
    avatar = estado_avatar(config)
    if avatar.estado == "ok" and clave not in avatar.expresiones + avatar.animaciones:
        raise PersonalidadInvalida([f"el avatar {avatar.nombre!r} no tiene la clave {clave!r}; "
                                    f"animaciones: {', '.join(avatar.animaciones) or '—'}; "
                                    f"expresiones: {', '.join(avatar.expresiones)}"])
    datos = config.model_dump(mode="json")
    datos["avatar"]["eventos"][evento] = clave
    return _escribir(datos)


def colores_avatar(cuerpo: str | None = None, ojos: str | None = None) -> PersonalidadConfig:
    _exigir_proyecto()
    datos = _config().model_dump(mode="json")
    for clave, valor in (("cuerpo", cuerpo), ("ojos", ojos)):
        if valor is None:
            continue
        valor = valor.strip().lower()
        if not re.fullmatch(HEX, valor):
            raise PersonalidadInvalida([f"color de {clave} inválido {valor!r}: usa #rrggbb (p. ej. #f5f1e8)"])
        datos["avatar"]["colores"][clave] = valor
    return _escribir(datos)


__all__ = [
    "EstadoAvatar", "PersonalidadInvalida", "ResumenPersonalidad", "SinProyecto", "TonoDisponible", "aplicar_avatar",
    "aplicar_tono", "asignar_evento", "colores_avatar", "estado_avatar", "importar_avatar", "listar_avatares",
    "listar_tonos", "probar_tono", "resumen_personalidad", "validar_personalidad",
    "actualizar_personalidad", "config_avatar_publica", "definicion_publica", "importar_avatar_desde", "resumen_admin",
]


# --- para la API (/admin y /config) --------------------------------------------------------------
def _fusionar(base: dict, cambios: dict) -> dict:
    salida = dict(base)
    for clave, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(salida.get(clave), dict) and clave not in ("plantillas", "eventos"):
            salida[clave] = _fusionar(salida[clave], valor)
        else:
            salida[clave] = valor  # plantillas y eventos se reemplazan completos
    return salida


def actualizar_personalidad(cambios: dict) -> PersonalidadConfig:
    """Fusiona ``cambios`` (parcial) sobre la personalidad y escribe si todo es válido."""
    _exigir_proyecto()
    if not isinstance(cambios, dict):
        raise PersonalidadInvalida(["el cuerpo debe ser un objeto JSON"])
    return _escribir(_fusionar(_config().model_dump(mode="json"), cambios))


def importar_avatar_desde(contenido: bytes, nombre: str):
    """Como ``importar_avatar`` pero desde el contenido (lo usa la API)."""
    import os
    import tempfile

    from ipsis.aplicacion.avatar import importar_avatar as importar

    _exigir_proyecto()
    descriptor, temporal = tempfile.mkstemp(suffix=".avatar.json")
    try:
        with os.fdopen(descriptor, "wb") as archivo:
            archivo.write(contenido)
        return importar(temporal, nombre)
    finally:
        os.unlink(temporal)


def resumen_admin() -> dict:
    """Todo lo que el panel necesita para mostrar y editar la personalidad."""
    from ipsis.lenguaje.tonos import SITUACIONES

    resumen = resumen_personalidad()
    avatares, _ = listar_avatares()
    return {
        "config": resumen.config.model_dump(mode="json"),
        "tonos": [t.__dict__ for t in listar_tonos()],
        "situaciones": {s: {"origen": r.origen, "variables": sorted(r.permitidas)} for s, r in SITUACIONES.items()},
        "eventos": {e: {"sugerida": s, "respaldo": r} for e, (s, r) in EVENTOS.items()},
        "avatares": [{"nombre": a.nombre, "origen": a.origen, "animaciones": list(a.animaciones),
                      "expresiones": list(a.expresiones)} if not isinstance(a, tuple)
                     else {"nombre": a[0], "origen": a[1], "error": a[2]} for a in avatares],
        "avisos_tono": avisos_neutralidad(resumen.config),
        "avatar": {"nombre": resumen.avatar.nombre, "estado": resumen.avatar.estado,
                   "mensaje": resumen.avatar.mensaje, "claves": resumen.avatar.claves,
                   "respaldos": resumen.avatar.respaldos},
    }


def config_avatar_publica() -> dict:
    """Lo que el widget necesita del avatar (``/config``). ``activo`` es falso si
    falta o no es válido: el widget muestra el ícono."""
    config = _config()
    estado = estado_avatar(config)
    a = config.avatar
    activo = estado.estado == "ok"
    return {
        "activo": activo,
        "nombre": a.definicion,
        "url_definicion": f"/avatares/{a.definicion}.avatar.json" if activo else None,
        "url_motor": "/avatar.js" if activo else None,
        "ubicacion": a.ubicacion, "tamano": a.tamano, "en_lanzador": a.en_lanzador,
        "mirada": a.mirada.model_dump(), "inactividad_min": a.inactividad_min,
        "eventos": estado.claves,
        # Respaldo de cada evento: el widget lo usa si la definición no trae la clave.
        "respaldos": {evento: respaldo for evento, (_, respaldo) in EVENTOS.items() if respaldo in EVENTOS},
    }


def definicion_publica(nombre: str) -> dict:
    """Definición del avatar con los colores del proyecto aplicados."""
    from ipsis.aplicacion.avatar import cargar_avatar, con_colores

    _, datos = cargar_avatar(nombre)
    colores = _config().avatar.colores
    return con_colores(datos, colores.cuerpo, colores.ojos)
