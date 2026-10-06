"""Etapa de análisis: normaliza la pregunta y detecta su intención."""
from __future__ import annotations

from ipsis.consulta.etapas.base import _Etapa


class EtapaAnalisis(_Etapa):
    nombre = "analisis"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        resolutor = getattr(m, "seguimiento", None)
        obtener = getattr(getattr(m, "retriever", None), "estadisticas_lexico", None)
        if resolutor is not None and callable(obtener):
            # «¿y con 90?»: la pregunta de seguimiento hereda el tema del turno anterior.
            resolucion = resolutor.resolver(ctx.pregunta, ctx.id_sesion, getattr(m, "idioma", None), obtener())
            if resolucion.seguimiento:
                ctx.diagnostico["pregunta_interpretada"] = resolucion.pregunta
                ctx.pregunta_usuario = ctx.pregunta
                ctx.pregunta = resolucion.pregunta
        if callable(obtener):
            # Expansión controlada: una palabra que no está en el corpus suma sus
            # sinónimos que sí están, para buscar y seleccionar («necesita» → «requieren»).
            from ipsis.lenguaje.consultas import sinonimos_presentes

            sinonimos = sinonimos_presentes(ctx.pregunta, getattr(m, "idioma", None), obtener())
            if sinonimos:
                ctx.diagnostico["sinonimos"] = sinonimos
                ctx.pregunta = f"{ctx.pregunta.rstrip()} {' '.join(f for formas in sinonimos.values() for f in formas)}"
        ctx.consulta = m._analizar(ctx.pregunta, ctx.id_sesion)
        if ctx.pregunta_usuario:
            ctx.consulta = ctx.consulta.model_copy(
                update={"contexto": {**ctx.consulta.contexto, "pregunta_usuario": ctx.pregunta_usuario}})


__all__ = ["EtapaAnalisis"]
