"""Estrategias de chunking sobre la salida de ``parsear.py``.

Todas las estrategias operan sobre la lista de :class:`~ingesta.parsear.Bloque`
de un :class:`~ingesta.parsear.DocumentoParseado` y devuelven una lista de
:class:`Chunk`, cada uno con offsets ``[offset_inicio, offset_fin)`` **exactos**
dentro de ``texto_completo`` del documento.

Invariante verificada por los tests (``tests/ingesta/test_chunking.py``): para cada
estrategia, concatenar los chunks en orden y comparar contra el texto de los
bloques de origen no debe perder ni duplicar caracteres del contenido
original (se permite colapsar separadores de bloque, nunca contenido).

Un token se aproxima aquí como ``len(texto.split())`` (conteo de palabras);
es una aproximación deliberada y documentada — no se usa un tokenizer de
subpalabras para mantener el módulo sin dependencias pesadas y 100%
determinista.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ipsis.ingesta.parsear import Bloque, DocumentoParseado


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    orden: int
    seccion_path: list[str]
    seccion_nivel: int
    tipo_contenido: str
    texto: str
    offset_inicio: int
    offset_fin: int
    estrategia: str
    bloques_origen: list[int] = field(default_factory=list)
    # Tramos (offset_inicio, offset_fin, seccion_path) de cada sección del chunk,
    # en offsets del documento. Un chunk puede cruzar de sección (se busca por
    # chunk); la cita usa la sección del tramo que se muestra.
    secciones: list[tuple[int, int, list[str]]] = field(default_factory=list)


def _secciones(bloques: list[Bloque], offset_fin: int) -> list[tuple[int, int, list[str]]]:
    tramos: list[tuple[int, int, list[str]]] = []
    for b in bloques:
        if tramos and tramos[-1][2] == b.seccion_path:
            tramos[-1] = (tramos[-1][0], b.offset_fin, tramos[-1][2])
        else:
            tramos.append((b.offset_inicio, b.offset_fin, list(b.seccion_path)))
    return [(ini, min(fin, offset_fin), ruta) for ini, fin, ruta in tramos]


def _n_tokens(texto: str) -> int:
    return len(texto.split())


def _construir_chunk(doc: DocumentoParseado, bloques: list[Bloque], orden: int, estrategia: str) -> Chunk:
    texto = doc.texto_completo[bloques[0].offset_inicio:bloques[-1].offset_fin]
    # recorta el separador final de bloque para no incluir un '\n' colgante
    texto_sin_sep = texto.rstrip("\n")
    offset_fin = bloques[0].offset_inicio + len(texto_sin_sep)
    seccion_path = bloques[0].seccion_path
    tipos = {b.tipo_contenido for b in bloques}
    tipo_contenido = "tabla" if tipos == {"tabla"} else ("titulo" if "titulo" in tipos and len(tipos) == 1 else "narrativo")
    return Chunk(
        chunk_id=f"{doc.doc_id}__c{orden:04d}",
        doc_id=doc.doc_id,
        orden=orden,
        seccion_path=seccion_path,
        seccion_nivel=bloques[0].seccion_nivel,
        tipo_contenido=tipo_contenido,
        texto=texto_sin_sep,
        offset_inicio=bloques[0].offset_inicio,
        offset_fin=offset_fin,
        estrategia=estrategia,
        bloques_origen=[b.indice for b in bloques],
        secciones=_secciones(bloques, offset_fin),
    )


def _bloques_contenido(doc: DocumentoParseado) -> list[Bloque]:
    """Bloques de contenido real (excluye títulos, que solo aportan seccion_path)."""
    return [b for b in doc.bloques if b.tipo_contenido != "titulo"]


# ---------------------------------------------------------------------------
# CH-F256 / CH-F512: tamaño fijo (en "tokens" ~ palabras), solape 15%
# ---------------------------------------------------------------------------

def chunking_tamano_fijo(doc: DocumentoParseado, tamano_tokens: int, solape_pct: float = 0.15) -> list[Chunk]:
    bloques = _bloques_contenido(doc)
    chunks: list[Chunk] = []
    orden = 0
    i = 0
    solape_tokens = max(1, int(tamano_tokens * solape_pct))
    while i < len(bloques):
        grupo: list[Bloque] = []
        tokens_acum = 0
        j = i
        while j < len(bloques) and tokens_acum < tamano_tokens:
            grupo.append(bloques[j])
            tokens_acum += _n_tokens(bloques[j].texto)
            j += 1
        if not grupo:
            break
        chunks.append(_construir_chunk(doc, grupo, orden, f"CH-F{tamano_tokens}"))
        orden += 1
        if j >= len(bloques):
            break
        # retrocede aproximadamente `solape_tokens` en términos de bloques
        tokens_retro = 0
        k = j - 1
        while k > i and tokens_retro < solape_tokens:
            tokens_retro += _n_tokens(bloques[k].texto)
            k -= 1
        i = max(i + 1, k + 1)
    return chunks


# ---------------------------------------------------------------------------
# CH-PAR: por párrafo, fusionando cortos (min 80, max 400 tokens)
# ---------------------------------------------------------------------------

def chunking_por_parrafo(doc: DocumentoParseado, min_tokens: int = 80, max_tokens: int = 400) -> list[Chunk]:
    bloques = _bloques_contenido(doc)
    chunks: list[Chunk] = []
    orden = 0
    grupo: list[Bloque] = []
    tokens_acum = 0

    def cerrar_grupo():
        nonlocal grupo, tokens_acum, orden
        if grupo:
            chunks.append(_construir_chunk(doc, grupo, orden, "CH-PAR"))
            orden += 1
        grupo = []
        tokens_acum = 0

    for b in bloques:
        nt = _n_tokens(b.texto)
        # si agregar este bloque excede el máximo y ya hay contenido mínimo, cierra antes
        if grupo and tokens_acum >= min_tokens and (tokens_acum + nt) > max_tokens:
            cerrar_grupo()
        # si el bloque no comparte seccion_path con el grupo actual, cierra (no mezcla secciones)
        if grupo and grupo[-1].seccion_path != b.seccion_path and tokens_acum >= min_tokens:
            cerrar_grupo()
        grupo.append(b)
        tokens_acum += nt
        if tokens_acum >= max_tokens:
            cerrar_grupo()
    cerrar_grupo()
    return chunks


# ---------------------------------------------------------------------------
# CH-SEC: por sección/encabezado, subdividiendo si es muy largo (max 400)
# ---------------------------------------------------------------------------

def chunking_por_seccion(doc: DocumentoParseado, max_tokens: int = 400) -> list[Chunk]:
    bloques = _bloques_contenido(doc)
    chunks: list[Chunk] = []
    orden = 0

    # agrupa bloques consecutivos con el mismo seccion_path
    secciones: list[list[Bloque]] = []
    actual: list[Bloque] = []
    path_actual = None
    for b in bloques:
        if path_actual is not None and b.seccion_path != path_actual:
            secciones.append(actual)
            actual = []
        actual.append(b)
        path_actual = b.seccion_path
    if actual:
        secciones.append(actual)

    for seccion_bloques in secciones:
        tokens_totales = sum(_n_tokens(b.texto) for b in seccion_bloques)
        if tokens_totales <= max_tokens:
            chunks.append(_construir_chunk(doc, seccion_bloques, orden, "CH-SEC"))
            orden += 1
            continue
        # subdivide la sección larga en sub-grupos <= max_tokens
        sub: list[Bloque] = []
        acumulado = 0
        for b in seccion_bloques:
            nt = _n_tokens(b.texto)
            if sub and acumulado + nt > max_tokens:
                chunks.append(_construir_chunk(doc, sub, orden, "CH-SEC"))
                orden += 1
                sub = []
                acumulado = 0
            sub.append(b)
            acumulado += nt
        if sub:
            chunks.append(_construir_chunk(doc, sub, orden, "CH-SEC"))
            orden += 1

    return chunks


# ---------------------------------------------------------------------------
# CH-ORA: oraciones agrupadas por similitud léxica simple (sin embeddings,
# para mantener el chunking determinista y barato). Se agrupan oraciones
# consecutivas mientras compartan al menos `umbral_jaccard` de palabras clave
# con la oración anterior; si cae por debajo, se corta.
# ---------------------------------------------------------------------------
def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def chunking_por_oraciones(doc: DocumentoParseado, umbral_jaccard: float = 0.08, max_tokens: int = 300) -> list[Chunk]:
    bloques = _bloques_contenido(doc)
    chunks: list[Chunk] = []
    orden = 0
    grupo: list[Bloque] = []
    tokens_acum = 0
    palabras_prev: set[str] | None = None

    def cerrar():
        nonlocal grupo, tokens_acum, orden
        if grupo:
            chunks.append(_construir_chunk(doc, grupo, orden, "CH-ORA"))
            orden += 1
        grupo = []
        tokens_acum = 0

    for b in bloques:
        palabras_bloque = set(w.lower() for w in b.texto.split())
        nt = _n_tokens(b.texto)
        corta = False
        if grupo:
            sim = _jaccard(palabras_prev or set(), palabras_bloque)
            if sim < umbral_jaccard or (tokens_acum + nt) > max_tokens or grupo[-1].seccion_path != b.seccion_path:
                corta = True
        if corta:
            cerrar()
        grupo.append(b)
        tokens_acum += nt
        palabras_prev = palabras_bloque
    cerrar()
    return chunks


ESTRATEGIAS = {
    "CH-F256": lambda doc: chunking_tamano_fijo(doc, 256),
    "CH-F512": lambda doc: chunking_tamano_fijo(doc, 512),
    "CH-PAR": lambda doc: chunking_por_parrafo(doc),
    "CH-SEC": lambda doc: chunking_por_seccion(doc),
    "CH-ORA": lambda doc: chunking_por_oraciones(doc),
}


def construir_texto_embebido(doc_titulo: str, seccion_path: list[str], texto: str, paquete=None) -> str:
    """Header contextual (sección 3.3, campo texto_embebido) en el idioma de
    ``paquete`` (sin paquete, en español, como antes)."""
    if paquete is None:
        cabecera, sin_seccion = "Documento: {documento} | Sección: {seccion}", "(sin sección)"
    else:
        cabecera, sin_seccion = paquete.mensajes.cabecera_embebido, paquete.mensajes.sin_seccion
    seccion_str = " > ".join(seccion_path) if seccion_path else sin_seccion
    return f"{cabecera.format(documento=doc_titulo, seccion=seccion_str)}\n{texto}"
