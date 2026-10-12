"""Hijos buscables y contextos fuente; nunca cruza sección o tabla."""
from __future__ import annotations

import re

from ipsis.nucleo.documentos import DocumentoPreparado
from ipsis.nucleo.esquemas import ChunkRecord

CHUNKER_VERSION = "unidades-estructura-1.2"


def unidades_documento(documento: DocumentoPreparado, max_palabras=400, palabras_hijo=80):
    if max_palabras < 1 or palabras_hijo < 1:
        raise ValueError("los presupuestos de unidades deben ser positivos")
    por_id = {e.element_id: e for e in documento.elementos}
    tablas = {t.table_id: t for t in documento.tablas}
    padres, hijos, grupos, actual = {}, [], [], []

    def cerrar():
        nonlocal actual
        if actual:
            grupos.append((actual, None))
        actual = []

    for e in documento.elementos:
        if e.metadata.get("tipo") == "fila":
            continue
        if e.tipo == "tabla":
            cerrar()
            tabla = tablas[e.element_id]
            filas = [por_id[fid] for fid in tabla.filas_ids]
            # Una tabla pequeña es una unidad completa; una grande conserva
            # filas enteras, y referencias separadas a sus encabezados.
            grupo, n = [], 0
            for fila in filas:
                palabras = len(fila.texto.split())
                if grupo and n + palabras > max_palabras:
                    grupos.append((grupo, tabla))
                    grupo, n = [], 0
                grupo.append(fila)
                n += palabras
            if grupo:
                grupos.append((grupo, tabla))
        elif e.tipo == "titulo":
            cerrar()
        elif e.texto.strip():
            if actual and (e.metadata.get("enfasis_parrafo") or actual[-1].seccion_path != e.seccion_path or
                    sum(len(x.texto.split()) for x in actual) + len(e.texto.split()) > max_palabras):
                cerrar()
            actual.append(e)
    cerrar()

    for numero, (grupo, tabla) in enumerate(grupos):
        inicio, fin = grupo[0].offset_inicio, grupo[-1].offset_fin
        contexto_refs = []
        if tabla is not None:
            anterior = por_id.get(tabla.contexto_previo_id)
            if anterior is not None:
                contexto_refs.append({"element_id": anterior.element_id, "offset_inicio": anterior.offset_inicio,
                    "offset_fin": anterior.offset_fin, "rol": "contexto_previo"})
                if grupo[0].element_id == tabla.filas_ids[0] and len(anterior.texto.split()) + sum(len(e.texto.split()) for e in grupo) <= max_palabras:
                    inicio = anterior.offset_inicio
            # La primera fila se conserva como contexto, sin inferir que sea header.
            for fid in [tabla.filas_ids[i] for i in tabla.filas_encabezado] or tabla.filas_ids[:1]:
                header = por_id[fid]
                contexto_refs.append({"element_id": fid, "offset_inicio": header.offset_inicio,
                    "offset_fin": header.offset_fin, "rol": "encabezado" if tabla.encabezado_explicito else "primera_fila"})
        pid = f"{documento.doc_id}__u{numero:04d}"
        fuente = documento.texto_completo[inicio:fin]
        padre = ChunkRecord(chunk_id=pid, doc_id=documento.doc_id, doc_titulo=documento.titulo,
            version=documento.version, texto_fuente=fuente,
            texto_embedding="\n".join([*grupo[0].seccion_path, fuente]),
            offset_inicio=inicio, offset_fin=fin, seccion_path=grupo[0].seccion_path,
            tipo_contenido="tabla" if tabla else "narrativo", parent_id=grupo[0].metadata.get("parent_id"),
            metadata={"elementos": [e.element_id for e in grupo], "table_id": tabla.table_id if tabla else None,
                      "referencias_contexto": contexto_refs, "structure_hash": documento.structure_hash})
        if tabla is not None:
            from ipsis.ingesta.lectura import contexto_tabla

            lectura = contexto_tabla(documento, tabla, [e.element_id for e in grupo])
            padre.metadata["contexto_lectura"] = lectura.model_dump(mode="json")
        padres[pid] = padre
        prefijo = "\n".join([documento.titulo, *padre.seccion_path,
            *[documento.texto_completo[r["offset_inicio"]:r["offset_fin"]] for r in contexto_refs]])
        for e in grupo:
            # Filas completas siempre; párrafos largos se dividen sin perder texto.
            limites = [(0, len(e.texto))]
            if not tabla:
                palabras = list(re.finditer(r"\S+", e.texto))
                puntos = [0, *[palabras[i].start() for i in range(palabras_hijo, len(palabras), palabras_hijo)], len(e.texto)]
                limites = list(zip(puntos, puntos[1:]))
            for desde, hasta in limites:
                texto = e.texto[desde:hasta]
                if not texto.strip():
                    continue
                cid = f"{documento.doc_id}__s{len(hijos):05d}"
                hijos.append(ChunkRecord(chunk_id=cid, doc_id=documento.doc_id, doc_titulo=documento.titulo,
                    version=documento.version, texto_fuente=texto, texto_embedding=f"{prefijo}\n{texto}",
                    offset_inicio=e.offset_inicio + desde, offset_fin=e.offset_inicio + hasta,
                    seccion_path=padre.seccion_path, tipo_contenido=padre.tipo_contenido, parent_id=pid,
                    metadata={"element_id": e.element_id, "table_id": tabla.table_id if tabla else None,
                              "referencias_contexto": contexto_refs, "structure_hash": documento.structure_hash}))
    for chunks in (list(padres.values()), hijos):
        for i, ch in enumerate(chunks):
            ch.prev_id = chunks[i - 1].chunk_id if i else None
            ch.next_id = chunks[i + 1].chunk_id if i + 1 < len(chunks) else None
    return hijos, padres


def construir_payloads_estructurados(docs, taxonomia, opciones):
    from ipsis.ingesta.chunking import Chunk
    from ipsis.ingesta.metadata import construir_payload
    from ipsis.indice.estadisticas import EstadisticasLexicas
    from ipsis.lenguaje.entidades import idioma_activo

    todos, padres, documentos = [], {}, []
    for doc in docs:
        preparado = DocumentoPreparado.model_validate(doc.estructura)
        hijos, contextos = unidades_documento(preparado, opciones["max_palabras_unidad"], opciones["palabras_hijo"])
        todos.extend(hijos)
        padres.update(contextos)
        documentos.append(preparado)
    est = EstadisticasLexicas.construir([c.texto_fuente for c in todos], idioma_activo())
    payloads = []
    por_doc = {d.doc_id: d for d in documentos}
    for i, hijo in enumerate(todos):
        chunk = Chunk(chunk_id=hijo.chunk_id, doc_id=hijo.doc_id, orden=i, seccion_path=hijo.seccion_path,
            seccion_nivel=len(hijo.seccion_path), tipo_contenido=hijo.tipo_contenido, texto=hijo.texto_fuente,
            offset_inicio=hijo.offset_inicio, offset_fin=hijo.offset_fin, estrategia="CH-STRUCT")
        p = construir_payload(chunk, hijo.doc_titulo, hijo.version, True, taxonomia, hijo.texto_embedding,
                              pipeline_version=CHUNKER_VERSION, estadisticas=est)
        p.update(parent_id=hijo.parent_id, prev_id=hijo.prev_id, next_id=hijo.next_id,
                 **hijo.metadata, preparacion={**opciones, "parser_version": por_doc[hijo.doc_id].parser_version,
                     "chunker_version": CHUNKER_VERSION, "source_hash": por_doc[hijo.doc_id].source_hash})
        payloads.append(p)
    return todos, payloads, padres, documentos
