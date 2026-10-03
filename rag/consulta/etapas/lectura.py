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
        ctx.lecturas = m.lector.leer(ctx.pregunta, [c.chunk.texto_fuente for c in candidatos])
        ctx.diagnostico["lecturas"] = [
            {"chunk_id": candidatos[lec.indice_pasaje].chunk.chunk_id, "texto": lec.texto,
             "prob_respuesta": round(lec.prob_respuesta, 4), "s_qa": round(lec.s_qa, 4)}
            for lec in ctx.lecturas
        ]
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


__all__ = ["EtapaLectura", "oracion_que_contiene"]
