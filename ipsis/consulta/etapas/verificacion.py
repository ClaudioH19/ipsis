"""Verificación de fidelidad antes de responder.

Toda entidad determinista de la respuesta debe aparecer literalmente en los
fragmentos fuente. Si la evidencia responde lo pedido lo decide la política
(lector QA y señales léxicas), no reglas por idioma.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ipsis.consulta.etapas.base import _Etapa
from ipsis.lenguaje.entidades import extraer_entidades
from ipsis.recursos.mensajes import t

# ==========================================================================
# GUARDIA (sección 6.3 — verificación de fidelidad en línea)
# ==========================================================================
@dataclass
class ResultadoFidelidad:
    fiel: bool
    motivos: list[str] = field(default_factory=list)


def _texto_fuente(fragmentos: list[dict]) -> str:
    return " ".join(
        f"{f['texto']} {f['doc_titulo']} {' '.join(f.get('seccion_path') or [])}"
        for f in fragmentos
    )


def verificar_fidelidad(respuesta_generada: str, fragmentos: list[dict]) -> ResultadoFidelidad:
    """Guardia real (no un stub): toda entidad determinista (nota,
    porcentaje, plazo, fecha, artículo, saber, semana, organismo —
    ``ipsis/lenguaje/entidades.py``) presente en ``respuesta_generada`` debe
    estar también, literalmente, en el texto fuente (los fragmentos
    recuperados, más su cita determinista: título del documento y ruta de
    sección, que también se copian del corpus vía ``documents/catalog.yaml`` /
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
            motivos=[t("runtime.unsupported_entity", entities=sorted(faltantes))],
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
            respuesta_exacta=ctx.respuesta_exacta if ctx.estado.value == "respuesta_directa" else None,
            bloques=ctx.bloques,
        )
