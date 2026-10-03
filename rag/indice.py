"""Recuperación real contra Qdrant (cierre de la brecha detectada por la
revisión independiente de 2026-09-18).

Antes de esta revisión, `eval/e2_recuperacion.py` y `eval/e3_metadata_impacto.py`
recuperaban con NumPy en memoria (producto punto) y `rank_bm25.BM25Okapi` para
la parte léxica: nunca se ejecutó `ingesta.indexar.indexar_qdrant`, y las
métricas oficiales de E2/E3 se midieron sobre un motor que no es el que iría
a producción.

Este módulo es la ÚNICA fuente de recuperación oficial a partir de esta
revisión: construye una colección Qdrant on-disk real por cada combinación
(modelo, estrategia de chunking, header) — con vector denso y vector sparse
BM25 (`Modifier.IDF`, sección 3.2 del molde) — y expone dos modos de consulta
que usan la búsqueda híbrida NATIVA de Qdrant (`query_points` con `prefetch` +
`FusionQuery(fusion=Fusion.RRF)`), nunca una reimplementación en Python:

  - "vectorial": solo el vector denso.
  - "hibrida":   fusión RRF de denso + sparse BM25, ambos resueltos por Qdrant.

La implementación NumPy/`rank_bm25` anterior se conserva, intacta y
renombrada, en `eval/referencia_numpy_e2.py`, marcada explícitamente como
"solo referencia" — nunca como fuente de métricas oficiales.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from rag.corpus import (
    indexar_qdrant,
    texto_a_vector_sparse,
)


@dataclass
class ColeccionQdrant:
    client: object
    modelo_st: object
    vocab: dict
    nombre: str
    qdrant_path: str


def construir_coleccion(payloads: list[dict], modelo_nombre: str, coleccion_base: str,
                         qdrant_path: str, con_header: bool, modelo_st=None,
                         n_version: int = 1, sufijo_coleccion: str | None = None,
                         client=None, modo: str | None = None,
                         url_servidor: str | None = None) -> ColeccionQdrant:
    """Indexa `payloads` en una colección Qdrant real (denso + sparse BM25).
    Devuelve el envoltorio con todo lo necesario para consultar.

    `modo` en {"local", "servidor"} (por defecto, configuración de
    `configuracion/motor.yaml` o la variable de entorno ``QDRANT_MODO`` -- ver
    `rag/corpus.py::crear_cliente_qdrant`, Etapa 1 tarea 2). En modo "local"
    `qdrant_path` es la carpeta on-disk; en modo "servidor" se ignora y se usa
    `url_servidor` (o ``QDRANT_URL``).

    `client`, si se pasa, se reutiliza (el cliente local toma un lock
    exclusivo de la carpeta de almacenamiento; para crear muchas colecciones
    en la misma corrida hay que reusar un único cliente por `qdrant_path` o
    por servidor)."""
    client, modelo, vocab, nombre_col = indexar_qdrant(
        payloads, modelo_nombre, coleccion_base, qdrant_path,
        usar_texto_embebido=con_header, modelo_st=modelo_st,
        n_version=n_version, sufijo_coleccion=sufijo_coleccion, client=client,
        modo=modo, url_servidor=url_servidor,
    )
    return ColeccionQdrant(client=client, modelo_st=modelo, vocab=vocab, nombre=nombre_col,
                            qdrant_path=qdrant_path)


def construir_filtro_entidad(valor_norm: str):
    """`models.Filter` que restringe la búsqueda a chunks cuyo campo
    `entidades` contiene una entidad con este `valor_norm` exacto (Etapa C,
    punto 1: recuperación dirigida para la capa de premisa cuando una
    entidad de la pregunta existe en el corpus pero no llegó al top-k
    recuperado). Sintaxis verificada contra Qdrant real (local y servidor):
    `"entidades[].valor_norm"` -- la variante sin `[]` NO encuentra nada
    (probado, no asumido; la sintaxis con corchetes es la que Qdrant espera
    para condiciones sobre un campo dentro de un array de objetos)."""
    from qdrant_client import models

    return models.Filter(must=[
        models.FieldCondition(key="entidades[].valor_norm", match=models.MatchValue(value=valor_norm))
    ])


def codificar_pregunta(col: ColeccionQdrant, pregunta: str, prefijo_query: str = ""):
    """Codifica la pregunta una sola vez (mismo modelo/normalización que usa
    `buscar` internamente). Pensado para el servicio (Etapa A): cuando hace
    falta consultar dos veces la MISMA pregunta (p.ej. vectorial para la
    señal de abstención + híbrida para los fragmentos), se codifica una vez
    aquí y se reusa con `buscar(..., vector_precomputado=vq)` en ambas
    llamadas, evitando pagar el costo de `encode` dos veces por petición."""
    return col.modelo_st.encode([prefijo_query + pregunta], convert_to_numpy=True,
                                 normalize_embeddings=True)[0]


@dataclass
class ResultadoBusqueda:
    ids_ordenados: list[int]
    scores: list[float]
    latencia_encode_ms: float
    latencia_qdrant_ms: float
    # Payload completo de cada punto, en el MISMO orden que `ids_ordenados`/
    # `scores` (Etapa A/B, 2026-09-19): Qdrant ya devuelve el payload con
    # cada resultado por defecto (`with_payload=True` es el default de
    # `query_points`, verificado) -- no hace falta mantener una lista
    # `payloads` externa indexada por posición para recuperar el chunk_id/
    # texto/offsets/sección de cada acierto. Esto es lo que permite que el
    # servicio NO dependa del corpus en runtime (ver `rag/servicio/api.py`):
    # todo lo que necesita para citar un fragmento ya vino en la respuesta
    # de Qdrant.
    payloads: list[dict]


def buscar(col: ColeccionQdrant, pregunta: str, modo: str, limit: int,
           prefijo_query: str = "", query_filter=None, vector_precomputado=None) -> ResultadoBusqueda:
    """Busca en Qdrant real (nunca en memoria). `modo` en {"vectorial","hibrida"}.

    Mide, por separado, la latencia de codificar la pregunta (sentence-
    transformers) y la latencia de la llamada a Qdrant (`query_points`),
    tal como exige la tarea 1.4. `query_filter` (opcional) es un
    `models.Filter` de Qdrant real (p.ej. filtro duro por `categoria`),
    resuelto por Qdrant, no en Python.

    `vector_precomputado` (opcional, Etapa A / servicio): si se entrega, se
    usa tal cual y se salta la codificación (`latencia_encode_ms` queda en
    0.0) -- permite que un llamador que necesita dos consultas para la MISMA
    pregunta (p.ej. el servicio: una vectorial para la señal de abstención y
    una híbrida para los fragmentos a mostrar, ver `rag/consulta/motor.py`)
    codifique una sola vez y reuse el vector, en vez de pagar el costo de
    `modelo_st.encode` dos veces por petición.
    """
    from qdrant_client import models

    if vector_precomputado is not None:
        vq = vector_precomputado
        latencia_encode_ms = 0.0
    else:
        t0 = time.perf_counter()
        vq = col.modelo_st.encode([prefijo_query + pregunta], convert_to_numpy=True,
                                   normalize_embeddings=True)[0]
        latencia_encode_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    if modo == "vectorial":
        resp = col.client.query_points(
            collection_name=col.nombre,
            query=vq.tolist(),
            using="denso",
            limit=limit,
            query_filter=query_filter,
        )
    elif modo == "hibrida":
        sparse_q = texto_a_vector_sparse(pregunta, col.vocab)
        resp = col.client.query_points(
            collection_name=col.nombre,
            prefetch=[
                models.Prefetch(query=vq.tolist(), using="denso", limit=limit, filter=query_filter),
                models.Prefetch(query=sparse_q, using="bm25", limit=limit, filter=query_filter),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
        )
    else:
        raise ValueError(f"modo desconocido: {modo!r}")
    latencia_qdrant_ms = (time.perf_counter() - t0) * 1000

    ids = [p.id for p in resp.points]
    scores = [p.score for p in resp.points]
    payloads = [p.payload or {} for p in resp.points]
    return ResultadoBusqueda(ids_ordenados=ids, scores=scores, latencia_encode_ms=latencia_encode_ms,
                              latencia_qdrant_ms=latencia_qdrant_ms, payloads=payloads)
