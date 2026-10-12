"""Puntuación incremental: presupuesto de trabajo, sin descartar el resto."""
from __future__ import annotations

import math
import time

from ipsis.consulta.v2.resultados import texto_reranking
from ipsis.nucleo.traza import ejecutar_modelo_con_traza


def preparar_vistas(originales, contextos):
    """El mejor hijo recuperado representa al padre para clasificar.

    El texto fuente y sus offsets nunca se sustituyen por esta vista. Los hijos
    estructurales ya incluyen sección/encabezados; legacy conserva su pasaje.
    """
    por_id = {c.chunk.chunk_id: c for c in originales}
    nuevos = []
    for c in contextos:
        hijos = c.chunk.metadata.get("hijos_recuperados", [c.chunk.chunk_id])
        origen = next((por_id[i] for i in hijos if i in por_id), None)
        if origen is None:
            nuevos.append(c)
            continue
        if origen.chunk.doc_id != c.chunk.doc_id or origen.chunk.version != c.chunk.version:
            raise ValueError("vista de reranking de otro documento o versión")
        ch = c.chunk.model_copy(deep=True)
        ch.metadata["vista_reranking"] = {
            "texto": texto_reranking(origen), "chunk_id": origen.chunk.chunk_id,
            "offset_inicio": origen.chunk.offset_inicio, "offset_fin": origen.chunk.offset_fin,
            "origen": "hijo_recuperado" if origen.chunk.chunk_id != ch.chunk_id else "pasaje"}
        nuevos.append(c.model_copy(update={"chunk": ch}))
    return nuevos


def puntuar_progresivo(candidatos, pregunta, reranker, opciones, *, limite,
                      reloj=time.perf_counter, estimado_ms=None):
    """Conserva puntuados y pendientes; no inicia un lote que no cabe estimado.

    `limite` es absoluto, después de reservar el costo de publicación. El
    estimador se actualiza con cada lote; no constituye un plazo duro de ONNX.
    """
    pendientes = [c for c in candidatos if c.signals.reranker_score is None]
    coste = estimado_ms or 100.0
    nuevos = {}
    lotes = []
    if reranker is not None:
        cola = pendientes[:opciones["rerank_candidatos"]]
        lote = opciones["lote_reranker"]
        for i in range(0, len(cola), lote):
            grupo = cola[i:i + lote]
            disponible_ms = (limite - reloj()) * 1000
            if disponible_ms <= coste * len(grupo) * 1.25:
                break
            textos = [texto_reranking(c) for c in grupo]
            inicio = reloj()
            scores = ejecutar_modelo_con_traza("reranker", pregunta, textos, reranker.puntuar)
            duracion = max(0.0, (reloj() - inicio) * 1000)
            if len(scores) != len(grupo):
                raise ValueError("reranker no devolvió un puntaje por candidato")
            if not all(math.isfinite(s) for s in scores):
                raise ValueError("reranker devolvió un puntaje no finito")
            coste = max(duracion / len(grupo), coste * 0.5, 1.0)
            lotes.append({"chunk_ids": [c.chunk.chunk_id for c in grupo],
                          "caracteres": [len(t) for t in textos], "duracion_ms": round(duracion, 2)})
            for c, score in zip(grupo, scores, strict=True):
                nuevos[c.chunk.chunk_id] = c.model_copy(update={"signals": c.signals.model_copy(
                    update={"reranker_score": float(score)})})
    actuales = [nuevos.get(c.chunk.chunk_id, c) for c in candidatos]
    puntuados = sorted((c for c in actuales if c.signals.reranker_score is not None),
                       key=lambda c: (-c.signals.reranker_score, c.chunk.chunk_id))
    # Un logit del modelo y un score híbrido no se comparan numéricamente.
    puntuados = [c.model_copy(update={"signals": c.signals.model_copy(
        update={"reranker_rank": i + 1})}) for i, c in enumerate(puntuados)]
    restantes = [c for c in actuales if c.signals.reranker_score is None]
    return puntuados + restantes, {
        "puntuados_esta_pagina": len(nuevos), "puntuados_disponibles": len(puntuados),
        "pendientes": len(restantes), "candidatos_conservados": len(actuales),
        "presupuesto_agotado": reranker is not None and len(nuevos) < min(
            len(pendientes), opciones["rerank_candidatos"]),
        "limite_candidatos_alcanzado": len(pendientes) > opciones["rerank_candidatos"] and
                                      len(nuevos) == opciones["rerank_candidatos"],
        "orden": "puntuados_primero_pendientes_en_orden_hibrido",
        "estimado_ms_por_pasaje": coste, "lotes": lotes}
