"""Bloques visuales de la fuente: sin interpretación semántica ni cambios de texto."""
from __future__ import annotations


def bloques_fuente(documento, inicio: int, fin: int) -> list[dict]:
    fuente = documento.texto_completo
    candidatos = []
    elementos = getattr(documento, "elementos", []) or getattr(documento, "bloques", [])
    tablas = {t.table_id: t for t in getattr(documento, "tablas", [])}
    for elemento in elementos:
        metadata = getattr(elemento, "metadata", {})
        if metadata.get("tipo") == "fila":
            continue  # sus celdas pertenecen al elemento tabla
        a, b = max(inicio, elemento.offset_inicio), min(fin, elemento.offset_fin)
        if a >= b:
            continue
        tipo = getattr(elemento, "tipo", getattr(elemento, "tipo_contenido", "narrativo"))
        bloque = {"kind": "heading" if tipo == "titulo" else "paragraph",
                  "text": fuente[a:b], "offset_start": a, "offset_end": b}
        completo = a == elemento.offset_inicio and b == elemento.offset_fin
        tabla = tablas.get(getattr(elemento, "element_id", None))
        if tabla is not None and completo:
            filas = []
            for i in range(tabla.filas):
                celdas = [{"column": c.columna, "column_span": c.columnas, "row_span": c.filas,
                           "text": c.texto, "offset_start": c.referencia.offset_inicio,
                           "offset_end": c.referencia.offset_fin}
                          for c in tabla.celdas if c.fila == i and not c.continuacion_de]
                filas.append({"header": i in tabla.filas_encabezado, "cells": celdas})
            bloque.update(kind="table", columns=tabla.columnas, rows=filas)
        elif tipo == "tabla" and completo and metadata.get("cells"):
            bloque.update(kind="table", columns=metadata["columns"],
                          rows=[{"header": metadata.get("header", False),
                                 "cells": metadata["cells"]}],
                          _table_id=metadata["table_id"])
        candidatos.append(bloque)
    candidatos.sort(key=lambda b: b["offset_start"])
    salida, posicion = [], inicio
    for bloque in candidatos:
        a, b = bloque["offset_start"], bloque["offset_end"]
        if a < posicion:
            continue
        if posicion < a and fuente[posicion:a].strip():
            salida.append({"kind": "paragraph", "text": fuente[posicion:a],
                           "offset_start": posicion, "offset_end": a})
        tabla_id = bloque.pop("_table_id", None)
        if (tabla_id and salida and salida[-1].get("_table_id") == tabla_id
                and salida[-1]["columns"] == bloque["columns"] and not fuente[posicion:a].strip()):
            anterior = salida[-1]
            anterior["rows"].extend(bloque["rows"])
            anterior["offset_end"] = b
            anterior["text"] = fuente[anterior["offset_start"]:b]
        else:
            if tabla_id:
                bloque["_table_id"] = tabla_id
            salida.append(bloque)
        posicion = b
    if posicion < fin and fuente[posicion:fin].strip():
        salida.append({"kind": "paragraph", "text": fuente[posicion:fin],
                       "offset_start": posicion, "offset_end": fin})
    for bloque in salida:
        bloque.pop("_table_id", None)
        for fila in bloque.get("rows", []):
            for celda in fila["cells"]:
                a, b = celda["offset_start"], celda["offset_end"]
                if not inicio <= a <= b <= fin or fuente[a:b] != celda["text"]:
                    raise ValueError("celda visual fuera del texto fuente")
    return salida
