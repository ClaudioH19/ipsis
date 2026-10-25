"""Validación versionada de los archivos principales de configuración."""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ipsis.recursos.mensajes import t

CONFIG_VERSION = 8
COMPONENTE_CONFIG_KEYS = (
    "parser", "chunker", "dense_encoder", "sparse_encoder", "retriever",
    "fusion", "reranker", "evidence_verifier",
)
# Componentes del motor v1 (retirado): un engine.yaml anterior todavía los trae y se ignoran al cargar.
COMPONENTES_RETIRADOS = ("intent_classifier", "answer_extractor", "response_renderer", "abstention_policy")
# Secciones de engine.yaml y ajustes de perfil que solo usaba v1 (cascada, umbrales, redacción por plantilla).
# Se listan los nombres internos y los del archivo: estas claves ya no están en el glosario que los traduce.
SECCIONES_RETIRADAS = ("redaccion", "rendering", "abstencion", "abstention", "criterios_aceptacion", "acceptance_criteria")
AJUSTES_RETIRADOS = ("cascada", "cascade", "etapas", "stages", "lexico", "lexical", "umbrales_por_defecto",
                     "default_thresholds", "alternativas", "alternatives")


class ConfiguracionEstricta(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegistroConfig(ConfiguracionEstricta):
    """Registro de consultas (``.ipsis/logs/queries.jsonl``): apagado por privacidad."""

    activo: bool = False


class AsistenteConfig(ConfiguracionEstricta):
    config_version: int = Field(default=CONFIG_VERSION, ge=1)
    nombre_asistente: str = Field(default="Asistente documental", min_length=1)
    descripcion_dominio: str = Field(default="la información disponible", min_length=1)
    idioma: str = Field(default="es", min_length=2)
    # «bm25» es de diagnóstico (ipsis benchmark): ipsis init no lo ofrece.
    perfil: Literal["light", "medium", "bm25"] = "light"
    cors_origenes: list[str] = Field(default_factory=list)
    claves_widget: list[str] = Field(default_factory=list)
    registro: RegistroConfig = Field(default_factory=RegistroConfig)


class PreparacionConfig(ConfiguracionEstricta):
    modo: Literal["legacy", "estructural_v1"] = "legacy"
    max_palabras_unidad: int = Field(default=400, ge=32, le=4000)
    palabras_hijo: int = Field(default=80, ge=16, le=1000)
    # Alcance («Práctica Profesional II») y términos que distinguen a unidades hermanas, agregados a lo que se
    # indexa y puntúa. Desactivados por defecto; cambiarlos obliga a reindexar.
    alcance: bool = False
    rasgos_distintivos: int = Field(default=0, ge=0, le=8)
    umbral_hermanos: float = Field(default=0.5, gt=0.0, le=1.0)
    # Cómo se agrupan las hermanas: «tfidf» (texto, sin modelo) o «vectores» (vecinos del modelo denso sobre cada
    # unidad: codifica el corpus una vez más al indexar). El umbral de vectores es un coseno alto (e5: 0,93 a 0,97).
    similitud_hermanos: Literal["tfidf", "vectores"] = "tfidf"
    umbral_vectores: float = Field(default=0.95, gt=0.0, le=1.0)


class RecuperacionConfig(ConfiguracionEstricta):
    modelo: str | None = None  # si falta, el modelo denso del perfil
    estrategia_chunking: str = Field(min_length=1)
    con_header: bool = False
    # «extendido» agrega a la cabecera los tipos de dato, la condición y la excepción del fragmento.
    detalle_cabecera: Literal["basico", "extendido"] = "basico"
    modo: Literal["vectorial", "hibrida", "dispersa"] = "hibrida"
    top_k: int = Field(default=3, ge=1)
    coleccion_base: str = Field(min_length=1)
    qdrant_path: str = ".ipsis/index/qdrant"
    version_coleccion: int = Field(default=1, ge=1)
    preparacion: PreparacionConfig = Field(default_factory=PreparacionConfig)


class ComponentesConfig(ConfiguracionEstricta):
    """Selección declarativa de implementaciones de la tubería.

    Los nombres son estables; la resolución de factories vive en
    ``ipsis.nucleo.contratos``. Un valor ``None`` desactiva un componente opcional.
    """

    parser: str = Field(default="builtin", min_length=1)
    chunker: str = Field(default="builtin", min_length=1)
    dense_encoder: str = Field(default="onnx", min_length=1)
    sparse_encoder: str = Field(default="bm25", min_length=1)
    retriever: str = Field(default="qdrant", min_length=1)
    fusion: str = Field(default="rrf", min_length=1)
    reranker: str | None = Field(default=None, min_length=1)
    evidence_verifier: str = Field(default="literal_offsets", min_length=1)


class QdrantConfig(ConfiguracionEstricta):
    modo: Literal["local", "servidor"] = "local"
    url_servidor: str = "http://localhost:6333"


class ServicioConfig(ConfiguracionEstricta):
    concurrencia_maxima: int = Field(default=4, ge=1)


class ConversacionConfig(ConfiguracionEstricta):
    # Una conversación sin preguntas por este tiempo se olvida (ipsis.consulta.seguimiento).
    vencimiento_minutos: float = Field(default=30, gt=0)
    max_sesiones: int = Field(default=1024, ge=1)


class LimitePeticionesConfig(ConfiguracionEstricta):
    capacidad: int = Field(default=100, ge=1)
    tasa_por_segundo: float = Field(default=1.0, gt=0)


class SeguridadConfig(ConfiguracionEstricta):
    limite_peticiones: LimitePeticionesConfig = Field(default_factory=LimitePeticionesConfig)


class PresentacionConfig(ConfiguracionEstricta):
    """Presentación según la forma de los resultados (ADR 0010): encendida por defecto.

    ``margen_claro`` es la separación mínima entre la primera y la segunda fuente para llamar «clara» a una página; ``None``
    la desactiva (solo quedan ``variantes``, ``documentos`` y ``neutral``). Se mide por perfil, porque la escala del
    puntaje de ``light`` (recuperación) y la de ``medium`` (logit del reranker) no son comparables.
    """

    activo: bool = True
    margen_claro: float | None = Field(default=None, ge=0)
    margen_claro_por_perfil: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def margenes_no_negativos(self):
        if any(v < 0 for v in self.margen_claro_por_perfil.values()):
            raise ValueError("clear_margin_by_profile requiere márgenes no negativos")
        return self


class PipelineV2Config(ConfiguracionEstricta):
    """Fuentes ordenadas, contexto de lectura y destacado QA optativo."""

    corregir_erratas: bool = True
    max_caracteres_contexto: int = Field(default=12000, ge=256, le=100000)
    recuperar_n: int = Field(default=60, ge=1, le=500)
    rerank_candidatos: int = Field(default=60, ge=1, le=500)
    rerank_k: int = Field(default=8, ge=1, le=500)  # Compatibilidad; ya no recorta el ranking publicado.
    lote_reranker: int = Field(default=2, ge=1, le=32)
    max_tokens_reranker: int = Field(default=256, ge=64, le=8192)
    presupuesto_consulta_ms: int = Field(default=2500, ge=1, le=30000)
    leer_m: int = Field(default=4, ge=1, le=100)
    resultados_n: int = Field(default=3, ge=1, le=50)
    max_caracteres_resultado: int = Field(default=16000, ge=256, le=100000)
    vecinos_contexto: int = Field(default=1, ge=0, le=5)
    destacar_fragmentos: bool = False
    max_tokens_pasaje: int = Field(default=384, ge=64, le=512)
    stride: int = Field(default=128, ge=0, le=256)
    presentacion: PresentacionConfig = Field(default_factory=PresentacionConfig)

    @model_validator(mode="after")
    def presupuestos(self):
        if self.rerank_candidatos > self.recuperar_n:
            raise ValueError("v2 requiere rerank_candidates <= retrieve_n")
        if self.stride >= self.max_tokens_pasaje - 32:
            raise ValueError("v2 requiere stride menor que la ventana útil de lectura")
        return self


class MediaConfig(ConfiguracionEstricta):
    """Carril multimedia (ADR 0011): encendido por defecto, con el umbral medido en M2.2.

    ``puntaje_minimo`` es un coseno denso (absoluto); ``None`` significa «no se muestra nada»: la búsqueda corre y queda
    en el diagnóstico, pero ninguna ficha se publica. Sin carpeta ``media/`` indexada no hace nada.
    """

    activo: bool = True
    max_resultados: int = Field(default=1, ge=1, le=5)
    puntaje_minimo: float | None = Field(default=0.874, ge=-1.0, le=1.0)
    presupuesto_ms: int = Field(default=150, ge=1, le=5000)


class MotorConfig(ConfiguracionEstricta):
    config_version: int = Field(default=CONFIG_VERSION, ge=1)
    pipeline: Literal["v2"] = "v2"
    v2: PipelineV2Config = Field(default_factory=PipelineV2Config)
    media: MediaConfig = Field(default_factory=MediaConfig)
    recuperacion: RecuperacionConfig
    componentes: ComponentesConfig = Field(default_factory=ComponentesConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    servicio: ServicioConfig = Field(default_factory=ServicioConfig)
    conversacion: ConversacionConfig = Field(default_factory=ConversacionConfig)
    seguridad: SeguridadConfig = Field(default_factory=SeguridadConfig)
    pipeline_version: str = "ingesta-0.1.0"
    # Sobrescrituras del perfil de instalación (ver ipsis/configuracion/perfiles.py).
    ajustes_perfil: dict[str, Any] = Field(default_factory=dict)


PREPARACION_ESTRUCTURAL = {"modo": "estructural_v1", "max_palabras_unidad": 400, "palabras_hijo": 80,
                           "rasgos_distintivos": 5, "umbral_hermanos": 0.6}


def activar_preparacion_estructural(motor: dict[str, Any]) -> bool:
    """Activa la preparación estructural en un ``engine.yaml`` (claves internas) que usa v2 y no eligió
    preparación. Una elección explícita, incluida ``legacy``, se respeta; un ``pipeline: v1`` heredado también
    (conserva su índice actual hasta que se reindexe). Devuelve si cambió."""
    if motor.get("pipeline", "v2") != "v2":
        return False
    recuperacion = motor.setdefault("recuperacion", {})
    if "preparacion" in recuperacion:
        return False
    recuperacion["preparacion"] = dict(PREPARACION_ESTRUCTURAL)
    return True


def _migrar(datos: dict[str, Any], nombre: str) -> dict[str, Any]:
    """Migra una configuración a la versión vigente sin mutar la entrada.

    La versión 1 es la primera versión pública. La migración explícita de
    ``0`` cubre archivos creados antes de que ``config_version`` fuese
    obligatorio; es idempotente y deja la validación estricta para Pydantic.
    """
    if not isinstance(datos, dict):
        raise TypeError(t("core.not_yaml_object", name=nombre))
    salida = deepcopy(datos)
    version = salida.get("config_version", 0)
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise ValueError(t("core.config_version_type", name=nombre))
    if version > CONFIG_VERSION:
        raise ValueError(t("core.config_version_newer", name=nombre, version=version, supported=CONFIG_VERSION))
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
                    raise ValueError(t("core.reranker_options"))
                if heredado is not None and seleccionado not in {None, heredado}:
                    raise ValueError(t("core.reranker_conflict"))
                if heredado is not None:
                    componentes["reranker"] = heredado
            salida["config_version"] = 2
            version = 2
        elif version == 2:
            # v3: un único config/domain.yaml reemplaza a los perfiles
            # de dominio con nombre, y los artefactos pasan de .cache/ a .ipsis/.
            # Los archivos los mueve ipsis.configuracion.migraciones.
            if nombre == "asistente":
                # En v2, «perfil» era el perfil de dominio; en v3 es el perfil de
                # instalación. Los proyectos existentes conservan el comportamiento
                # sin modelos adicionales: light.
                salida.pop("perfil", None)
                salida["perfil"] = "light"
            if nombre == "motor":
                (salida.get("redaccion") or {}).pop("metodo_seleccion", None)
                componentes = salida.get("componentes") or {}
                if componentes.get("dense_encoder") == "sentence_transformers":
                    componentes["dense_encoder"] = "onnx"  # sin torch desde el plan V3
                recuperacion = salida.get("recuperacion") or {}
                # Los prefijos del modelo los define el catálogo (ipsis/modelos/catalogo.py).
                recuperacion.pop("prefijo_query", None)
                recuperacion.pop("prefijo_documento", None)
                if recuperacion.get("qdrant_path") == ".cache/qdrant_local":
                    recuperacion["qdrant_path"] = ".ipsis/index/qdrant"
            salida["config_version"] = 3
            version = 3
        elif version == 3:
            # v4: la política por capas de v3 (su única política) se reemplaza por
            # cascada_v1, que decide con las señales de la cascada y los umbrales
            # del perfil.
            if nombre == "motor":
                componentes = salida.get("componentes") or {}
                if componentes.get("abstention_policy") is not None:
                    componentes["abstention_policy"] = "cascada_v1"
                # Los umbrales viven en el perfil y en calibration.yaml; de la
                # abstención solo queda la recuperación dirigida por premisa.
                abstencion = salida.get("abstencion")
                if isinstance(abstencion, dict):
                    premisa = abstencion.get("capa_b_premisa") or {}
                    salida["abstencion"] = {
                        "max_fragmentos_adicionales": int(
                            abstencion.get("max_fragmentos_adicionales", premisa.get("max_fragmentos_adicionales", 2))
                        ),
                    }
            salida["config_version"] = 4
            version = 4
        elif version == 4:
            # v5: claves y valores en inglés en el disco. El glosario (configuracion/glosario.py)
            # traduce al cargar, así que en memoria no cambia nada.
            salida["config_version"] = 5
            version = 5
        elif version == 5:
            if nombre == "motor":
                # La selección explícita se conserva; sin selector se usa v2.
                salida.setdefault("pipeline", "v2")
            salida["config_version"] = 6
            version = 6
        elif version == 6:
            if nombre == "motor" and isinstance(salida.get("v2"), dict):
                # El experimento se retiró; conservar los otros presupuestos.
                salida["v2"].pop("consejo", None)
                salida["v2"].pop("council", None)
            salida["config_version"] = 7
            version = 7
        elif version == 7:
            # v8: los proyectos con v2 y sin elegir preparación pasan a la estructural (ADR 0009).
            if nombre == "motor":
                activar_preparacion_estructural(salida)
            salida["config_version"] = 8
            version = 8
        else:  # protección para que añadir versiones futuras no cree bucles
            raise ValueError(t("core.no_migration", name=nombre, version=version))
    if nombre == "asistente" and salida.get("perfil") == "heavy":
        # El perfil heavy se retiró: no superó a medium en ningún banco (ADR 0003).
        # Un proyecto que lo tenía se carga como medium; si su índice era de otro
        # modelo denso, ``ipsis profile show`` pide reindexar.
        salida["perfil"] = "medium"
    if nombre == "motor":
        _retirar_motor_v1(salida)
    elif nombre == "asistente":
        salida.pop("postura", None)  # las alternativas de abstención eran de v1
        salida.pop("posture", None)
    return salida


_AVISADO_V1 = False


def _retirar_motor_v1(motor: dict[str, Any]) -> None:
    """El motor v1 se retiró (ADR 0012): un proyecto que lo elegía pasa a v2, con un aviso por proceso, y
    pierden efecto los componentes que solo él usaba. La preparación del índice no cambia: no hace falta reindexar."""
    global _AVISADO_V1
    if motor.get("pipeline") == "v1":
        motor["pipeline"] = "v2"
        if not _AVISADO_V1:
            _AVISADO_V1 = True
            logging.getLogger(__name__).warning(t("core.pipeline_v1_retired"))
    componentes = motor.get("componentes")
    if isinstance(componentes, dict):
        for clave in COMPONENTES_RETIRADOS:
            componentes.pop(clave, None)
    for clave in SECCIONES_RETIRADAS:
        motor.pop(clave, None)
    ajustes = motor.get("ajustes_perfil")
    if isinstance(ajustes, dict):
        for clave in AJUSTES_RETIRADOS:
            ajustes.pop(clave, None)


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
