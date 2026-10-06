"""Selección de las oraciones (o filas de tabla) más pertinentes dentro de
un fragmento recuperado. Motivo: la
respuesta concatenaba los 3 chunks completos (~1.700 caracteres cada uno,
CH-F256) y la oración que respondía la pregunta podía quedar enterrada bajo
texto irrelevante del mismo chunk.

Determinista: cada unidad se puntúa con ``s_lex`` (BM25 de la unidad
normalizado, ``ipsis/lenguaje/lexico.py``) usando las estadísticas del índice y
el stemmer del idioma activo. Sin estadísticas del índice, se calculan sobre
las propias unidades del fragmento (tf-isf).

La selección no "redacta": solo deciden qué texto LITERAL
mostrar y qué recortar. La unidad elegida es siempre substring exacto del
chunk (y por transitividad del documento fuente) — invariante que aprovecha
``ipsis/ingesta/parsear.py`` (offsets exactos por bloque) y se verifica con test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ipsis.consulta.etapas.base import _Etapa
from ipsis.lenguaje.entidades import extraer_entidades
from ipsis.lenguaje.texto import dividir_oraciones, terminos

# Una "unidad" es una línea completa (fila de tabla, ya unida por
# `ipsis/ingesta/parsear.py::_fila_a_texto` con " | " entre celdas) o una oración
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
    ``ipsis/lenguaje/entidades.py``): para toda unidad ``u``,
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
    determinista de ``ipsis/lenguaje/entidades.py``, no substring ingenuo), al
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
    """``s_lex`` de cada unidad frente a la pregunta, en [0, 1]; si la pregunta
    tiene una intención (``ipsis.lenguaje.consultas``), la unidad que ya comparte
    tema con ella y contiene una de sus pistas sube (``peso_pista``)."""
    from ipsis.indice.estadisticas import EstadisticasLexicas
    from ipsis.lenguaje.consultas import BONO_PISTA, comprender, peso_pista, terminos_de_contenido
    from ipsis.lenguaje.entidades import idioma_activo
    from ipsis.lenguaje.lexico import s_lex

    if not unidades:
        return []
    paquete = idioma_activo()
    est = estadisticas or EstadisticasLexicas.construir([u.texto for u in unidades], paquete)
    tq = terminos_de_contenido(pregunta, paquete, est)
    comprension = comprender(pregunta, paquete)
    scores = []
    for u in unidades:
        score = s_lex(tq, terminos(u.texto, paquete), est)
        if score > 0:
            score *= 1 + BONO_PISTA * peso_pista(u.texto, comprension)
        scores.append(score)
    return scores


PESO_HEREDADO = 0.5


def _puntuar_turno(pregunta: str, unidades: list[Unidad], estadisticas=None,
                   pregunta_usuario: str | None = None) -> list[float]:
    """``_puntuar`` para un turno de seguimiento: si lo que el usuario escribió
    ahora («¿y qué cubre?») aparece en alguna unidad, eso pesa entero y la
    pregunta interpretada (con lo heredado, «garantía cafetera») la mitad:
    dentro de un pasaje manda lo propio, y entre pasajes parecidos de documentos
    distintos decide el contexto («pagan» en el reembolso, no en las facturas).
    Si lo propio no aparece («¿y con 90?»), se usa la interpretada."""
    if pregunta_usuario:
        propios = _puntuar(pregunta_usuario, unidades, estadisticas)
        if any(propios):
            interpretada = _puntuar(pregunta, unidades, estadisticas)
            return [p + PESO_HEREDADO * i for p, i in zip(propios, interpretada)]
    return _puntuar(pregunta, unidades, estadisticas)


def _es_salvedad(texto: str) -> bool:
    """Una unidad que matiza a la anterior: con un marcador de excepción, o que
    empieza con uno de condición («Si…», «Siempre que…»). Una condición de una
    sola palabra en medio de la frase («se», «caso») es demasiado común para contar."""
    from ipsis.lenguaje.entidades import idioma_activo, tiene_marcador

    paquete = idioma_activo()
    if paquete is None:
        return False
    if tiene_marcador(texto, paquete.marcadores.excepcion):
        return True
    inicio = texto.lstrip(" \t\n-•*(¿¡\"'«").lower()
    return any(inicio.startswith(m.lower() + " ") or (" " in m.strip() and tiene_marcador(texto, [m]))
               for m in paquete.marcadores.condicion if m.strip())


@dataclass
class ResultadoSeleccion:
    texto: str
    offset_inicio: int  # ABSOLUTO (documento) — ya sumado al offset del chunk
    offset_fin: int
    recortado: bool  # False si el chunk completo ya entraba en el límite
    score_ancla: float  # score de la unidad más pertinente del tramo -- para ORDENAR entre fragmentos
    tiene_entidad_pregunta: bool = False  # True si el ancla se forzó por contener una entidad literal de la pregunta
    seccion_path: list[str] | None = None  # la sección del tramo, si el chunk cruza de sección


def seleccionar_texto_pertinente(pregunta: str, texto_chunk: str, offset_chunk_inicio: int,
                                   limite_caracteres: int, estadisticas=None,
                                   entidades_pregunta: list[dict] | None = None,
                                   centrada: bool = False,
                                   secciones: list[tuple[int, int, list[str]]] | None = None,
                                   pregunta_usuario: str | None = None) -> ResultadoSeleccion:
    """Elige el tramo CONTIGUO más pertinente dentro de ``texto_chunk``
    (oraciones o filas de tabla completas, nunca cortadas a la mitad),
    hasta ``limite_caracteres``. ``score_ancla`` (máximo de sus unidades)
    permite comparar fragmentos entre sí más adelante.

    Algoritmo del ancla, en orden de prioridad (antes
    solo existía el paso 2, el score de similitud, que es ciego a
    entidades cortas como "3,9"):
      1. Si ``entidades_pregunta`` no es vacío y alguna unidad contiene
         LITERALMENTE una de esas entidades (``ipsis/lenguaje/entidades.py``,
         mismo criterio que la capa de premisa), esa unidad es el ancla --
         la coincidencia exacta de una entidad manda sobre cualquier score
         de similitud, léxica o densa.
      2. Si no, ancla en la unidad de mayor ``s_lex``.
    El tramo empieza en el ancla y suma las unidades siguientes mientras
    quepan en ``limite_caracteres``: la oración que responde va primero y el
    contexto después, nunca antes (ver docs/methodology/policy.md).

    ``centrada=True`` es para el lector QA, no para mostrar: agrega vecinos a
    ambos lados (primero el de mayor score; en empate, el de la izquierda),
    porque el modelo lee mejor con el contexto previo.

    ``secciones`` (offsets relativos a ``texto_chunk``): si el chunk cruza de
    sección, el tramo no sale de la sección de la oración ancla y
    ``seccion_path`` la nombra, para que la cita sea la correcta."""
    unidades_completas = dividir_en_unidades(texto_chunk)
    scores_completos = _puntuar_turno(pregunta, unidades_completas, estadisticas, pregunta_usuario)
    score_ancla_global = max(scores_completos) if scores_completos else 0.0

    valores_norm_entidad = {e["valor_norm"] for e in entidades_pregunta} if entidades_pregunta else set()
    indices_con_entidad_global = _unidades_con_entidad(unidades_completas, valores_norm_entidad) if unidades_completas else []

    unidades = unidades_completas
    if not unidades:
        recorte = texto_chunk[:limite_caracteres]
        return ResultadoSeleccion(texto=recorte, offset_inicio=offset_chunk_inicio,
                                   offset_fin=offset_chunk_inicio + len(recorte),
                                   recortado=len(recorte) < len(texto_chunk), score_ancla=0.0)

    scores = scores_completos
    # En un chunk que cruza de sección, una línea que no está en ninguna es un
    # título: puede quedar en el tramo, pero nunca es la respuesta.
    elegibles = [i for i in range(len(unidades))
                 if not secciones or any(ini <= unidades[i].offset_inicio and unidades[i].offset_fin <= fin
                                         for ini, fin, _ in secciones)] or list(range(len(unidades)))
    indices_con_entidad_global = [i for i in indices_con_entidad_global if i in elegibles]
    tiene_entidad = bool(indices_con_entidad_global)
    if tiene_entidad:
        # entre las unidades con coincidencia exacta, ancla en la de mejor
        # score (desempate determinista, no arbitrario).
        idx_ancla = max(indices_con_entidad_global, key=lambda i: scores[i])
    else:
        idx_ancla = max(elegibles, key=lambda i: scores[i])
    # Si el chunk cruza de sección, el tramo se queda en la del ancla.
    seccion_ancla, rango = None, None
    for ini_sec, fin_sec, ruta in secciones or []:
        if ini_sec <= unidades[idx_ancla].offset_inicio < fin_sec:
            seccion_ancla, rango = list(ruta), (ini_sec, fin_sec)
            break

    def en_rango(i: int) -> bool:
        return rango is None or (rango[0] <= unidades[i].offset_inicio and unidades[i].offset_fin <= rango[1])

    # La oración ancla va PRIMERA y el contexto solo se agrega a la derecha:
    # si se antepusiera contexto, otra cifra («5 días hábiles») podría parecer
    # la respuesta a «¿En cuántos días hábiles se paga el reembolso?».
    lo = hi = idx_ancla
    while True:
        vecinos = [i for i in ((lo - 1) if centrada else -1, hi + 1) if 0 <= i < len(unidades) and en_rango(i)]
        vecinos = [i for i in vecinos
                   if unidades[max(hi, i)].offset_fin - unidades[min(lo, i)].offset_inicio <= limite_caracteres]
        if not vecinos:
            break
        elegido = max(vecinos, key=lambda i: (scores[i], i < lo))
        lo, hi = min(lo, elegido), max(hi, elegido)

    # Lo que se muestra no corta la salvedad que matiza la respuesta: si la
    # unidad siguiente es una condición o excepción («salvo que…») y quedó
    # afuera solo por largo, entra igual, con hasta un 50 % de margen.
    if not centrada and hi + 1 < len(unidades) and en_rango(hi + 1) and _es_salvedad(unidades[hi + 1].texto):
        if unidades[hi + 1].offset_fin - unidades[lo].offset_inicio <= limite_caracteres * 1.5:
            hi += 1

    inicio, fin = unidades[lo].offset_inicio, unidades[hi].offset_fin
    return ResultadoSeleccion(
        texto=texto_chunk[inicio:fin],
        offset_inicio=offset_chunk_inicio + inicio,
        offset_fin=offset_chunk_inicio + fin,
        recortado=(inicio, fin) != (0, len(texto_chunk)),
        score_ancla=score_ancla_global,
        tiene_entidad_pregunta=tiene_entidad,
        seccion_path=seccion_ancla,
    )


def recortar_payload_a_texto_pertinente(payload: dict, pregunta: str, limite_caracteres: int,
                                          estadisticas=None,
                                          entidades_pregunta: list[dict] | None = None,
                                          pregunta_usuario: str | None = None) -> dict:
    """Devuelve una COPIA del payload de un chunk con ``texto``,
    ``offset_inicio`` y ``offset_fin`` reemplazados por el tramo pertinente
    seleccionado -- el resto de los campos (``doc_titulo``, ``seccion_path``,
    ``tiene_excepcion``, ``tiene_condicion``, ``chunk_id``, ``version``...)
    se conservan intactos para que la cita y los conectores de
    ``ipsis/consulta/etapas/redaccion.py::redactar`` sigan funcionando igual.

    ``entidades_pregunta``: si se entrega, prioriza la
    oración que contiene LITERALMENTE una de esas entidades como ancla,
    por sobre el score de similitud (ver ``seleccionar_texto_pertinente``)."""
    base = payload["offset_inicio"]
    secciones = [(s["inicio"] - base, s["fin"] - base, s["ruta"]) for s in payload.get("secciones") or []]
    resultado = seleccionar_texto_pertinente(
        pregunta, payload["texto"], base, limite_caracteres,
        estadisticas=estadisticas, entidades_pregunta=entidades_pregunta, secciones=secciones or None,
        pregunta_usuario=pregunta_usuario,
    )
    nuevo = dict(payload)
    if resultado.seccion_path is not None:
        nuevo["seccion_path"] = resultado.seccion_path  # la cita nombra la sección del tramo
    nuevo["texto"] = resultado.texto
    nuevo["offset_inicio"] = resultado.offset_inicio
    nuevo["offset_fin"] = resultado.offset_fin
    # score_ancla/tiene_entidad_pregunta NO son parte del esquema de
    # payload del chunk: son información de trabajo
    # interna para ordenar fragmentos por pertinencia global (ver
    # `ordenar_por_pertinencia_global`), nunca se exponen en el contrato
    # HTTP (ipsis/servicio/api.py arma `Fragmento` con campos explícitos, estas
    # claves extra se ignoran ahí sin problema).
    nuevo["_score_ancla"] = resultado.score_ancla
    nuevo["_tiene_entidad_pregunta"] = resultado.tiene_entidad_pregunta
    return nuevo


def quitar_tramos_repetidos(payloads: list[dict], scores: list[float]) -> tuple[list[dict], list[float]]:
    """Dos chunks que se solapan pueden dar el mismo tramo (o uno dentro del otro):
    se deja el primero, para no mostrar ni citar dos veces el mismo texto."""
    vistos: list[tuple[str, int, int, str]] = []
    salida_p, salida_s = [], []
    for payload, score in zip(payloads, scores, strict=True):
        doc, ini, fin, texto = payload.get("doc_id"), payload["offset_inicio"], payload["offset_fin"], payload["texto"]
        if any(d == doc and ((i <= ini and fin <= f and texto in tx) or (ini <= i and f <= fin and tx in texto))
               for d, i, f, tx in vistos):
            continue
        vistos.append((doc, ini, fin, texto))
        salida_p.append(payload)
        salida_s.append(score)
    return salida_p, salida_s


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


def oracion_ancla(pregunta: str, texto: str, estadisticas=None, pregunta_usuario: str | None = None) -> str:
    """Oración (o fila) de ``texto`` con mayor ``s_lex`` frente a la pregunta."""
    unidades = dividir_en_unidades(texto)
    if not unidades:
        return texto
    scores = _puntuar_turno(pregunta, unidades, estadisticas, pregunta_usuario)
    return unidades[max(range(len(unidades)), key=lambda i: scores[i])].texto


def _proximidad_del_foco(motor, ctx) -> None:
    """``s_foco`` y ``s_cov`` sobre la oración que responde.

    Un tramo correcto debe estar cerca de lo que se pregunta: «6 meses» en una
    oración sobre el filtro no responde «¿Cuánto dura la garantía?». Con lector,
    la evidencia ya es la oración de su tramo; sin lector, la evidencia es una
    ventana de contexto y se mide sobre su oración ancla (mayor ``s_lex``), no
    sobre la ventana entera, que casi siempre contiene los términos de foco.
    """
    if ctx.lexicas is None or not ctx.evidencias:
        return
    from ipsis.lenguaje.lexico import s_cov, s_foco

    obtener = getattr(motor.retriever, "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None
    if est is None or not hasattr(est, "idf"):
        return
    oracion = ctx.evidencias[0].texto
    if ctx.evidencia_lector is None:
        oracion = oracion_ancla(ctx.pregunta, oracion, est, ctx.pregunta_usuario or None)
    ctx.diagnostico["oracion_foco"] = oracion
    terminos_oracion = terminos(oracion, motor.idioma)
    ctx.lexicas = ctx.lexicas.model_copy(update={
        "s_foco": s_foco(ctx.terminos_foco, terminos_oracion),
        "s_cov": s_cov(ctx.terminos_pregunta, terminos_oracion, est),
    })
    if isinstance(ctx.diagnostico.get("senales_lexicas"), dict):
        presentes = set(terminos_oracion)
        superficie = getattr(est, "superficie", {})
        ctx.diagnostico["senales_lexicas"].update(
            s_foco=ctx.lexicas.s_foco, s_cov=ctx.lexicas.s_cov,
            # Qué términos foco explican s_foco: los de la pregunta que están (o no) en la oración.
            foco_encontrados=[superficie.get(t, t) for t in ctx.terminos_foco if t in presentes],
            foco_ausentes=[superficie.get(t, t) for t in ctx.terminos_foco if t not in presentes],
        )


class EtapaEvidencia(_Etapa):
    """Selecciona el tramo literal de cada candidato y verifica sus offsets."""

    nombre = "evidencia"

    def ejecutar(self, ctx) -> None:
        from ipsis.indice.payload import payload_desde_evidencia

        m = self.motor
        # Con lector, la evidencia es la oración que contiene su tramo.
        if ctx.evidencia_lector is not None:
            evidencias = [ctx.evidencia_lector]
        else:
            evidencias = m.extractor.extraer(ctx.consulta, ctx.candidatos)
        validas, errores = m.verificador.verificar(evidencias, ctx.candidatos)
        if not validas:
            ctx.diagnostico["advertencias"].extend(errores)
            ctx.resultado = m._abstener("guardia", ctx.confianza, ctx.latencia_ms(), diagnostico=ctx.diagnostico)
            return
        ctx.evidencias = evidencias
        ctx.diagnostico["evidencias"] = [e.model_dump(mode="python") for e in evidencias]
        _proximidad_del_foco(m, ctx)
        por_chunk = {c.chunk.chunk_id: c for c in ctx.candidatos}
        ctx.payloads = [payload_desde_evidencia(e, por_chunk[e.chunk_id].chunk) for e in evidencias]
        resolutor = getattr(m, "seguimiento", None)
        if resolutor is not None:
            # El turno siguiente puede seguir hablando de lo que mostraron estos fragmentos.
            raices = set()
            for e in evidencias[:1]:  # el que respondió, no los relacionados de otros temas
                raices.update(terminos(por_chunk[e.chunk_id].chunk.texto_fuente, m.idioma))
            resolutor.recordar_evidencia(ctx.id_sesion, raices)
