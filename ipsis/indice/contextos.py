"""Almacén de unidades fuente, verificable sin abrir los documentos originales."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from ipsis.configuracion import rutas
from ipsis.nucleo.documentos import DocumentoPreparado
from ipsis.nucleo.esquemas import ChunkRecord


def ruta_contextos(coleccion, directorio=rutas.INDICE):
    return Path(directorio) / f"{coleccion}.contexts.json"


def guardar_contextos(coleccion, documentos, padres, preparacion, directorio=rutas.INDICE):
    datos = {"version": 1, "coleccion": coleccion, "preparacion": preparacion,
        "documentos": [d.model_dump(mode="json") for d in documentos],
        "padres": {pid: p.model_dump(mode="json") for pid, p in padres.items()}}
    contenido = json.dumps(datos, sort_keys=True, ensure_ascii=False).encode("utf-8")
    destino = ruta_contextos(coleccion, directorio)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".json.tmp")
    temporal.write_bytes(contenido)
    os.replace(temporal, destino)
    return "sha256:" + hashlib.sha256(contenido).hexdigest()


def cargar_contextos(manifiesto, directorio=rutas.INDICE, *, incluir_documentos=False):
    contenido = ruta_contextos(manifiesto.coleccion, directorio).read_bytes()
    if "sha256:" + hashlib.sha256(contenido).hexdigest() != manifiesto.preparacion.get("contextos_sha256"):
        raise ValueError("el almacén estructural no coincide con el manifiesto")
    datos = json.loads(contenido)
    if datos.get("version") != 1 or datos.get("coleccion") != manifiesto.coleccion:
        raise ValueError("versión o colección estructural incompatible")
    documentos = {d.doc_id: d for d in (DocumentoPreparado.model_validate(v) for v in datos["documentos"])}
    padres = {pid: ChunkRecord.model_validate(p) for pid, p in datos["padres"].items()}
    for pid, p in padres.items():
        doc = documentos[p.doc_id]
        if (pid != p.chunk_id or p.version != doc.version or
                p.metadata.get("structure_hash") != doc.structure_hash or
                doc.texto_completo[p.offset_inicio:p.offset_fin] != p.texto_fuente):
            raise ValueError("unidad fuente estructural inconsistente")
        if p.metadata.get("contexto_lectura") is not None:
            from ipsis.nucleo.lectura import ContextoLectura

            contexto = ContextoLectura.model_validate(p.metadata["contexto_lectura"])
            contexto.verificar_fuente(doc.texto_completo)
            elementos = {e.element_id for e in doc.elementos}
            celdas = {c.cell_id: c for t in doc.tablas for c in t.celdas}
            if any(c.referencia.element_id not in elementos or
                   (c.cell_id is not None and c.cell_id not in celdas) for c in contexto.copias):
                raise ValueError("referencia de lectura a un elemento o celda ausente")
            rangos = [(p.offset_inicio, p.offset_fin), *[(r["offset_inicio"], r["offset_fin"])
                      for r in p.metadata.get("referencias_contexto", [])]]
            for copia in contexto.copias:
                ref = copia.referencia
                if copia.cell_id is not None and ref != celdas[copia.cell_id].referencia:
                    raise ValueError("mapa de lectura con identidad de celda inconsistente")
                if not any(ini <= ref.offset_inicio <= ref.offset_fin <= fin for ini, fin in rangos):
                    raise ValueError("mapa de lectura fuera de las relaciones de la unidad")
    return (padres, documentos) if incluir_documentos else padres


class RecuperadorConContextos:
    """Delega búsqueda; amplía solo las relaciones declaradas por la ingesta."""

    def __init__(self, recuperador, padres, documentos=None):
        self.recuperador, self.padres = recuperador, padres
        self.documentos = documentos or {}
        self._unidades = {}
        for padre in padres.values():
            self._unidades.setdefault(padre.doc_id, []).append(padre)
        for doc_id, unidades in self._unidades.items():
            unidades.sort(key=lambda p: (p.offset_inicio, p.offset_fin, p.chunk_id))
        for doc_id, doc in self.documentos.items():
            self._unidades.setdefault(doc_id, list(getattr(doc, "bloques", [])))

    def __getattr__(self, nombre):
        return getattr(self.recuperador, nombre)

    def ampliar_contextos(self, candidatos, max_caracteres):
        salida, por_id, expansiones = [], {}, []
        for candidato in candidatos:
            hijo = candidato.chunk
            padre = self.padres.get(hijo.parent_id)
            if hijo.parent_id is None:
                salida.append(candidato)
                continue
            if padre is None:
                raise ValueError("unidad padre ausente para el candidato")
            ini, fin = hijo.offset_inicio - padre.offset_inicio, hijo.offset_fin - padre.offset_inicio
            if (hijo.doc_id != padre.doc_id or hijo.version != padre.version or
                    hijo.metadata.get("structure_hash") != padre.metadata.get("structure_hash") or
                    not 0 <= ini <= fin <= len(padre.texto_fuente) or padre.texto_fuente[ini:fin] != hijo.texto_fuente):
                raise ValueError("relación hijo/padre no literal o de otra extracción")
            if fin > max_caracteres:
                salida.append(candidato)
                expansiones.append({"hijo": hijo.chunk_id, "padre": padre.chunk_id,
                                    "aplicada": False, "motivo": "hijo fuera del presupuesto de contexto"})
                continue
            expansiones.append({"hijo": hijo.chunk_id, "padre": padre.chunk_id,
                                "aplicada": True, "motivo": "relación estructural"})
            if padre.chunk_id not in por_id:
                nuevo = candidato.model_copy(update={"chunk": padre.model_copy(deep=True)})
                nuevo.chunk.metadata["hijos_recuperados"] = []
                por_id[padre.chunk_id] = nuevo
                salida.append(nuevo)
            por_id[padre.chunk_id].chunk.metadata["hijos_recuperados"].append(hijo.chunk_id)
        return salida, expansiones

    def ampliar_resultado(self, candidato, max_caracteres, vecinos=1):
        """Ventana literal para lectura, después de puntuar la unidad original."""
        ch = candidato.chunk
        doc = self.documentos.get(ch.doc_id)
        if doc is None:
            return candidato
        fuente = doc.texto_completo
        if (doc.version != ch.version or fuente[ch.offset_inicio:ch.offset_fin] != ch.texto_fuente or
                (getattr(doc, "structure_hash", None) is not None and
                 doc.structure_hash != ch.metadata.get("structure_hash"))):
            raise ValueError("contexto de resultado de otra versión o extracción")
        ini, fin = ch.offset_inicio, ch.offset_fin
        unidades = self._unidades.get(ch.doc_id, [])
        indices = [i for i, u in enumerate(unidades)
                   if u.offset_inicio < fin and ini < u.offset_fin]
        usados = []
        if indices:
            # Las unidades que contienen la coincidencia también se conservan:
            # en legacy una búsqueda puede haber encontrado solo media frase.
            cercanos = list(range(min(indices), max(indices) + 1))
            for borde, paso in ((min(indices) - 1, -1), (max(indices) + 1, 1)):
                for n in range(vecinos):
                    i = borde + paso * n
                    if (not 0 <= i < len(unidades) or list(unidades[i].seccion_path) != list(ch.seccion_path) or
                            getattr(unidades[i], "version", ch.version) != ch.version):
                        break
                    cercanos.append(i)
            for i in cercanos:
                u = unidades[i]
                if list(u.seccion_path) != list(ch.seccion_path):
                    continue
                ini, fin = min(ini, u.offset_inicio), max(fin, u.offset_fin)
                usados.append(getattr(u, "chunk_id", f"{u.offset_inicio}:{u.offset_fin}"))
        # Centrarse en la coincidencia; nunca añadir solo un prefijo que la pierda.
        deseado = (ini, fin)
        if fin - ini > max_caracteres:
            longitud = min(ch.offset_fin - ch.offset_inicio, max_caracteres)
            margen = (max_caracteres - longitud) // 2
            ini = max(ini, ch.offset_inicio - margen)
            fin = min(fin, ini + max_caracteres)
            ini = max(deseado[0], fin - max_caracteres)
        nuevo = ch.model_copy(deep=True)
        nuevo.texto_fuente = fuente[ini:fin]
        nuevo.offset_inicio, nuevo.offset_fin = ini, fin
        nuevo.metadata["ventana_resultado"] = {
            "coincidencia_inicio": max(ini, ch.offset_inicio),
            "coincidencia_fin": min(fin, ch.offset_fin),
            "unidades": usados, "truncado": (ini, fin) != deseado,
            "origen": "texto_canonico", "source_hash": getattr(doc, "source_hash",
                getattr(doc, "hash_documento", None))}
        if getattr(doc, "ruta_origen", None):
            nuevo.metadata["ventana_resultado"]["archivo_fuente"] = str(doc.ruta_origen).replace("\\", "/").rsplit("/", 1)[-1]
        return candidato.model_copy(update={"chunk": nuevo})


def envolver_contextos(recuperador):
    from ipsis.indice.manifiesto import cargar_manifiesto

    nombre = getattr(getattr(recuperador, "coleccion", None), "nombre", None)
    if not nombre:
        return recuperador
    manifiesto = cargar_manifiesto(nombre)
    if not manifiesto.preparacion:
        return recuperador
    padres, documentos = cargar_contextos(manifiesto, incluir_documentos=True)
    ampliado = RecuperadorConContextos(recuperador, padres, documentos)
    ampliado.preparacion_indice = dict(manifiesto.preparacion)
    return ampliado
