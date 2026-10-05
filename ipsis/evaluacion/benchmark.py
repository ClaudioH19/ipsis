"""Reporte del benchmark por perfiles (``ipsis benchmark --profiles``).

Funciones puras sobre observaciones ya producidas: compara seguridad,
cobertura, latencia y costo de cada perfil sobre los mismos casos. Las
métricas de calidad son las de ``reporte_cobertura`` (P10.1).

Un banco de regresión (el universal) sirve para **comparar** perfiles: sus
cotas no certifican el riesgo de ningún cliente (eso lo hace ``ipsis calibrate``
con el golden del cliente).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ipsis.evaluacion.metricas import ObservacionEvaluacion, ReporteCobertura
from ipsis.recursos.mensajes import t


def percentil(valores: list[float], q: float) -> float:
    """Percentil con interpolación lineal (el mismo de ``--latency-only``)."""
    ordenados = sorted(valores)
    if not ordenados:
        return 0.0
    posicion = (len(ordenados) - 1) * q
    abajo = int(posicion)
    arriba = min(abajo + 1, len(ordenados) - 1)
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (posicion - abajo)


class Latencia(BaseModel):
    n: int
    p50: float
    p95: float
    etapas: dict[str, dict[str, float]] = Field(default_factory=dict)


def latencia_de(observaciones: list[ObservacionEvaluacion], extra_ms: dict[str, float] | None = None) -> Latencia:
    """p50/p95 por consulta (motor ya calentado) y por etapa, desde las
    mediciones del propio motor. ``extra_ms`` suma un costo por caso (para
    estimar una variante con trabajo adicional)."""
    extra_ms = extra_ms or {}
    totales = [o.latencia_ms + extra_ms.get(o.caso_id, 0.0) for o in observaciones]
    por_etapa: dict[str, list[float]] = {}
    for o in observaciones:
        for etapa, ms in o.etapas_ms.items():
            por_etapa.setdefault(etapa.removesuffix("_ms"), []).append(ms)
    return Latencia(
        n=len(totales), p50=round(percentil(totales, 0.5), 1), p95=round(percentil(totales, 0.95), 1),
        etapas={e: {"p50": round(percentil(v, 0.5), 1), "p95": round(percentil(v, 0.95), 1)}
                for e, v in por_etapa.items()},
    )


class ModeloCargado(BaseModel):
    rol: str  # denso, reranker, lector
    id_hf: str
    parametros: int | None = None
    onnx_mb: float | None = None  # tamaño del archivo ONNX en caché; NO es la RAM usada


class ResultadoPerfil(BaseModel):
    nombre: str  # «medium» o una variante: «medium+ok0.85»
    perfil: str
    variante: str | None = None  # qué cambia y cómo se midió (experimental, nunca default)
    presupuesto_p95_ms: int
    latencia: Latencia
    cumple_presupuesto: bool
    cobertura: ReporteCobertura
    modelos: list[ModeloCargado] = Field(default_factory=list)
    cascada: dict = Field(default_factory=dict)
    tiempo_indexado_s: float | None = None  # costo único, fuera de la latencia por consulta
    tono: str | None = None
    costo_extra: dict | None = None  # p. ej. búsquedas adicionales de una variante


class BancoUsado(BaseModel):
    dataset_id: str
    dataset_version: str
    uso: str
    idioma: str | None
    n_casos: int


class ReporteBenchmark(BaseModel):
    schema_version: int = 1
    bancos: list[BancoUsado]
    nota: str
    perfiles: list[ResultadoPerfil]
    artefactos: list[str] = Field(default_factory=list)  # ArtefactoEvaluacion por perfil y banco (ipsis compare)


def nota_de(bancos: list[BancoUsado]) -> str:
    regresion = any(b.uso == "regresion" for b in bancos)
    return t("evaluation.note_regression" if regresion else "evaluation.note_evaluation")


def codigo_salida(reporte: ReporteBenchmark) -> int:
    """≠ 0 si un perfil (no las variantes experimentales) excede su presupuesto
    p95 o, con un banco de evaluación del cliente, da algún falso ok (la misma
    guardia de ``ipsis evaluate``). Un banco de regresión no tiene límite de falsos
    ok propio: los compara la línea base de las pruebas."""
    perfiles = [p for p in reporte.perfiles if p.variante is None]
    if any(not p.cumple_presupuesto for p in perfiles):
        return 1
    if all(b.uso == "evaluacion" for b in reporte.bancos) and any(p.cobertura.total.falsos_ok for p in perfiles):
        return 1
    return 0


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def _pct(valor) -> str:
    return "—" if valor is None else f"{valor:.1%}"


def _fraccion(grupos, nombre: str) -> str:
    g = grupos.get(nombre)
    return "—" if g is None else f"{g.directas}/{g.respondibles}"


def markdown(reporte: ReporteBenchmark) -> str:
    perfil = t("evaluation.report_profile")
    lineas = [t("evaluation.report_title"), ""]
    for b in reporte.bancos:
        lineas.append(t("evaluation.report_bank", bank=f"{b.dataset_id}@{b.dataset_version}",
                        language=b.idioma or t("evaluation.report_project_language"), use=b.uso, cases=b.n_casos))
    lineas += ["", f"> {reporte.nota}", "",
               t("evaluation.report_quality"), "",
               t("evaluation.report_quality_header"),
               "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in reporte.perfiles:
        c, g, r = p.cobertura.total, p.cobertura.por_grupo, p.cobertura.riesgo_aceptadas
        trampas = g.get("trampa_mismo_tema")
        lineas.append(
            f"| {p.nombre} | {c.directas - c.falsos_ok}/{c.respondibles} ({_pct(c.cobertura_directa)}) | "
            f"{_fraccion(g, 'exacta')} | {_fraccion(g, 'parafrasis')} | {c.falsos_ok}/{c.no_respondibles} | "
            f"{trampas.falsos_ok if trampas else 0}/{trampas.n if trampas else 0} | {r.x}/{r.n} | "
            f"{p.latencia.p50} | {p.latencia.p95} | {p.presupuesto_p95_ms} | "
            f"{t('evaluation.report_yes') if p.cumple_presupuesto else t('evaluation.report_no')} |")
    lineas += ["", t("evaluation.report_rejection"), "",
               t("evaluation.report_rejection_header"), "|---|---|---|---|---|---|"]
    for p in reporte.perfiles:
        g, c = p.cobertura.por_grupo, p.cobertura.total
        ambiguas = g.get("ambigua")
        lineas.append(
            f"| {p.nombre} | {_pct(g['fuera_de_dominio'].recall_sin_respuesta) if 'fuera_de_dominio' in g else '—'} | "
            f"{_pct(g['premisa_falsa'].recall_sin_respuesta) if 'premisa_falsa' in g else '—'} | "
            f"{ambiguas.falsos_ok if ambiguas else 0}/{ambiguas.n if ambiguas else 0} | "
            f"{_pct(c.cobertura_relacionada)} | {c.directas_sin_literal} |")
    idiomas = sorted({i for p in reporte.perfiles for i in p.cobertura.por_idioma})
    if len(idiomas) > 1:
        lineas += ["", t("evaluation.report_by_language"), "",
                   f"| {perfil} | " + " | ".join(idiomas) + " |", "|---|" + "---|" * len(idiomas)]
        for p in reporte.perfiles:
            celdas = []
            for i in idiomas:
                v = p.cobertura.por_idioma.get(i)
                ex = p.cobertura.por_idioma_y_grupo.get(i, {}).get("exacta")
                celdas.append("—" if v is None else
                              f"{_pct(v.cobertura_directa)} · {ex.directas if ex else 0}/{ex.n if ex else 0} · "
                              f"{v.falsos_ok}")
            lineas.append(f"| {p.nombre} | " + " | ".join(celdas) + " |")
    lineas += ["", t("evaluation.report_false_ok"), ""]
    for p in reporte.perfiles:
        falsos = [f for f in p.cobertura.casos if f.falso_ok]
        lineas.append(f"- **{p.nombre}**: " + (t("evaluation.report_none") if not falsos else
                      "; ".join(f"`{f.caso_id}` «{f.pregunta}»" for f in falsos)))
    lineas += ["", t("evaluation.report_cost"), "",
               t("evaluation.report_cost_header"), "|---|---|---|---|---|"]
    for p in reporte.perfiles:
        modelos = "<br>".join(
            f"{m.rol}: {m.id_hf.split('/')[-1]} ({m.parametros / 1e6:.0f} M · "
            f"{'—' if m.onnx_mb is None else f'{m.onnx_mb:.0f} MB'})" for m in p.modelos) or "—"
        k = p.cascada
        extra = "—" if not p.costo_extra else ", ".join(f"{a}: {b}" for a, b in p.costo_extra.items())
        lineas.append(f"| {p.nombre} | {modelos} | {k.get('recuperar_n')} / {k.get('rerank_k')} / "
                      f"{k.get('leer_m')} | {p.tiempo_indexado_s if p.tiempo_indexado_s is not None else '—'} | "
                      f"{extra} |")
    lineas += ["", t("evaluation.report_onnx_note"), "",
               t("evaluation.report_stage_latency"), ""]
    etapas = list(dict.fromkeys(e for p in reporte.perfiles if p.variante is None for e in p.latencia.etapas))
    lineas += [f"| {perfil} | " + " | ".join(etapas) + " |", "|---|" + "---|" * len(etapas)]
    for p in reporte.perfiles:
        if p.variante is None:
            lineas.append(f"| {p.nombre} | " + " | ".join(
                str(p.latencia.etapas.get(e, {}).get("p95", "—")) for e in etapas) + " |")
    variantes = [p for p in reporte.perfiles if p.variante]
    if variantes:
        lineas += ["", t("evaluation.report_variants"), ""]
        lineas += [f"- **{p.nombre}**: {p.variante}" for p in variantes]
    return "\n".join(lineas) + "\n"


__all__ = [
    "BancoUsado", "Latencia", "ModeloCargado", "ReporteBenchmark",
    "ResultadoPerfil", "codigo_salida", "latencia_de", "markdown", "nota_de", "percentil",
]
