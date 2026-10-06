"""Filtros baratos antes de recuperar: señales léxicas y política disponible."""
from __future__ import annotations

from ipsis.consulta.etapas.base import _Etapa


class EtapaFiltros(_Etapa):
    nombre = "filtros"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        _senales_lexicas(m, ctx)
        if m.politica_abstencion is None:
            ctx.resultado = m._abstener("generico", ctx.confianza, ctx.latencia_ms(), diagnostico=ctx.diagnostico)
            return


def _senales_lexicas(motor, ctx) -> None:
    """Términos foco y ``s_oov`` de la pregunta, con las estadísticas del índice."""
    from ipsis.lenguaje.consultas import comprender, terminos_de_contenido, terminos_genericos
    from ipsis.lenguaje.lexico import s_oov, terminos_foco
    from ipsis.nucleo.esquemas import SenalesLexicas

    obtener = getattr(motor.retriever, "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None
    if est is None or not hasattr(est, "idf"):
        return
    perfil = getattr(motor, "perfil_instalacion", None)
    k = perfil.lexico.max_terminos_foco if perfil is not None else 2
    # Sin las palabras de la relación («empieza» en «¿cuándo empieza la compra?»).
    tq = terminos_de_contenido(ctx.pregunta, motor.idioma, est, sin_genericas=False)
    if ctx.pregunta_usuario:
        # Seguimiento: lo heredado ayuda a buscar, pero si el usuario trajo tema
        # propio, las señales léxicas se miden sobre eso: la oración que se acepte
        # debe tener lo que preguntó ahora («acepta» en «¿y si la acepta?»).
        propios = terminos_de_contenido(ctx.pregunta_usuario, motor.idioma, est, sin_genericas=False)
        if any(est.df.get(t, 0) > 0 for t in propios):
            tq = propios
    ctx.terminos_pregunta = tq
    # El foco es el tema: una palabra de la relación («monto» en «¿desde qué monto…?»)
    # o una genérica («hace» en «¿desde cuándo se hace la compra?», «meses») nunca
    # lo es, aunque esté en el corpus y cuente para la cobertura.
    relacion = comprender(ctx.pregunta_usuario or ctx.pregunta, motor.idioma).terminos_relacion
    genericos = terminos_genericos(motor.idioma)
    tema = [t for t in tq if t not in relacion]
    ctx.terminos_foco = terminos_foco([t for t in tema if t not in genericos] or tema or tq, est, k)
    ctx.lexicas = SenalesLexicas(
        terminos_foco=[est.superficie.get(t, t) for t in ctx.terminos_foco],
        s_oov=s_oov(tq, est),
    )
    ctx.diagnostico["senales_lexicas"] = {
        **ctx.lexicas.model_dump(mode="python"),
        "terminos": {est.superficie.get(t, t): round(est.idf(t), 4) for t in tq},
        "ausentes_del_corpus": [t for t in tq if est.df.get(t, 0) == 0],
    }


__all__ = ["EtapaFiltros"]
