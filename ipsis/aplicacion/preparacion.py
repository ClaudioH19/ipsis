"""Preparar y revisar un proyecto independiente antes de construir su índice."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from html import escape


@dataclass
class ResumenPreparacion:
    proyecto: Path
    vista_previa: Path
    datos: Path
    documentos: int
    unidades: int
    hijos: int
    advertencias: list[str]
    indexado: bool = False


def preparar_proyecto(origen, destino, *, indexar=False):
    from ipsis.configuracion.carga import cargar_proyecto
    from ipsis.configuracion.archivos import volcar
    from ipsis.ingesta.catalogo import entradas_vigentes
    from ipsis.ingesta.preparacion import preparar_documento
    from ipsis.ingesta.unidades import unidades_documento

    origen, destino = Path(origen).resolve(), Path(destino).resolve()
    if destino == origen or destino.is_relative_to(origen) or origen.is_relative_to(destino):
        raise ValueError("la preparación debe escribirse fuera del proyecto original")
    if destino.exists():
        raise FileExistsError("la carpeta destino ya existe; usar otra para conservar la referencia")
    cfg = cargar_proyecto(str(origen / "config/engine.yaml"))
    entradas = entradas_vigentes(str(origen / "documents/catalog.yaml"))
    if not entradas:
        raise ValueError("el proyecto no tiene documentos vigentes")
    docs, padres, hijos, avisos = [], {}, [], []
    for e in entradas:
        archivo = (origen / "documents" / e["archivo"]).resolve()
        if not archivo.is_relative_to(origen / "documents"):
            raise ValueError("archivo del catálogo fuera de documents")
        d = preparar_documento(archivo, doc_id=e["doc_id"], doc_titulo=e["doc_titulo"], version=e["version"])
        cs, ps = unidades_documento(d)
        docs.append(d)
        padres.update(ps)
        hijos.extend(cs)
        avisos.extend(f"{d.doc_id}: {a}" for a in d.advertencias)
    # Se valida y prepara todo antes de crear la carpeta nueva.
    shutil.copytree(origen / "config", destino / "config")
    shutil.copytree(origen / "documents", destino / "documents")
    cfg["pipeline"] = "v2"
    from ipsis.configuracion.esquemas import PREPARACION_ESTRUCTURAL

    cfg["recuperacion"]["preparacion"] = dict(PREPARACION_ESTRUCTURAL)
    # Una copia nunca apunta a servidores ni a rutas de índices del proyecto servido.
    cfg["recuperacion"]["qdrant_path"] = ".ipsis/index/qdrant"
    cfg["qdrant"]["modo"] = "local"
    (destino / "config/engine.yaml").write_text(volcar(cfg, "motor"), encoding="utf-8")
    for doc in docs:
        doc.ruta_origen = str(destino / "documents" / Path(doc.ruta_origen).relative_to(origen / "documents"))
    directorio = destino / ".ipsis/preparation"
    directorio.mkdir(parents=True)
    datos = directorio / "documents.json"
    datos.write_text(json.dumps({"version": 1, "documentos": [d.model_dump(mode="json") for d in docs],
        "unidades": [p.model_dump(mode="json") for p in padres.values()],
        "hijos": [c.model_dump(mode="json") for c in hijos]}, ensure_ascii=False, indent=1), encoding="utf-8")
    vista = directorio / "preview.html"
    vista.write_text(_vista_previa(docs, padres, avisos), encoding="utf-8")
    resumen = ResumenPreparacion(destino, vista, datos, len(docs), len(padres), len(hijos), avisos)
    if indexar:
        from ipsis.aplicacion.corpus import indexar_proyecto

        anterior = Path.cwd()
        modo_previo = os.environ.get("QDRANT_MODE")
        try:
            os.chdir(destino)
            os.environ["QDRANT_MODE"] = "local"
            indexar_proyecto("documents")
            resumen.indexado = True
        finally:
            os.chdir(anterior)
            if modo_previo is None:
                os.environ.pop("QDRANT_MODE", None)
            else:
                os.environ["QDRANT_MODE"] = modo_previo
    return resumen


def _vista_previa(docs, padres, avisos):
    partes = ['<!doctype html><html lang="es"><meta charset="utf-8"><title>Preparación documental</title>',
        '<style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 24px}pre{white-space:pre-wrap}',
        'table{border-collapse:collapse;margin:12px 0;width:100%}td,th{border:1px solid #aaa;padding:8px;white-space:pre-wrap}',
        'details{margin:16px 0}.aviso{color:#823d00}small{color:#555}</style>',
        '<h1>Preparación documental</h1><p>Texto extraído y estructura del cuerpo. Revisar los avisos antes de indexar.</p>']
    partes.extend(f'<p class="aviso">{escape(a)}</p>' for a in avisos)
    for doc in docs:
        partes.append(f'<h2>{escape(doc.titulo)}</h2><p>{escape(Path(doc.ruta_origen).name)}</p>')
        elementos = {e.element_id: e for e in doc.elementos}
        for tabla in doc.tablas:
            contexto = elementos.get(tabla.contexto_previo_id)
            label = contexto.texto if contexto is not None else "Tabla"
            partes.append(f'<details open><summary>{escape(label)}</summary><table>')
            for fila in range(tabla.filas):
                partes.append('<tr>')
                ocupadas = {col for c in tabla.celdas if c.fila < fila < c.fila + c.filas
                            for col in range(c.columna, c.columna + c.columnas)}
                celdas = {c.columna: c for c in tabla.celdas if c.fila == fila and not c.continuacion_de}
                col = 0
                while col < tabla.columnas:
                    if col in ocupadas:
                        col += 1
                        continue
                    c = celdas.get(col)
                    if c is None:
                        partes.append('<td title="posición omitida"></td>')
                        col += 1
                    else:
                        tag = 'th' if fila in tabla.filas_encabezado else 'td'
                        partes.append(f'<{tag} rowspan="{c.filas}" colspan="{c.columnas}" title="{escape(c.referencia.localizador)}">{escape(c.texto)}</{tag}>')
                        col += c.columnas
                partes.append('</tr>')
            partes.append('</table></details>')
        partes.append('<details><summary>Unidades fuente para el lector, en orden</summary>')
        for padre in padres.values():
            if padre.doc_id == doc.doc_id:
                partes.append(f'<h3>{escape(padre.chunk_id)}</h3><small>Offsets {padre.offset_inicio}–{padre.offset_fin}</small><pre>{escape(padre.texto_fuente)}</pre>')
                lectura = padre.metadata.get("contexto_lectura")
                if lectura:
                    partes.append('<details><summary>Representación por campos para los modelos</summary>')
                    for supuesto in lectura["supuestos"]:
                        partes.append(f'<p class="aviso">Supuesto estructural: {escape(supuesto)}</p>')
                    partes.append('<pre>' + escape(lectura["texto"]) + '</pre></details>')
        partes.append('</details><details><summary>Texto completo extraído</summary><pre>' + escape(doc.texto_completo) + '</pre></details>')
    partes.append('</html>')
    return '\n'.join(partes)
