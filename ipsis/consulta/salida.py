"""Construcción del resultado y adaptador de salida, sin decisiones semánticas."""
from __future__ import annotations

from ipsis.nucleo.esquemas import AssistantResult, AssistantState


def construir_resultado(*, estado, motivo, mensaje, confianza, latencia_ms, plan,
                        diagnostico, evidencias=None, fragmentos_http=None,
                        respuesta_exacta=None, bloques=None, nivel_confianza=None,
                        alternativas=None, modo_respuesta=None):
    estados_http = {
        AssistantState.RESPUESTA_DIRECTA: "ok", AssistantState.RELACIONADO: "relacionado",
        AssistantState.CONVERSACIONAL: "conversacional", AssistantState.SIN_RESPUESTA: "sin_respuesta",
        AssistantState.NECESITA_ACLARACION: "sin_respuesta",
    }
    contrato = {
        "estado": estados_http[estado], "nivel_servicio": "normal", "respuesta": mensaje,
        "bloques": bloques or [{"tipo": "mensaje", "texto": mensaje}], "plan": plan,
        "fragmentos": fragmentos_http or [], "confianza": confianza, "latencia_ms": latencia_ms,
    }
    if nivel_confianza is not None:
        contrato["nivel_confianza"] = nivel_confianza
    if modo_respuesta is not None:
        contrato["modo_respuesta"] = modo_respuesta
    if respuesta_exacta is not None:
        contrato["respuesta_exacta"] = respuesta_exacta
    if alternativas:
        contrato["alternativas"] = alternativas
    if estado == AssistantState.CONVERSACIONAL and motivo.startswith("conversacional:"):
        contrato["categoria_conversacional"] = motivo.split(":", 1)[1]
    detalles = {**diagnostico, "contrato_http": contrato}
    return AssistantResult(estado=estado, motivo=motivo, mensaje_usuario=mensaje,
                           evidencias=evidencias or [], confianza=confianza,
                           contrato_http=contrato, diagnostico=detalles)
