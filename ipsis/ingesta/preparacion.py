"""Preparación estructural sin modelos ni interpretación de temas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ipsis.nucleo.documentos import CeldaPreparada, DocumentoPreparado, ReferenciaFuente, TablaPreparada
from ipsis.nucleo.esquemas import ElementRecord

PARSER_VERSION = "docx-estructura-1"
PARSER_VERSION_MARKDOWN = "markdown-estructura-1"
PARSER_VERSION_TEXTO = "texto-estructura-1"


def preparar_documento(ruta, *, doc_id, doc_titulo, version="1"):
    from ipsis.ingesta.tabulares import EXTENSIONES, preparar_tabular

    if Path(ruta).suffix.lower() in EXTENSIONES:
        return preparar_tabular(ruta, doc_id=doc_id, doc_titulo=doc_titulo, version=version)
    if Path(ruta).suffix.lower() == ".docx":
        return preparar_docx(ruta, doc_id=doc_id, doc_titulo=doc_titulo, version=version)
    if Path(ruta).suffix.lower() in {".md", ".markdown"}:
        return preparar_markdown(ruta, doc_id=doc_id, doc_titulo=doc_titulo, version=version)
    if Path(ruta).suffix.lower() == ".txt":
        return preparar_texto(ruta, doc_id=doc_id, doc_titulo=doc_titulo, version=version)
    raise ValueError("estructura-1 soporta DOCX, Markdown, texto, XLSX, XLS, CSV y TSV; el PDF sigue en legacy")


def _hash(datos):
    return "sha256:" + hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def preparar_docx(ruta, *, doc_id, doc_titulo, version="1") -> DocumentoPreparado:
    import docx
    from docx.oxml.ns import qn
    from docx.table import _Cell, Table
    from docx.text.paragraph import Paragraph

    documento = docx.Document(ruta)
    partes, elementos, tablas, avisos, pila = [], [], [], [], []
    offset = 0
    previo = None

    def agregar(texto, eid, tipo, metadata, ruta_seccion=None):
        nonlocal offset
        elemento = ElementRecord(element_id=eid, tipo=tipo, texto=texto,
            offset_inicio=offset, offset_fin=offset + len(texto),
            seccion_path=ruta_seccion if ruta_seccion is not None else [x[1] for x in pila],
            metadata={"orden": len(elementos), **metadata})
        partes.extend((texto, "\n"))
        offset += len(texto) + 1
        elementos.append(elemento)
        return elemento

    def texto_celda(tc, tabla):
        celda = _Cell(tc, tabla)
        textos = []
        for interior in tc.iterchildren():
            if interior.tag == qn("w:p"):
                textos.append(Paragraph(interior, celda).text)
            elif interior.tag == qn("w:tbl"):
                avisos.append("tabla anidada: contenido conservado como texto; relaciones internas no soportadas")
                anidada = Table(interior, celda)
                for fila in anidada._tbl.tr_lst:
                    textos.append(" | ".join(texto_celda(c, anidada) for c in fila.tc_lst))
        return "\n".join(textos)

    for posicion, xml in enumerate(documento.element.body.iterchildren()):
        eid = f"{doc_id}__e{posicion:04d}"
        localizador = f"word/document.xml/body/*[{posicion + 1}]"
        if xml.tag == qn("w:p"):
            parrafo = Paragraph(xml, documento)
            texto = parrafo.text
            estilo = parrafo.style
            # Outline declarado en el párrafo o en su estilo, sin regex sobre su tema.
            nivel = None
            propiedad = xml.find("./" + qn("w:pPr") + "/" + qn("w:outlineLvl"))
            if propiedad is not None:
                nivel = int(propiedad.get(qn("w:val"))) + 1
            elif estilo is not None:
                actual, vistos = estilo, set()
                while actual is not None and actual.style_id not in vistos:
                    vistos.add(actual.style_id)
                    p = actual.element.find("./" + qn("w:pPr") + "/" + qn("w:outlineLvl"))
                    if p is not None:
                        nivel = int(p.get(qn("w:val"))) + 1
                        break
                    actual = actual.base_style
                if estilo.style_id == "Title":
                    nivel = 0
            if nivel is not None and nivel < 10 and texto.strip():
                pila[:] = [x for x in pila if x[0] < nivel]
                padre = pila[-1][2] if pila else None
                pila.append((nivel, texto, eid))
                tipo = "titulo"
            else:
                padre = pila[-1][2] if pila else None
                numeracion = xml.find("./" + qn("w:pPr") + "/" + qn("w:numPr"))
                tipo = "lista" if numeracion is not None or (estilo and estilo.style_id.startswith("List")) else "parrafo"
            e = agregar(texto, eid, tipo, {"parent_id": padre, "nivel": nivel,
                "estilo": estilo.style_id if estilo else None, "localizador": localizador,
                "enfasis_parrafo": bool(parrafo.runs) and all(
                    r.bold is True or (r.bold is None and r.style.font.bold is True)
                    for r in parrafo.runs if r.text.strip())})
            if texto.strip():
                previo = e
        elif xml.tag == qn("w:tbl"):
            tabla = Table(xml, documento)
            inicio_tabla = offset
            tabla_elemento = ElementRecord(element_id=eid, tipo="tabla", texto="",
                offset_inicio=offset, offset_fin=offset,
                seccion_path=[x[1] for x in pila], metadata={"orden": len(elementos),
                "parent_id": pila[-1][2] if pila else None, "localizador": localizador, "tipo": "tabla"})
            elementos.append(tabla_elemento)
            contexto_id = previo.element_id if previo is not None and previo.seccion_path == tabla_elemento.seccion_path else None
            columnas = len(xml.tblGrid.gridCol_lst) if xml.tblGrid is not None else 0
            celdas, filas_ids, headers, activos = [], [], [], {}
            for numero, fila in enumerate(xml.tr_lst):
                fid = f"{eid}__r{numero:04d}"
                tr_pr = fila.trPr
                antes = tr_pr.find(qn("w:gridBefore")) if tr_pr is not None else None
                despues = tr_pr.find(qn("w:gridAfter")) if tr_pr is not None else None
                col = int(antes.get(qn("w:val"))) if antes is not None else 0
                inicio_col = col
                slots, relativos, siguientes = [""] * col, [], {}
                for j, tc in enumerate(fila.tc_lst):
                    tc_pr = tc.tcPr
                    span = tc_pr.gridSpan.val if tc_pr is not None and tc_pr.gridSpan is not None else 1
                    vertical = tc_pr.vMerge if tc_pr is not None else None
                    continuacion = vertical is not None and vertical.val != "restart"
                    texto = texto_celda(tc, tabla)
                    anchor = activos.get(col) if continuacion else None
                    if continuacion and (anchor is None or anchor.columnas != span):
                        raise ValueError("combinación vertical sin celda origen compatible")
                    if anchor is not None:
                        anchor.filas += 1
                    cid = f"{fid}__c{col:04d}"
                    relativos.append((cid, col, span, texto, anchor, j))
                    slots.extend([texto, *([""] * (span - 1))])
                    if vertical is not None:
                        siguientes[col] = anchor or cid
                    col += span
                omitidas = int(despues.get(qn("w:val"))) if despues is not None else 0
                columnas = max(columnas, col + omitidas)
                slots.extend([""] * max(omitidas, columnas - len(slots)))
                texto_fila = " | ".join(slots)
                e = agregar(texto_fila, fid, "tabla", {"tipo": "fila", "parent_id": eid,
                    "fila": numero, "omitidas_inicio": inicio_col,
                    "omitidas_fin": omitidas, "localizador": f"{localizador}/tr[{numero + 1}]"})
                filas_ids.append(fid)
                starts, pos = [], 0
                for valor in slots:
                    starts.append(pos)
                    pos += len(valor) + 3
                for cid, columna, span, texto, anchor, j in relativos:
                    ini = e.offset_inicio + starts[columna]
                    celda = CeldaPreparada(cell_id=cid, fila=numero, columna=columna, columnas=span,
                        texto=texto, continuacion_de=anchor.cell_id if anchor else None,
                        referencia=ReferenciaFuente(element_id=fid, offset_inicio=ini, offset_fin=ini + len(texto),
                            localizador=f"{localizador}/tr[{numero + 1}]/tc[{j + 1}]"))
                    celdas.append(celda)
                    if siguientes.get(columna) == cid:
                        siguientes[columna] = celda
                activos = siguientes
                if tr_pr is not None:
                    header = tr_pr.find(qn("w:tblHeader"))
                    if header is not None and header.get(qn("w:val"), "true") not in ("0", "false", "off"):
                        headers.append(numero)
            fin_tabla = offset - 1 if filas_ids else offset
            tabla_elemento.texto = "".join(partes)[inicio_tabla:fin_tabla]
            tabla_elemento.offset_fin = fin_tabla
            tablas.append(TablaPreparada(table_id=eid, filas=len(filas_ids), columnas=columnas,
                celdas=celdas, filas_encabezado=headers, encabezado_explicito=bool(headers),
                contexto_previo_id=contexto_id, filas_ids=filas_ids,
                referencia=ReferenciaFuente(element_id=eid, offset_inicio=inicio_tabla, offset_fin=fin_tabla,
                    localizador=localizador)))
            previo = None
        elif xml.tag != qn("w:sectPr"):
            avisos.append(f"elemento de cuerpo no soportado: {xml.tag.rsplit('}', 1)[-1]}")
    if not pila:
        avisos.append("sin títulos estructurales declarados: no se infieren por palabras del documento")
    if documento.element.body.xpath(".//w:drawing | .//w:pict"):
        avisos.append("imágenes o formas: contenido visual no extraído")
    if documento.element.body.xpath(".//w:ins | .//w:del"):
        avisos.append("control de cambios: revisar la vista previa; revisiones no resueltas")
    if documento.element.body.xpath(".//m:oMath"):
        avisos.append("ecuaciones: representación matemática no soportada")
    if any(str(p.partname).startswith(("/word/header", "/word/footer", "/word/footnotes", "/word/endnotes"))
           for p in documento.part.package.parts):
        avisos.append("encabezados, pies o notas fuera del cuerpo: no extraídos")
    texto = "".join(partes)
    datos_estructura = {"parser": PARSER_VERSION, "elementos": [e.model_dump(mode="json") for e in elementos],
        "tablas": [t.model_dump(mode="json") for t in tablas], "texto": texto}
    return DocumentoPreparado(doc_id=doc_id, titulo=doc_titulo, version=str(version), ruta_origen=str(ruta),
        texto_completo=texto, elementos=elementos, tablas=tablas, parser_version=PARSER_VERSION,
        source_hash="sha256:" + hashlib.sha256(Path(ruta).read_bytes()).hexdigest(),
        structure_hash=_hash(datos_estructura), advertencias=sorted(set(avisos)))


def _preparar_desde_parseado(parseado, *, parser_version, avisos_extra=()) -> DocumentoPreparado:
    """Convierte la salida de ``parsear_markdown`` / ``parsear_texto_plano`` en un documento preparado.

    El texto canónico y los offsets son los del parser existente (no se duplica su lectura de
    encabezados). Los títulos son los declarados por ``#`` (Markdown) o los que ese parser
    reconoce en texto plano; las filas de tablas Markdown quedan como párrafos."""
    elementos, avisos = [], list(parseado.advertencias) + list(avisos_extra)
    pila: list[tuple[int, str]] = []  # (nivel, element_id) de los títulos abiertos
    seccion: list[str] = []
    for bloque in parseado.bloques:
        eid = f"{parseado.doc_id}__e{len(elementos):04d}"
        if bloque.tipo_contenido == "titulo":
            nivel = bloque.seccion_nivel
            pila = [x for x in pila if x[0] < nivel]
            padre = pila[-1][1] if pila else None
            pila.append((nivel, eid))
            seccion = list(bloque.seccion_path)
            tipo, metadata = "titulo", {"parent_id": padre, "nivel": nivel}
        else:
            padre = pila[-1][1] if pila else None
            # Una fila de tabla Markdown lleva su encabezado en la ruta del parser; aquí la sección
            # es la del último título, igual que para un párrafo.
            tipo = "lista" if bloque.tipo_contenido == "lista" else "parrafo"
            metadata = {"parent_id": padre, "nivel": None}
            if bloque.tipo_contenido == "tabla":
                metadata["origen"] = "fila_tabla_markdown"
        elementos.append(ElementRecord(
            element_id=eid, tipo=tipo, texto=bloque.texto, offset_inicio=bloque.offset_inicio,
            offset_fin=bloque.offset_fin, seccion_path=list(seccion),
            metadata={"orden": len(elementos), **metadata}))
    if any(e.metadata.get("origen") == "fila_tabla_markdown" for e in elementos):
        avisos.append("tablas Markdown: cada fila se conserva como párrafo, sin celdas ni encabezados")
    datos_estructura = {"parser": parser_version, "elementos": [e.model_dump(mode="json") for e in elementos],
                        "texto": parseado.texto_completo}
    return DocumentoPreparado(
        doc_id=parseado.doc_id, titulo=parseado.doc_titulo, version=str(parseado.version),
        ruta_origen=str(parseado.ruta_origen), texto_completo=parseado.texto_completo, elementos=elementos,
        parser_version=parser_version, source_hash="sha256:" + hashlib.sha256(Path(parseado.ruta_origen).read_bytes()).hexdigest(),
        structure_hash=_hash(datos_estructura), advertencias=sorted(set(avisos)))


def preparar_markdown(ruta, *, doc_id, doc_titulo, version="1") -> DocumentoPreparado:
    from ipsis.ingesta.parsear import parsear_markdown

    return _preparar_desde_parseado(parsear_markdown(str(ruta), doc_id, doc_titulo, version),
                                    parser_version=PARSER_VERSION_MARKDOWN)


def preparar_texto(ruta, *, doc_id, doc_titulo, version="1") -> DocumentoPreparado:
    from ipsis.ingesta.parsear import parsear_texto_plano

    return _preparar_desde_parseado(parsear_texto_plano(str(ruta), doc_id, doc_titulo, version),
                                    parser_version=PARSER_VERSION_TEXTO)


def como_documento_parseado(preparado):
    from ipsis.ingesta.parsear import Bloque, DocumentoParseado

    hojas = [e for e in preparado.elementos if e.metadata.get("tipo") != "tabla"]
    bloques = [Bloque(indice=i, seccion_path=e.seccion_path, seccion_nivel=len(e.seccion_path),
        tipo_contenido={"parrafo": "narrativo"}.get(e.tipo, e.tipo), texto=e.texto,
        offset_inicio=e.offset_inicio, offset_fin=e.offset_fin) for i, e in enumerate(hojas) if e.texto.strip()]
    return DocumentoParseado(doc_id=preparado.doc_id, doc_titulo=preparado.titulo, version=preparado.version,
        ruta_origen=preparado.ruta_origen, texto_completo=preparado.texto_completo, bloques=bloques,
        advertencias=preparado.advertencias, estructura=preparado.model_dump(mode="json"))
