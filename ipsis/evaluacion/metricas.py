"""Métricas comparables para bancos de evaluación versionados."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ipsis.evaluacion.banco import BancoEvaluacion, CasoEvaluacion
from ipsis.nucleo.esquemas import ChunkRecord, EvidenceSpan

CRITERIO_RESPUESTA = "respuesta_completa_v2"
CRITERIO_LEGADO = "tramo_o_respuesta_v1"


class SenalesObservadas(BaseModel):
    """Señales con que decidió la política (``diagnostico.senales_politica``).

    Son los valores que usó, no recalculados: ``s_ret`` ya normalizado con el
    piso de coseno y ``s_foco``/``s_cov`` neutros (1 y 0) si la etapa no los
    midió. ``None`` = no aplica en ese perfil (sin reranker no hay ``s_rr``;
    sin lector no hay ``s_qa``). ``s_lex`` viene de las señales léxicas.
    """

    model_config = ConfigDict(extra="forbid")

    s_ret: float | None = None
    s_oov: float | None = None
    s_foco: float | None = None
    s_cov: float | None = None
    s_lex: float | None = None
    acuerdo: float | None = None
    s_rr: float | None = None
    s_qa: float | None = None
    dominio: float | None = None
    coloquial: bool | None = None  # la pregunta está escrita de manera coloquial

    @classmethod
    def desde_diagnostico(cls, diagnostico: dict) -> "SenalesObservadas | None":
        """``None`` si la política no llegó a decidir (p. ej. conversacional)."""
        politica = diagnostico.get("senales_politica")
        if not politica:
            return None
        lexicas = diagnostico.get("senales_lexicas") or {}
        campos = set(cls.model_fields) - {"s_lex"}
        return cls(**{k: politica.get(k) for k in campos}, s_lex=lexicas.get("s_lex"))


class ObservacionEvaluacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caso_id: str
    backend: str
    estado: str
    respuesta: str = ""
    candidatos: list[ChunkRecord] = Field(default_factory=list)
    evidencias: list[EvidenceSpan] = Field(default_factory=list)
    latencia_ms: int = Field(default=0, ge=0)
    etapas_ms: dict[str, int] = Field(default_factory=dict)
    confianza_top1: float = 0.0
    metodo_confianza: str | None = None
    # Auditoría de la decisión: pregunta → señales → regla → estado.
    idioma: str | None = None
    regla: str | None = None
    senales: SenalesObservadas | None = None
    respuesta_exacta: str | None = None  # tramo del lector, solo en respuesta directa


class ResumenGrupo(BaseModel):
    n: int
    exactitud_estado: float
    recall_at_k: float
    tasa_falsos_ok: float


class ReporteMetricas(BaseModel):
    schema_version: int = 1
    criterio_respuesta: str = CRITERIO_LEGADO
    dataset_id: str
    dataset_version: str
    k: int
    n_casos: int
    recall_at_k: float
    mrr: float
    tasa_falsos_ok: float
    precision_abstencion: float
    exactitud_estado: float
    exactitud_literal: float
    exactitud_tramo_qa: float | None = None
    exactitud_offsets: float
    tasa_respuestas_excesivas: float
    distribucion_estados: dict[str, int]
    latencia_media_ms: float
    latencia_p95_ms: float
    latencia_etapas_media_ms: dict[str, float]
    por_backend: dict[str, ResumenGrupo]
    por_categoria: dict[str, ResumenGrupo]
    guardia_falsos_ok: bool
    guardia_respuestas: bool | None = None
    # Cobertura y riesgo por grupo, idioma y caso (P10.1). Opcional para leer
    # artefactos anteriores.
    cobertura: "ReporteCobertura | None" = None


class ArtefactoEvaluacion(BaseModel):
    schema_version: int = 1
    backend: str
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    configuracion_sha256: str
    configuracion: dict[str, Any]
    indice: dict[str, Any]
    reporte: ReporteMetricas
    observaciones: list[ObservacionEvaluacion] = Field(default_factory=list)
    tono: str | None = None  # tono de las respuestas (no cambia estados ni literalidad)


ESTADOS_ABSTENCION = {"sin_respuesta", "fuera_dominio", "necesita_aclaracion"}
ESTADOS_OK = {"respuesta_directa", "respuesta_parcial"}


def _solapa(chunk: ChunkRecord, caso: CasoEvaluacion) -> bool:
    return any(
        chunk.doc_id == evidencia.doc_id
        and chunk.offset_inicio < evidencia.offset_fin
        and chunk.offset_fin > evidencia.offset_inicio
        for evidencia in caso.evidencias
    )


def _rango_acierto(caso: CasoEvaluacion, observacion: ObservacionEvaluacion, k: int) -> int | None:
    for rango, chunk in enumerate(observacion.candidatos[:k], start=1):
        if _solapa(chunk, caso):
            return rango
    return None


def _percentil_95(valores: list[int]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return float(ordenados[max(0, math.ceil(0.95 * len(ordenados)) - 1)])


def _resumen_grupo(pares: list[tuple[CasoEvaluacion, ObservacionEvaluacion]], k: int) -> ResumenGrupo:
    respondibles = [(c, o) for c, o in pares if c.respondible]
    no_respondibles = [(c, o) for c, o in pares if es_no_respondible(c)]
    aciertos = sum(_rango_acierto(c, o, k) is not None for c, o in respondibles)
    falsos_ok = sum(o.estado in ESTADOS_OK for _c, o in no_respondibles)
    return ResumenGrupo(
        n=len(pares),
        exactitud_estado=(sum(c.estado_esperado == o.estado for c, o in pares) / len(pares) if pares else 0.0),
        recall_at_k=(aciertos / len(respondibles) if respondibles else 0.0),
        tasa_falsos_ok=(falsos_ok / len(no_respondibles) if no_respondibles else 0.0),
    )


def evaluar_observaciones(
    banco: BancoEvaluacion,
    observaciones: list[ObservacionEvaluacion],
    documentos: dict[str, str],
    *,
    k: int = 3,
    limite_respuesta_chars: int = 500,
) -> ReporteMetricas:
    if k < 1 or limite_respuesta_chars < 1:
        raise ValueError("k y limite_respuesta_chars deben ser positivos")
    por_id = {observacion.caso_id: observacion for observacion in observaciones}
    if len(por_id) != len(observaciones):
        raise ValueError("hay observaciones duplicadas")
    ids_esperados = {caso.id for caso in banco.casos}
    if set(por_id) != ids_esperados:
        raise ValueError("las observaciones no coinciden exactamente con los casos del banco")
    pares = [(caso, por_id[caso.id]) for caso in banco.casos]
    respondibles = [(c, o) for c, o in pares if c.respondible]
    no_respondibles = [(c, o) for c, o in pares if es_no_respondible(c)]
    rangos = [_rango_acierto(c, o, k) for c, o in respondibles]
    falsos_ok = sum(o.estado in ESTADOS_OK for _c, o in no_respondibles)
    abstenciones = [(c, o) for c, o in pares if o.estado in ESTADOS_ABSTENCION]
    abstenciones_correctas = sum(not c.respondible for c, _o in abstenciones)
    literales = sum(o.estado in ESTADOS_OK and muestra_respuesta_literal(c, o) for c, o in respondibles)
    tramos = [muestra_tramo_literal(c, o) for c, o in respondibles
              if o.estado in ESTADOS_OK and o.respuesta_exacta is not None]
    evidencias = [e for _c, o in pares for e in o.evidencias]
    offsets_validos = sum(
        evidencia.doc_id in documentos
        and documentos[evidencia.doc_id][evidencia.offset_inicio:evidencia.offset_fin] == evidencia.texto
        for evidencia in evidencias
    )
    respuestas = [o for _c, o in pares if o.estado in ESTADOS_OK | {"relacionado"}]
    excesivas = sum(len(o.respuesta) > limite_respuesta_chars for o in respuestas)
    latencias = [o.latencia_ms for _c, o in pares]
    etapas: dict[str, list[int]] = defaultdict(list)
    for _caso, observacion in pares:
        for nombre, valor in observacion.etapas_ms.items():
            etapas[nombre].append(valor)
    grupos_backend: dict[str, list[tuple[CasoEvaluacion, ObservacionEvaluacion]]] = defaultdict(list)
    grupos_categoria: dict[str, list[tuple[CasoEvaluacion, ObservacionEvaluacion]]] = defaultdict(list)
    for caso, observacion in pares:
        grupos_backend[observacion.backend].append((caso, observacion))
        grupos_categoria[caso.categoria.value].append((caso, observacion))

    tasa_falsos_ok = falsos_ok / len(no_respondibles) if no_respondibles else 0.0
    cobertura = reporte_cobertura(pares)
    return ReporteMetricas(
        schema_version=2,
        criterio_respuesta=CRITERIO_RESPUESTA,
        dataset_id=banco.manifiesto.dataset_id,
        dataset_version=banco.manifiesto.dataset_version,
        k=k,
        n_casos=len(pares),
        recall_at_k=sum(rango is not None for rango in rangos) / len(rangos) if rangos else 0.0,
        mrr=sum(1.0 / rango for rango in rangos if rango is not None) / len(rangos) if rangos else 0.0,
        tasa_falsos_ok=tasa_falsos_ok,
        precision_abstencion=(abstenciones_correctas / len(abstenciones) if abstenciones else 0.0),
        exactitud_estado=sum(c.estado_esperado == o.estado for c, o in pares) / len(pares),
        exactitud_literal=literales / len(respondibles) if respondibles else 0.0,
        exactitud_tramo_qa=sum(tramos) / len(tramos) if tramos else None,
        exactitud_offsets=offsets_validos / len(evidencias) if evidencias else 1.0,
        tasa_respuestas_excesivas=excesivas / len(respuestas) if respuestas else 0.0,
        distribucion_estados=dict(sorted(Counter(o.estado for _c, o in pares).items())),
        latencia_media_ms=mean(latencias) if latencias else 0.0,
        latencia_p95_ms=_percentil_95(latencias),
        latencia_etapas_media_ms={nombre: mean(valores) for nombre, valores in sorted(etapas.items())},
        por_backend={nombre: _resumen_grupo(grupo, k) for nombre, grupo in sorted(grupos_backend.items())},
        por_categoria={nombre: _resumen_grupo(grupo, k) for nombre, grupo in sorted(grupos_categoria.items())},
        guardia_falsos_ok=tasa_falsos_ok == 0.0,
        guardia_respuestas=cobertura.riesgo_aceptadas.x == 0,
        cobertura=cobertura,
    )


# ---------------------------------------------------------------------------
# Cota de riesgo (Clopper-Pearson) y tamaño de muestra. Funciones puras.
# ---------------------------------------------------------------------------
def _cdf_binomial(x: int, n: int, p: float) -> float:
    """P(X ≤ x) para X ~ Binomial(n, p), sumando en el espacio de logaritmos."""
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if x >= n else 0.0
    log_p, log_q = math.log(p), math.log1p(-p)
    return min(1.0, sum(math.exp(math.log(math.comb(n, k)) + k * log_p + (n - k) * log_q) for k in range(x + 1)))


def cota_superior_clopper_pearson(x: int, n: int, confianza: float = 0.95) -> float:
    """Cota superior unilateral exacta de una proporción binomial.

    Devuelve el ``p`` tal que ``P(X ≤ x | n, p) = 1 − confianza``: con ``x``
    errores en ``n`` observaciones, la tasa real de error es ≤ ``p`` con la
    confianza pedida. Con ``x = n`` la cota es 1. Sin observaciones (``n = 0``)
    no hay garantía posible: es un error, no una cota de 0.
    """
    if isinstance(x, bool) or isinstance(n, bool) or not isinstance(x, int) or not isinstance(n, int):
        raise TypeError("x y n deben ser enteros")
    if n <= 0:
        raise ValueError("sin observaciones (n = 0) no hay cota de riesgo")
    if not 0 <= x <= n:
        raise ValueError(f"x debe estar entre 0 y n (x={x}, n={n})")
    if not 0.0 < confianza < 1.0:
        raise ValueError(f"la confianza debe estar en (0, 1) (confianza={confianza})")
    if x == n:
        return 1.0
    objetivo = 1.0 - confianza
    bajo, alto = x / n, 1.0  # la CDF baja con p: en x/n vale > objetivo, en 1 vale 0
    for _ in range(200):
        medio = (bajo + alto) / 2
        if _cdf_binomial(x, n, medio) > objetivo:
            bajo = medio
        else:
            alto = medio
        if alto - bajo < 1e-12:
            break
    return alto


def n_minimo(errores: int, alfa: float, confianza: float = 0.95, limite: int = 1_000_000) -> int:
    """Menor ``n`` cuya cota superior con ``errores`` errores es ≤ ``alfa``.

    Es la cantidad de observaciones relevantes (p. ej. respuestas aceptadas)
    que hace falta para certificar ``alfa`` si se observan esos errores.
    """
    if not 0.0 < alfa < 1.0:
        raise ValueError(f"alfa debe estar en (0, 1) (alfa={alfa})")
    if errores < 0:
        raise ValueError("errores no puede ser negativo")
    n = errores + 1
    while cota_superior_clopper_pearson(errores, n, confianza) > alfa:
        n += 1
        if n > limite:
            raise ValueError(f"no se alcanza alfa={alfa} con menos de {limite} observaciones")
    return n


# ---------------------------------------------------------------------------
# Cobertura y riesgo por grupo, idioma y caso. Funciones puras sobre
# observaciones ya producidas: sin modelos, sin red.
# ---------------------------------------------------------------------------
GRUPOS = ("exacta", "parafrasis", "trampa_mismo_tema", "sin_respuesta", "fuera_de_dominio", "premisa_falsa",
          "ambigua", "conversacional")


def grupo_de(caso: CasoEvaluacion) -> str:
    """Grupo de evaluación: la categoría, salvo trampas y fuera de dominio,
    que se separan de las demás sin respuesta."""
    if caso.subtipo == "trampa_mismo_tema":
        return "trampa_mismo_tema"
    if caso.estado_esperado == "fuera_dominio":
        return "fuera_de_dominio"
    return caso.categoria.value


def es_no_respondible(caso: CasoEvaluacion) -> bool:
    """Casos donde una respuesta directa es un error (falso ok): todo lo no
    respondible salvo las conversacionales, que miden otra conducta."""
    return not caso.respondible and caso.categoria.value != "conversacional"


def muestra_respuesta_literal(caso: CasoEvaluacion, observacion: ObservacionEvaluacion) -> bool:
    """Mismo criterio en todos los perfiles: literal en la respuesta publicada
    y en evidencia del documento/rango esperado. Una cita escondida no basta.

    Es una comprobación literal del golden, no una prueba semántica general.
    El resaltado QA se evalúa aparte mediante ``muestra_tramo_literal``.
    """
    return bool(caso.respuesta_literal) and caso.respuesta_literal in observacion.respuesta and any(
        caso.respuesta_literal in evidencia.texto and any(
            evidencia.doc_id == esperada.doc_id
            and evidencia.offset_inicio < esperada.offset_fin
            and evidencia.offset_fin > esperada.offset_inicio
            for esperada in caso.evidencias
        ) for evidencia in observacion.evidencias
    )


def muestra_tramo_literal(caso: CasoEvaluacion, observacion: ObservacionEvaluacion) -> bool | None:
    """Cumplimiento del literal esperado en QA; None si no hay tramo QA."""
    if observacion.respuesta_exacta is None:
        return None
    return bool(caso.respuesta_literal) and caso.respuesta_literal in observacion.respuesta_exacta


class FilaCaso(BaseModel):
    """Vista inspeccionable de un caso: lo esperado, lo obtenido y por qué."""

    caso_id: str
    idioma: str | None
    split: str
    grupo: str
    subtipo: str | None
    par: str | None
    pregunta: str
    respondible: bool
    estado_esperado: str
    estado: str
    directa: bool
    relacionado: bool
    abstiene: bool
    falso_ok: bool
    directa_sin_literal: bool
    tramo_qa_sin_literal: bool | None = None
    regla: str | None
    senales: SenalesObservadas | None
    respuesta_literal_esperada: str | None
    respuesta_exacta: str | None
    respuesta_completa: str | None = None
    evidencia: str | None


def filas_de_casos(pares: list[tuple[CasoEvaluacion, ObservacionEvaluacion]]) -> list[FilaCaso]:
    filas = []
    for caso, obs in pares:
        directa = obs.estado in ESTADOS_OK
        filas.append(FilaCaso(
            caso_id=caso.id, idioma=obs.idioma, split=caso.split, grupo=grupo_de(caso), subtipo=caso.subtipo,
            par=caso.par, pregunta=caso.pregunta, respondible=caso.respondible,
            estado_esperado=caso.estado_esperado, estado=obs.estado, directa=directa,
            relacionado=obs.estado == "relacionado",
            abstiene=not directa and obs.estado not in {"relacionado", "conversacional"},
            falso_ok=directa and es_no_respondible(caso),
            directa_sin_literal=directa and caso.respondible and not muestra_respuesta_literal(caso, obs),
            tramo_qa_sin_literal=(not muestra_tramo_literal(caso, obs)
                                  if directa and caso.respondible and obs.respuesta_exacta is not None else None),
            regla=obs.regla, senales=obs.senales, respuesta_literal_esperada=caso.respuesta_literal,
            respuesta_exacta=obs.respuesta_exacta,
            respuesta_completa=obs.respuesta,
            evidencia=obs.evidencias[0].texto if obs.evidencias else None,
        ))
    return filas


class ResumenCobertura(BaseModel):
    """Conteos y tasas de un conjunto de casos. Las tasas son ``None`` si su
    denominador es 0 (no se inventa un 0)."""

    n: int
    respondibles: int
    no_respondibles: int
    directas: int
    relacionadas: int
    abstenciones: int
    falsos_ok: int
    directas_sin_literal: int
    directas_con_literal: int | None = None
    cobertura_literal: float | None = None
    tramos_qa_evaluados: int | None = None
    tramos_qa_sin_literal: int | None = None
    exactitud_tramo_qa: float | None = None
    # directas / respondibles
    cobertura_directa: float | None
    # respondibles en «relacionado» (con evidencia, sin respuesta directa) / respondibles
    cobertura_relacionada: float | None
    # no respondibles sin respuesta directa / no respondibles
    recall_sin_respuesta: float | None
    # falsos ok / no respondibles: «¿en cuántos casos donde no debía contestar, contestó?»
    tasa_falsos_ok_no_respondibles: float | None


def _tasa(a: int, b: int) -> float | None:
    return a / b if b else None


def resumir_cobertura(filas: list[FilaCaso]) -> ResumenCobertura:
    respondibles = [f for f in filas if f.respondible]
    no_respondibles = [f for f in filas if not f.respondible and f.grupo != "conversacional"]
    directas_resp = sum(f.directa for f in respondibles)
    relacionadas_resp = sum(f.relacionado for f in respondibles)
    falsos = sum(f.falso_ok for f in filas)
    sin_literal = sum(f.directa_sin_literal for f in filas)
    con_literal = directas_resp - sin_literal
    tramos = [f for f in filas if f.tramo_qa_sin_literal is not None]
    errores_tramo = sum(f.tramo_qa_sin_literal for f in tramos)
    return ResumenCobertura(
        n=len(filas), respondibles=len(respondibles), no_respondibles=len(no_respondibles),
        directas=sum(f.directa for f in filas), relacionadas=sum(f.relacionado for f in filas),
        abstenciones=sum(f.abstiene for f in filas), falsos_ok=falsos,
        directas_sin_literal=sin_literal,
        directas_con_literal=con_literal,
        cobertura_literal=_tasa(con_literal, len(respondibles)),
        tramos_qa_evaluados=len(tramos), tramos_qa_sin_literal=errores_tramo,
        exactitud_tramo_qa=_tasa(len(tramos) - errores_tramo, len(tramos)),
        cobertura_directa=_tasa(directas_resp, len(respondibles)),
        cobertura_relacionada=_tasa(relacionadas_resp, len(respondibles)),
        recall_sin_respuesta=_tasa(len(no_respondibles) - falsos, len(no_respondibles)),
        tasa_falsos_ok_no_respondibles=_tasa(falsos, len(no_respondibles)),
    )


class RiesgoAceptadas(BaseModel):
    """Riesgo de una respuesta directa aceptada: P(error | el sistema respondió ok).

    ``n`` son las respuestas directas emitidas (no el total del banco) y ``x``
    las erróneas entre ellas: falsos ok (caso no respondible) más directas que
    no muestran la respuesta literal esperada.
    """

    n: int
    criterio_respuesta: str = CRITERIO_LEGADO
    x: int
    falsos_ok: int
    directas_sin_literal: int
    observado: float | None
    confianza: float
    cota_superior: float | None  # None si n = 0: sin respuestas no hay garantía


def riesgo_aceptadas(filas: list[FilaCaso], confianza: float = 0.95) -> RiesgoAceptadas:
    aceptadas = [f for f in filas if f.directa and f.grupo != "conversacional"]
    falsos = sum(f.falso_ok for f in aceptadas)
    sin_literal = sum(f.directa_sin_literal for f in aceptadas)
    n, x = len(aceptadas), falsos + sin_literal
    return RiesgoAceptadas(
        criterio_respuesta=CRITERIO_RESPUESTA,
        n=n, x=x, falsos_ok=falsos, directas_sin_literal=sin_literal, observado=_tasa(x, n),
        confianza=confianza, cota_superior=cota_superior_clopper_pearson(x, n, confianza) if n else None,
    )


class ReporteCobertura(BaseModel):
    """Cobertura y riesgo global, por grupo y por idioma, más la vista por caso."""

    total: ResumenCobertura
    criterio_respuesta: str = CRITERIO_LEGADO
    por_grupo: dict[str, ResumenCobertura]
    por_idioma: dict[str, ResumenCobertura]
    por_idioma_y_grupo: dict[str, dict[str, ResumenCobertura]]
    riesgo_aceptadas: RiesgoAceptadas
    casos: list[FilaCaso]


def reporte_cobertura(
    pares: list[tuple[CasoEvaluacion, ObservacionEvaluacion]],
    confianza: float = 0.95,
) -> ReporteCobertura:
    """Acepta pares de varios bancos (p. ej. es, en y pt) a la vez."""
    filas = filas_de_casos(pares)
    por_grupo = {g: resumir_cobertura([f for f in filas if f.grupo == g])
                 for g in GRUPOS if any(f.grupo == g for f in filas)}
    idiomas = sorted({f.idioma for f in filas if f.idioma})
    return ReporteCobertura(
        criterio_respuesta=CRITERIO_RESPUESTA,
        total=resumir_cobertura(filas),
        por_grupo=por_grupo,
        por_idioma={i: resumir_cobertura([f for f in filas if f.idioma == i]) for i in idiomas},
        por_idioma_y_grupo={
            i: {g: resumir_cobertura([f for f in filas if f.idioma == i and f.grupo == g])
                for g in GRUPOS if any(f.idioma == i and f.grupo == g for f in filas)}
            for i in idiomas
        },
        riesgo_aceptadas=riesgo_aceptadas(filas, confianza),
        casos=filas,
    )


ReporteMetricas.model_rebuild()
ArtefactoEvaluacion.model_rebuild()


__all__ = [
    "ArtefactoEvaluacion", "FilaCaso", "GRUPOS", "ObservacionEvaluacion", "ReporteCobertura",
    "ReporteMetricas", "ResumenCobertura", "ResumenGrupo", "RiesgoAceptadas", "SenalesObservadas",
    "cota_superior_clopper_pearson", "es_no_respondible", "evaluar_observaciones",
    "filas_de_casos", "grupo_de", "muestra_respuesta_literal", "muestra_tramo_literal", "n_minimo", "reporte_cobertura",
    "resumir_cobertura", "riesgo_aceptadas",
]
