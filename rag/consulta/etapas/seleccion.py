"""Selección de las oraciones (o filas de tabla) más pertinentes dentro de
un fragmento recuperado. Motivo: la
respuesta concatenaba los 3 chunks completos (~1.700 caracteres cada uno,
CH-F256) y la oración que respondía la pregunta podía quedar enterrada bajo
texto irrelevante del mismo chunk.

Determinista: cada unidad se puntúa con ``s_lex`` (BM25 de la unidad
normalizado, ``rag/lenguaje/lexico.py``) usando las estadísticas del índice y
el stemmer del idioma activo. Sin estadísticas del índice, se calculan sobre
las propias unidades del fragmento (tf-isf).

La selección no "redacta": solo deciden qué texto LITERAL
mostrar y qué recortar. La unidad elegida es siempre substring exacto del
chunk (y por transitividad del documento fuente) — invariante que aprovecha
``rag/ingesta/parsear.py`` (offsets exactos por bloque) y se verifica con test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rag.consulta.etapas.base import _Etapa
from rag.lenguaje.entidades import extraer_entidades
from rag.lenguaje.texto import dividir_oraciones, terminos

# Una "unidad" es una línea completa (fila de tabla, ya unida por
# `rag/ingesta/parsear.py::_fila_a_texto` con " | " entre celdas) o una oración
# dentro de una línea narrativa. Nunca se parte una fila de tabla a la
# mitad: el marcador " | " es el MISMO que usa el parser para unir celdas,
# así que su presencia es una señal determinista de "esto es una fila", no
# una heurística inventada aquí.
_RE_LINEA = re.compile(r"[^\n]+")


@dataclass
class Unidad:
    texto: str
    offset_inicio: int  # relativo al texto del CHUNK (no del documento)
    offset_fin: int
    es_fila_tabla: bool


def dividir_en_unidades(texto_chunk: str) -> list[Unidad]:
    """Divide el texto de un chunk en líneas/filas y, dentro de cada línea
    narrativa, en oraciones — con offsets EXACTOS dentro de ``texto_chunk``.

    Invariante verificada por test (mismo criterio que
    ``rag/lenguaje/entidades.py``): para toda unidad ``u``,
    ``texto_chunk[u.offset_inicio:u.offset_fin] == u.texto``.
    """
    unidades: list[Unidad] = []
    for m_linea in _RE_LINEA.finditer(texto_chunk):
        linea = m_linea.group(0)
        es_fila = " | " in linea
        texto_linea_sin_espacios = linea.strip()
        if not texto_linea_sin_espacios:
            continue
        if es_fila:
            ini_rel = linea.index(texto_linea_sin_espacios)
            unidades.append(Unidad(
                texto=texto_linea_sin_espacios,
                offset_inicio=m_linea.start() + ini_rel,
                offset_fin=m_linea.start() + ini_rel + len(texto_linea_sin_espacios),
                es_fila_tabla=True,
            ))
            continue
        for ini, fin in dividir_oraciones(linea):
            unidades.append(Unidad(
                texto=linea[ini:fin],
                offset_inicio=m_linea.start() + ini,
                offset_fin=m_linea.start() + fin,
                es_fila_tabla=False,
            ))
    return unidades


def _unidades_con_entidad(unidades: list[Unidad], valores_norm_entidad: set[str]) -> list[int]:
    """Índices de las unidades que contienen, LITERALMENTE (mismo criterio
    determinista de ``rag/lenguaje/entidades.py``, no substring ingenuo), al
    menos una de las entidades de la pregunta. Caso real que motivó esto:
    "¿Qué pasa si saco un 3,9?" -- una cifra corta pesa poco en
    un puntaje léxico, así que el score no prioriza de forma confiable la
    oración "Reprobará asimismo con nota final 3,9..." frente a otras del
    mismo chunk o de otros fragmentos -- hace falta una señal exacta de
    entidad, no una de similitud."""
    if not valores_norm_entidad:
        return []
    indices = []
    for i, u in enumerate(unidades):
        valores_unidad = {e["valor_norm"] for e in extraer_entidades(u.texto)}
        if valores_unidad & valores_norm_entidad:
            indices.append(i)
    return indices


def _puntuar(pregunta: str, unidades: list[Unidad], estadisticas=None) -> list[float]:
    """``s_lex`` de cada unidad frente a la pregunta, en [0, 1]."""
    from rag.indice.estadisticas import EstadisticasLexicas
    from rag.lenguaje.entidades import idioma_activo
    from rag.lenguaje.lexico import s_lex, terminos_pregunta

    if not unidades:
        return []
    paquete = idioma_activo()
    est = estadisticas or EstadisticasLexicas.construir([u.texto for u in unidades], paquete)
    tq = terminos_pregunta(pregunta, paquete)
    return [s_lex(tq, terminos(u.texto, paquete), est) for u in unidades]


@dataclass
class ResultadoSeleccion:
    texto: str
    offset_inicio: int  # ABSOLUTO (documento) — ya sumado al offset del chunk
    offset_fin: int
    recortado: bool  # False si el chunk completo ya entraba en el límite
    score_ancla: float  # score de la unidad más pertinente del tramo -- para ORDENAR entre fragmentos
    tiene_entidad_pregunta: bool = False  # True si el ancla se forzó por contener una entidad literal de la pregunta


def seleccionar_texto_pertinente(pregunta: str, texto_chunk: str, offset_chunk_inicio: int,
                                   limite_caracteres: int, estadisticas=None,
                                   entidades_pregunta: list[dict] | None = None) -> ResultadoSeleccion:
    """Elige el tramo CONTIGUO más pertinente dentro de ``texto_chunk``
    (oraciones o filas de tabla completas, nunca cortadas a la mitad),
    hasta ``limite_caracteres``. Si el chunk completo ya entra en el
    límite, se devuelve completo (no hay nada que recortar) -- pero IGUAL
    se calcula ``score_ancla`` (máximo de sus unidades) para poder comparar
    fragmentos entre sí más adelante.

    Algoritmo del ancla, en orden de prioridad (antes
    solo existía el paso 2, el score de similitud, que es ciego a
    entidades cortas como "3,9"):
      1. Si ``entidades_pregunta`` no es vacío y alguna unidad contiene
         LITERALMENTE una de esas entidades (``rag/lenguaje/entidades.py``,
         mismo criterio que la capa de premisa), esa unidad es el ancla --
         la coincidencia exacta de una entidad manda sobre cualquier score
         de similitud, léxica o densa.
      2. Si no, ancla en la unidad de mayor ``s_lex``.
    Desde el ancla, se expande hacia los vecinos (antes/después) en orden
    de score decreciente mientras quepan en el presupuesto de caracteres --
    da contexto alrededor de la oración más pertinente en vez de
    devolverla aislada, sin salirse del límite."""
    unidades_completas = dividir_en_unidades(texto_chunk)
    scores_completos = _puntuar(pregunta, unidades_completas, estadisticas)
    score_ancla_global = max(scores_completos) if scores_completos else 0.0

    valores_norm_entidad = {e["valor_norm"] for e in entidades_pregunta} if entidades_pregunta else set()
    indices_con_entidad_global = _unidades_con_entidad(unidades_completas, valores_norm_entidad) if unidades_completas else []

    if len(texto_chunk) <= limite_caracteres:
        return ResultadoSeleccion(texto=texto_chunk, offset_inicio=offset_chunk_inicio,
                                   offset_fin=offset_chunk_inicio + len(texto_chunk), recortado=False,
                                   score_ancla=score_ancla_global,
                                   tiene_entidad_pregunta=bool(indices_con_entidad_global))

    unidades = unidades_completas
    if not unidades:
        recorte = texto_chunk[:limite_caracteres]
        return ResultadoSeleccion(texto=recorte, offset_inicio=offset_chunk_inicio,
                                   offset_fin=offset_chunk_inicio + len(recorte), recortado=True,
                                   score_ancla=0.0)

    scores = scores_completos
    indices_con_entidad = indices_con_entidad_global
    tiene_entidad = bool(indices_con_entidad)

    if tiene_entidad:
        # entre las unidades con coincidencia exacta, ancla en la de mejor
        # score (desempate determinista, no arbitrario).
        idx_ancla = max(indices_con_entidad, key=lambda i: scores[i])
    else:
        idx_ancla = max(range(len(unidades)), key=lambda i: scores[i])
    lo, hi = idx_ancla, idx_ancla
    largo = len(unidades[idx_ancla].texto)
    while True:
        opciones = []
        # Si el ancla se forzó por una entidad literal,
        # esa oración debe quedar PRIMERA en el texto mostrado -- no se
        # expande hacia atrás: la oración con la entidad debe ser la
        # primera, no "una de las primeras".
        # Sin esta restricción, el contexto previo podía anteponerse y
        # dejar la oración con "3,9" al final del fragmento.
        if lo - 1 >= 0 and not tiene_entidad:
            candidato = lo - 1
            nuevo_largo = largo + 1 + len(unidades[candidato].texto)
            opciones.append(("izq", candidato, nuevo_largo, scores[candidato]))
        if hi + 1 < len(unidades):
            candidato = hi + 1
            nuevo_largo = largo + 1 + len(unidades[candidato].texto)
            opciones.append(("der", candidato, nuevo_largo, scores[candidato]))
        opciones = [o for o in opciones if o[2] <= limite_caracteres]
        if not opciones:
            break
        # agrega primero el vecino con mejor score propio (más pertinente);
        # empate: prioriza el de la izquierda (contexto previo).
        opciones.sort(key=lambda o: -o[3])
        lado, idx, nuevo_largo, _ = opciones[0]
        if lado == "izq":
            lo = idx
        else:
            hi = idx
        largo = nuevo_largo

    texto_sel = texto_chunk[unidades[lo].offset_inicio:unidades[hi].offset_fin]
    return ResultadoSeleccion(
        texto=texto_sel,
        offset_inicio=offset_chunk_inicio + unidades[lo].offset_inicio,
        offset_fin=offset_chunk_inicio + unidades[hi].offset_fin,
        recortado=True,
        score_ancla=scores[idx_ancla],
        tiene_entidad_pregunta=tiene_entidad,
    )


def recortar_payload_a_texto_pertinente(payload: dict, pregunta: str, limite_caracteres: int,
                                          estadisticas=None,
                                          entidades_pregunta: list[dict] | None = None) -> dict:
    """Devuelve una COPIA del payload de un chunk con ``texto``,
    ``offset_inicio`` y ``offset_fin`` reemplazados por el tramo pertinente
    seleccionado -- el resto de los campos (``doc_titulo``, ``seccion_path``,
    ``tiene_excepcion``, ``tiene_condicion``, ``chunk_id``, ``version``...)
    se conservan intactos para que la cita y los conectores de
    ``rag/consulta/etapas/redaccion.py::redactar`` sigan funcionando igual.

    ``entidades_pregunta``: si se entrega, prioriza la
    oración que contiene LITERALMENTE una de esas entidades como ancla,
    por sobre el score de similitud (ver ``seleccionar_texto_pertinente``)."""
    resultado = seleccionar_texto_pertinente(
        pregunta, payload["texto"], payload["offset_inicio"], limite_caracteres,
        estadisticas=estadisticas, entidades_pregunta=entidades_pregunta,
    )
    nuevo = dict(payload)
    nuevo["texto"] = resultado.texto
    nuevo["offset_inicio"] = resultado.offset_inicio
    nuevo["offset_fin"] = resultado.offset_fin
    # score_ancla/tiene_entidad_pregunta NO son parte del esquema de
    # payload del chunk: son información de trabajo
    # interna para ordenar fragmentos por pertinencia global (ver
    # `ordenar_por_pertinencia_global`), nunca se exponen en el contrato
    # HTTP (rag/servicio/api.py arma `Fragmento` con campos explícitos, estas
    # claves extra se ignoran ahí sin problema).
    nuevo["_score_ancla"] = resultado.score_ancla
    nuevo["_tiene_entidad_pregunta"] = resultado.tiene_entidad_pregunta
    return nuevo


def ordenar_por_pertinencia_global(payloads_recortados: list[dict], scores_recuperacion: list[float]) -> tuple[list[dict], list[float]]:
    """Reordena los fragmentos ya
    recortados por dos claves, en este orden de prioridad:

      1. ``_tiene_entidad_pregunta``: un fragmento cuya oración
         ancla contiene LITERALMENTE una entidad de la pregunta va PRIMERO,
         sin importar el score -- una coincidencia exacta ("3,9", "Práctica
         II", un artículo) es más fuerte que cualquier similitud léxica o
         densa. Caso real que motivó esto: "¿Qué pasa si saco un 3,9?"
         mostraba primero la Tabla 6 (ponderaciones, score de similitud más
         alto) en vez del Artículo 20 (que contiene "3,9" literal).
      2. ``_score_ancla``: entre fragmentos empatados en el
         criterio anterior, el de mayor score de su propia oración ancla.

    Caso real que motivó el criterio 2: a "¿Cuántas semanas dura
    el modelo X100?" el fragmento con mejor score de
    RECUPERACIÓN traía como oración más relevante una mención lateral
    ("los artículos 13 y 14 describen las etapas..."), mientras que un
    fragmento con score de recuperación más bajo tenía la oración que
    responde directamente. Reordenar agrupa las citas (cada fragmento
    sigue siendo un bloque con su propia cita) sin mezclar oraciones
    sueltas de distintos fragmentos.

    ``scores_recuperacion`` (los scores de la búsqueda real, en el mismo
    orden que ``payloads_recortados``) se reordena en paralelo para que
    ``Fragmento.score`` en la respuesta HTTP siga reflejando el score de
    recuperación real de cada fragmento, no el de ordenamiento."""
    orden = sorted(range(len(payloads_recortados)),
                    key=lambda i: (not payloads_recortados[i].get("_tiene_entidad_pregunta", False),
                                    -payloads_recortados[i].get("_score_ancla", 0.0)))
    payloads_ordenados = [payloads_recortados[i] for i in orden]
    scores_ordenados = [scores_recuperacion[i] for i in orden]
    return payloads_ordenados, scores_ordenados


class EtapaEvidencia(_Etapa):
    """Selecciona el tramo literal de cada candidato y verifica sus offsets."""

    nombre = "evidencia"

    def ejecutar(self, ctx) -> None:
        from rag.indice.payload import payload_desde_evidencia

        m = self.motor
        evidencias = m.extractor.extraer(ctx.consulta, ctx.candidatos)
        validas, errores = m.verificador.verificar(evidencias, ctx.candidatos)
        if not validas:
            ctx.diagnostico["advertencias"].extend(errores)
            ctx.resultado = m._abstener("guardia", ctx.confianza, ctx.latencia_ms(), diagnostico=ctx.diagnostico)
            return
        ctx.evidencias = evidencias
        ctx.diagnostico["evidencias"] = [e.model_dump(mode="python") for e in evidencias]
        por_chunk = {c.chunk.chunk_id: c for c in ctx.candidatos}
        ctx.payloads = [payload_desde_evidencia(e, por_chunk[e.chunk_id].chunk) for e in evidencias]
