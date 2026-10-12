"""Publicación de fuentes ordenadas; contexto sin alterar sus puntajes."""
from __future__ import annotations


def texto_reranking(candidato):
    ch = candidato.chunk
    if "vista_reranking" in ch.metadata:
        return ch.metadata["vista_reranking"]["texto"]
    return ch.texto_embedding if ch.metadata.get("structure_hash") else ch.texto_fuente


def preparar_resultados(candidatos, recuperador, *, limite, vecinos, cantidad):
    ampliar = getattr(recuperador, "ampliar_resultado", None)
    elegidos, eventos = [], []
    for candidato in candidatos:
        original = candidato.chunk
        resultado = ampliar(candidato, limite, vecinos) if ampliar is not None else candidato
        ch = resultado.chunk.model_copy(deep=True)
        ch.texto_fuente = ch.texto_fuente[:limite]
        ch.offset_fin = ch.offset_inicio + len(ch.texto_fuente)
        ventana = ch.metadata.setdefault("ventana_resultado", {
            "coincidencia_inicio": ch.offset_inicio, "coincidencia_fin": ch.offset_fin,
            "unidades": [], "truncado": len(original.texto_fuente) > limite, "origen": "chunk"})
        ventana["coincidencia_fin"] = min(ch.offset_fin, ventana["coincidencia_fin"])
        if not ch.texto_fuente.strip():
            continue
        # No repetir una coincidencia que ya se puede leer en otra tarjeta.
        duplicado = any(c.chunk.doc_id == ch.doc_id and c.chunk.version == ch.version and
            c.chunk.seccion_path == ch.seccion_path and
            c.chunk.offset_inicio <= ventana["coincidencia_inicio"] and
            ventana["coincidencia_fin"] <= c.chunk.offset_fin and
            c.chunk.texto_fuente[ventana["coincidencia_inicio"] - c.chunk.offset_inicio:
                                ventana["coincidencia_fin"] - c.chunk.offset_inicio] ==
            ch.texto_fuente[ventana["coincidencia_inicio"] - ch.offset_inicio:
                           ventana["coincidencia_fin"] - ch.offset_inicio] for c, _ in elegidos)
        evento = {"chunk_id": ch.chunk_id, "inicio": ch.offset_inicio, "fin": ch.offset_fin,
                  "publicado": not duplicado, **ventana}
        eventos.append(evento)
        if duplicado:
            continue
        ch.metadata["rango_resultado"] = len(elegidos) + 1
        elegidos.append((resultado.model_copy(update={"chunk": ch}), ch.texto_fuente))
        if len(elegidos) >= cantidad:
            break
    return elegidos, eventos
