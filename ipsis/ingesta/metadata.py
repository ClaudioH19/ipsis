"""Metadata determinista y validaciones de ingesta.

Este módulo NO depende de ningún modelo para los campos deterministas
(entidades, tiene_excepcion, tiene_condicion, keywords por frecuencia).
La categoría se asigna con un clasificador léxico determinista
(coincidencia de palabras clave contra la descripción de cada categoría de
la sección ``taxonomia`` de ``configuracion/dominio.yaml``): es más auditable
que una clasificación por embeddings y no depende de un modelo. La categoría se
marca con ``origen.categoria = "keywords_v1"`` y NUNCA se usa como filtro duro
salvo que una evaluación confirme exactitud >= umbral_categoria_filtro_duro.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

from pathlib import Path

import yaml

from ipsis.configuracion import rutas
from ipsis.lenguaje.texto import terminos, tokenizar

from ipsis.lenguaje.entidades import extraer_entidades, idioma_activo, tiene_marcador
from ipsis.ingesta.chunking import Chunk
from ipsis.recursos import leer_plantilla

def cargar_taxonomia(ruta: str = rutas.DOMINIO) -> dict:
    """Taxonomía del proyecto: sección ``taxonomia`` de ``configuracion/dominio.yaml``.

    Si el archivo o la sección faltan, usa la taxonomía genérica de la
    plantilla. ``id: otro`` es obligatorio: ``clasificar_categoria`` degrada a
    esa categoría y ``validar_chunk`` rechaza cualquier categoría no declarada.
    """
    p = Path(ruta)
    datos = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}
    if datos.get("taxonomia"):
        return datos["taxonomia"]
    plantilla = yaml.safe_load(leer_plantilla("dominio.yaml"))
    return plantilla["taxonomia"]


@dataclass
class ResultadoCategoria:
    categoria: str
    score: float
    origen: str = "keywords_v1"


def _terminos_con_superficie(texto: str) -> list[tuple[str, str]]:
    """Pares (término, forma original) sin stopwords, cifras ni palabras cortas."""
    paquete = idioma_activo()
    stop = set(terminos(" ".join(paquete.stopwords), paquete)) if paquete is not None else set()
    pares = zip(terminos(texto, paquete), tokenizar(texto, normalizado=False))
    return [(t, f) for t, f in pares if t not in stop and len(f) >= 3 and f.isalpha()]


def _terminos(texto: str) -> set[str]:
    return {t for t, _ in _terminos_con_superficie(texto)}


def clasificar_categoria(texto: str, taxonomia: dict) -> ResultadoCategoria:
    """Clasificador léxico determinista: puntúa cada categoría por solape de
    palabras entre el texto del chunk y la descripción de la categoría, más
    las palabras gatillo de esa categoría.

    Las palabras gatillo viven en
    ``configuracion/dominio.yaml::taxonomia.categorias[].palabras_gatillo`` -- antes eran
    un diccionario ``GATILLOS`` fijo en este módulo, lo que acoplaba el
    núcleo a un dominio particular. El YAML de categorías es
    configuración por dominio (categorías, descripciones): las palabras
    configuración por dominio y las palabras gatillo se declaran ahí mismo.
    """
    palabras_texto = _terminos(texto)

    mejor_cat = "otro"
    mejor_score = 0.0
    for cat in taxonomia.get("categorias", []):
        cid = cat["id"]
        if cid == "otro":
            continue
        desc_palabras = _terminos(cat.get("descripcion", ""))
        gatillo = _terminos(" ".join(cat.get("palabras_gatillo", [])))
        solape_desc = len(palabras_texto & desc_palabras)
        solape_gatillo = len(palabras_texto & gatillo)
        score_bruto = solape_gatillo * 2 + solape_desc
        # normaliza a [0,1] con un techo razonable (evita 1.0 artificial con textos largos)
        score = min(1.0, score_bruto / 6.0)
        if score > mejor_score:
            mejor_score = score
            mejor_cat = cid

    umbral = taxonomia.get("umbral_categoria_filtro_duro", 0.95)
    # el umbral de la taxonomía rige el uso como filtro DURO, no la asignación
    # de la etiqueta en sí; aquí solo degradamos a "otro" si no hubo señal mínima.
    if mejor_score == 0.0:
        return ResultadoCategoria("otro", 0.0)
    return ResultadoCategoria(mejor_cat, round(mejor_score, 3))


def extraer_keywords(texto: str, top_k: int = 5, estadisticas=None) -> list[str]:
    """Palabras clave del texto: mayor TF-IDF (o frecuencia sin estadísticas).

    Devuelve la forma original más frecuente de cada término (con tildes).
    Los empates se resuelven por orden alfabético del término.
    """
    pares = _terminos_con_superficie(texto)
    tf = Counter(t for t, _ in pares)
    formas: dict[str, Counter] = {}
    for t, f in pares:
        formas.setdefault(t, Counter())[f] += 1
    idf = estadisticas.idf if estadisticas is not None else (lambda _t: 1.0)
    orden = sorted(tf, key=lambda t: (-tf[t] * idf(t), t))[:top_k]
    return [max(formas[t].items(), key=lambda par: (par[1], par[0]))[0] for t in orden]


@dataclass
class ErrorValidacion:
    chunk_id: str
    campo: str
    detalle: str


def validar_chunk(chunk_payload: dict, taxonomia: dict) -> list[ErrorValidacion]:
    """Reglas de validación de ingesta. Devuelve lista de errores
    (vacía si el chunk es válido)."""
    errores: list[ErrorValidacion] = []
    texto = chunk_payload["texto"]
    cid = chunk_payload["chunk_id"]

    # 1) toda entidad debe encontrarse literalmente en texto (offset válido)
    for ent in chunk_payload.get("entidades", []):
        offset = ent["offset"]
        frag = texto[offset:offset + len(ent["texto"])]
        if frag != ent["texto"]:
            errores.append(ErrorValidacion(cid, "entidades", f"offset inválido para {ent!r}"))

    # 2) categoria ∈ taxonomía
    cats_validas = {c["id"] for c in taxonomia.get("categorias", [])}
    if chunk_payload.get("categoria") not in cats_validas:
        errores.append(ErrorValidacion(cid, "categoria", f"{chunk_payload.get('categoria')!r} no está en la taxonomía"))

    # 3) si score < umbral, debe haberse degradado a "otro" para uso como filtro duro
    #    (la exactitud se mide aparte; aquí solo se verifica consistencia score/categoria)
    score = chunk_payload.get("categoria_score", 0.0)
    if chunk_payload.get("categoria") != "otro" and score == 0.0:
        errores.append(ErrorValidacion(cid, "categoria_score", "score 0.0 con categoría distinta de 'otro'"))

    # 4) offsets del chunk deben ser coherentes (fin > inicio)
    if chunk_payload["offset_fin"] <= chunk_payload["offset_inicio"]:
        errores.append(ErrorValidacion(cid, "offsets", "offset_fin <= offset_inicio"))

    # 5) hash_texto coherente con el texto
    hash_calc = "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()
    if chunk_payload.get("hash_texto") != hash_calc:
        errores.append(ErrorValidacion(cid, "hash_texto", "hash no coincide con el texto"))

    return errores


def construir_payload(chunk: Chunk, doc_titulo: str, version: str, vigente: bool,
                       taxonomia: dict, texto_embebido: str,
                       pipeline_version: str = "ingesta-0.1.0", estadisticas=None) -> dict:
    """Construye el payload completo de un chunk (esquema sección 3.3)."""
    entidades = extraer_entidades(chunk.texto)
    cat = clasificar_categoria(chunk.texto, taxonomia)
    paquete = idioma_activo()
    marcadores = paquete.marcadores if paquete is not None else None
    tiene_exc = tiene_marcador(chunk.texto, marcadores.excepcion if marcadores else [])
    tiene_cond = tiene_marcador(chunk.texto, marcadores.condicion if marcadores else [])
    keywords = extraer_keywords(chunk.texto, estadisticas=estadisticas)
    hash_texto = "sha256:" + hashlib.sha256(chunk.texto.encode("utf-8")).hexdigest()

    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "doc_titulo": doc_titulo,
        "version": version,
        "vigente": vigente,
        "seccion_path": chunk.seccion_path,
        "seccion_nivel": chunk.seccion_nivel,
        "orden": chunk.orden,
        "offset_inicio": chunk.offset_inicio,
        "offset_fin": chunk.offset_fin,
        "texto": chunk.texto,
        "texto_embebido": texto_embebido,
        "hash_texto": hash_texto,
        "categoria": cat.categoria,
        "categoria_score": cat.score,
        "tipo_contenido": chunk.tipo_contenido,
        "tiene_excepcion": tiene_exc,
        "tiene_condicion": tiene_cond,
        "entidades": entidades,
        "keywords": keywords,
        "descripcion_libre": None,  # FASE 4 — reservado para descripcion_llm.py (desactivado)
        "origen": {
            "estructural": "parser",
            "entidades": "regex",
            "categoria": cat.origen,
            "descripcion_libre": None,
        },
        "pipeline_version": pipeline_version,
        "estrategia_chunking": chunk.estrategia,
    }
