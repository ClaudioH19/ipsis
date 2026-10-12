"""Serialización de filas por campos; cada copia conserva celda y offsets."""
from __future__ import annotations

from ipsis.nucleo.lectura import ContextoLectura, CopiaFuente
from ipsis.nucleo.documentos import ReferenciaFuente


def contexto_tabla(documento, tabla, filas_ids):
    elementos = {e.element_id: e for e in documento.elementos}
    filas = {fid: i for i, fid in enumerate(tabla.filas_ids)}
    texto, copias = "", []

    def agregar(valor, referencia=None, cell_id=None, rol="contenido"):
        nonlocal texto
        inicio = len(texto)
        texto += valor
        if valor and referencia is not None:
            copias.append(CopiaFuente(inicio=inicio, fin=len(texto), referencia=referencia,
                                     cell_id=cell_id, rol=rol))

    def celda(c, rol):
        agregar(c.texto, c.referencia, c.cell_id, rol)

    previo = elementos.get(tabla.contexto_previo_id)
    if previo is not None:
        agregar(previo.texto, ReferenciaFuente(element_id=previo.element_id,
            offset_inicio=previo.offset_inicio, offset_fin=previo.offset_fin,
            localizador=previo.metadata.get("localizador", previo.element_id)), rol="contexto_previo")
        agregar("\n")
    headers = tabla.filas_encabezado or [0]
    supuestos = [] if tabla.encabezado_explicito else ["primera_fila_como_etiquetas_no_declaradas"]
    # Se retiene la fila que aporta etiquetas incluso en unidades posteriores.
    for fila in headers:
        for j, c in enumerate(c for c in tabla.celdas if c.fila == fila and not c.continuacion_de):
            if j:
                agregar(" | ")
            celda(c, "encabezado" if tabla.encabezado_explicito else "primera_fila")
        agregar("\n")
    for fid in filas_ids:
        fila = filas[fid]
        if fila in headers:
            continue
        for j, c in enumerate(c for c in tabla.celdas if c.fila == fila and not c.continuacion_de):
            if j:
                agregar("; ")
            etiquetas = [h for h in tabla.celdas if h.fila in headers and not h.continuacion_de
                         and h.texto and h.columna <= c.columna < h.columna + h.columnas]
            for k, h in enumerate(etiquetas):
                if k:
                    agregar(" / ")
                celda(h, "etiqueta")
            if not etiquetas:
                agregar(f"Columna {c.columna + 1}")
            agregar(": ")
            celda(c, "valor")
        agregar(".\n")
    contexto = ContextoLectura(texto=texto, copias=copias, supuestos=supuestos)
    contexto.verificar_fuente(documento.texto_completo)
    return contexto
