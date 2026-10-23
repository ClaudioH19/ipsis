"""Casos de uso de consulta: construir el motor desde la configuración."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ipsis.modelos.catalogo import obtener as obtener_modelo
from ipsis.configuracion.glosario import ETAPAS
from ipsis.consulta.plantillas import cargar_plantillas
# El servicio usa los errores del motor a través de esta capa.
from ipsis.consulta.errores import ContinuacionInvalida, MotorNoListo, MotorSaturado
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.configuracion.perfiles import perfil_efectivo
from ipsis.nucleo.registro import RegistroComponentes
from ipsis.nucleo.contratos import QueryEngine
from ipsis.recursos.mensajes import t


def _hash_corpus_indexado(retriever) -> str | None:
    """``hash_corpus`` del manifiesto del índice abierto (``None`` si no hay)."""
    nombre = getattr(getattr(retriever, "coleccion", None), "nombre", None)
    if not nombre:
        return None
    from ipsis.indice.manifiesto import cargar_manifiesto

    try:
        return cargar_manifiesto(nombre).hash_corpus
    except (FileNotFoundError, ValueError):
        return None


def construir_motor(
    cfg: dict[str, Any],
    *,
    cfg_dominio: dict[str, Any] | None = None,
    registro: RegistroComponentes | None = None,
) -> QueryEngine:
    """Construye el motor completo desde la selección declarativa.

    Primero valida todos los nombres configurados y solo después crea
    los componentes que participan en consulta. Así un nombre inválido
    falla durante el arranque, incluso si corresponde a otra fase como
    ingesta.
    """
    from ipsis.configuracion.carga import (
        cargar_dominio,
        config_recuperacion,
        config_servicio,
    )
    from ipsis.aplicacion.registro_base import registrar_componentes_base
    from ipsis.consulta.admision import ConfiguracionAdmision, ControlAdmision
    from ipsis.nucleo.progreso import informar

    informar("configuracion")
    if cfg.get("pipeline", "v2") != "v2":
        raise ValueError("pipeline debe ser v2 (el motor v1 se retiró)")
    from ipsis.configuracion.esquemas import PipelineV2Config

    opciones_v2 = PipelineV2Config.model_validate(cfg.get("v2") or {}).model_dump()
    componentes = dict(cfg.get("componentes") or {})
    if not componentes:
        raise ValueError(t("app.no_components"))
    registro = registrar_componentes_base(registro or RegistroComponentes())
    for tipo, nombre in componentes.items():
        if nombre is not None:
            registro.obtener(tipo, nombre)

    cfg_dominio = cfg_dominio or cargar_dominio()
    from ipsis.configuracion.perfiles import ajustes_de_idioma

    ajustes_perfil, candidatos_idioma = ajustes_de_idioma(
        cfg_dominio.get("perfil", "light"), cfg.get("ajustes_perfil"), cfg_dominio.get("idioma"))
    # 60 es el valor por defecto de v2: significa «el del perfil para este idioma».
    if candidatos_idioma and opciones_v2["rerank_candidatos"] == 60:
        opciones_v2["rerank_candidatos"] = min(candidatos_idioma, opciones_v2["recuperar_n"])
    perfil_instalacion = perfil_efectivo(cfg_dominio.get("perfil", "light"), ajustes_perfil)
    idioma = cargar_paquete(cfg_dominio.get("idioma", "es"), proyecto=Path.cwd())
    from ipsis.lenguaje.sinonimos import huella_lexica

    hash_lexico = huella_lexica(idioma)
    if not idioma.respaldo:
        informar("lexico")
        from ipsis.lenguaje.ortografia import raices_lexico

        raices_lexico(idioma.codigo.split("-")[0], idioma.stemmer)  # la primera errata no espera al léxico
    plantillas = cargar_plantillas(idioma, cfg_dominio)
    cfg_rec = config_recuperacion(cfg)
    cfg_srv = config_servicio(cfg)

    informar("apertura_indice")
    retriever = registro.crear(
        "retriever",
        componentes["retriever"],
        recuperacion=cfg_rec,
        qdrant=cfg.get("qdrant", {}),
    )
    from ipsis.consulta.v2 import MotorV2
    from ipsis.indice.contextos import envolver_contextos

    retriever = envolver_contextos(retriever)
    if not hasattr(retriever, "ampliar_resultado") and getattr(getattr(retriever, "coleccion", None), "nombre", None):
        from ipsis.indice.contextos import RecuperadorConContextos
        from ipsis.ingesta.ingesta import parsear_corpus
        from ipsis.configuracion import rutas

        documentos = parsear_corpus(rutas.DOCUMENTOS, preparacion="legacy")
        retriever = RecuperadorConContextos(retriever, {}, {d.doc_id: d for d in documentos})
    hash_corpus = _hash_corpus_indexado(retriever)
    motor = MotorV2(
        retriever=retriever,
        verificador=registro.crear("evidence_verifier", componentes["evidence_verifier"]),
        idioma=idioma, perfil=perfil_instalacion, plantillas=plantillas,
        control_admision=ControlAdmision(ConfiguracionAdmision(
            concurrencia_maxima=cfg_srv["concurrencia_maxima"])),
        opciones=opciones_v2,
    )
    motor.backend = componentes["retriever"]
    from ipsis.configuracion.esquemas import MediaConfig

    opciones_media = MediaConfig.model_validate(cfg.get("media") or {}).model_dump()
    if opciones_media["activo"]:
        from ipsis.consulta.media import BuscadorMedia

        # El carril es opcional: un recuperador sin colección Qdrant o un fallo al abrirla no impiden servir documentos.
        try:
            motor.buscador_media = (BuscadorMedia.desde_recuperador(retriever, cfg_rec, opciones_media)
                                    if hasattr(retriever, "coleccion") else None)
        except Exception as error:  # noqa: BLE001
            logging.getLogger(__name__).warning("carril multimedia no disponible: %s", type(error).__name__)
            motor.buscador_media = None
        motor.opciones_media = {"presupuesto_ms": opciones_media["presupuesto_ms"]}
    if perfil_instalacion.modelos.reranker:
        motor.reranker = registro.crear("reranker", "onnx", modelo=perfil_instalacion.modelos.reranker)
        motor.reranker.lote = motor.opciones["lote_reranker"]
        spec = motor.reranker.spec
        motor.reranker.spec = spec.model_copy(update={"max_tokens": min(
            spec.max_tokens, motor.opciones["max_tokens_reranker"])})
    if perfil_instalacion.modelos.lector and motor.opciones["destacar_fragmentos"]:
        motor.lector = registro.crear(
            "answer_reader", "onnx", modelo=perfil_instalacion.modelos.lector,
            max_tokens_pasaje=motor.opciones["max_tokens_pasaje"], stride=motor.opciones["stride"],
        )
    from ipsis import __version__

    motor.metadatos_auditoria = {
        "version_ipsis": __version__, "backend": motor.backend, "pipeline": "v2",
        "componentes": {
            "retriever": componentes["retriever"], "fusion": componentes["fusion"],
            "reranker": "onnx" if motor.reranker is not None else None,
            "answer_reader": "onnx" if motor.lector is not None else None,
            "evidence_verifier": componentes["evidence_verifier"],
            "response_renderer": "fuentes_ordenadas_v2",
            "abstention_policy": "recuperacion_sin_certificacion_de_respuesta_v2",
        },
        "perfil_efectivo": perfil_instalacion.model_dump(mode="json"),
        "modelos": {rol: {"id": nombre, "revision": obtener_modelo(nombre).revision,
                           "archivo_onnx": obtener_modelo(nombre).archivo_onnx()}
                    for rol, nombre in perfil_instalacion.modelos.model_dump().items() if nombre},
        "hash_corpus": hash_corpus, "hash_lexico": hash_lexico,
        "etapas_efectivas": list(motor.etapas_efectivas),
        "calibracion_aplicada": motor.abstencion_calibrada,
        "hash_configuracion": hashlib.sha256(json.dumps(
            {"motor": cfg, "asistente": cfg_dominio}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "preparacion_indice": getattr(retriever, "preparacion_indice", None),
        "presupuestos_v2": dict(motor.opciones),
    }
    if motor.lector is None:
        motor.metadatos_auditoria["modelos"].pop("lector", None)
    if motor.reranker is not None:
        motor.metadatos_auditoria["modelos"]["reranker"].update(
            lote=motor.reranker.lote, max_tokens=motor.reranker.spec.max_tokens)
    motor._marca_presentacion = _marca_presentacion()  # base para recargar_presentacion
    return motor


def motor_vacio() -> QueryEngine:
    """Motor sin componentes: contesta «no listo» mientras el real se recarga o aún no existe."""
    from ipsis.consulta.v2 import MotorV2

    return MotorV2()


def construir_motor_del_proyecto() -> QueryEngine:
    """Motor del proyecto del directorio actual (lo que sirve ``ipsis serve``)."""
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

    return construir_motor(cargar_proyecto(), cfg_dominio=cargar_dominio())


@dataclass(frozen=True)
class DiagnosticoConsulta:
    """Por qué una consulta terminó como terminó, leído del diagnóstico del motor v2."""

    pregunta: str
    estado: str  # el del contrato HTTP: related, no_answer, conversational
    respuesta: str
    regla: str | None
    motivo: str
    etapas: list[tuple[str, int]]  # en orden de ejecución, en ms (motor ya calentado)
    evidencias: list[dict[str, Any]]
    advertencias: list[str]
    # Dónde se gana o se pierde cada fragmento: su lugar en el ranking denso, en
    # BM25, en la fusión y en el reranker, y lo que leyó el lector (si el perfil lo carga).
    candidatos: list[dict[str, Any]] = field(default_factory=list)
    ortografia: dict[str, str] = field(default_factory=dict)

    @property
    def total_ms(self) -> int:
        return sum(ms for _, ms in self.etapas)


def diagnosticar_pregunta(pregunta: str, motor: QueryEngine | None = None) -> DiagnosticoConsulta:
    """Ejecuta ``pregunta`` con el motor del proyecto, en este proceso, y devuelve
    su diagnóstico. No pasa por el servicio HTTP, que no publica el diagnóstico.
    ``motor`` se inyecta en las pruebas (motor falso)."""
    propio = motor is None
    motor = construir_motor_del_proyecto() if propio else motor
    try:
        if propio:
            motor.calentar()  # que las latencias sean las de operación, sin la carga de modelos
        resultado = motor.consultar(pregunta, "rag-diagnostico")
        d = resultado.diagnostico or {}
    finally:
        if propio:
            motor.cerrar()
    contrato = d.get("contrato_http") or {}
    return DiagnosticoConsulta(
        pregunta=pregunta,
        estado=contrato.get("estado", resultado.estado.value),
        respuesta=contrato.get("respuesta", resultado.mensaje_usuario),
        regla=d.get("regla"),
        motivo=resultado.motivo,
        etapas=[(ETAPAS.get(nombre.removesuffix("_ms"), nombre.removesuffix("_ms")), ms)
                for nombre, ms in (d.get("etapas") or {}).items()],
        evidencias=[{k: e.get(k) for k in ("doc_id", "chunk_id", "offset_inicio", "offset_fin", "texto")}
                    for e in d.get("evidencias") or []],
        advertencias=list(d.get("advertencias") or []),
        candidatos=_ranking_diagnostico(d),
        ortografia=dict(d.get("ortografia") or {}),
    )


def _ranking_diagnostico(d: dict) -> list[dict]:
    """El lugar de cada candidato en cada etapa (denso, BM25, fusión, reranker y lector)."""
    rerank = {r["chunk_id"]: (i, r["score"]) for i, r in enumerate(d.get("rerank") or [], start=1)}
    lecturas = {lec["chunk_id"]: lec for lec in d.get("lecturas") or []}
    candidatos = []
    for c in d.get("candidatos") or []:
        cid = c["chunk_id"]
        senales = c.get("signals") or {}
        lectura = lecturas.get(cid) or {}
        candidatos.append({
            "chunk_id": cid, "inicio": c.get("inicio", ""),
            "denso": senales.get("dense_rank"), "bm25": senales.get("sparse_rank"),
            "fusion": senales.get("fusion_rank"),
            "rerank": rerank.get(cid, (None, None))[0], "rerank_score": rerank.get(cid, (None, None))[1],
            "qa": lectura.get("prob_respuesta"), "qa_texto": lectura.get("texto"),
        })
    return candidatos


__all__ = ["DiagnosticoConsulta", "MotorNoListo", "MotorSaturado", "ContinuacionInvalida", "construir_motor",
           "construir_motor_del_proyecto", "diagnosticar_pregunta", "motor_vacio", "recargar_presentacion"]


def _marca_presentacion() -> tuple:
    """mtime de los archivos que cambian el texto que redacta el motor."""
    from ipsis.configuracion import rutas

    marcas = []
    for ruta in (rutas.PERSONALIDAD, rutas.IDIOMA, rutas.ASISTENTE):
        try:
            marcas.append(Path(ruta).stat().st_mtime_ns)
        except OSError:
            marcas.append(None)
    return tuple(marcas)


def recargar_presentacion(motor: QueryEngine) -> bool:
    """Si cambió el tono o los textos del proyecto, el motor toma las plantillas
    nuevas sin reiniciar (un ``stat`` por llamada). Las consultas en curso
    terminan con las anteriores: el cambio es una asignación atómica."""
    from ipsis.configuracion.carga import cargar_dominio

    marca = _marca_presentacion()
    anterior = getattr(motor, "_marca_presentacion", None)
    if anterior is None:
        motor._marca_presentacion = marca
        return False
    if marca == anterior or motor.idioma is None:
        return False
    motor.plantillas = cargar_plantillas(motor.idioma, cargar_dominio())
    motor._marca_presentacion = marca
    return True
