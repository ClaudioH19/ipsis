"""Métricas comparables para bancos de evaluación versionados."""
from __future__ import annotations

import math
import hashlib
import json
from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rag.banco_evaluacion import BancoEvaluacion, CasoEvaluacion, hash_banco
from rag.esquemas import ChunkRecord, EvidenceSpan


class ObservacionEvaluacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caso_id: str
    backend: str
    estado: str
    respuesta: str = ""
    candidatos: list[ChunkRecord] = Field(default_factory=list)
    evidencias: list[EvidenceSpan] = Field(default_factory=list)
    latencia_ms: int = Field(default=0, ge=0)
    etapas_ms: dict[str, int] = Field(default_factory=dict)
    confianza_top1: float = 0.0
    metodo_confianza: str | None = None


class ResumenGrupo(BaseModel):
    n: int
    exactitud_estado: float
    recall_at_k: float
    tasa_falsos_ok: float


class ReporteMetricas(BaseModel):
    schema_version: int = 1
    dataset_id: str
    dataset_version: str
    k: int
    n_casos: int
    recall_at_k: float
    mrr: float
    tasa_falsos_ok: float
    precision_abstencion: float
    exactitud_estado: float
    exactitud_literal: float
    exactitud_offsets: float
    tasa_respuestas_excesivas: float
    distribucion_estados: dict[str, int]
    latencia_media_ms: float
    latencia_p95_ms: float
    latencia_etapas_media_ms: dict[str, float]
    por_backend: dict[str, ResumenGrupo]
    por_categoria: dict[str, ResumenGrupo]
    guardia_falsos_ok: bool


class CalibracionDev(BaseModel):
    split: Literal["dev"] = "dev"
    metodo_confianza: str
    fpr_objetivo: float
    umbral: float
    falsa_respuesta_dev: float
    falsa_abstencion_dev: float
    n_respondibles: int
    n_no_respondibles: int


class ArtefactoEvaluacion(BaseModel):
    schema_version: int = 1
    backend: str
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    configuracion_sha256: str
    configuracion: dict[str, Any]
    indice: dict[str, Any]
    calibracion_dev: CalibracionDev
    reporte: ReporteMetricas
    observaciones: list[ObservacionEvaluacion] = Field(default_factory=list)


ESTADOS_ABSTENCION = {"sin_respuesta", "fuera_dominio", "necesita_aclaracion"}
ESTADOS_OK = {"respuesta_directa", "respuesta_parcial"}


def _solapa(chunk: ChunkRecord, caso: CasoEvaluacion) -> bool:
    return any(
        chunk.doc_id == evidencia.doc_id
        and chunk.offset_inicio < evidencia.offset_fin
        and chunk.offset_fin > evidencia.offset_inicio
        for evidencia in caso.evidencias
    )


def _rango_acierto(caso: CasoEvaluacion, observacion: ObservacionEvaluacion, k: int) -> int | None:
    for rango, chunk in enumerate(observacion.candidatos[:k], start=1):
        if _solapa(chunk, caso):
            return rango
    return None


def _percentil_95(valores: list[int]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return float(ordenados[max(0, math.ceil(0.95 * len(ordenados)) - 1)])


def _resumen_grupo(pares: list[tuple[CasoEvaluacion, ObservacionEvaluacion]], k: int) -> ResumenGrupo:
    respondibles = [(c, o) for c, o in pares if c.respondible]
    no_respondibles = [(c, o) for c, o in pares if not c.respondible]
    aciertos = sum(_rango_acierto(c, o, k) is not None for c, o in respondibles)
    falsos_ok = sum(o.estado in ESTADOS_OK for _c, o in no_respondibles)
    return ResumenGrupo(
        n=len(pares),
        exactitud_estado=(sum(c.estado_esperado == o.estado for c, o in pares) / len(pares) if pares else 0.0),
        recall_at_k=(aciertos / len(respondibles) if respondibles else 0.0),
        tasa_falsos_ok=(falsos_ok / len(no_respondibles) if no_respondibles else 0.0),
    )


def evaluar_observaciones(
    banco: BancoEvaluacion,
    observaciones: list[ObservacionEvaluacion],
    documentos: dict[str, str],
    *,
    k: int = 3,
    limite_respuesta_chars: int = 500,
) -> ReporteMetricas:
    if k < 1 or limite_respuesta_chars < 1:
        raise ValueError("k y limite_respuesta_chars deben ser positivos")
    por_id = {observacion.caso_id: observacion for observacion in observaciones}
    if len(por_id) != len(observaciones):
        raise ValueError("hay observaciones duplicadas")
    ids_esperados = {caso.id for caso in banco.casos}
    if set(por_id) != ids_esperados:
        raise ValueError("las observaciones no coinciden exactamente con los casos del banco")
    pares = [(caso, por_id[caso.id]) for caso in banco.casos]
    respondibles = [(c, o) for c, o in pares if c.respondible]
    no_respondibles = [(c, o) for c, o in pares if not c.respondible]
    rangos = [_rango_acierto(c, o, k) for c, o in respondibles]
    falsos_ok = sum(o.estado in ESTADOS_OK for _c, o in no_respondibles)
    abstenciones = [(c, o) for c, o in pares if o.estado in ESTADOS_ABSTENCION]
    abstenciones_correctas = sum(not c.respondible for c, _o in abstenciones)
    literales = sum(
        bool(c.respuesta_literal)
        and c.respuesta_literal in o.respuesta
        and any(c.respuesta_literal in evidencia.texto for evidencia in o.evidencias)
        for c, o in respondibles
    )
    evidencias = [e for _c, o in pares for e in o.evidencias]
    offsets_validos = sum(
        evidencia.doc_id in documentos
        and documentos[evidencia.doc_id][evidencia.offset_inicio:evidencia.offset_fin] == evidencia.texto
        for evidencia in evidencias
    )
    respuestas = [o for _c, o in pares if o.estado in ESTADOS_OK | {"relacionado"}]
    excesivas = sum(len(o.respuesta) > limite_respuesta_chars for o in respuestas)
    latencias = [o.latencia_ms for _c, o in pares]
    etapas: dict[str, list[int]] = defaultdict(list)
    for _caso, observacion in pares:
        for nombre, valor in observacion.etapas_ms.items():
            etapas[nombre].append(valor)
    grupos_backend: dict[str, list[tuple[CasoEvaluacion, ObservacionEvaluacion]]] = defaultdict(list)
    grupos_categoria: dict[str, list[tuple[CasoEvaluacion, ObservacionEvaluacion]]] = defaultdict(list)
    for caso, observacion in pares:
        grupos_backend[observacion.backend].append((caso, observacion))
        grupos_categoria[caso.categoria.value].append((caso, observacion))

    tasa_falsos_ok = falsos_ok / len(no_respondibles) if no_respondibles else 0.0
    return ReporteMetricas(
        dataset_id=banco.manifiesto.dataset_id,
        dataset_version=banco.manifiesto.dataset_version,
        k=k,
        n_casos=len(pares),
        recall_at_k=sum(rango is not None for rango in rangos) / len(rangos) if rangos else 0.0,
        mrr=sum(1.0 / rango for rango in rangos if rango is not None) / len(rangos) if rangos else 0.0,
        tasa_falsos_ok=tasa_falsos_ok,
        precision_abstencion=(abstenciones_correctas / len(abstenciones) if abstenciones else 0.0),
        exactitud_estado=sum(c.estado_esperado == o.estado for c, o in pares) / len(pares),
        exactitud_literal=literales / len(respondibles) if respondibles else 0.0,
        exactitud_offsets=offsets_validos / len(evidencias) if evidencias else 1.0,
        tasa_respuestas_excesivas=excesivas / len(respuestas) if respuestas else 0.0,
        distribucion_estados=dict(sorted(Counter(o.estado for _c, o in pares).items())),
        latencia_media_ms=mean(latencias) if latencias else 0.0,
        latencia_p95_ms=_percentil_95(latencias),
        latencia_etapas_media_ms={nombre: mean(valores) for nombre, valores in sorted(etapas.items())},
        por_backend={nombre: _resumen_grupo(grupo, k) for nombre, grupo in sorted(grupos_backend.items())},
        por_categoria={nombre: _resumen_grupo(grupo, k) for nombre, grupo in sorted(grupos_categoria.items())},
        guardia_falsos_ok=tasa_falsos_ok == 0.0,
    )


def evaluar_backend_activo(
    ruta_manifiesto: str,
    *,
    k: int | None = None,
    limite_respuesta_chars: int = 500,
) -> ArtefactoEvaluacion:
    """Ejecuta recuperación y motor actuales contra un banco completo."""
    import time
    from pathlib import Path

    from rag.banco_evaluacion import cargar_banco
    from rag.configuracion import cargar_dominio, cargar_proyecto
    from rag.esquemas import QueryAnalysis
    from rag.parsear import parsear_documento
    from rag.servicio.motor import Motor

    ruta = Path(ruta_manifiesto).resolve()
    banco = cargar_banco(ruta)
    cfg = cargar_proyecto()
    k = k or cfg["recuperacion"]["top_k"]
    directorio = (ruta.parent / banco.manifiesto.corpus.directorio).resolve()
    documentos = {}
    for archivo in banco.manifiesto.corpus.archivos:
        documento = parsear_documento(
            str(directorio / archivo.ruta),
            doc_id=archivo.doc_id,
            doc_titulo=archivo.doc_id,
            version="1",
        )
        documentos[archivo.doc_id] = documento.texto_completo

    motor = Motor.desde_configuracion(cfg, cfg_dominio=cargar_dominio())
    etiqueta_backend = (
        f"qdrant_{cfg['recuperacion']['modo']}"
        if motor.backend == "qdrant"
        else motor.backend
    )
    observaciones = []
    try:
        motor.calentar()
        for caso in banco.casos:
            consulta = QueryAnalysis(
                pregunta_original=caso.pregunta,
                pregunta_normalizada=" ".join(caso.pregunta.lower().split()),
            )
            candidatos = motor.retriever.recuperar(consulta, k)
            inicio = time.perf_counter()
            resultado = motor.consultar(caso.pregunta, f"evaluacion:{caso.id}")
            latencia = int((time.perf_counter() - inicio) * 1000)
            observaciones.append(ObservacionEvaluacion(
                caso_id=caso.id,
                backend=etiqueta_backend,
                estado=resultado.estado.value,
                respuesta=resultado.mensaje_usuario,
                candidatos=[candidato.chunk for candidato in candidatos],
                evidencias=resultado.evidencias,
                latencia_ms=latencia,
                etapas_ms=dict(resultado.diagnostico.get("etapas") or {}),
                confianza_top1=float(resultado.confianza.get("top1", 0.0)),
                metodo_confianza=(resultado.diagnostico.get("senales") or {}).get("metodo_confianza"),
            ))
        retriever = motor.retriever
        if hasattr(retriever, "indice"):
            indice = retriever.indice.manifiesto.model_dump(mode="json")
        else:
            indice = {
                "coleccion": getattr(getattr(retriever, "coleccion", None), "nombre", None),
                "modelo": cfg["recuperacion"].get("modelo"),
                "modo": cfg["recuperacion"].get("modo"),
                "version_coleccion": cfg["recuperacion"].get("version_coleccion"),
            }
    finally:
        motor.cerrar()
    reporte = evaluar_observaciones(
        banco,
        observaciones,
        documentos,
        k=k,
        limite_respuesta_chars=limite_respuesta_chars,
    )
    calibracion = calibrar_observaciones_dev(banco, observaciones)
    config_json = json.dumps(cfg, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ArtefactoEvaluacion(
        backend=etiqueta_backend,
        dataset_id=banco.manifiesto.dataset_id,
        dataset_version=banco.manifiesto.dataset_version,
        dataset_sha256=hash_banco(banco),
        configuracion_sha256=hashlib.sha256(config_json.encode("utf-8")).hexdigest(),
        configuracion=cfg,
        indice=indice,
        calibracion_dev=calibracion,
        reporte=reporte,
        observaciones=observaciones,
    )


def calibrar_observaciones_dev(
    banco: BancoEvaluacion,
    observaciones: list[ObservacionEvaluacion],
    *,
    fpr_objetivo: float = 0.0,
) -> CalibracionDev:
    """Calibra solo con dev; test no participa en la elección del umbral."""
    from rag.servicio.pipeline import calibrar_umbral

    por_id = {observacion.caso_id: observacion for observacion in observaciones}
    positivas = []
    negativas = []
    metodos = set()
    for caso in banco.casos:
        if caso.split != "dev" or caso.categoria.value in {"ambigua", "conversacional"}:
            continue
        observacion = por_id[caso.id]
        (positivas if caso.respondible else negativas).append(observacion.confianza_top1)
        if observacion.metodo_confianza:
            metodos.add(observacion.metodo_confianza)
    resultado = calibrar_umbral(positivas, negativas, fpr_objetivo)
    return CalibracionDev(
        metodo_confianza=next(iter(metodos)) if len(metodos) == 1 else "backend_activo",
        fpr_objetivo=fpr_objetivo,
        umbral=resultado.umbral,
        falsa_respuesta_dev=resultado.falsa_respuesta,
        falsa_abstencion_dev=resultado.falsa_abstencion,
        n_respondibles=resultado.n_respondibles,
        n_no_respondibles=resultado.n_no_respondibles,
    )


__all__ = [
    "ArtefactoEvaluacion", "CalibracionDev", "ObservacionEvaluacion",
    "ReporteMetricas", "ResumenGrupo", "calibrar_observaciones_dev",
    "evaluar_backend_activo", "evaluar_observaciones",
]
