"""Etapa de lectura: el lector QA busca el tramo exacto en los mejores pasajes."""
from __future__ import annotations

from ipsis.consulta.etapas.base import _Etapa
from ipsis.lenguaje.texto import dividir_oraciones
from ipsis.nucleo.esquemas import EvidenceSpan
from ipsis.recursos.mensajes import t


def _es_titulo(linea: str) -> bool:
    """Una línea corta y sin puntuación final («6.3 Procedimiento de Compra», «Verano»)."""
    linea = linea.strip()
    return bool(linea) and len(linea.split()) <= 10 and not linea.endswith((".", ":", ";", "?", "!", ")", "»", '"'))


def oracion_que_contiene(texto: str, inicio: int, fin: int) -> tuple[int, int]:
    """Rango de las oraciones de ``texto`` que cubren ``[inicio, fin)``. Se corta
    primero por línea: un título («6.3 Procedimiento de Compra») no es parte de la
    oración que lo sigue."""
    linea_ini = texto.rfind("\n", 0, inicio) + 1
    linea_fin = texto.find("\n", fin)
    linea_fin = len(texto) if linea_fin == -1 else linea_fin
    linea = texto[linea_ini:linea_fin]
    if _es_titulo(linea) and linea_fin < len(texto):
        # Un tramo dentro de un título («Verano») no basta como evidencia: va con
        # la primera oración de lo que titula, que es donde está el contenido.
        siguiente_fin = texto.find("\n", linea_fin + 1)
        siguiente_fin = len(texto) if siguiente_fin == -1 else siguiente_fin
        oraciones = dividir_oraciones(texto[linea_fin + 1:siguiente_fin])
        if oraciones:
            return linea_ini, linea_fin + 1 + oraciones[0][1]
    rangos = [(a + linea_ini, b + linea_ini) for a, b in dividir_oraciones(linea)
              if a + linea_ini < fin and b + linea_ini > inicio]
    if not rangos:
        return inicio, fin
    return rangos[0][0], rangos[-1][1]


def hay_discordancia(lecturas, umbral: float = 0.5) -> bool:
    """Dos tramos confiables de pasajes distintos con entidades del mismo tipo
    y valor distinto (p. ej. «6 meses» y «12 meses») se contradicen."""
    from ipsis.lenguaje.entidades import extraer_entidades

    confiables = sorted((lec for lec in lecturas if lec.texto and lec.s_qa >= umbral), key=lambda lec: -lec.s_qa)[:2]
    if len(confiables) < 2 or confiables[0].indice_pasaje == confiables[1].indice_pasaje:
        return False
    a = {(e["tipo"], e["valor_norm"]) for e in extraer_entidades(confiables[0].texto)}
    b = {(e["tipo"], e["valor_norm"]) for e in extraer_entidades(confiables[1].texto)}
    tipos_comunes = {t for t, _ in a} & {t for t, _ in b}
    return any({v for t, v in a if t == tipo} != {v for t, v in b if t == tipo} for tipo in tipos_comunes)


def _ventana_pertinente(motor, pregunta: str, texto: str, limite: int,
                        pregunta_usuario: str | None = None) -> tuple[int, int]:
    """Rango ``[a, b)`` de ``texto`` (a lo más ``limite`` caracteres) más pertinente."""
    if len(texto) <= limite:
        return 0, len(texto)
    from ipsis.consulta.etapas.seleccion import seleccionar_texto_pertinente

    obtener = getattr(getattr(motor, "retriever", None), "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None
    resultado = seleccionar_texto_pertinente(pregunta, texto, 0, limite, estadisticas=est, centrada=True,
                                             pregunta_usuario=pregunta_usuario)
    return resultado.offset_inicio, resultado.offset_fin


def _candidato_por_pista(motor, pregunta: str, leidos: list, resto: list):
    """Si la pregunta tiene una intención (``ipsis.lenguaje.consultas``) y la mejor
    oración con una pista suya está en un candidato que el reranker dejó fuera
    de la lectura, ese candidato también se lee. El reranker mide «se parece»;
    la pista dice «puede responder esta relación»: con «¿cuándo empieza la
    compra?», un pasaje sobre horarios puede quedar arriba y «Una vez aprobado
    el formulario, se realizará la compra», abajo. El lector sigue decidiendo."""
    if not resto:
        return None
    from ipsis.consulta.etapas.seleccion import _puntuar, dividir_en_unidades
    from ipsis.lenguaje.consultas import comprender, peso_pista

    comprension = comprender(pregunta, motor.idioma)
    if not comprension.pistas:
        return None
    obtener = getattr(getattr(motor, "retriever", None), "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None

    def mejor_con_pista(candidato) -> float:
        unidades = dividir_en_unidades(candidato.chunk.texto_fuente)
        scores = _puntuar(pregunta, unidades, est)
        return max((s for u, s in zip(unidades, scores) if peso_pista(u.texto, comprension) > 0), default=0.0)

    techo = max((mejor_con_pista(c) for c in leidos), default=0.0)
    mejor = max(resto, key=mejor_con_pista)
    return mejor if mejor_con_pista(mejor) > techo else None


class EtapaLectura(_Etapa):
    """Lee los ``leer_m`` primeros candidatos. Si hay un tramo con respuesta,
    la evidencia es la oración que lo contiene (texto literal, offsets exactos)
    y el tramo viaja aparte como ``respuesta_exacta``."""

    nombre = "lectura"
    usa_modelos = True

    def ejecutar(self, ctx) -> None:
        m = self.motor
        if m.lector is None or not ctx.candidatos:
            return
        perfil = getattr(m, "perfil_instalacion", None)
        leer_m = perfil.cascada.leer_m if perfil is not None and perfil.cascada.leer_m else 2
        candidatos = ctx.candidatos[:leer_m]
        extra = _candidato_por_pista(m, ctx.pregunta, candidatos, ctx.candidatos[leer_m:])
        if extra is not None:
            candidatos = [*candidatos, extra]
            ctx.diagnostico["lectura_por_pista"] = extra.chunk.chunk_id
        limite = perfil.cascada.max_caracteres_lectura if perfil is not None else 600
        ventanas = [_ventana_pertinente(m, ctx.pregunta, c.chunk.texto_fuente, limite, ctx.pregunta_usuario or None)
                    for c in candidatos]
        lecturas = m.lector.leer(ctx.pregunta, [texto[a:b] for texto, (a, b) in zip(
            (c.chunk.texto_fuente for c in candidatos), ventanas)])
        # offsets de la ventana -> offsets del pasaje completo
        ctx.lecturas = [
            lec.model_copy(update={"inicio": lec.inicio + ventanas[lec.indice_pasaje][0],
                                   "fin": lec.fin + ventanas[lec.indice_pasaje][0]})
            for lec in lecturas
        ]
        ctx.diagnostico["lecturas"] = [
            {"chunk_id": candidatos[lec.indice_pasaje].chunk.chunk_id, "texto": lec.texto,
             "prob_respuesta": round(lec.prob_respuesta, 4), "s_qa": round(lec.s_qa, 4)}
            for lec in ctx.lecturas
        ]
        if perfil is not None and perfil.cascada.concordancia:
            ctx.discordancia = hay_discordancia(ctx.lecturas)
            if ctx.discordancia:
                ctx.diagnostico["advertencias"].append(t("runtime.reader_disagreement"))
        mejor = max(ctx.lecturas, key=lambda lec: (lec.s_qa, -lec.indice_pasaje))
        if not mejor.texto or mejor.s_qa <= 0:
            return
        chunk = candidatos[mejor.indice_pasaje].chunk
        ini, fin = oracion_que_contiene(chunk.texto_fuente, mejor.inicio, mejor.fin)
        ctx.evidencia_lector = EvidenceSpan(
            doc_id=chunk.doc_id,
            chunk_id=chunk.chunk_id,
            texto=chunk.texto_fuente[ini:fin],
            offset_inicio=chunk.offset_inicio + ini,
            offset_fin=chunk.offset_inicio + fin,
            seccion_path=chunk.seccion_path,
            score=mejor.s_qa,
        )
        ctx.respuesta_exacta = {
            "chunk_id": chunk.chunk_id,
            "texto": mejor.texto,
            "offset_inicio": chunk.offset_inicio + mejor.inicio,
            "offset_fin": chunk.offset_inicio + mejor.fin,
        }


__all__ = ["EtapaLectura", "hay_discordancia", "oracion_que_contiene"]
