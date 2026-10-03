"""Detección de saludos y charla trivial, respondidos con texto fijo.

Se evalúa antes de recuperar: una pregunta conversacional nunca pasa por
recuperación, abstención ni verificación.
"""
from __future__ import annotations

import functools
import re

from rag.consulta.etapas.base import _Etapa
from rag.consulta.etapas.redaccion import _cargar_plantillas, _elegir_variante

# ==========================================================================
# CONVERSACIONAL (Etapa C, punto 4): saludos y charla trivial se detectan
# ANTES de tocar Qdrant y se responden con texto fijo -- nunca pasan por
# recuperación, abstención ni guardia (no hay nada del corpus que
# verificar en "hola"). Pensado para el widget de chat: sin esto, un
# saludo caía en "No encontré esa información...", que es un mal primer
# mensaje para cualquier persona que recién abre el chat.
# ==========================================================================
@functools.lru_cache(maxsize=16)
def _compilar_patrones(patrones: tuple[tuple[str, tuple[str, ...]], ...]) -> dict[str, list[re.Pattern]]:
    return {cat: [re.compile(p, re.IGNORECASE) for p in lista] for cat, lista in patrones}


def _patrones_conversacionales_compilados(datos: dict) -> dict[str, list[re.Pattern]]:
    patrones = datos.get("conversacional", {}).get("patrones", {})
    return _compilar_patrones(tuple((cat, tuple(lista)) for cat, lista in patrones.items()))


def detectar_conversacional(pregunta: str, plantillas: dict | None = None) -> str | None:
    """Devuelve la categoría conversacional detectada (``"saludo"``,
    ``"agradecimiento"``, ``"despedida"``, ``"capacidad"``) según los
    patrones deterministas de ``conversacional`` del paquete de idioma, o
    ``None`` si la pregunta no matchea ninguno -- en cuyo caso sigue el
    flujo normal (recuperación + abstención). Se evalúan las categorías en
    el orden declarado en config; la primera que matchea gana. Regex
    simples, sin NLP: exactamente el mismo criterio de determinismo que el
    resto del proyecto (nada de esto lo decide un modelo)."""
    datos = plantillas or _cargar_plantillas()
    categorias = datos.get("conversacional", {}).get("categorias", [])
    patrones = _patrones_conversacionales_compilados(datos)
    for categoria in categorias:
        for patron in patrones.get(categoria, []):
            if patron.search(pregunta):
                return categoria
    return None


def respuesta_conversacional(
    categoria: str,
    pregunta: str = "",
    plantillas: dict | None = None,
) -> str:
    """Texto FIJO de ``conversacional.respuestas`` del paquete de idioma
    para la categoría detectada -- nunca generado.

    Consume: la categoría y, opcionalmente, la pregunta tal cual la escribió
    el usuario. Produce: una de las formulaciones declaradas para esa
    categoría.

    La categoría declara varias formulaciones para que el asistente no
    conteste siempre con la misma frase. La elección es DETERMINISTA (hash
    de la pregunta): la misma pregunta devuelve siempre el mismo texto, así
    que sigue siendo testeable, pero "hola" y "buenas" no contestan lo
    mismo. Acepta también un string suelto, por compatibilidad con un
    `plantillas.yaml` anterior a esta variedad."""
    opciones = (plantillas or _cargar_plantillas())["conversacional"]["respuestas"][categoria]
    if isinstance(opciones, str):
        return opciones
    return _elegir_variante(opciones, pregunta)


class EtapaConversacional(_Etapa):
    """Saludos y charla trivial: respuesta fija, antes de recuperar nada."""

    nombre = "conversacional"
    requiere_admision = False

    def ejecutar(self, ctx) -> None:
        from rag.nucleo.esquemas import AssistantState

        m = self.motor
        categoria = detectar_conversacional(ctx.pregunta, m.plantillas)
        if categoria is None:
            return
        ctx.resultado = m._resultado(
            estado=AssistantState.CONVERSACIONAL,
            motivo=f"conversacional:{categoria}",
            mensaje=m.respuesta_conversacional(categoria, ctx.pregunta),
            confianza={"top1": 0.0, "margen": 0.0, "acuerdo_bm25": None},
            latencia_ms=ctx.latencia_ms(),
            plan="conversacional",
            diagnostico={"etapas": {}},
        )
