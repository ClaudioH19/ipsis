from __future__ import annotations

from pathlib import Path

import pytest

from rag.evaluacion.banco import cargar_banco
from rag.nucleo.esquemas import ChunkRecord, EvidenceSpan
from rag.evaluacion.metricas import (
    ObservacionEvaluacion,
    calibrar_observaciones_dev,
    evaluar_observaciones,
)
from rag.ingesta.parsear import parsear_markdown

RAIZ = Path(__file__).parent
MANIFIESTO = RAIZ / "evaluacion" / "sintetico" / "manifiesto.json"
CORPUS = RAIZ / "caracterizacion" / "corpus"


def _documentos():
    salida = {}
    for ruta in CORPUS.glob("*.md"):
        doc_id = ruta.stem.replace("_", "-")
        salida[doc_id] = parsear_markdown(
            str(ruta), doc_id=doc_id, doc_titulo=doc_id, version="1"
        ).texto_completo
    return salida


def _observaciones_perfectas():
    banco = cargar_banco(MANIFIESTO)
    observaciones = []
    for indice, caso in enumerate(banco.casos, start=1):
        candidatos = []
        evidencias = []
        if caso.evidencias:
            esperada = caso.evidencias[0]
            candidatos = [ChunkRecord(
                chunk_id=f"chunk-{caso.id}",
                doc_id=esperada.doc_id,
                texto_fuente=esperada.texto,
                texto_embedding=esperada.texto,
                offset_inicio=esperada.offset_inicio,
                offset_fin=esperada.offset_fin,
            )]
            evidencias = [EvidenceSpan(
                doc_id=esperada.doc_id,
                chunk_id=f"chunk-{caso.id}",
                texto=esperada.texto,
                offset_inicio=esperada.offset_inicio,
                offset_fin=esperada.offset_fin,
            )]
        observaciones.append(ObservacionEvaluacion(
            caso_id=caso.id,
            backend="qdrant_vectorial",
            estado=caso.estado_esperado,
            respuesta=caso.respuesta_literal or "",
            candidatos=candidatos,
            evidencias=evidencias,
            latencia_ms=indice,
            etapas_ms={"recuperacion_ms": indice},
            confianza_top1=0.9 if caso.respondible else 0.1,
            metodo_confianza="cosine_top1_v1",
        ))
    return banco, observaciones


def test_reporte_perfecto_cubre_metricas_y_desgloses():
    banco, observaciones = _observaciones_perfectas()

    reporte = evaluar_observaciones(banco, observaciones, _documentos(), k=3)

    assert reporte.n_casos == 12
    assert reporte.recall_at_k == 1.0
    assert reporte.mrr == 1.0
    assert reporte.tasa_falsos_ok == 0.0
    assert reporte.guardia_falsos_ok is True
    assert reporte.precision_abstencion == 1.0
    assert reporte.exactitud_estado == 1.0
    assert reporte.exactitud_literal == 1.0
    assert reporte.exactitud_offsets == 1.0
    assert reporte.latencia_media_ms == pytest.approx(6.5)
    assert reporte.latencia_p95_ms == 12.0
    assert set(reporte.por_categoria) == {
        "ambigua", "conversacional", "exacta", "parafrasis",
        "premisa_falsa", "sin_respuesta",
    }
    assert reporte.por_backend["qdrant_vectorial"].n == 12


def test_falso_ok_es_bloqueante_aunque_recall_sea_perfecto():
    banco, observaciones = _observaciones_perfectas()
    objetivo = next(o for o in observaciones if o.caso_id == "sin_respuesta_precio")
    objetivo.estado = "respuesta_directa"
    objetivo.respuesta = "Precio inventado"

    reporte = evaluar_observaciones(banco, observaciones, _documentos())

    assert reporte.recall_at_k == 1.0
    assert reporte.tasa_falsos_ok > 0.0
    assert reporte.guardia_falsos_ok is False


def test_offset_mutado_reduce_exactitud():
    banco, observaciones = _observaciones_perfectas()
    objetivo = next(o for o in observaciones if o.evidencias)
    objetivo.evidencias[0].texto = "X" * len(objetivo.evidencias[0].texto)

    reporte = evaluar_observaciones(banco, observaciones, _documentos())

    assert reporte.exactitud_offsets < 1.0
    assert reporte.exactitud_literal < 1.0


def test_respuesta_larga_se_mide_sin_cambiar_otras_metricas():
    banco, observaciones = _observaciones_perfectas()
    objetivo = next(o for o in observaciones if o.estado == "respuesta_directa")
    objetivo.respuesta += " x" * 300

    reporte = evaluar_observaciones(
        banco, observaciones, _documentos(), limite_respuesta_chars=100
    )

    assert reporte.tasa_respuestas_excesivas > 0.0
    assert reporte.recall_at_k == 1.0


def test_rechaza_observaciones_incompletas():
    banco, observaciones = _observaciones_perfectas()

    with pytest.raises(ValueError, match="no coinciden exactamente"):
        evaluar_observaciones(banco, observaciones[:-1], _documentos())


def test_calibracion_usa_dev_y_no_mira_test():
    banco, observaciones = _observaciones_perfectas()
    primera = calibrar_observaciones_dev(banco, observaciones)
    for caso in banco.casos:
        if caso.split == "test":
            next(o for o in observaciones if o.caso_id == caso.id).confianza_top1 = 99.0

    segunda = calibrar_observaciones_dev(banco, observaciones)

    assert primera == segunda
    assert primera.split == "dev"
    assert primera.n_respondibles == 2
    assert primera.n_no_respondibles == 2
