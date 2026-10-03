"""Etapa de lectura: el lector QA busca el tramo exacto en los mejores pasajes."""
from __future__ import annotations

from rag.consulta.etapas.base import _Etapa
from rag.lenguaje.texto import dividir_oraciones
from rag.nucleo.esquemas import EvidenceSpan


def oracion_que_contiene(texto: str, inicio: int, fin: int) -> tuple[int, int]:
    """Rango de las oraciones de ``texto`` que cubren ``[inicio, fin)``."""
    rangos = [(a, b) for a, b in dividir_oraciones(texto) if a < fin and b > inicio]
    if not rangos:
        return inicio, fin
    return rangos[0][0], rangos[-1][1]


def hay_discordancia(lecturas, umbral: float = 0.5) -> bool:
    """Dos tramos confiables de pasajes distintos con entidades del mismo tipo
    y valor distinto (p. ej. «6 meses» y «12 meses») se contradicen."""
    from rag.lenguaje.entidades import extraer_entidades

    confiables = sorted((lec for lec in lecturas if lec.texto and lec.s_qa >= umbral), key=lambda lec: -lec.s_qa)[:2]
    if len(confiables) < 2 or confiables[0].indice_pasaje == confiables[1].indice_pasaje:
        return False
    a = {(e["tipo"], e["valor_norm"]) for e in extraer_entidades(confiables[0].texto)}
    b = {(e["tipo"], e["valor_norm"]) for e in extraer_entidades(confiables[1].texto)}
    tipos_comunes = {t for t, _ in a} & {t for t, _ in b}
    return any({v for t, v in a if t == tipo} != {v for t, v in b if t == tipo} for tipo in tipos_comunes)


def _ventana_pertinente(motor, pregunta: str, texto: str, limite: int) -> tuple[int, int]:
    """Rango ``[a, b)`` de ``texto`` (a lo más ``limite`` caracteres) más pertinente."""
    if len(texto) <= limite:
        return 0, len(texto)
    from rag.consulta.etapas.seleccion import seleccionar_texto_pertinente

    obtener = getattr(getattr(motor, "retriever", None), "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None
    resultado = seleccionar_texto_pertinente(pregunta, texto, 0, limite, estadisticas=est)
    return resultado.offset_inicio, resultado.offset_fin


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
        limite = perfil.cascada.max_caracteres_lectura if perfil is not None else 600
        ventanas = [_ventana_pertinente(m, ctx.pregunta, c.chunk.texto_fuente, limite) for c in candidatos]
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
                ctx.diagnostico["advertencias"].append("los dos mejores tramos dan valores distintos del mismo tipo")
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
