"""Índice Qdrant: colección densa + dispersa BM25, indexación y búsqueda híbrida.

La búsqueda usa la fusión RRF nativa de Qdrant (``query_points`` con
``prefetch``). El modo "vectorial" consulta solo el vector denso; el modo
"hibrida" fusiona denso y BM25.
"""
from __future__ import annotations

from ipsis.configuracion import rutas
from ipsis.indice.estadisticas import EstadisticasLexicas
from ipsis.lenguaje.entidades import idioma_activo
from ipsis.lenguaje.lexico import bm25_consulta, bm25_doc
from ipsis.lenguaje.texto import terminos

import time
from pathlib import Path
from types import SimpleNamespace
from dataclasses import dataclass


@dataclass
class ColeccionQdrant:
    client: object
    codificador: object  # CodificadorDenso: codificar_consultas / codificar_documentos
    estadisticas: EstadisticasLexicas
    nombre: str
    qdrant_path: str


def construir_filtro_entidad(valor_norm: str):
    """`models.Filter` que restringe la búsqueda a chunks cuyo campo
    `entidades` contiene una entidad con este `valor_norm` exacto
    (recuperación dirigida para la capa de premisa cuando una
    entidad de la pregunta existe en el corpus pero no llegó al top-k
    recuperado). Sintaxis verificada contra Qdrant real (local y servidor):
    `"entidades[].valor_norm"` -- la variante sin `[]` NO encuentra nada
    (probado, no asumido; la sintaxis con corchetes es la que Qdrant espera
    para condiciones sobre un campo dentro de un array de objetos)."""
    from qdrant_client import models

    return models.Filter(must=[
        models.FieldCondition(key="entidades[].valor_norm", match=models.MatchValue(value=valor_norm))
    ])


@dataclass
class ResultadoBusqueda:
    ids_ordenados: list[int]
    scores: list[float]
    latencia_encode_ms: float
    latencia_qdrant_ms: float
    # Payload completo de cada punto, en el MISMO orden que `ids_ordenados`/
    # `scores`: Qdrant ya devuelve el payload con
    # cada resultado por defecto (`with_payload=True` es el default de
    # `query_points`, verificado) -- no hace falta mantener una lista
    # `payloads` externa indexada por posición para recuperar el chunk_id/
    # texto/offsets/sección de cada acierto. Esto es lo que permite que el
    # servicio NO dependa del corpus en runtime (ver `ipsis/servicio/api.py`):
    # todo lo que necesita para citar un fragmento ya vino en la respuesta
    # de Qdrant.
    payloads: list[dict]


def buscar(col: ColeccionQdrant, pregunta: str, modo: str, limit: int,
           query_filter=None, vector_precomputado=None) -> ResultadoBusqueda:
    """Busca en Qdrant real (nunca en memoria). `modo` en {"vectorial","hibrida","dispersa"}.

    «dispersa» usa solo BM25: la usa el perfil de diagnóstico ``bm25`` para
    medir cuánto aporta el denso a la recuperación.

    Mide, por separado, la latencia de codificar la pregunta y la latencia de la llamada a Qdrant (`query_points`),
    tal como exige la tarea 1.4. `query_filter` (opcional) es un
    `models.Filter` de Qdrant real (p.ej. filtro duro por `categoria`),
    resuelto por Qdrant, no en Python.

    `vector_precomputado` (opcional): si se entrega, se
    usa tal cual y se salta la codificación (`latencia_encode_ms` queda en
    0.0) -- permite que un llamador que necesita dos consultas para la MISMA
    pregunta (p.ej. el servicio: una vectorial para la señal de abstención y
    una híbrida para los fragmentos a mostrar, ver `ipsis/consulta/motor.py`)
    codifique una sola vez y reuse el vector, en vez de pagar el costo de
    codificar dos veces por petición.
    """
    from qdrant_client import models

    if vector_precomputado is not None:
        vq = vector_precomputado
        latencia_encode_ms = 0.0
    else:
        t0 = time.perf_counter()
        vq = col.codificador.codificar_consultas([pregunta])[0]
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
        sparse_q = vector_disperso(bm25_consulta(terminos(pregunta, paquete_del_indice(col.estadisticas))))
        resp = col.client.query_points(
            collection_name=col.nombre,
            prefetch=[
                models.Prefetch(query=vq.tolist(), using="denso", limit=limit, filter=query_filter),
                models.Prefetch(query=sparse_q, using="bm25", limit=limit, filter=query_filter),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
        )
    elif modo == "dispersa":
        sparse_q = vector_disperso(bm25_consulta(terminos(pregunta, paquete_del_indice(col.estadisticas))))
        resp = col.client.query_points(
            collection_name=col.nombre,
            query=sparse_q,
            using="bm25",
            limit=limit,
            query_filter=query_filter,
        )
    else:
        raise ValueError(f"modo desconocido: {modo!r}")
    latencia_qdrant_ms = (time.perf_counter() - t0) * 1000

    ids = [p.id for p in resp.points]
    scores = [p.score for p in resp.points]
    payloads = [p.payload or {} for p in resp.points]
    return ResultadoBusqueda(ids_ordenados=ids, scores=scores, latencia_encode_ms=latencia_encode_ms,
                              latencia_qdrant_ms=latencia_qdrant_ms, payloads=payloads)


# ---------------------------------------------------------------------------
# BM25 disperso: términos de ``ipsis.lenguaje.texto.terminos`` con id por hash.
# La parte del documento (TF saturado) se calcula aquí y Qdrant aplica el IDF
# (``Modifier.IDF``). No hay vocabulario que guardar: las estadísticas del
# corpus (``EstadisticasLexicas``) bastan para reproducir cualquier puntaje.
# ---------------------------------------------------------------------------
def vector_disperso(pesos: dict[int, float]):
    from qdrant_client import models

    return models.SparseVector(indices=list(pesos), values=list(pesos.values()))


def ruta_estadisticas(nombre_coleccion: str, directorio: str = rutas.INDICE) -> Path:
    return Path(directorio) / f"{nombre_coleccion}.stats.json"


def cargar_estadisticas(nombre_coleccion: str, directorio: str = rutas.INDICE) -> EstadisticasLexicas:
    ruta = ruta_estadisticas(nombre_coleccion, directorio)
    if not ruta.is_file():
        raise FileNotFoundError(
            f"no existen las estadísticas léxicas del índice en {str(ruta)!r}. "
            f"Ejecuta 'ipsis index' para reconstruir el índice."
        )
    return EstadisticasLexicas.cargar(ruta)


def paquete_del_indice(est: EstadisticasLexicas):
    """Lo mínimo que ``terminos()`` necesita para tokenizar como el índice."""
    return SimpleNamespace(stemmer=est.stemmer)


def nombre_coleccion_versionada(coleccion_base: str, modelo_nombre: str, n_version: int = 1,
                                 sufijo: str | None = None) -> str:
    """Nombre de colección versionado:
    ``{{COLECCION}}_{{MODELO}}_v{{N}}``. Si cambia el modelo de embeddings,
    se crea una colección nueva (nunca se mezclan vectores de modelos
    distintos en la misma colección)."""
    modelo_sanitizado = modelo_nombre.replace("/", "-")
    base = f"{coleccion_base}_{modelo_sanitizado}_v{n_version}"
    return f"{base}__{sufijo}" if sufijo else base

# Catálogo de documentos del corpus real (sección "Contexto del proyecto anfitrión").
# doc_id / doc_titulo / version son deterministas: nombre de archivo + registro manual,
# tal como exige la tabla 3.4 (no se infieren con modelos).


def crear_cliente_qdrant(qdrant_path: str | None = None, modo: str | None = None,
                          url_servidor: str | None = None):
    """Único punto donde se decide LOCAL (on-disk) vs. SERVIDOR (docker
    compose) para el cliente Qdrant. La elección es de
    configuración, nunca de código duplicado.

    Prioridad: parámetro explícito > variable de entorno > `qdrant_path`
    (compatibilidad hacia atrás, modo local) > `config/engine.yaml`.

    - "local": ``QdrantClient(path=qdrant_path)``, on-disk. `create_payload_index`
      NO tiene efecto en este modo (advertencia del propio cliente) -- solo
      sirve para evaluación rápida sin Docker.
    - "servidor": ``QdrantClient(url=url_servidor)``, contra el Qdrant real
      (por ejemplo, el contenedor oficial ``qdrant/qdrant``). Aquí los índices de
      payload SÍ toman efecto.
    """
    import os
    from qdrant_client import QdrantClient

    modo = (modo or os.environ.get("QDRANT_MODO") or "local").strip().lower()
    if modo == "servidor":
        url = url_servidor or os.environ.get("QDRANT_URL") or "http://localhost:6333"
        return QdrantClient(url=url)
    if not qdrant_path:
        raise ValueError("modo 'local' requiere qdrant_path")
    return QdrantClient(path=qdrant_path)


def indexar_qdrant(payloads: list[dict], modelo_nombre: str, coleccion: str, qdrant_path: str,
                    usar_texto_embebido: bool = True,
                    codificador=None, n_version: int = 1, sufijo_coleccion: str | None = None,
                    client=None, modo: str | None = None, url_servidor: str | None = None,
                    paquete=None):
    """Codifica los textos con el codificador ONNX de ``modelo_nombre`` (con el
    prefijo de pasaje que exige el modelo, p. ej. ``passage: `` en e5) e
    indexa en una colección Qdrant real. Crea la colección con vector denso COSENO + vector sparse BM25
    (``Modifier.IDF``) más los índices de payload de filtrado, y nombra
    la colección como ``{coleccion}_{modelo}_v{n}`` para no mezclar nunca
    vectores de modelos distintos.

    Devuelve ``(client, codificador, estadisticas, nombre_coleccion)``. Las
    estadísticas léxicas (con el stemmer usado) permiten codificar las
    preguntas exactamente igual que el corpus.
    """
    from qdrant_client import models

    if codificador is None:
        from ipsis.modelos.catalogo import obtener
        from ipsis.modelos.denso import CodificadorDenso

        codificador = CodificadorDenso(obtener(modelo_nombre))
    dim = codificador.dimension

    nombre_col = nombre_coleccion_versionada(coleccion, modelo_nombre, n_version, sufijo_coleccion)

    # El cliente Qdrant on-disk local toma un lock exclusivo de la carpeta de
    # almacenamiento: para poder crear/consultar muchas colecciones en la
    # misma corrida (p. ej. el benchmark de perfiles) hay que REUSAR un único cliente por
    # `qdrant_path`, nunca abrir uno nuevo por colección.
    if client is None:
        client = crear_cliente_qdrant(qdrant_path=qdrant_path, modo=modo, url_servidor=url_servidor)
    if client.collection_exists(nombre_col):
        client.delete_collection(nombre_col)
    client.create_collection(
        collection_name=nombre_col,
        vectors_config={"denso": models.VectorParams(size=dim, distance=models.Distance.COSINE)},
        sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    # Índices de payload de la sección 3.2. `fecha_vigencia` no se indexa:
    # El esquema base no exige ese campo en el payload; se omite en vez de
    # simular una fecha de vigencia por chunk.
    for campo, tipo in [
        ("doc_id", "keyword"), ("version", "keyword"), ("vigente", "bool"),
        ("categoria", "keyword"), ("tipo_contenido", "keyword"),
        ("seccion_path", "keyword"), ("entidades[].tipo", "keyword"),
    ]:
        try:
            client.create_payload_index(nombre_col, campo, tipo)
        except Exception:
            # algunos campos anidados usan sintaxis distinta según versión
            # del cliente; se reintenta con la variante sin `[]`.
            client.create_payload_index(nombre_col, campo.replace("[]", ""), tipo)

    textos = [p["texto_embebido"] if usar_texto_embebido else p["texto"] for p in payloads]
    vectores = codificador.codificar_documentos(textos)

    paquete = paquete if paquete is not None else idioma_activo()
    terminos_por_chunk = [terminos(t, paquete) for t in textos]
    estadisticas = EstadisticasLexicas.construir(textos, paquete)
    puntos = []
    for i, (p, v) in enumerate(zip(payloads, vectores)):
        sparse = vector_disperso(bm25_doc(terminos_por_chunk[i], estadisticas))
        puntos.append(models.PointStruct(
            id=i, vector={"denso": v.tolist(), "bm25": sparse}, payload=p,
        ))
    client.upsert(collection_name=nombre_col, points=puntos)
    return client, codificador, estadisticas, nombre_col
