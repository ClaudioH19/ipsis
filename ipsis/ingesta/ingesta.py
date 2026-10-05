"""Ingesta completa: parsear, fragmentar, enriquecer, validar e indexar."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


from ipsis.configuracion import rutas
from ipsis.ingesta.parsear import parsear_documento, DocumentoParseado
from ipsis.ingesta.chunking import ESTRATEGIAS, construir_texto_embebido, Chunk
from ipsis.ingesta.metadata import cargar_taxonomia, construir_payload, validar_chunk
from ipsis.ingesta.catalogo import entradas_vigentes
from ipsis.indice.manifiesto import ManifiestoIndice, guardar_manifiesto, hash_corpus, inventario_entidades
from ipsis.indice.qdrant import (
    indexar_qdrant,
    ruta_estadisticas,
)


def parsear_corpus(carpeta_corpus: str) -> list[DocumentoParseado]:
    """Parsea todo el catálogo (``documents/catalog.yaml``) con el despacho por
    extensión de ``ipsis/ingesta/parsear.py::parsear_documento`` -- soporta ``.docx``, ``.pdf``, ``.md``/``.markdown`` y ``.txt`` sin
    que este módulo (ni ningún otro consumidor de ``DocumentoParseado``)
    tenga que saber cuál es cuál."""
    docs = []
    for entrada in entradas_vigentes():
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

    from ipsis.indice.estadisticas import EstadisticasLexicas
    from ipsis.lenguaje.entidades import idioma_activo

    entradas = {e["doc_id"]: e for e in entradas_vigentes()}
    por_documento = [(chunk_fn(doc), entradas[doc.doc_id]) for doc in docs]
    # Las palabras clave usan el IDF del corpus completo.
    estadisticas = EstadisticasLexicas.construir(
        [ch.texto for chunks, _ in por_documento for ch in chunks], idioma_activo()
    )
    for chunks, entrada in por_documento:
        todos_chunks.extend(chunks)
        for i, ch in enumerate(chunks):
            texto_embebido = construir_texto_embebido(entrada["doc_titulo"], ch.seccion_path, ch.texto) \
                if con_header else ch.texto
            payload = construir_payload(ch, entrada["doc_titulo"], entrada["version"],
                                         entrada["vigente"], taxonomia, texto_embebido,
                                         estadisticas=estadisticas)
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


# ---------------------------------------------------------------------------
# `ipsis index`: parsear, fragmentar, validar, indexar y persistir los
# artefactos de ingesta, en una única implementación que usan la CLI y
# `ipsis serve <carpeta>`.
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

    @property
    def n_documentos(self) -> int:
        return len(self.documentos)


def huella_archivos(carpeta_corpus: str = rutas.DOCUMENTOS, cfg_rec: dict | None = None) -> str:
    """Huella de lo que se indexaría, sin parsear: bytes de cada documento vigente
    y la configuración de fragmentado. Igual huella ⇒ igual ``hash_corpus``."""
    import hashlib

    from ipsis.configuracion.carga import config_recuperacion

    cfg_rec = cfg_rec if cfg_rec is not None else config_recuperacion()
    digest = hashlib.sha256(f"{cfg_rec['estrategia_chunking']}|{cfg_rec['con_header']}".encode("utf-8"))
    for entrada in sorted(entradas_vigentes(), key=lambda e: e["doc_id"]):
        contenido = (Path(carpeta_corpus) / entrada["archivo"]).read_bytes()
        digest.update(f"\n{entrada['doc_id']}|{entrada['doc_titulo']}|{entrada['version']}|".encode("utf-8"))
        digest.update(hashlib.sha256(contenido).digest())
    return "sha256:" + digest.hexdigest()


def huella_corpus(carpeta_corpus: str = rutas.DOCUMENTOS, cfg_rec: dict | None = None) -> str:
    """``hash_corpus`` que tendría el índice si se indexara ahora: parsea y
    fragmenta igual que ``ejecutar_ingesta``, sin modelos ni Qdrant."""
    from ipsis.configuracion.carga import config_recuperacion

    cfg_rec = cfg_rec if cfg_rec is not None else config_recuperacion()
    _chunks, payloads = construir_chunks_y_payloads(parsear_corpus(carpeta_corpus), cfg_rec["estrategia_chunking"],
                                                    cfg_rec["con_header"], cargar_taxonomia())
    return hash_corpus(payloads)


def ejecutar_ingesta(carpeta_corpus: str = rutas.DOCUMENTOS, estrategia: str | None = None,
                      con_header: bool | None = None, modelo: str | None = None,
                      coleccion: str | None = None, qdrant_path: str | None = None,
                      version_coleccion: int | None = None, sufijo_coleccion: str | None = None,
                      solo_validar: bool = False, cfg_rec: dict | None = None) -> ResumenIngesta:
    """Ingesta completa: parsea el catálogo (con el despacho por extensión
    de `ipsis/ingesta/parsear.py`, cualquier mezcla de `.docx`/`.pdf`/`.md`/`.txt`),
    fragmenta, valida y (salvo `solo_validar`) indexa en Qdrant + persiste
    vocabulario BM25, inventario de entidades y estadísticas léxicas de
    dominio -- exactamente los mismos artefactos que ya consumía
    `ipsis/servicio/api.py`.

    Es IDEMPOTENTE: `indexar_qdrant` borra la colección si ya existe antes
    de recrearla (ver más arriba), así que correr esto dos veces seguidas
    con el mismo corpus/config dos veces produce el mismo índice, no uno
    duplicado.

    Las advertencias combinan las que trae cada `DocumentoParseado` (PDF sin
    outline, Markdown/texto sin encabezados) con un chequeo genérico para
    `.docx` (que hoy no las emite desde el propio parser): si NINGÚN bloque
    del documento tiene `seccion_path`, se advierte igual ("este documento no
    tiene estructura de secciones")."""
    import time

    from ipsis.configuracion.carga import config_recuperacion

    t0 = time.perf_counter()
    cfg_rec = cfg_rec if cfg_rec is not None else config_recuperacion()
    estrategia = estrategia or cfg_rec["estrategia_chunking"]
    con_header = cfg_rec["con_header"] if con_header is None else con_header
    modelo = modelo or cfg_rec["modelo"]
    coleccion = coleccion or cfg_rec["coleccion_base"]
    qdrant_path = qdrant_path or cfg_rec["qdrant_path"]
    version_coleccion = cfg_rec["version_coleccion"] if version_coleccion is None else version_coleccion

    taxonomia = cargar_taxonomia()
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

    _client, _codificador, estadisticas_lexicas, nombre_col = indexar_qdrant(
        payloads, modelo, coleccion, qdrant_path, usar_texto_embebido=con_header,
        n_version=version_coleccion, sufijo_coleccion=sufijo_coleccion,
    )
    estadisticas_lexicas.guardar(ruta_estadisticas(nombre_col))
    huella = hash_corpus(payloads)
    estadisticas_lexicas.hash_corpus = huella
    estadisticas_lexicas.guardar(ruta_estadisticas(nombre_col))
    inventario = inventario_entidades(payloads)
    guardar_manifiesto(ManifiestoIndice(
        coleccion=nombre_col, modelo_denso=modelo, dimension=_codificador.dimension,
        stemmer=estadisticas_lexicas.stemmer, hash_corpus=huella, n_chunks=len(payloads),
        hash_archivos=huella_archivos(carpeta_corpus, {"estrategia_chunking": estrategia, "con_header": con_header}),
        inventario_entidades=inventario,
    ))

    return ResumenIngesta(
        documentos=resumen_docs, n_chunks=len(chunks), errores_validacion=errores, advertencias=advertencias,
        tiempo_seg=time.perf_counter() - t0, nombre_coleccion=nombre_col, n_vocab_bm25=len(estadisticas_lexicas.df),
        n_entidades_inventario=len(inventario),
    )
