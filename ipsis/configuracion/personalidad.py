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
from ipsis.recursos.mensajes import t

TONOS = ("cordial", "formal", "serious", "upbeat", "friendly", "empathetic", "direct")
# Variables de las plantillas anteriores a ipsis 0.9 → las actuales.
VARIABLES_ANTERIORES = {"nombre_asistente": "assistant_name", "descripcion_dominio": "domain_description",
                        "termino": "term", "entidad": "entity"}
# Nombres anteriores a ipsis 0.9 (en español) → los actuales; los usa la migración.
TONOS_ANTERIORES = {"serio": "serious", "animoso": "upbeat", "cercano": "friendly", "empatico": "empathetic",
                    "directo": "direct"}
SITUACIONES_ANTERIORES = {
    "saludo": "greeting", "agradecimiento": "thanks", "despedida": "farewell", "capacidad": "capability",
    "apertura": "opening", "complemento": "addition", "condicion": "condition", "excepcion": "exception",
    "relacionado_intro": "related_intro", "foco_ausente": "missing_focus", "sin_respuesta": "no_answer",
    "premisa_no_encontrada": "premise_not_found", "bienvenida": "welcome", "esperando": "waiting",
    "invitacion_citas": "citations_hint", "error_red": "network_error", "error_limite": "rate_limit_error",
    "error_servicio": "service_error",
}
EVENTOS_ANTERIORES = {
    "inactivo": "idle", "lanzador": "launcher", "saludo": "greeting", "atento": "attentive", "escribiendo": "typing",
    "enviado": "sent", "pensando": "thinking", "pensando_largo": "thinking_long", "respuesta_ok": "answer_ok",
    "respuesta_relacionada": "answer_related", "sin_respuesta": "no_answer", "conversacional": "conversational",
    "despedida": "farewell", "somnoliento": "sleepy", "despertar": "wake_up",
}
CLAVES_FOLIO_ANTERIORES = {
    "atento": "attentive", "leyendo": "reading", "contento": "happy", "amable": "kind", "dudoso": "unsure",
    "apenado": "sorry", "pensando": "thinking", "pensando-lado": "thinking-side", "somnoliento": "sleepy",
    "ojos-cerrados": "eyes-closed", "sorprendido": "surprised", "preocupado": "worried", "asentir-abajo": "nod-down",
    "inactivo": "idle", "saludo": "wave", "escuchando": "listening", "asentir": "nod",
    "pensando-largo": "thinking-long", "despedida": "goodbye", "despertar": "wake-up",
}


def vocabulario_actual(datos: dict) -> dict:
    """``personality.yaml`` (nombres del archivo) con tonos, situaciones, variables y eventos actuales."""
    tono = datos.get("tone")
    if isinstance(tono, dict):
        if tono.get("active") in TONOS_ANTERIORES:
            tono["active"] = TONOS_ANTERIORES[tono["active"]]
        plantillas = tono.get("templates")
        if isinstance(plantillas, dict):
            def actuales(texto):
                if not isinstance(texto, str):
                    return texto
                for anterior, actual in VARIABLES_ANTERIORES.items():
                    texto = texto.replace("{" + anterior + "}", "{" + actual + "}")
                return texto

            tono["templates"] = {SITUACIONES_ANTERIORES.get(s, s): ([actuales(t) for t in v] if isinstance(v, list)
                                                                   else actuales(v))
                                 for s, v in plantillas.items()}
    avatar = datos.get("avatar")
    if isinstance(avatar, dict) and isinstance(avatar.get("events"), dict):
        de_folio = avatar.get("definition", "folio") == "folio"
        avatar["events"] = {EVENTOS_ANTERIORES.get(e, e): (CLAVES_FOLIO_ANTERIORES.get(c, c) if de_folio else c)
                            for e, c in avatar["events"].items()}
    return datos
CLAVE_SEMANTICA = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"  # la de @bible-strong/avatar-core
HEX = r"^#[0-9a-f]{6}$"

# evento → (clave sugerida, respaldo si el avatar no la tiene). El respaldo
# puede ser otro evento (se resuelve en cadena) o ``neutral``.
EVENTOS: dict[str, tuple[str, str]] = {
    "idle": ("idle", "neutral"),
    "launcher": ("idle", "idle"),
    "greeting": ("wave", "idle"),
    "attentive": ("attentive", "idle"),
    "typing": ("listening", "attentive"),
    "sent": ("nod", "thinking"),
    "thinking": ("thinking", "idle"),
    "thinking_long": ("thinking-long", "thinking"),
    "answer_ok": ("happy", "idle"),
    "answer_related": ("unsure", "idle"),
    "no_answer": ("sorry", "idle"),
    "conversational": ("kind", "answer_ok"),
    "farewell": ("goodbye", "idle"),
    "error": ("worried", "no_answer"),
    "sleepy": ("sleepy", "idle"),
    "wake_up": ("wake-up", "attentive"),
}
# Eventos que no se asignan a una clave: los resuelve el widget.
EVENTOS_DEL_WIDGET = ("viewing_citations", "follow_pointer", "hidden", "reduced_motion")


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
                raise ValueError(t("core.unknown_event", event=evento, valid=", ".join(EVENTOS)))
            if not re.fullmatch(CLAVE_SEMANTICA, clave or ""):
                raise ValueError(t("core.invalid_event_key", key=clave, event=evento, pattern=CLAVE_SEMANTICA))
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
