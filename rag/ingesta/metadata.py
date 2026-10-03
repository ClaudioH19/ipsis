"""Metadata determinista + validaciones de ingesta (secciones 3.3 y 3.4).

Este módulo NO depende de ningún modelo para los campos deterministas
(entidades, tiene_excepcion, tiene_condicion, keywords por frecuencia).
La categoría se asigna con un clasificador de respaldo determinista
(coincidencia de palabras clave contra la descripción de cada categoría de
``taxonomia.yaml``) — documentado en el registro de decisiones de ESTADO.md
como una simplificación deliberada frente al "zero-shot por embeddings"
sugerido en la sección 2.3: en este dominio (17 categorías cerradas, corpus
pequeño) un clasificador léxico determinista es más auditable y no depende de
que un modelo de embeddings esté disponible offline. La categoría se marca
con ``origen.categoria = "keywords_v1"`` y NUNCA se usa como filtro duro salvo
que E1 confirme exactitud >= umbral_categoria_filtro_duro.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

from pathlib import Path

import yaml

from rag.configuracion import rutas
from rag.lenguaje.texto import tokenizar

from rag.lenguaje.entidades import extraer_entidades, idioma_activo, tiene_marcador
from rag.ingesta.chunking import Chunk
from rag.recursos import leer_plantilla

_STOPWORDS_ES = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por",
    "un", "para", "con", "no", "una", "su", "al", "lo", "como", "más", "o",
    "pero", "sus", "le", "ya", "este", "esta", "entre", "cuando", "muy", "sin",
    "sobre", "también", "me", "hasta", "hay", "donde", "quien", "desde", "todo",
    "durante", "cada", "cual", "les", "si", "así", "mismo", "aunque", "otro",
    "otra", "ser", "es", "son", "ha", "han", "será", "fue", "estar", "está",
    "e", "u", "cuyo", "cuya", "cualquier", "dicho", "dicha", "podrá", "deberá",
}


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


def _tokenizar(texto: str) -> list[str]:
    return [t for t in tokenizar(texto, normalizado=False) if len(t) >= 3 and t.isalpha()]


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
    palabras_texto = set(_tokenizar(texto)) - _STOPWORDS_ES

    mejor_cat = "otro"
    mejor_score = 0.0
    for cat in taxonomia.get("categorias", []):
        cid = cat["id"]
        if cid == "otro":
            continue
        desc_palabras = set(_tokenizar(cat.get("descripcion", "")))
        gatillo = {w.lower() for w in cat.get("palabras_gatillo", [])}
        solape_desc = len(palabras_texto & desc_palabras)
        solape_gatillo = len(palabras_texto & gatillo)
        score_bruto = solape_gatillo * 2 + solape_desc
        # normaliza a [0,1] con un techo razonable (evita 1.0 artificial con textos largos)
        score = min(1.0, score_bruto / 6.0)
        if score > mejor_score:
            mejor_score = score
            mejor_cat = cid

    umbral = taxonomia.get("umbral_categoria_filtro_duro", 0.95)
    # el umbral de la taxonomía rige el uso como filtro DURO (ver E1), no la asignación
    # de la etiqueta en sí; aquí solo degradamos a "otro" si no hubo señal mínima.
    if mejor_score == 0.0:
        return ResultadoCategoria("otro", 0.0)
    return ResultadoCategoria(mejor_cat, round(mejor_score, 3))


def extraer_keywords(texto: str, top_k: int = 5) -> list[str]:
    """Extracción de palabras clave por frecuencia (simplificación determinista
    y reproducible de YAKE/KeyBERT — documentada en ESTADO.md)."""
    palabras = [w for w in _tokenizar(texto) if w not in _STOPWORDS_ES]
    conteo = Counter(palabras)
    return [w for w, _ in conteo.most_common(top_k)]


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
    #    (se valida en E1, aquí solo se verifica consistencia score/categoria)
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
                       pipeline_version: str = "ingesta-0.1.0") -> dict:
    """Construye el payload completo de un chunk (esquema sección 3.3)."""
    entidades = extraer_entidades(chunk.texto)
    cat = clasificar_categoria(chunk.texto, taxonomia)
    paquete = idioma_activo()
    marcadores = paquete.marcadores if paquete is not None else None
    tiene_exc = tiene_marcador(chunk.texto, marcadores.excepcion if marcadores else [])
    tiene_cond = tiene_marcador(chunk.texto, marcadores.condicion if marcadores else [])
    keywords = extraer_keywords(chunk.texto)
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
