"""Índice del carril multimedia (plan multimedia, M1): las fichas de ``media/`` en una colección propia.

Cada ficha activa aporta una unidad (título, descripción y palabras clave) y cada capítulo otra (título de la ficha más
título y descripción del capítulo). Se indexan en una colección de Qdrant **separada** de la de documentos
(``…_v{n}__media``), con el mismo modelo denso y estadísticas léxicas propias, y con su propio manifiesto: el índice
de documentos, su manifiesto y su ``hash_corpus`` no cambian (ADR 0011).

Lo indexado y lo que se muestra es el texto que escribió una persona: nada se transcribe ni se analiza (ADR 0001).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from ipsis.configuracion import rutas
from ipsis.indice.manifiesto import ManifiestoIndice, cargar_manifiesto, guardar_manifiesto, hash_corpus
from ipsis.indice.qdrant import indexar_qdrant, nombre_coleccion_versionada, ruta_estadisticas
from ipsis.ingesta.fichas import Ficha, leer_fichas

SUFIJO_COLECCION = "media"


@dataclass
class ResumenMedia:
    nombre_coleccion: str = ""  # vacío si no se indexó nada (todas inválidas o retiradas)
    n_fichas: int = 0
    n_capitulos: int = 0
    errores: dict[str, list[str]] = field(default_factory=dict)  # id de ficha → mensajes


def nombre_coleccion_media(coleccion: str, modelo: str, version: int, sufijo: str | None = None) -> str:
    """Nombre de la colección del carril: el de documentos con el sufijo ``media`` (``…_v2__media``). Comparten
    versión, así que ``ipsis sync`` los renueva juntos y ``--prune`` borra las dos series."""
    return nombre_coleccion_versionada(coleccion, modelo, version, f"{sufijo}_{SUFIJO_COLECCION}" if sufijo
                                       else SUFIJO_COLECCION)


def es_coleccion_media(nombre: str) -> bool:
    """``True`` si ``nombre`` (de colección o de manifiesto) es del carril multimedia y no de documentos."""
    return re.search(rf"_v\d+__(?:.+_)?{SUFIJO_COLECCION}$", nombre) is not None


def huella_fichas(carpeta: str | Path = rutas.MEDIA) -> str | None:
    """Huella barata de ``media/*.yaml`` (nombre y bytes de cada archivo); ``None`` si no hay ninguno.

    Igual huella ⇒ mismo índice: no hace falta leer ni validar las fichas para saber si cambiaron.
    """
    base = Path(carpeta)
    archivos = sorted(base.glob("*.yaml")) if base.is_dir() else []
    if not archivos:
        return None
    digest = hashlib.sha256()
    for archivo in archivos:
        digest.update(archivo.name.encode("utf-8") + b"\0" + hashlib.sha256(archivo.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def unidades_de_fichas(fichas: list[Ficha]) -> list[dict]:
    """Un payload por ficha activa y uno por capítulo, en orden de ``id`` y de capítulo (determinista).

    ``texto`` es lo que se mostrará, literal; ``texto_embebido`` es lo que se vectoriza y busca. ``doc_id`` repite el
    ``media_id`` para los índices de payload que Qdrant crea por ese nombre.
    """
    unidades: list[dict] = []
    for ficha in sorted(fichas, key=lambda f: f.id):
        if not ficha.vigente:
            continue
        comun = {
            "media_id": ficha.id, "doc_id": ficha.id, "tipo_media": ficha.tipo, "titulo": ficha.titulo,
            "descripcion": ficha.descripcion, "url": ficha.url, "archivo": ficha.archivo,
            "palabras_clave": list(ficha.palabras_clave), "idioma": ficha.idioma, "version": ficha.version or "",
            "duracion_segundos": ficha.duracion, "vigente": True,
        }
        texto = f"{ficha.titulo}\n{ficha.descripcion}"
        embebido = ". ".join(parte for parte in (ficha.titulo, ficha.descripcion, ", ".join(ficha.palabras_clave)) if parte)
        unidades.append({**comun, "chunk_id": ficha.id, "tipo_unidad": "ficha", "capitulo": None,
                         "capitulo_titulo": None, "capitulo_descripcion": None, "inicio_segundos": None,
                         "texto": texto, "texto_embebido": embebido, "hash_texto": _hash(texto)})
        for n, capitulo in enumerate(ficha.capitulos, start=1):
            texto_cap = f"{capitulo.titulo}\n{capitulo.descripcion}".strip()
            embebido_cap = ". ".join(parte for parte in (ficha.titulo, capitulo.titulo, capitulo.descripcion) if parte)
            unidades.append({**comun, "chunk_id": f"{ficha.id}#{n}", "tipo_unidad": "capitulo", "capitulo": n,
                             "capitulo_titulo": capitulo.titulo, "capitulo_descripcion": capitulo.descripcion or None,
                             "inicio_segundos": capitulo.segundos, "texto": texto_cap,
                             "texto_embebido": embebido_cap, "hash_texto": _hash(texto_cap)})
    return unidades


def indexar_fichas(*, modelo: str, coleccion: str, qdrant_path: str, version_coleccion: int, codificador, client,
                   permitir_recrear: bool, sufijo_coleccion: str | None = None, paquete=None,
                   carpeta: str | Path = rutas.MEDIA) -> ResumenMedia | None:
    """Indexa las fichas válidas y activas en la colección del carril. ``None`` si ``media/`` no tiene fichas.

    Una ficha inválida se informa en ``ResumenMedia.errores`` y no impide indexar las demás; si ninguna es utilizable
    no se crea colección. Reutiliza el ``client`` y el ``codificador`` de la indexación de documentos: el Qdrant local
    toma un candado exclusivo de su carpeta y el modelo denso ya está cargado.
    """
    lectura = leer_fichas(carpeta)
    if not lectura.fichas and not lectura.errores:
        return None
    resumen = ResumenMedia(errores=lectura.errores)
    unidades = unidades_de_fichas(lectura.fichas)
    if not unidades:
        return resumen
    _client, _codificador, estadisticas, nombre = indexar_qdrant(
        unidades, modelo, coleccion, qdrant_path, usar_texto_embebido=True, codificador=codificador,
        n_version=version_coleccion, sufijo_coleccion=(f"{sufijo_coleccion}_{SUFIJO_COLECCION}" if sufijo_coleccion
                                                       else SUFIJO_COLECCION),
        client=client, permitir_recrear=permitir_recrear, paquete=paquete)
    huella = hash_corpus(unidades)
    estadisticas.hash_corpus = huella
    estadisticas.guardar(ruta_estadisticas(nombre))
    guardar_manifiesto(ManifiestoIndice(
        coleccion=nombre, modelo_denso=modelo, dimension=codificador.dimension, stemmer=estadisticas.stemmer,
        hash_corpus=huella, hash_archivos=huella_fichas(carpeta), n_chunks=len(unidades)))
    resumen.nombre_coleccion = nombre
    resumen.n_fichas = sum(1 for u in unidades if u["tipo_unidad"] == "ficha")
    resumen.n_capitulos = len(unidades) - resumen.n_fichas
    return resumen


def media_desactualizado(cfg_rec: dict, carpeta: str | Path = rutas.MEDIA, sufijo: str | None = None) -> bool:
    """``True`` si hay fichas activas y válidas que el índice del carril aún no refleja.

    Compara la huella de ``media/*.yaml`` con la del manifiesto de la colección vigente; sin manifiesto, está
    desactualizado. Sin fichas utilizables no hay nada que indexar: ``False`` (así una carpeta con solo fichas
    inválidas no hace reindexar en cada ``ipsis sync``).
    """
    huella = huella_fichas(carpeta)
    if huella is None or not any(f.vigente for f in leer_fichas(carpeta).fichas):
        return False
    nombre = nombre_coleccion_media(cfg_rec["coleccion_base"], cfg_rec["modelo"], cfg_rec["version_coleccion"], sufijo)
    try:
        return cargar_manifiesto(nombre).hash_archivos != huella
    except FileNotFoundError:
        return True


__all__ = ["ResumenMedia", "SUFIJO_COLECCION", "es_coleccion_media", "huella_fichas", "indexar_fichas",
           "media_desactualizado", "nombre_coleccion_media", "unidades_de_fichas"]
