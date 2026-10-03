"""Índice Qdrant: colección densa + dispersa BM25, indexación y búsqueda híbrida.

La búsqueda usa la fusión RRF nativa de Qdrant (``query_points`` con
``prefetch``). El modo "vectorial" consulta solo el vector denso; el modo
"hibrida" fusiona denso y BM25.
"""
from __future__ import annotations

from rag.configuracion import rutas

import pathlib
import re
from collections import Counter
import time
from dataclasses import dataclass


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
    `rag/indice/qdrant.py::crear_cliente_qdrant`). En modo "local"
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


# ---------------------------------------------------------------------------
# Vocabulario BM25 disperso (sección 3.2: sparse_vectors_config con Modifier.IDF).
# Qdrant calcula el IDF internamente a partir de los conteos de término que le
# entregamos; nosotros solo tokenizamos y contamos, de forma 100% determinista
# y reproducible (mismo tokenizador para indexar y para consultar).
# ---------------------------------------------------------------------------

_RE_TOKEN = re.compile(r"[a-záéíóúñü0-9]+")


def tokenizar_bm25(texto: str) -> list[str]:
    return _RE_TOKEN.findall(texto.lower())


def construir_vocabulario_bm25(textos: list[str]) -> dict[str, int]:
    """Vocabulario determinista: id = orden de primera aparición sobre la
    lista de textos, en el orden dado (reproducible entre corridas)."""
    vocab: dict[str, int] = {}
    for t in textos:
        for tok in tokenizar_bm25(t):
            if tok not in vocab:
                vocab[tok] = len(vocab)
    return vocab


def texto_a_vector_sparse(texto: str, vocab: dict[str, int]):
    """Conteos de término (no normalizados) restringidos al vocabulario del
    índice. Tokens fuera de vocabulario (OOV) se descartan: es una limitación
    documentada, no una aproximación oculta."""
    from qdrant_client import models

    conteos = Counter(tok for tok in tokenizar_bm25(texto) if tok in vocab)
    if not conteos:
        return models.SparseVector(indices=[], values=[])
    indices = [vocab[t] for t in conteos]
    valores = [float(c) for c in conteos.values()]
    return models.SparseVector(indices=indices, values=valores)


# ---------------------------------------------------------------------------
# Persistencia del vocabulario BM25 como artefacto de INGESTA (Etapa B,
# 2026-09-19). Antes, el servicio reconstruía el vocabulario leyendo
# `documentos/` en cada arranque -- lo obligaba a tener el corpus
# disponible en runtime, lo que impide un despliegue real (el corpus
# institucional no debería vivir dentro del contenedor del servicio). El
# vocabulario es solo un `dict[str, int]` (token -> índice, determinista,
# reproducible desde el corpus con `construir_vocabulario_bm25`) — se guarda
# como JSON junto al resto de artefactos de ingesta y el servicio lo carga
# de ahí, sin tocar el corpus para nada.
# ---------------------------------------------------------------------------
def ruta_vocabulario_bm25(nombre_coleccion: str, directorio: str = rutas.INDICE) -> str:
    return str(pathlib.Path(directorio) / f"{nombre_coleccion}.json")


def guardar_vocabulario_bm25(vocab: dict[str, int], nombre_coleccion: str,
                              directorio: str = rutas.INDICE) -> str:
    """Escribe el vocabulario BM25 como artefacto de ingesta (JSON, un dict
    token->índice). Devuelve la ruta escrita."""
    import json

    ruta = ruta_vocabulario_bm25(nombre_coleccion, directorio)
    pathlib.Path(directorio).mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False)
    return ruta


def cargar_vocabulario_bm25(nombre_coleccion: str, directorio: str = rutas.INDICE) -> dict[str, int]:
    """Lee el vocabulario BM25 persistido por `guardar_vocabulario_bm25`
    (creado por ``rag indexar``). Falla fuerte y explícito (`FileNotFoundError`
    con el comando a correr) si el artefacto no existe -- nunca se inventa
    un vocabulario vacío ni se cae de vuelta a reconstruirlo desde el corpus."""
    import json

    ruta = ruta_vocabulario_bm25(nombre_coleccion, directorio)
    if not pathlib.Path(ruta).exists():
        raise FileNotFoundError(
            f"no existe el vocabulario BM25 persistido en {ruta!r}. Corré "
            f"'rag indexar' primero (deja este artefacto junto al índice)."
        )
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Inventario de entidades del corpus COMPLETO (Etapa C, 2026-09-19, punto 1
# del ajuste del coordinador): antes, la capa (b) de abstención
# (`rag/consulta/etapas/politica.py::verificar_premisa_textos`) solo podía comprobar si una
# entidad de la pregunta aparecía en los 3 fragmentos RECUPERADOS -- si la
# evidencia real existía en el corpus pero no llegó al top-3 (Recall@3=0.84,
# no 1.00), la capa (b) la trataba como "ausente" y se abstenía de más,
# aunque el corpus sí la cubriera. El inventario -- ya
# calculado gratis, `entidades` va en el payload de cada chunk desde E1 --
# permite distinguir "no existe en el corpus" (abstención correcta) de
# "existe, pero no llegó al top-3" (dispara una recuperación dirigida, ver
# `rag/indice/qdrant.py::construir_filtro_entidad`).
# ---------------------------------------------------------------------------
def construir_inventario_entidades(payloads: list[dict]) -> list[str]:
    """Todos los `valor_norm` de entidades presentes en algún chunk del
    corpus (unión, sin duplicar) -- se calcula desde el mismo campo
    `entidades` que ya construye `rag/ingesta/metadata.py::construir_payload` para
    cada chunk, no se reextrae nada."""
    valores: set[str] = set()
    for p in payloads:
        for e in p.get("entidades", []):
            valores.add(e["valor_norm"])
    return sorted(valores)


def ruta_inventario_entidades(nombre_coleccion: str, directorio: str = rutas.INDICE) -> str:
    return str(pathlib.Path(directorio) / f"{nombre_coleccion}.entidades.json")


def guardar_inventario_entidades(inventario: list[str], nombre_coleccion: str,
                                  directorio: str = rutas.INDICE) -> str:
    """Escribe el inventario de entidades como artefacto de ingesta (JSON,
    lista de `valor_norm`), junto al vocabulario BM25 (mismo directorio, un
    solo lugar de artefactos de ingesta que el servicio necesita en
    runtime). Devuelve la ruta escrita."""
    import json

    ruta = ruta_inventario_entidades(nombre_coleccion, directorio)
    pathlib.Path(directorio).mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(inventario, f, ensure_ascii=False)
    return ruta


def cargar_inventario_entidades(nombre_coleccion: str,
                                 directorio: str = rutas.INDICE) -> set[str]:
    """Lee el inventario de entidades persistido por
    `guardar_inventario_entidades` durante ``rag indexar``. Falla fuerte
    y explícito si el artefacto no existe -- mismo criterio que
    `cargar_vocabulario_bm25`."""
    import json

    ruta = ruta_inventario_entidades(nombre_coleccion, directorio)
    if not pathlib.Path(ruta).exists():
        raise FileNotFoundError(
            f"no existe el inventario de entidades persistido en {ruta!r}. Corré "
            f"'rag indexar' primero (deja este artefacto junto al índice)."
        )
    with open(ruta, encoding="utf-8") as f:
        return set(json.load(f))


# ---------------------------------------------------------------------------
# Estadísticas léxicas de dominio (Etapa D, punto 1): reemplaza el chequeo
# de "grounding léxico" anterior (¿está la palabra en el vocabulario BM25?
# -- demasiado permisivo, medido: "prepara" o "necesito" bastaban porque
# aparecían un par de veces en el corpus). Se persiste, por token (sin
# acentos), la FRACCIÓN de chunks del corpus que lo contienen -- una
# palabra que aparece en muy pocos chunks por simple azar (típico en un
# corpus de 38 chunks) no es, solo por eso, evidencia de dominio; hace
# falta combinarlo con la lista de palabras de alta frecuencia general
# (``rag/lenguaje/texto.py::PALABRAS_GENERALES_ES``) en el chequeo real.
# ---------------------------------------------------------------------------
def construir_estadisticas_lexico_dominio(payloads: list[dict], con_header: bool) -> dict[str, float]:
    from rag.lenguaje.texto import sin_acentos

    textos = [p["texto_embebido"] if con_header else p["texto"] for p in payloads]
    n = len(textos)
    df: dict[str, int] = {}
    for t in textos:
        vistos = {sin_acentos(tok).lower() for tok in tokenizar_bm25(t)}
        for tok in vistos:
            df[tok] = df.get(tok, 0) + 1
    return {tok: d / n for tok, d in df.items()} if n else {}


def ruta_estadisticas_lexico_dominio(nombre_coleccion: str,
                                      directorio: str = rutas.INDICE) -> str:
    return str(pathlib.Path(directorio) / f"{nombre_coleccion}.estadisticas_lexico.json")


def guardar_estadisticas_lexico_dominio(estadisticas: dict[str, float], nombre_coleccion: str,
                                         directorio: str = rutas.INDICE) -> str:
    import json

    ruta = ruta_estadisticas_lexico_dominio(nombre_coleccion, directorio)
    pathlib.Path(directorio).mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(estadisticas, f, ensure_ascii=False)
    return ruta


def cargar_estadisticas_lexico_dominio(nombre_coleccion: str,
                                        directorio: str = rutas.INDICE) -> dict[str, float]:
    import json

    ruta = ruta_estadisticas_lexico_dominio(nombre_coleccion, directorio)
    if not pathlib.Path(ruta).exists():
        raise FileNotFoundError(
            f"no existen las estadísticas léxicas persistidas en {ruta!r}. Corré "
            f"'rag indexar' primero (deja este artefacto junto al índice)."
        )
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def nombre_coleccion_versionada(coleccion_base: str, modelo_nombre: str, n_version: int = 1,
                                 sufijo: str | None = None) -> str:
    """Nombre de colección exigido por la sección 3.2 del molde:
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
    compose) para el cliente Qdrant (Etapa 1, tarea 2). La elección es de
    configuración, nunca de código duplicado.

    Prioridad: parámetro explícito > variable de entorno > `qdrant_path`
    (compatibilidad hacia atrás, modo local) > `configuracion/motor.yaml`.

    - "local": ``QdrantClient(path=qdrant_path)``, on-disk. `create_payload_index`
      NO tiene efecto en este modo (advertencia del propio cliente) -- solo
      sirve para evaluación rápida sin Docker.
    - "servidor": ``QdrantClient(url=url_servidor)``, contra el Qdrant real
      levantado con ``docker compose up -d qdrant`` (ver rag/recursos/despliegue/docker-compose.yml.plantilla
      y README.md). Aquí los índices de payload SÍ toman efecto.
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
                    usar_texto_embebido: bool = True, batch_size: int = 32,
                    modelo_st=None, n_version: int = 1, sufijo_coleccion: str | None = None,
                    client=None, modo: str | None = None, url_servidor: str | None = None):
    """Codifica los textos con `modelo_nombre` (sentence-transformers, CPU) e
    indexa en una colección Qdrant on-disk local **real** (no numpy en
    memoria). Crea la colección con vector denso COSENO + vector sparse BM25
    (``Modifier.IDF``) más los índices de payload de la sección 3.2, y nombra
    la colección como ``{coleccion}_{modelo}_v{n}`` para no mezclar nunca
    vectores de modelos distintos.

    Devuelve ``(client, modelo, vocab_bm25, nombre_coleccion)``: el
    vocabulario BM25 es necesario para codificar preguntas en tiempo de
    consulta exactamente igual que se codificó el corpus.
    """
    from qdrant_client import QdrantClient, models
    from sentence_transformers import SentenceTransformer

    modelo = modelo_st if modelo_st is not None else SentenceTransformer(modelo_nombre, device="cpu")
    dim = modelo.get_sentence_embedding_dimension()

    nombre_col = nombre_coleccion_versionada(coleccion, modelo_nombre, n_version, sufijo_coleccion)

    # El cliente Qdrant on-disk local toma un lock exclusivo de la carpeta de
    # almacenamiento: para poder crear/consultar muchas colecciones en la
    # misma corrida (grid de E2/E3) hay que REUSAR un único cliente por
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
    vectores = modelo.encode(textos, batch_size=batch_size, show_progress_bar=False,
                              convert_to_numpy=True, normalize_embeddings=True)

    vocab = construir_vocabulario_bm25(textos)
    puntos = []
    for i, (p, v) in enumerate(zip(payloads, vectores)):
        sparse = texto_a_vector_sparse(textos[i], vocab)
        puntos.append(models.PointStruct(
            id=i, vector={"denso": v.tolist(), "bm25": sparse}, payload=p,
        ))
    client.upsert(collection_name=nombre_col, points=puntos)
    return client, modelo, vocab, nombre_col
