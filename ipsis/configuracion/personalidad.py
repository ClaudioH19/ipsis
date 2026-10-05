"""``config/personality.yaml``: tono de las respuestas y avatar del widget.

Es solo presentación: no cambia estados, umbrales, índice ni calibración. Si
el archivo falta rigen los valores por defecto. El catálogo de eventos del
avatar (con su clave sugerida y su respaldo) vive aquí para que la CLI, el
diagnóstico y el servicio usen el mismo.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ipsis.configuracion import rutas

TONOS = ("cordial", "formal", "serio", "animoso", "cercano", "empatico", "directo")
CLAVE_SEMANTICA = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"  # la de @bible-strong/avatar-core
HEX = r"^#[0-9a-f]{6}$"

# evento → (clave sugerida, respaldo si el avatar no la tiene). El respaldo
# puede ser otro evento (se resuelve en cadena) o ``neutral``.
EVENTOS: dict[str, tuple[str, str]] = {
    "inactivo": ("inactivo", "neutral"),
    "lanzador": ("inactivo", "inactivo"),
    "saludo": ("saludo", "inactivo"),
    "atento": ("atento", "inactivo"),
    "escribiendo": ("escuchando", "atento"),
    "enviado": ("asentir", "pensando"),
    "pensando": ("pensando", "inactivo"),
    "pensando_largo": ("pensando-largo", "pensando"),
    "respuesta_ok": ("contento", "inactivo"),
    "respuesta_relacionada": ("dudoso", "inactivo"),
    "sin_respuesta": ("apenado", "inactivo"),
    "conversacional": ("amable", "respuesta_ok"),
    "despedida": ("despedida", "inactivo"),
    "error": ("preocupado", "sin_respuesta"),
    "somnoliento": ("somnoliento", "inactivo"),
    "despertar": ("despertar", "atento"),
}
# Eventos que no se asignan a una clave: los resuelve el widget.
EVENTOS_DEL_WIDGET = ("mirando_citas", "seguir_puntero", "oculto", "movimiento_reducido")


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TonoConfig(_Estricto):
    activo: Literal[TONOS] = "cordial"  # type: ignore[valid-type]
    variedad: Literal["rotativa", "fija"] = "rotativa"
    plantillas: dict[str, list[str] | str] = Field(default_factory=dict)


class MiradaConfig(_Estricto):
    activa: bool = True
    amplitud_ojos: float = Field(default=6, ge=0, le=20)
    amplitud_cabeza: float = Field(default=8, ge=0, le=20)
    zona_muerta: int = Field(default=24, ge=0, le=200)


class ColoresAvatar(_Estricto):
    cuerpo: str | None = Field(default=None, pattern=HEX)
    ojos: str | None = Field(default=None, pattern=HEX)


class AvatarConfig(_Estricto):
    activo: bool = True
    definicion: str = Field(default="folio", pattern=CLAVE_SEMANTICA, max_length=64)
    ubicacion: Literal["cabecera", "esquina-superior", "esquina-inferior"] = "cabecera"
    tamano: int = Field(default=56, ge=32, le=160)
    en_lanzador: bool = True
    mirada: MiradaConfig = Field(default_factory=MiradaConfig)
    inactividad_min: float = Field(default=2, ge=0.5, le=60)
    colores: ColoresAvatar = Field(default_factory=ColoresAvatar)
    eventos: dict[str, str] = Field(default_factory=dict)

    @field_validator("eventos")
    @classmethod
    def _eventos_validos(cls, valor: dict[str, str]) -> dict[str, str]:
        import re

        for evento, clave in valor.items():
            if evento not in EVENTOS:
                raise ValueError(f"evento desconocido {evento!r}; válidos: {', '.join(EVENTOS)}")
            if not re.fullmatch(CLAVE_SEMANTICA, clave or ""):
                raise ValueError(f"clave inválida {clave!r} para {evento!r} (formato: {CLAVE_SEMANTICA})")
        return valor


class PersonalidadConfig(_Estricto):
    config_version: Literal[1] = 1
    tono: TonoConfig = Field(default_factory=TonoConfig)
    avatar: AvatarConfig = Field(default_factory=AvatarConfig)


def ruta_personalidad(proyecto: str | Path | None = None) -> Path:
    return Path(proyecto or ".") / rutas.PERSONALIDAD


def cargar_personalidad(proyecto: str | Path | None = None) -> PersonalidadConfig:
    """La personalidad del proyecto; los valores por defecto si el archivo no existe."""
    ruta = ruta_personalidad(proyecto)
    if not ruta.is_file():
        return PersonalidadConfig()
    from ipsis.configuracion.archivos import interpretar

    return PersonalidadConfig.model_validate(interpretar(ruta.read_text(encoding="utf-8"), "personalidad"))


def guardar_personalidad(config: PersonalidadConfig, proyecto: str | Path | None = None) -> Path:
    """Escritura atómica; conserva el bloque de comentarios inicial del archivo."""
    ruta = ruta_personalidad(proyecto)
    cabecera = ""
    if ruta.is_file():
        for linea in ruta.read_text(encoding="utf-8").splitlines(keepends=True):
            if not linea.startswith("#"):
                break
            cabecera += linea
    from ipsis.configuracion.archivos import escribir

    return escribir(ruta, config.model_dump(mode="json", exclude_none=True), "personalidad", cabecera)


__all__ = [
    "AvatarConfig", "CLAVE_SEMANTICA", "ColoresAvatar", "EVENTOS", "EVENTOS_DEL_WIDGET", "HEX", "MiradaConfig",
    "PersonalidadConfig", "TONOS", "TonoConfig", "cargar_personalidad", "guardar_personalidad", "ruta_personalidad",
]
