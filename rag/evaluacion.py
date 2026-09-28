"""Evaluación reproducible de un índice contra un golden set del usuario."""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from rag.metricas import acierto_chunk, mrr, ndcg_at_k, bootstrap_ic

# El índice Qdrant es un artefacto regenerable creado por ``rag indexar``.
QDRANT_PATH = ".cache/qdrant_local"


def coleccion_base() -> str:
    """Nombre base configurado para el índice Qdrant de evaluación."""
    from rag.configuracion import config_recuperacion
    return config_recuperacion()["coleccion_base"]


GOLDEN_PATH = "data/golden/golden.jsonl"
REPORTES_DIR = "data/reportes"

# Valores de referencia para evaluaciones comparativas opcionales.
MODELO_BASE = "paraphrase-multilingual-MiniLM-L12-v2"
ESTRATEGIA_BASE = "CH-SEC"
CON_HEADER_BASE = True
PROFUNDIDADES_POOL = [10, 20]
N_CORRIDAS_LATENCIA = 3


def etiqueta_version_golden(ruta: str = GOLDEN_PATH) -> str:
    """Convierte el nombre del archivo en una etiqueta para reportes."""
    from pathlib import Path
    nombre = Path(ruta).stem
    return nombre.replace("golden_", "") or nombre


def etiqueta_motor_qdrant() -> str:
    """"local" o "servidor", según QDRANT_MODO (ver
    ``rag/corpus.py::crear_cliente_qdrant``). Se usa para que el nombre del
    reporte distinga sobre qué motor se midió: los
    índices de payload solo tienen efecto en modo servidor, así que E2/E3
    corridas en cada modo NO son comparables sin decirlo en el nombre."""
    import os
    return (os.environ.get("QDRANT_MODO") or "local").strip().lower()


def sufijo_reporte(incluir_motor_qdrant: bool = False, ruta_golden: str = GOLDEN_PATH) -> str:
    """Sufijo distintivo para el nombre de archivo del reporte (tarea 1c):
    como mínimo la versión del golden set, y opcionalmente el motor Qdrant
    (local/servidor) para las evaluaciones que dependen de él (E2/E3/E2bis/E2ter)."""
    partes = [f"golden_{etiqueta_version_golden(ruta_golden)}"]
    if incluir_motor_qdrant:
        partes.append(f"qdrant_{etiqueta_motor_qdrant()}")
    return "-".join(partes)


def cargar_golden_dev_respondible(ruta: str = GOLDEN_PATH) -> list[dict]:
    """Ítems del golden set que son respondibles y están en el split `dev`.

    El split `test` queda bloqueado hasta la decisión final del golden set,
    así que ninguna evaluación de ajuste debe tocarlo.
    """
    items = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                items.append(json.loads(linea))
    return [it for it in items if it["respondible"] and it["split"] == "dev"]


def aciertos_del_pool(payloads, ids_pool, item, k) -> list[bool]:
    """Para cada uno de los primeros `k` chunks recuperados, si contiene al
    menos la mitad de los caracteres de alguna evidencia del ítem (criterio de
    acierto)."""
    aciertos = []
    for idx in ids_pool[:k]:
        p = payloads[idx]
        acierto = any(
            p["doc_id"] == ev["doc_id"] and
            acierto_chunk(p["offset_inicio"], p["offset_fin"], ev["offset_inicio"], ev["offset_fin"])
            for ev in item["evidencias"]
        )
        aciertos.append(acierto)
    return aciertos


@dataclass
class MetricasCalidad:
    recall_at_3: float
    ic_lo: float
    ic_hi: float
    mrr: float
    ndcg_at_3: float
    cobertura_hechos: float


def calcular_metricas(aciertos_por_pregunta: list[list[bool]],
                       cobertura_hechos_por_pregunta: list[float]) -> MetricasCalidad:
    """Recall@3 con intervalo de confianza por bootstrap, más MRR, nDCG@3 y
    cobertura de hechos promedio."""
    valores_r3 = [1.0 if any(a[:3]) else 0.0 for a in aciertos_por_pregunta]
    media, lo, hi = bootstrap_ic(valores_r3, n_remuestreos=1000, nivel=0.95)
    return MetricasCalidad(
        recall_at_3=media, ic_lo=lo, ic_hi=hi,
        mrr=mrr(aciertos_por_pregunta), ndcg_at_3=ndcg_at_k(aciertos_por_pregunta, 3),
        cobertura_hechos=float(np.mean(cobertura_hechos_por_pregunta))
        if cobertura_hechos_por_pregunta else 0.0,
    )


def aciertos_en_topk(payloads_topk: list[dict], evidencias: list[dict]) -> list[bool]:
    """Igual que ``aciertos_del_pool``, pero sobre los payloads que devuelve
    DIRECTAMENTE una consulta real a Qdrant (``rag/indice.py::buscar``), no
    sobre índices dentro de un array de payloads en memoria. La usa
    ``evaluar_indice_produccion`` (``rag evaluar``),
    que consulta el índice YA indexado en vez de reconstruirlo en memoria
    como hacen los scripts E2/E3 sobre un grid completo."""
    aciertos = []
    for p in payloads_topk:
        acierto = any(
            p["doc_id"] == ev["doc_id"] and
            acierto_chunk(p["offset_inicio"], p["offset_fin"], ev["offset_inicio"], ev["offset_fin"])
            for ev in evidencias
        )
        aciertos.append(acierto)
    return aciertos


@dataclass
class ResultadoEvaluacionRapida:
    n_items: int
    recall_at_3: float
    ic_lo: float
    ic_hi: float
    cobertura_hechos: float
    recall_at_3_min_requerido: float
    cumple: bool


def evaluar_indice_produccion(ruta_golden: str, top_k: int | None = None) -> ResultadoEvaluacionRapida:
    """Evalúa Recall@k y cobertura de hechos del ÍNDICE DE PRODUCCIÓN
    ACTIVO (``configuracion/motor.yaml::recuperacion``, el mismo que consulta
    ``rag/servicio/api.py``) contra un golden set, SIN reindexar nada -- pensado
    para ``rag evaluar``: una corrida rápida sobre lo que el servicio
    respondería hoy, sin reconstruir ni modificar el índice.

    Cada cifra que devuelve viene de una consulta real contra Qdrant (nunca
    estimada): si el índice no existe todavía, falla con un mensaje que dice
    qué comando correr, en vez de simular un resultado."""
    import os

    from rag.configuracion import cargar_dominio, cargar_proyecto, config_recuperacion
    from rag.corpus import cargar_vocabulario_bm25, crear_cliente_qdrant, nombre_coleccion_versionada
    from rag.dominio import cargar_perfil
    from rag.indice import ColeccionQdrant, buscar
    from rag.metricas import cobertura_hechos as calcular_cobertura_hechos
    from rag.reglas_extraccion import configurar_perfil

    cfg = cargar_proyecto()
    cfg_rec = config_recuperacion(cfg)
    top_k = top_k or cfg_rec["top_k"]

    configurar_perfil(cargar_perfil(cargar_dominio()["perfil"]))

    modo = os.environ.get("QDRANT_MODO") or cfg.get("qdrant", {}).get("modo")
    url_servidor = os.environ.get("QDRANT_URL") or cfg.get("qdrant", {}).get("url_servidor")
    client = crear_cliente_qdrant(qdrant_path=cfg_rec["qdrant_path"], modo=modo, url_servidor=url_servidor)
    nombre_col = nombre_coleccion_versionada(cfg_rec["coleccion_base"], cfg_rec["modelo"],
                                              cfg_rec["version_coleccion"])
    if not client.collection_exists(nombre_col):
        raise RuntimeError(
            f"la colección Qdrant {nombre_col!r} no existe todavía. Corré 'rag indexar' primero."
        )
    vocab = cargar_vocabulario_bm25(nombre_col)

    from sentence_transformers import SentenceTransformer
    modelo_st = SentenceTransformer(cfg_rec["modelo"], device="cpu")
    col = ColeccionQdrant(client=client, modelo_st=modelo_st, vocab=vocab, nombre=nombre_col,
                           qdrant_path=cfg_rec["qdrant_path"])

    items = cargar_golden_dev_respondible(ruta_golden)
    aciertos_por_pregunta: list[list[bool]] = []
    cobertura_por_pregunta: list[float] = []
    for item in items:
        res = buscar(col, item["pregunta"], modo=cfg_rec["modo"], limit=top_k,
                      prefijo_query=cfg_rec.get("prefijo_query", ""))
        aciertos_por_pregunta.append(aciertos_en_topk(res.payloads, item["evidencias"]))
        textos_top_k = [p["texto"] for p in res.payloads]
        cobertura_por_pregunta.append(calcular_cobertura_hechos(item.get("hechos_clave", []), textos_top_k))

    metricas = calcular_metricas(aciertos_por_pregunta, cobertura_por_pregunta)
    umbral = cfg["criterios_aceptacion"]["E2_embeddings_chunking_recuperacion"]["recall_at_3_min"]
    return ResultadoEvaluacionRapida(
        n_items=len(items), recall_at_3=metricas.recall_at_3, ic_lo=metricas.ic_lo, ic_hi=metricas.ic_hi,
        cobertura_hechos=metricas.cobertura_hechos, recall_at_3_min_requerido=umbral,
        cumple=metricas.recall_at_3 >= umbral,
    )
