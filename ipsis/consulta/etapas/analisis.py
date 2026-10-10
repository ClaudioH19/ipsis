"""Etapa de análisis: normaliza la pregunta y detecta su intención."""
from __future__ import annotations

from ipsis.consulta.etapas.base import _Etapa


class EtapaAnalisis(_Etapa):
    nombre = "analisis"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        resolutor = getattr(m, "seguimiento", None)
        obtener = getattr(getattr(m, "retriever", None), "estadisticas_lexico", None)
        from ipsis.lenguaje.estilo import es_coloquial

        # Sobre lo que escribió el usuario, antes de corregir: la forma, no las palabras.
        ctx.coloquial = es_coloquial(ctx.pregunta, getattr(m, "idioma", None))
        if ctx.coloquial:
            ctx.diagnostico["estilo_coloquial"] = True
        if callable(obtener):
            # «pasword» → «password»: una errata no es una palabra ausente del corpus.
            from ipsis.lenguaje.ortografia import correcciones, corregir

            cambios = correcciones(ctx.pregunta, getattr(m, "idioma", None), obtener())
            if cambios:
                ctx.diagnostico["ortografia"] = cambios
                ctx.pregunta = corregir(ctx.pregunta, cambios)
        if resolutor is not None and callable(obtener):
            # «¿y con 90?»: la pregunta de seguimiento hereda el tema de la conversación.
            resolucion = resolutor.resolver(ctx.pregunta, ctx.id_sesion, getattr(m, "idioma", None), obtener())
            ctx.turno_memoria = resolucion.turno
            ctx.diagnostico["conversacion"] = {"accion": resolucion.accion, "tema": resolucion.tema}
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
            # La pregunta interpretada recupera el tema; sus patrones antiguos
            # no determinan qué relación se pregunta en este turno.
            actual = m._analizar(ctx.pregunta_usuario, ctx.id_sesion)
            contexto = {k: v for k, v in ctx.consulta.contexto.items() if k != "relacion"}
            if "relacion" in actual.contexto:
                contexto["relacion"] = actual.contexto["relacion"]
            ctx.consulta = ctx.consulta.model_copy(update={"intencion": actual.intencion, "contexto": contexto})
        if callable(obtener) and getattr(m.retriever, "modo", "hibrida") != "vectorial":
            from ipsis.lenguaje.sinonimos import expansion_automatica

            expansion, detalles = expansion_automatica(ctx.pregunta, getattr(m, "idioma", None), obtener())
            if expansion:
                recuperacion = f"{ctx.pregunta.rstrip()} {' '.join(f for fs in expansion.values() for f in fs)}"
                ctx.consulta = ctx.consulta.model_copy(update={"contexto": {
                    **ctx.consulta.contexto, "pregunta_recuperacion": recuperacion,
                }})
                ctx.diagnostico["recursos_lexicos"] = detalles
                ctx.diagnostico["pregunta_recuperacion"] = recuperacion
        if ctx.consulta.intencion != "desconocida":
            ctx.diagnostico["intencion"] = {"nombre": ctx.consulta.intencion,
                                            "origen": "patron",
                                            "relacion": ctx.consulta.contexto.get("relacion", "")}
        if ctx.pregunta_usuario:
            ctx.consulta = ctx.consulta.model_copy(
                update={"contexto": {**ctx.consulta.contexto, "pregunta_usuario": ctx.pregunta_usuario}})


__all__ = ["EtapaAnalisis"]
