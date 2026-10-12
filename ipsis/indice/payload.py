"""Conversión entre el payload de un chunk indexado y ``ChunkRecord``.

El payload es el diccionario que produce ``ipsis.ingesta.metadata.construir_payload`` y
que el índice guarda junto a cada chunk. ``ChunkRecord`` es su forma tipada en
el contrato de componentes. La ida y vuelta es exacta para cualquier payload
completo: los campos sin equivalente tipado viajan en ``metadata``.
"""
from __future__ import annotations

from typing import Any

from ipsis.nucleo.esquemas import ChunkRecord, EvidenceSpan

# Campos del payload que ChunkRecord tipa con otro nombre.
_RENOMBRADOS = {"texto": "texto_fuente", "texto_embebido": "texto_embedding"}

# Campos del payload que ChunkRecord tipa con el mismo nombre.
_DIRECTOS = (
    "chunk_id", "doc_id", "doc_titulo", "version", "seccion_path",
    "offset_inicio", "offset_fin", "tipo_contenido",
    "tiene_excepcion", "tiene_condicion", "entidades",
)


def chunk_desde_payload(payload: dict[str, Any]) -> ChunkRecord:
    datos: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    for clave, valor in payload.items():
        if clave in _RENOMBRADOS:
            datos[_RENOMBRADOS[clave]] = valor
        elif clave in _DIRECTOS:
            datos[clave] = valor
        else:
            metadata[clave] = valor
    datos.setdefault("texto_embedding", datos.get("texto_fuente", ""))
    if datos.get("seccion_path") is None:
        datos["seccion_path"] = []
    for campo in ("parent_id", "prev_id", "next_id"):
        if campo in payload:
            datos[campo] = payload[campo]
    return ChunkRecord(**datos, metadata=metadata)


def payload_desde_chunk(chunk: ChunkRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {campo: getattr(chunk, campo) for campo in _DIRECTOS}
    for original, tipado in _RENOMBRADOS.items():
        payload[original] = getattr(chunk, tipado)
    payload.update(chunk.metadata)
    for campo in ("parent_id", "prev_id", "next_id"):
        if getattr(chunk, campo) is not None:
            payload[campo] = getattr(chunk, campo)
    return payload


def payload_desde_evidencia(evidencia: EvidenceSpan, chunk: ChunkRecord) -> dict[str, Any]:
    """Adapta una evidencia seleccionada al diccionario de redacción legado."""
    if evidencia.chunk_id != chunk.chunk_id or evidencia.doc_id != chunk.doc_id:
        raise ValueError("la evidencia no pertenece al chunk indicado")
    payload = payload_desde_chunk(chunk)
    payload["texto"] = evidencia.texto
    payload["offset_inicio"] = evidencia.offset_inicio
    payload["offset_fin"] = evidencia.offset_fin
    payload["seccion_path"] = list(evidencia.seccion_path)
    return payload


__all__ = ["chunk_desde_payload", "payload_desde_chunk", "payload_desde_evidencia"]
