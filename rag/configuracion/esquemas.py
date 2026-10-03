"""Validación versionada de los archivos principales de configuración."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CONFIG_VERSION = 3
COMPONENTE_CONFIG_KEYS = (
    "parser", "chunker", "dense_encoder", "sparse_encoder", "retriever",
    "fusion", "reranker", "intent_classifier", "answer_extractor",
    "evidence_verifier", "response_renderer", "abstention_policy",
)


class ConfiguracionEstricta(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AsistenteConfig(ConfiguracionEstricta):
    config_version: int = Field(default=CONFIG_VERSION, ge=1)
    nombre_asistente: str = Field(default="Asistente documental", min_length=1)
    descripcion_dominio: str = Field(default="los documentos cargados", min_length=1)
    idioma: str = Field(default="es", min_length=2)
    cors_origenes: list[str] = Field(default_factory=list)
    claves_widget: list[str] = Field(default_factory=list)


class RecuperacionConfig(ConfiguracionEstricta):
    modelo: str = Field(min_length=1)
    estrategia_chunking: str = Field(min_length=1)
    con_header: bool = False
    modo: Literal["vectorial", "hibrida"] = "hibrida"
    top_k: int = Field(default=3, ge=1)
    coleccion_base: str = Field(min_length=1)
    qdrant_path: str = ".rag/indice/qdrant"
    version_coleccion: int = Field(default=1, ge=1)


class ComponentesConfig(ConfiguracionEstricta):
    """Selección declarativa de implementaciones de la tubería.

    Los nombres son estables; la resolución de factories vive en
    ``rag.nucleo.contratos``. Un valor ``None`` desactiva un componente opcional.
    """

    parser: str = Field(default="builtin", min_length=1)
    chunker: str = Field(default="builtin", min_length=1)
    dense_encoder: str = Field(default="sentence_transformers", min_length=1)
    sparse_encoder: str = Field(default="bm25", min_length=1)
    retriever: str = Field(default="qdrant", min_length=1)
    fusion: str = Field(default="rrf", min_length=1)
    reranker: str | None = Field(default=None, min_length=1)
    intent_classifier: str = Field(default="rules", min_length=1)
    answer_extractor: str = Field(default="sentence_selector", min_length=1)
    evidence_verifier: str = Field(default="literal_offsets", min_length=1)
    response_renderer: str = Field(default="templates", min_length=1)
    abstention_policy: str = Field(default="layered_v1", min_length=1)


class QdrantConfig(ConfiguracionEstricta):
    modo: Literal["local", "servidor"] = "local"
    url_servidor: str = "http://localhost:6333"


class ServicioConfig(ConfiguracionEstricta):
    concurrencia_maxima: int = Field(default=4, ge=1)


class LimitePeticionesConfig(ConfiguracionEstricta):
    capacidad: int = Field(default=100, ge=1)
    tasa_por_segundo: float = Field(default=1.0, gt=0)


class SeguridadConfig(ConfiguracionEstricta):
    limite_peticiones: LimitePeticionesConfig = Field(default_factory=LimitePeticionesConfig)


class RedaccionConfig(ConfiguracionEstricta):
    longitud_maxima_fragmento_chars: int = Field(default=500, ge=1)
    max_fragmentos_en_respuesta: int = Field(default=2, ge=1)
    score_relativo_minimo: float = Field(default=0.6, ge=0)
    cita_en_texto: Literal["completa", "breve", "ninguna"] = "breve"
    incluir_apertura: bool = True


class MotorConfig(ConfiguracionEstricta):
    config_version: int = Field(default=CONFIG_VERSION, ge=1)
    recuperacion: RecuperacionConfig
    componentes: ComponentesConfig = Field(default_factory=ComponentesConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    servicio: ServicioConfig = Field(default_factory=ServicioConfig)
    seguridad: SeguridadConfig = Field(default_factory=SeguridadConfig)
    redaccion: RedaccionConfig = Field(default_factory=RedaccionConfig)
    abstencion: dict[str, Any] | None = None
    criterios_aceptacion: dict[str, Any] = Field(default_factory=dict)
    pipeline_version: str = "ingesta-0.1.0"


def _migrar(datos: dict[str, Any], nombre: str) -> dict[str, Any]:
    """Migra una configuración a la versión vigente sin mutar la entrada.

    La versión 1 es la primera versión pública. La migración explícita de
    ``0`` cubre archivos creados antes de que ``config_version`` fuese
    obligatorio; es idempotente y deja la validación estricta para Pydantic.
    """
    if not isinstance(datos, dict):
        raise TypeError(f"{nombre} debe ser un objeto YAML")
    salida = deepcopy(datos)
    version = salida.get("config_version", 0)
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise ValueError(f"{nombre}.config_version debe ser un entero no negativo")
    if version > CONFIG_VERSION:
        raise ValueError(
            f"{nombre} usa config_version={version}, pero esta instalación solo soporta "
            f"hasta {CONFIG_VERSION}"
        )
    while version < CONFIG_VERSION:
        if version == 0:
            salida["config_version"] = 1
            version = 1
        elif version == 1:
            if nombre == "motor":
                recuperacion = salida.setdefault("recuperacion", {})
                heredado = recuperacion.pop("reranker", None)
                componentes = salida.setdefault("componentes", {})
                seleccionado = componentes.get("reranker")
                if isinstance(heredado, dict):
                    raise ValueError(
                        "recuperacion.reranker con opciones no puede migrarse "
                        "automáticamente; selecciona componentes.reranker por nombre"
                    )
                if heredado is not None and seleccionado not in {None, heredado}:
                    raise ValueError(
                        "recuperacion.reranker y componentes.reranker se contradicen"
                    )
                if heredado is not None:
                    componentes["reranker"] = heredado
            salida["config_version"] = 2
            version = 2
        elif version == 2:
            # v3: un único configuracion/dominio.yaml reemplaza a los perfiles
            # de dominio con nombre, y los artefactos pasan de .cache/ a .rag/.
            # Los archivos los mueve rag.configuracion.migraciones.
            if nombre == "asistente":
                salida.pop("perfil", None)
            if nombre == "motor":
                (salida.get("redaccion") or {}).pop("metodo_seleccion", None)
                recuperacion = salida.get("recuperacion") or {}
                # Los prefijos del modelo los define el catálogo (rag/modelos/catalogo.py).
                recuperacion.pop("prefijo_query", None)
                recuperacion.pop("prefijo_documento", None)
                if recuperacion.get("qdrant_path") == ".cache/qdrant_local":
                    recuperacion["qdrant_path"] = ".rag/indice/qdrant"
            salida["config_version"] = 3
            version = 3
        else:  # protección para que añadir versiones futuras no cree bucles
            raise ValueError(f"no existe migración de {nombre} versión {version}")
    return salida


def migrar_asistente(datos: dict[str, Any]) -> dict[str, Any]:
    return _migrar(datos, "asistente")


def migrar_motor(datos: dict[str, Any]) -> dict[str, Any]:
    return _migrar(datos, "motor")


def validar_asistente(datos: dict[str, Any]) -> dict[str, Any]:
    return AsistenteConfig.model_validate(migrar_asistente(datos)).model_dump(mode="python")


def validar_motor(datos: dict[str, Any]) -> dict[str, Any]:
    return MotorConfig.model_validate(migrar_motor(datos)).model_dump(mode="python")


__all__ = [
    "CONFIG_VERSION", "COMPONENTE_CONFIG_KEYS", "AsistenteConfig", "ComponentesConfig",
    "MotorConfig", "migrar_asistente", "migrar_motor", "validar_asistente", "validar_motor",
]
