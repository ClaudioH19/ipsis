"""Ingesta completa: parsear, fragmentar, enriquecer, validar e indexar."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


from ipsis.configuracion import rutas
from ipsis.ingesta.parsear import parsear_documento, DocumentoParseado
from ipsis.ingesta.chunking import ESTRATEGIAS, construir_texto_embebido, Chunk
from ipsis.ingesta.metadata import cargar_taxonomia, construir_payload, senales_de_texto, validar_chunk
from ipsis.ingesta.catalogo import entradas_vigentes
from ipsis.indice.manifiesto import ManifiestoIndice, guardar_manifiesto, hash_corpus, inventario_entidades
from ipsis.indice.qdrant import (
    indexar_qdrant,
    ruta_estadisticas,
)
from ipsis.recursos.mensajes import t


def parsear_corpus(carpeta_corpus: str, preparacion: str | None = None) -> list[DocumentoParseado]:
    """Parsea todo el catálogo (``documents/catalog.yaml``) con el despacho por
    extensión de ``ipsis/ingesta/parsear.py::parsear_documento``: documentos y
    archivos tabulares XLSX/XLS/CSV/TSV, sin
    que este módulo (ni ningún otro consumidor de ``DocumentoParseado``)
    tenga que saber cuál es cuál."""
    from ipsis.nucleo.progreso import informar

    docs = []
    if preparacion is None:
        from ipsis.configuracion.carga import cargar_proyecto

        preparacion = (cargar_proyecto()["recuperacion"].get("preparacion", {}).get("modo", "legacy")
                       if Path(rutas.MOTOR).is_file() else "legacy")
    if preparacion not in {"legacy", "estructural_v1"}:
        raise ValueError("preparación desconocida")
    entradas = entradas_vigentes()
    for numero, entrada in enumerate(entradas, 1):
        informar("documento", archivo=entrada["archivo"], actual=numero, total=len(entradas))
        ruta = str(Path(carpeta_corpus) / entrada["archivo"])
        if preparacion == "estructural_v1":
            from ipsis.ingesta.preparacion import como_documento_parseado, preparar_documento

            doc = como_documento_parseado(preparar_documento(ruta, doc_id=entrada["doc_id"],
                doc_titulo=entrada["doc_titulo"], version=entrada["version"]))
        else:
            doc = parsear_documento(ruta, doc_id=entrada["doc_id"], doc_titulo=entrada["doc_titulo"],
                                     version=entrada["version"])
        docs.append(doc)
    return docs


def construir_chunks_y_payloads(docs: list[DocumentoParseado], estrategia: str,
                                 con_header: bool, taxonomia: dict,
                                 detalle_cabecera: str = "basico") -> tuple[list[Chunk], list[dict]]:
    chunk_fn = ESTRATEGIAS[estrategia]
    todos_chunks: list[Chunk] = []
    payloads: list[dict] = []
    hashes_vistos: dict[str, str] = {}

    from ipsis.indice.estadisticas import EstadisticasLexicas
    from ipsis.lenguaje.entidades import idioma_activo

    entradas = {e["doc_id"]: e for e in entradas_vigentes()}
    from ipsis.ingesta.chunking import chunks_tabulares

    por_documento = [(chunks_tabulares(doc) if any(b.metadata.get("record_id") for b in doc.bloques)
                      else chunk_fn(doc), entradas[doc.doc_id]) for doc in docs]
    # Las palabras clave usan el IDF del corpus completo.
    estadisticas = EstadisticasLexicas.construir(
        [ch.texto for chunks, _ in por_documento for ch in chunks], idioma_activo()
    )
    for chunks, entrada in por_documento:
        todos_chunks.extend(chunks)
        for i, ch in enumerate(chunks):
            senales = None
            if con_header and detalle_cabecera == "extendido":
                # Entidades y marcas se calculan una vez: la cabecera y el payload usan las mismas.
                senales = senales_de_texto(ch.texto)
                texto_embebido = construir_texto_embebido(
                    entrada["doc_titulo"], ch.seccion_path, ch.texto, idioma_activo(),
                    tipos_entidad=[e["tipo"] for e in senales[0]], excepcion=senales[1], condicion=senales[2])
            elif con_header:
                texto_embebido = construir_texto_embebido(entrada["doc_titulo"], ch.seccion_path, ch.texto,
                                                          idioma_activo())
            else:
                texto_embebido = ch.texto
            payload = construir_payload(ch, entrada["doc_titulo"], entrada["version"],
                                         entrada["vigente"], taxonomia, texto_embebido,
                                         estadisticas=estadisticas, senales=senales)
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
    from ipsis.ingesta.tabulares import EXTENSIONES, PARSER_VERSION as VERSION_TABULAR

    cfg_rec = cfg_rec if cfg_rec is not None else config_recuperacion()
    digest = hashlib.sha256(f"{cfg_rec['estrategia_chunking']}|{cfg_rec['con_header']}".encode("utf-8"))
    if cfg_rec.get("detalle_cabecera", "basico") != "basico":
        digest.update(f"|cabecera={cfg_rec['detalle_cabecera']}".encode("utf-8"))
    preparacion = cfg_rec.get("preparacion", {})
    if preparacion.get("modo", "legacy") != "legacy":
        import json
        from ipsis.ingesta.preparacion import PARSER_VERSION
        from ipsis.ingesta.unidades import CHUNKER_VERSION

        digest.update(json.dumps({"preparacion": preparacion, "parser": PARSER_VERSION,
            "chunker": CHUNKER_VERSION}, sort_keys=True).encode("utf-8"))
    estructural_texto = preparacion.get("modo", "legacy") != "legacy"
    for entrada in sorted(entradas_vigentes(), key=lambda e: e["doc_id"]):
        sufijo = Path(entrada["archivo"]).suffix.lower()
        if sufijo in EXTENSIONES:
            digest.update(VERSION_TABULAR.encode("utf-8"))
        elif estructural_texto and sufijo in {".md", ".markdown", ".txt", ".pdf"}:
            from ipsis.ingesta.preparacion import PARSER_VERSION_MARKDOWN, PARSER_VERSION_PDF, PARSER_VERSION_TEXTO

            digest.update({".txt": PARSER_VERSION_TEXTO, ".pdf": PARSER_VERSION_PDF}.get(
                sufijo, PARSER_VERSION_MARKDOWN).encode("utf-8"))
        contenido = (Path(carpeta_corpus) / entrada["archivo"]).read_bytes()
        digest.update(f"\n{entrada['doc_id']}|{entrada['doc_titulo']}|{entrada['version']}|".encode("utf-8"))
        digest.update(hashlib.sha256(contenido).digest())
    return "sha256:" + digest.hexdigest()


def huella_corpus(carpeta_corpus: str = rutas.DOCUMENTOS, cfg_rec: dict | None = None) -> str:
    """``hash_corpus`` que tendría el índice si se indexara ahora: parsea y
    fragmenta igual que ``ejecutar_ingesta``, sin modelos ni Qdrant."""
    from ipsis.configuracion.carga import config_recuperacion

    cfg_rec = cfg_rec if cfg_rec is not None else config_recuperacion()
    opciones = cfg_rec.get("preparacion", {"modo": "legacy"})
    docs = parsear_corpus(carpeta_corpus, opciones["modo"])
    if opciones["modo"] == "estructural_v1":
        from ipsis.ingesta.unidades import construir_payloads_estructurados

        if opciones.get("similitud_hermanos", "tfidf") == "vectores" and opciones.get("rasgos_distintivos"):
            return "sin-modelo"  # los grupos dependen de los vectores: se compara por ``huella_archivos``
        _, payloads, _, _ = construir_payloads_estructurados(docs, cargar_taxonomia(), opciones)
    else:
        _chunks, payloads = construir_chunks_y_payloads(docs, cfg_rec["estrategia_chunking"],
                                                       cfg_rec["con_header"], cargar_taxonomia(),
                                                       cfg_rec.get("detalle_cabecera", "basico"))
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
    from ipsis.nucleo.progreso import informar

    informar("parseo")
    opciones = cfg_rec.get("preparacion", {"modo": "legacy"})
    estructural = opciones["modo"] == "estructural_v1"
    docs = parsear_corpus(carpeta_corpus, opciones["modo"])
    resumen_docs = [ResumenDocumento(d.doc_id, len(d.bloques), len(d.texto_completo)) for d in docs]

    informar("fragmentado", total=len(docs))
    padres, preparados, codificador_hermanos = {}, [], None
    if estructural:
        from ipsis.ingesta.unidades import construir_payloads_estructurados

        if opciones.get("similitud_hermanos", "tfidf") == "vectores" and opciones.get("rasgos_distintivos"):
            from ipsis.modelos.catalogo import obtener
            from ipsis.modelos.denso import CodificadorDenso

            informar("modelo")
            codificador_hermanos = CodificadorDenso(obtener(modelo))
        chunks, payloads, padres, preparados = construir_payloads_estructurados(
            docs, taxonomia, opciones, codificador_hermanos)
        con_header = True
    else:
        chunks, payloads = construir_chunks_y_payloads(docs, estrategia, con_header, taxonomia,
                                                       cfg_rec.get("detalle_cabecera", "basico"))
    informar("validacion", total=len(payloads))
    errores = validar_payloads(payloads, taxonomia)

    advertencias: list[str] = []
    for d in docs:
        if d.advertencias:
            advertencias.extend(f"{d.doc_id}: {a}" for a in d.advertencias)
        elif all(not b.seccion_path for b in d.bloques):
            advertencias.append(t("core.no_sections_document", doc_id=d.doc_id))

    if solo_validar:
        return ResumenIngesta(resumen_docs, len(chunks), errores, advertencias, time.perf_counter() - t0)
    if estructural and errores:
        raise ValueError("preparación estructural inválida: " + "; ".join(errores))

    _client, _codificador, estadisticas_lexicas, nombre_col = indexar_qdrant(
        payloads, modelo, coleccion, qdrant_path, usar_texto_embebido=con_header, codificador=codificador_hermanos,
        n_version=version_coleccion, sufijo_coleccion=sufijo_coleccion,
        **({"permitir_recrear": False, "modo": "local"} if estructural else {}),
    )
    try:
        informar("guardado")
        huella = hash_corpus(payloads)
        estadisticas_lexicas.hash_corpus = huella
        estadisticas_lexicas.guardar(ruta_estadisticas(nombre_col))
        inventario = inventario_entidades(payloads)
        metadata_preparacion = None
        if estructural:
            from ipsis.indice.contextos import guardar_contextos
            from ipsis.ingesta.preparacion import PARSER_VERSION
            from ipsis.ingesta.unidades import CHUNKER_VERSION

            metadata_preparacion = {**opciones, "parser_version": PARSER_VERSION, "chunker_version": CHUNKER_VERSION,
                "parser_versions": sorted({d.parser_version for d in preparados}),
                "contextos_sha256": guardar_contextos(nombre_col, preparados, padres, opciones)}
        guardar_manifiesto(ManifiestoIndice(
            coleccion=nombre_col, modelo_denso=modelo, dimension=_codificador.dimension,
            stemmer=estadisticas_lexicas.stemmer, hash_corpus=huella, n_chunks=len(payloads),
            hash_archivos=huella_archivos(carpeta_corpus, {"estrategia_chunking": estrategia, "con_header": con_header,
                                                       "detalle_cabecera": cfg_rec.get("detalle_cabecera", "basico"),
                                                       "preparacion": opciones}),
            inventario_entidades=inventario,
            preparacion=metadata_preparacion,
        ))
    finally:
        if estructural:
            _client.close()

    return ResumenIngesta(
        documentos=resumen_docs, n_chunks=len(chunks), errores_validacion=errores, advertencias=advertencias,
        tiempo_seg=time.perf_counter() - t0, nombre_coleccion=nombre_col, n_vocab_bm25=len(estadisticas_lexicas.df),
        n_entidades_inventario=len(inventario),
    )
