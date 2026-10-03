"""Verificación de fidelidad antes de responder.

Toda entidad determinista de la respuesta debe aparecer literalmente en los
fragmentos fuente. La guardia por tipo de dato solicitado se retira en P8.3.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rag.consulta.etapas.base import _Etapa
from rag.lenguaje.entidades import extraer_entidades
from rag.lenguaje.texto import sin_acentos

# ==========================================================================
# GUARDIA (sección 6.3 — verificación de fidelidad en línea)
# ==========================================================================
@dataclass
class ResultadoFidelidad:
    fiel: bool
    motivos: list[str] = field(default_factory=list)


_RE_SOLICITUD_PRECIO = re.compile(
    r"\b(?:precio|costo|coste|tarifa)\b|\bcuanto\s+(?:cuesta|cuestan|vale|valen)\b|\bvalor\s+(?:de|del)\b",
    re.IGNORECASE,
)
_RE_DINERO = re.compile(
    r"(?:[$€£]\s*\d)|(?:\b(?:clp|usd|eur|uf|utm)\s*\$?\s*\d)"
    r"|(?:\b\d[\d.,]*\s*(?:pesos?|dolares?|euros?|clp|usd|eur|uf|utm)\b)",
    re.IGNORECASE,
)
_RE_SOLICITUD_DURACION = re.compile(
    r"\bcada\s+cuanto\b|\bcuanto\s+dura\b|\bcuantos?\s+(?:dias?|semanas?|meses?|horas?|minutos?)\b",
    re.IGNORECASE,
)
_RE_SOLICITUD_CANTIDAD = re.compile(
    r"\bcuant(?:os|as)\s+([a-z]+)\b|\bcantidad\s+de\s+([a-z]+)\b",
    re.IGNORECASE,
)
_NUMEROS_CANTIDAD = {
    "un", "una", "uno", "dos", "tres", "cuatro", "cinco", "seis",
    "siete", "ocho", "nueve", "diez", "once", "doce", "trece",
    "catorce", "quince", "veinte", "treinta", "cien", "mil",
}


def _texto_fuente(fragmentos: list[dict]) -> str:
    return " ".join(
        f"{f['texto']} {f['doc_titulo']} {' '.join(f.get('seccion_path') or [])}"
        for f in fragmentos
    )


def _cantidad_cercana_a_objetivo(texto: str, objetivo: str) -> bool:
    tokens = re.findall(r"\d+(?:[.,]\d+)?|[a-z]+", sin_acentos(texto).lower())
    raiz = objetivo[:-2] if objetivo.endswith("es") else objetivo[:-1] if objetivo.endswith("s") else objetivo
    for indice, token in enumerate(tokens):
        if token != objetivo and not (len(raiz) >= 3 and token.startswith(raiz)):
            continue
        anteriores = tokens[max(0, indice - 4):indice]
        if any(re.fullmatch(r"\d+(?:[.,]\d+)?", valor) or valor in _NUMEROS_CANTIDAD for valor in anteriores):
            return True
    return False


def verificar_respaldo_dato_solicitado(
    pregunta: str,
    fragmentos: list[dict],
) -> ResultadoFidelidad:
    """Exige el tipo de dato pedido antes de permitir una respuesta directa.

    Es deliberadamente conservadora: solo bloquea intenciones cuantitativas
    reconocibles con alta precisión. No intenta juzgar relevancia semántica ni
    sustituye la evaluación de recuperación.
    """
    pregunta_norm = sin_acentos(pregunta).lower()
    fuente = _texto_fuente(fragmentos)
    fuente_norm = sin_acentos(fuente).lower()

    if _RE_SOLICITUD_PRECIO.search(pregunta_norm):
        if not _RE_DINERO.search(fuente_norm):
            return ResultadoFidelidad(
                fiel=False,
                motivos=["la pregunta solicita un precio, pero la evidencia no contiene un importe monetario"],
            )
        return ResultadoFidelidad(fiel=True)

    if _RE_SOLICITUD_DURACION.search(pregunta_norm):
        if not any(entidad["tipo"] == "plazo" for entidad in extraer_entidades(fuente)):
            return ResultadoFidelidad(
                fiel=False,
                motivos=["la pregunta solicita una duración, pero la evidencia no contiene un plazo"],
            )
        return ResultadoFidelidad(fiel=True)

    solicitud = _RE_SOLICITUD_CANTIDAD.search(pregunta_norm)
    if solicitud:
        objetivo = solicitud.group(1) or solicitud.group(2)
        if not _cantidad_cercana_a_objetivo(fuente_norm, objetivo):
            return ResultadoFidelidad(
                fiel=False,
                motivos=[
                    f"la pregunta solicita una cantidad de {objetivo}, pero la evidencia no contiene esa cantidad"
                ],
            )
    return ResultadoFidelidad(fiel=True)


def verificar_fidelidad(respuesta_generada: str, fragmentos: list[dict]) -> ResultadoFidelidad:
    """Guardia real (no un stub): toda entidad determinista (nota,
    porcentaje, plazo, fecha, artículo, saber, semana, organismo —
    ``rag/lenguaje/entidades.py``) presente en ``respuesta_generada`` debe
    estar también, literalmente, en el texto fuente (los fragmentos
    recuperados, más su cita determinista: título del documento y ruta de
    sección, que también se copian del corpus vía ``documentos/catalogo.yaml`` /
    el parser — nunca las produce un modelo). Si alguna entidad de la
    respuesta no tiene respaldo literal, la guardia falla y ``api.py`` debe
    abstenerse en vez de responder.

    No compara contra un golden set: en inferencia real no existe una
    "respuesta correcta". La única fuente de verdad son los fragmentos que el
    propio sistema recuperó."""
    entidades_respuesta = {e["valor_norm"] for e in extraer_entidades(respuesta_generada)}
    texto_fuente = _texto_fuente(fragmentos)
    entidades_fuente = {e["valor_norm"] for e in extraer_entidades(texto_fuente)}
    faltantes = entidades_respuesta - entidades_fuente
    if faltantes:
        return ResultadoFidelidad(
            fiel=False,
            motivos=[f"entidad en la respuesta sin respaldo literal en los fragmentos: {sorted(faltantes)}"],
        )
    return ResultadoFidelidad(fiel=True)


class EtapaVerificacion(_Etapa):
    """Última guardia: toda entidad de la respuesta existe en la fuente."""

    nombre = "verificacion"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        fidelidad = verificar_fidelidad(ctx.texto, ctx.payloads)
        if not fidelidad.fiel:
            ctx.diagnostico["advertencias"].extend(fidelidad.motivos)
            ctx.resultado = m._abstener("guardia", ctx.confianza, ctx.latencia_ms(), diagnostico=ctx.diagnostico)
            return
        ctx.resultado = m._resultado(
            estado=ctx.estado,
            motivo=ctx.decision.motivo,
            mensaje=ctx.texto,
            confianza=ctx.confianza,
            latencia_ms=ctx.latencia_ms(),
            plan=ctx.plan,
            evidencias=ctx.evidencias,
            fragmentos_http=m._fragmentos_http(ctx.evidencias, ctx.candidatos),
            diagnostico=ctx.diagnostico,
        )
