"""Ingesta completa: parsear + chunkear + metadata + validar + indexar en Qdrant.

Uso (PowerShell, desde rag-extractivo/, con el venv activado):

    python -m ingesta.indexar --estrategia CH-SEC --modelo paraphrase-multilingual-MiniLM-L12-v2 `
        --coleccion biblioteca --qdrant-path .cache/qdrant_local

Este módulo es el punto de entrada que usan E1/E2/E3 para materializar un
índice concreto (una combinación modelo × chunking) contra el corpus real de
``documentos/``. Para las evaluaciones se usa Qdrant en modo *on-disk* local
del cliente Python (sin servidor), tal como autorizan las restricciones del
encargo.

**Revisión 2026-09-18 (cierre de la brecha Qdrant):** ``indexar_qdrant`` ahora
crea la colección con vector denso **y** vector *sparse* BM25
(``models.Modifier.IDF``, sección 3.2 del molde), y agrega los índices de
payload que ahí se listan. El vocabulario BM25 se construye de forma
determinista a partir del propio corpus (tokenizador léxico simple) y se
devuelve junto con el cliente para poder codificar preguntas de la misma
forma en tiempo de consulta (ver ``eval/recuperacion_qdrant.py``).
"""
from __future__ import annotations

import json
import pathlib
import hashlib
import re
import shutil
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from rag.parsear import parsear_documento, DocumentoParseado, EXTENSIONES_SOPORTADAS
from rag.chunking import ESTRATEGIAS, construir_texto_embebido, Chunk
from rag.metadata import cargar_taxonomia, construir_payload, validar_chunk

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
def ruta_vocabulario_bm25(nombre_coleccion: str, directorio: str = ".cache/vocab_bm25") -> str:
    return str(pathlib.Path(directorio) / f"{nombre_coleccion}.json")


def guardar_vocabulario_bm25(vocab: dict[str, int], nombre_coleccion: str,
                              directorio: str = ".cache/vocab_bm25") -> str:
    """Escribe el vocabulario BM25 como artefacto de ingesta (JSON, un dict
    token->índice). Devuelve la ruta escrita."""
    import json

    ruta = ruta_vocabulario_bm25(nombre_coleccion, directorio)
    pathlib.Path(directorio).mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False)
    return ruta


def cargar_vocabulario_bm25(nombre_coleccion: str, directorio: str = ".cache/vocab_bm25") -> dict[str, int]:
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
# (`rag/servicio/pipeline.py::verificar_premisa`) solo podía comprobar si una
# entidad de la pregunta aparecía en los 3 fragmentos RECUPERADOS -- si la
# evidencia real existía en el corpus pero no llegó al top-3 (Recall@3=0.84,
# no 1.00), la capa (b) la trataba como "ausente" y se abstenía de más,
# aunque el corpus sí la cubriera. El inventario -- ya
# calculado gratis, `entidades` va en el payload de cada chunk desde E1 --
# permite distinguir "no existe en el corpus" (abstención correcta) de
# "existe, pero no llegó al top-3" (dispara una recuperación dirigida, ver
# `rag/indice.py::construir_filtro_entidad`).
# ---------------------------------------------------------------------------
def construir_inventario_entidades(payloads: list[dict]) -> list[str]:
    """Todos los `valor_norm` de entidades presentes en algún chunk del
    corpus (unión, sin duplicar) -- se calcula desde el mismo campo
    `entidades` que ya construye `rag/metadata.py::construir_payload` para
    cada chunk, no se reextrae nada."""
    valores: set[str] = set()
    for p in payloads:
        for e in p.get("entidades", []):
            valores.add(e["valor_norm"])
    return sorted(valores)


def ruta_inventario_entidades(nombre_coleccion: str, directorio: str = ".cache/vocab_bm25") -> str:
    return str(pathlib.Path(directorio) / f"{nombre_coleccion}.entidades.json")


def guardar_inventario_entidades(inventario: list[str], nombre_coleccion: str,
                                  directorio: str = ".cache/vocab_bm25") -> str:
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
                                 directorio: str = ".cache/vocab_bm25") -> set[str]:
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
                                      directorio: str = ".cache/vocab_bm25") -> str:
    return str(pathlib.Path(directorio) / f"{nombre_coleccion}.estadisticas_lexico.json")


def guardar_estadisticas_lexico_dominio(estadisticas: dict[str, float], nombre_coleccion: str,
                                         directorio: str = ".cache/vocab_bm25") -> str:
    import json

    ruta = ruta_estadisticas_lexico_dominio(nombre_coleccion, directorio)
    pathlib.Path(directorio).mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(estadisticas, f, ensure_ascii=False)
    return ruta


def cargar_estadisticas_lexico_dominio(nombre_coleccion: str,
                                        directorio: str = ".cache/vocab_bm25") -> dict[str, float]:
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
CATALOGO_PATH = "documentos/catalogo.yaml"


def cargar_catalogo(ruta: str = CATALOGO_PATH) -> list[dict]:
    """Catálogo de documentos, leído de ``documentos/catalogo.yaml``.

    Vive en configuración y no en código porque es lo primero que cambia al
    adoptar un dominio nuevo: agregar un documento debe ser agregar una
    entrada al YAML, no editar Python.
    """
    import yaml
    datos = yaml.safe_load(pathlib.Path(ruta).read_text(encoding="utf-8")) or {}
    # `datos["documentos"]` puede ser `None` si el catálogo se creó vacío
    # (`rag init`, o `_append_entrada_catalogo` antes de la primera entrada:
    # "documentos:\n" sin items parsea a `None`, no a `[]`) -- se normaliza
    # aquí, una sola vez, en vez de que cada llamador tenga que acordarse.
    return datos.get("documentos") or []


# ---------------------------------------------------------------------------
# `rag cargar` (Etapa Plugin, Tarea A): copia un documento al corpus y lo
# registra en `documentos/catalogo.yaml`. La lógica vive aquí (no en la CLI) por
# la regla del encargo: "si un comando necesita lógica nueva, esa lógica se
# escribe en rag/, nunca en la CLI".
# ---------------------------------------------------------------------------

def _slug(nombre: str) -> str:
    """Slug determinista y legible: sin acentos, minúsculas, solo
    ``[a-z0-9-]``. Nunca vacío (cae a "documento")."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return base or "documento"


def generar_doc_id(nombre_archivo: str, ids_existentes: set[str], hash_contenido: str) -> str:
    """``doc_id`` estable y legible: el slug del nombre de archivo (sin
    extensión); si ya existe un ``doc_id`` igual (otro documento con nombre
    parecido), se distingue con un sufijo corto del hash de CONTENIDO -- no
    un número de serie ciego, para que dos cargas del mismo archivo en
    momentos distintos sigan produciendo el mismo id si el contenido no
    cambió (ver `rag/corpus.py::agregar_documentos_al_catalogo`, que además
    detecta ese caso ANTES de llegar aquí y no duplica la entrada)."""
    base = _slug(Path(nombre_archivo).stem)
    if base not in ids_existentes:
        return base
    candidato = f"{base}-{hash_contenido[:6]}"
    contador = 2
    original = candidato
    while candidato in ids_existentes:
        candidato = f"{original}-{contador}"
        contador += 1
    return candidato


def inferir_titulo(doc: DocumentoParseado, nombre_archivo: str) -> str:
    """El primer encabezado del documento (bloque ``tipo_contenido ==
    "titulo"``); si no hay ninguno, el comienzo del primer bloque narrativo,
    recortado; si el documento no tiene ni un bloque, el nombre de archivo
    humanizado. Nunca inventa un título: siempre es texto que ya existe en
    el documento, o el nombre que el propio usuario le puso al archivo."""
    primero_titulo = next((b.texto for b in doc.bloques if b.tipo_contenido == "titulo"), None)
    if primero_titulo:
        return primero_titulo

    primero_narrativo = next((b.texto for b in doc.bloques if b.tipo_contenido == "narrativo"), None)
    if primero_narrativo:
        texto = primero_narrativo.strip()
        return texto[:80].rstrip() + ("..." if len(texto) > 80 else "")

    base = Path(nombre_archivo).stem
    return re.sub(r"[-_]+", " ", base).strip().title() or Path(nombre_archivo).name


def _yaml_valor(valor) -> str:
    """Serializa un valor escalar como YAML de flujo válido, en una línea --
    usa el mismo truco que ``rag/paquete_revision_externa.py::_json_una_linea``:
    un JSON válido de un escalar simple ES YAML de flujo válido, así que no
    hace falta razonar sobre el "quoting" de PyYAML a mano para un `dump`
    parcial (que además perdería los comentarios del resto del archivo)."""
    return json.dumps(valor, ensure_ascii=False)


def plantilla_catalogo_vacio() -> str:
    """Contenido inicial de ``documentos/catalogo.yaml`` sin documentos -- la usa
    tanto ``rag init`` (para que el archivo exista desde el principio, con
    un mensaje claro en vez de un ``FileNotFoundError``) como
    ``_append_entrada_catalogo`` (si `rag cargar` es lo primero que se
    corre). Nota: ``documentos:`` sin items parsea a ``None`` con
    ``yaml.safe_load``, no a una lista vacía -- ``cargar_catalogo`` ya lo
    normaliza."""
    return (
        "# Catálogo de documentos del corpus.\n"
        "# Agregado con 'rag cargar <archivo|carpeta>' -- no se edita a mano salvo\n"
        "# para corregir 'doc_titulo', 'version' o 'vigente' de una entrada existente.\n"
        "documentos:\n"
    )


def _append_entrada_catalogo(ruta_catalogo: str, entrada: dict) -> None:
    """Agrega una entrada al FINAL de ``documentos/catalogo.yaml`` sin volver a
    serializar el archivo completo -- es lo que garantiza que los
    comentarios existentes (y las entradas ya escritas a mano) queden
    intactos, letra por letra, en vez de depender de que un dumper YAML los
    preserve (PyYAML con `yaml.safe_load`/`safe_dump` los descarta
    siempre)."""
    ruta = Path(ruta_catalogo)
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(plantilla_catalogo_vacio(), encoding="utf-8")

    texto_actual = ruta.read_text(encoding="utf-8")
    if not texto_actual.endswith("\n"):
        texto_actual += "\n"

    bloque = (
        f"\n  - archivo: {_yaml_valor(entrada['archivo'])}\n"
        f"    doc_id: {entrada['doc_id']}\n"
        f"    doc_titulo: {_yaml_valor(entrada['doc_titulo'])}\n"
        f"    version: {_yaml_valor(str(entrada['version']))}\n"
        f"    vigente: {'true' if entrada['vigente'] else 'false'}\n"
        f"    hash_contenido: {entrada['hash_contenido']}\n"
    )
    ruta.write_text(texto_actual + bloque, encoding="utf-8")


@dataclass
class DocumentoCargado:
    archivo: str
    doc_id: str
    doc_titulo: str
    version: str
    vigente: bool
    hash_contenido: str
    ya_existia: bool = False
    advertencias: list[str] = field(default_factory=list)


def agregar_documentos_al_catalogo(rutas: list[str], carpeta_corpus: str = "documentos",
                                    ruta_catalogo: str = CATALOGO_PATH) -> list[DocumentoCargado]:
    """Copia cada archivo de ``rutas`` a ``carpeta_corpus`` (si no está ya
    ahí) y agrega una entrada nueva a ``documentos/catalogo.yaml`` -- salvo que su
    HASH de contenido ya esté registrado (misma carga repetida: se avisa y
    no se duplica). Devuelve un resumen por documento, incluidas las
    advertencias del parser (p.ej. "sin estructura de secciones") para que
    el llamador (la CLI) las muestre."""
    Path(carpeta_corpus).mkdir(parents=True, exist_ok=True)

    catalogo_actual = cargar_catalogo(ruta_catalogo) if Path(ruta_catalogo).exists() else []
    ids_existentes = {e["doc_id"] for e in catalogo_actual}
    hashes_existentes = {e["hash_contenido"]: e["doc_id"] for e in catalogo_actual if e.get("hash_contenido")}

    resultado: list[DocumentoCargado] = []
    for ruta_str in rutas:
        ruta_origen = Path(ruta_str)
        if not ruta_origen.is_file():
            raise FileNotFoundError(f"no existe el archivo {ruta_origen}")
        ext = ruta_origen.suffix.lower()
        if ext not in EXTENSIONES_SOPORTADAS:
            raise ValueError(
                f"{ruta_origen}: formato {ext!r} no soportado (soportados: {sorted(EXTENSIONES_SOPORTADAS)})"
            )

        contenido = ruta_origen.read_bytes()
        hash_contenido = hashlib.sha256(contenido).hexdigest()

        if hash_contenido in hashes_existentes:
            resultado.append(DocumentoCargado(
                archivo=ruta_origen.name, doc_id=hashes_existentes[hash_contenido],
                doc_titulo="(ya estaba en el catálogo, mismo contenido)", version="-", vigente=True,
                hash_contenido=hash_contenido, ya_existia=True,
            ))
            continue

        doc_id = generar_doc_id(ruta_origen.name, ids_existentes, hash_contenido)

        # Parsea desde el ORIGEN, antes de copiar nada: si el documento se
        # rechaza (p.ej. un PDF escaneado, DocumentoEscaneadoError), no debe
        # quedar un archivo huérfano en documentos/ sin entrada en el
        # catálogo -- defecto real encontrado reproduciendo 'rag cargar' con
        # un PDF escaneado en un directorio externo al repo.
        doc_parseado = parsear_documento(str(ruta_origen), doc_id=doc_id, doc_titulo="(pendiente)", version="1")
        titulo = inferir_titulo(doc_parseado, ruta_origen.name)

        destino = Path(carpeta_corpus) / ruta_origen.name
        if destino.is_file() and hashlib.sha256(destino.read_bytes()).hexdigest() != hash_contenido:
            destino = destino.with_name(
                f"{destino.stem}-{hash_contenido[:6]}{destino.suffix}"
            )
        if destino.resolve() != ruta_origen.resolve():
            shutil.copy2(ruta_origen, destino)
        ids_existentes.add(doc_id)

        entrada = {
            "archivo": destino.name, "doc_id": doc_id, "doc_titulo": titulo,
            "version": "1", "vigente": True, "hash_contenido": hash_contenido,
        }
        _append_entrada_catalogo(ruta_catalogo, entrada)
        catalogo_actual.append(entrada)
        hashes_existentes[hash_contenido] = doc_id

        resultado.append(DocumentoCargado(
            archivo=entrada["archivo"], doc_id=doc_id, doc_titulo=titulo, version="1",
            vigente=True, hash_contenido=hash_contenido, advertencias=list(doc_parseado.advertencias),
        ))
    return resultado


def parsear_corpus(carpeta_corpus: str) -> list[DocumentoParseado]:
    """Parsea todo el catálogo (``documentos/catalogo.yaml``) con el despacho por
    extensión de ``rag/parsear.py::parsear_documento`` (Etapa Plugin, Tarea
    B) -- soporta ``.docx``, ``.pdf``, ``.md``/``.markdown`` y ``.txt`` sin
    que este módulo (ni ningún otro consumidor de ``DocumentoParseado``)
    tenga que saber cuál es cuál."""
    docs = []
    for entrada in cargar_catalogo():
        ruta = str(Path(carpeta_corpus) / entrada["archivo"])
        doc = parsear_documento(ruta, doc_id=entrada["doc_id"], doc_titulo=entrada["doc_titulo"],
                                 version=entrada["version"])
        docs.append(doc)
    return docs


def construir_chunks_y_payloads(docs: list[DocumentoParseado], estrategia: str,
                                 con_header: bool, taxonomia: dict) -> tuple[list[Chunk], list[dict]]:
    chunk_fn = ESTRATEGIAS[estrategia]
    todos_chunks: list[Chunk] = []
    payloads: list[dict] = []
    hashes_vistos: dict[str, str] = {}

    for doc, entrada in zip(docs, cargar_catalogo()):
        chunks = chunk_fn(doc)
        todos_chunks.extend(chunks)
        for i, ch in enumerate(chunks):
            texto_embebido = construir_texto_embebido(entrada["doc_titulo"], ch.seccion_path, ch.texto) \
                if con_header else ch.texto
            payload = construir_payload(ch, entrada["doc_titulo"], entrada["version"],
                                         entrada["vigente"], taxonomia, texto_embebido)
            payload["chunk_prev"] = chunks[i - 1].chunk_id if i > 0 else None
            payload["chunk_next"] = chunks[i + 1].chunk_id if i < len(chunks) - 1 else None

            h = payload["hash_texto"]
            if h in hashes_vistos:
                payload["duplicado_de"] = hashes_vistos[h]
            else:
                hashes_vistos[h] = payload["chunk_id"]
            payloads.append(payload)

    return todos_chunks, payloads


def validar_payloads(payloads: list[dict], taxonomia: dict) -> list[str]:
    errores_totales: list[str] = []
    for p in payloads:
        for err in validar_chunk(p, taxonomia):
            errores_totales.append(f"{err.chunk_id} | {err.campo} | {err.detalle}")
    return errores_totales


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
      levantado con ``docker compose up -d qdrant`` (ver docker-compose.yml
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


# ---------------------------------------------------------------------------
# `rag indexar` (Etapa Plugin, Tarea A): la MISMA secuencia que corría
# Pipeline compartido por la CLI: parsear, fragmentar, validar e indexar.
# y persistir los artefactos de ingesta -- movida aquí para que el script
# numerado (que sigue existiendo como herramienta de desarrollo, ver
# README.md) y el comando de la CLI llamen a una única implementación en vez
# de reimplementar la orquestación dos veces.
# ---------------------------------------------------------------------------

@dataclass
class ResumenDocumento:
    doc_id: str
    n_bloques: int
    n_caracteres: int


@dataclass
class ResumenIngesta:
    documentos: list[ResumenDocumento]
    n_chunks: int
    errores_validacion: list[str]
    advertencias: list[str]
    tiempo_seg: float
    nombre_coleccion: str = ""
    n_vocab_bm25: int = 0
    n_entidades_inventario: int = 0
    n_terminos_lexico: int = 0

    @property
    def n_documentos(self) -> int:
        return len(self.documentos)


def ejecutar_ingesta(carpeta_corpus: str = "documentos", estrategia: str | None = None,
                      con_header: bool | None = None, modelo: str | None = None,
                      coleccion: str | None = None, qdrant_path: str | None = None,
                      version_coleccion: int | None = None, sufijo_coleccion: str | None = None,
                      solo_validar: bool = False, cfg_rec: dict | None = None) -> ResumenIngesta:
    """Ingesta completa: parsea el catálogo (con el despacho por extensión
    de `rag/parsear.py`, cualquier mezcla de `.docx`/`.pdf`/`.md`/`.txt`),
    fragmenta, valida y (salvo `solo_validar`) indexa en Qdrant + persiste
    vocabulario BM25, inventario de entidades y estadísticas léxicas de
    dominio -- exactamente los mismos artefactos que ya consumía
    `rag/servicio/api.py`.

    Es IDEMPOTENTE: `indexar_qdrant` borra la colección si ya existe antes
    de recrearla (ver más arriba), así que correr esto dos veces seguidas
    con el mismo corpus/config dos veces produce el mismo índice, no uno
    duplicado.

    Las advertencias combinan las que trae cada `DocumentoParseado` (PDF sin
    outline, Markdown/texto sin encabezados) con un chequeo genérico para
    `.docx` (que hoy no las emite desde el propio parser): si NINGÚN bloque
    del documento tiene `seccion_path`, se advierte igual -- el mensaje
    exacto que pide el encargo: "este documento no tiene estructura de
    secciones"."""
    import time

    from rag.configuracion.carga import config_recuperacion

    t0 = time.perf_counter()
    cfg_rec = cfg_rec if cfg_rec is not None else config_recuperacion()
    estrategia = estrategia or cfg_rec["estrategia_chunking"]
    con_header = cfg_rec["con_header"] if con_header is None else con_header
    modelo = modelo or cfg_rec["modelo"]
    coleccion = coleccion or cfg_rec["coleccion_base"]
    qdrant_path = qdrant_path or cfg_rec["qdrant_path"]
    version_coleccion = cfg_rec["version_coleccion"] if version_coleccion is None else version_coleccion

    taxonomia = cargar_taxonomia("configuracion/categorias.yaml")
    docs = parsear_corpus(carpeta_corpus)
    resumen_docs = [ResumenDocumento(d.doc_id, len(d.bloques), len(d.texto_completo)) for d in docs]

    chunks, payloads = construir_chunks_y_payloads(docs, estrategia, con_header, taxonomia)
    errores = validar_payloads(payloads, taxonomia)

    advertencias: list[str] = []
    for d in docs:
        if d.advertencias:
            advertencias.extend(f"{d.doc_id}: {a}" for a in d.advertencias)
        elif all(not b.seccion_path for b in d.bloques):
            advertencias.append(
                f"{d.doc_id}: este documento no tiene estructura de secciones, lo que degrada los filtros."
            )

    if solo_validar:
        return ResumenIngesta(resumen_docs, len(chunks), errores, advertencias, time.perf_counter() - t0)

    _client, _modelo_st, vocab, nombre_col = indexar_qdrant(
        payloads, modelo, coleccion, qdrant_path, usar_texto_embebido=con_header,
        n_version=version_coleccion, sufijo_coleccion=sufijo_coleccion,
    )
    guardar_vocabulario_bm25(vocab, nombre_col)
    inventario = construir_inventario_entidades(payloads)
    guardar_inventario_entidades(inventario, nombre_col)
    estadisticas = construir_estadisticas_lexico_dominio(payloads, con_header)
    guardar_estadisticas_lexico_dominio(estadisticas, nombre_col)

    return ResumenIngesta(
        documentos=resumen_docs, n_chunks=len(chunks), errores_validacion=errores, advertencias=advertencias,
        tiempo_seg=time.perf_counter() - t0, nombre_coleccion=nombre_col, n_vocab_bm25=len(vocab),
        n_entidades_inventario=len(inventario), n_terminos_lexico=len(estadisticas),
    )
