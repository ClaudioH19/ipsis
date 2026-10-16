"""Búsqueda del carril multimedia (plan multimedia, M2.1): fichas de audio y video que corresponden a la pregunta.

Busca en la colección ``…__media`` (``ipsis/ingesta/indice_media.py``) con el mismo modelo denso y el mismo cliente que
los documentos. No toca las fuentes de documentos: el motor v2 la llama después de publicarlas.

Dos medidas, que no son lo mismo:

* el **orden** lo da la fusión híbrida (denso + BM25, RRF), que es relativa a la consulta: el primero siempre vale lo
  mismo y no dice si algo corresponde;
* el **puntaje** que se publica y con el que se decide es el **coseno denso** de la unidad mostrada, una medida absoluta
  (``puntaje_minimo`` de ``MediaConfig``). Sin ``puntaje_minimo`` no se muestra nada.

Una ficha puede aparecer por sí misma o por uno de sus capítulos, y se muestra la unidad de mayor coseno: el capítulo si
la pregunta es sobre él (lleva al minuto exacto) y la ficha si es sobre el video en general. El plan decía «si coinciden la
ficha y un capítulo, el capítulo», pero eso mandaría al minuto de un capítulo cualquiera una pregunta sobre todo el video;
``carril_multimedia.py`` (M2.2) mide el acierto del capítulo y puede ajustar la regla.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ipsis.indice.qdrant import ColeccionQdrant, buscar as buscar_qdrant, cargar_estadisticas
from ipsis.ingesta.indice_media import nombre_coleccion_media

CANDIDATOS = 20  # unidades que se piden a cada búsqueda antes de agrupar por ficha


@dataclass
class BuscadorMedia:
    coleccion: ColeccionQdrant
    vector_consulta: Callable[[str], Any]  # el memoizado del recuperador: la pregunta ya está codificada
    max_resultados: int = 1
    puntaje_minimo: float | None = None
    candidatos: int = CANDIDATOS

    @classmethod
    def desde_recuperador(cls, recuperador, cfg_rec: dict, opciones: dict) -> "BuscadorMedia | None":
        """Abre la colección del carril con el cliente y el codificador del recuperador de documentos.

        ``None`` si no existe (el proyecto no tiene fichas indexadas): el motor sigue sin carril.
        """
        nombre = nombre_coleccion_media(cfg_rec["coleccion_base"], cfg_rec["modelo"], cfg_rec["version_coleccion"])
        base = recuperador.coleccion
        if not base.client.collection_exists(nombre):
            return None
        coleccion = ColeccionQdrant(client=base.client, codificador=base.codificador,
                                    estadisticas=cargar_estadisticas(nombre), nombre=nombre,
                                    qdrant_path=cfg_rec["qdrant_path"])
        return cls(coleccion, recuperador.vector_consulta, max_resultados=opciones["max_resultados"],
                   puntaje_minimo=opciones["puntaje_minimo"])

    def _cosenos(self, vector, ids: list) -> dict:
        """Coseno denso de cada punto de ``ids``, calculado por Qdrant con un filtro por id."""
        from qdrant_client import models

        if not ids:
            return {}
        respuesta = self.coleccion.client.query_points(
            collection_name=self.coleccion.nombre, query=vector.tolist(), using="denso", limit=len(ids),
            query_filter=models.Filter(must=[models.HasIdCondition(has_id=ids)]))
        return {p.id: float(p.score) for p in respuesta.points}

    def candidatos_agrupados(self, preguntas: list[str]) -> list[dict]:
        """Las fichas candidatas, mejor primero, **sin** umbral ni tope. Es lo que mide ``carril_multimedia.py``.

        ``preguntas`` es la pregunta y, si v2 la generó, su variante ortográfica; de cada unidad se conserva su mejor
        posición y su mejor coseno entre todas.
        """
        mejor: dict = {}  # id de punto → {payload, rango, coseno}
        for pregunta in preguntas:
            vector = self.vector_consulta(pregunta)
            hibrida = buscar_qdrant(self.coleccion, pregunta, modo="hibrida", limit=self.candidatos, vector_precomputado=vector)
            cosenos = self._cosenos(vector, list(hibrida.ids_ordenados))
            for rango, (id_punto, payload) in enumerate(zip(hibrida.ids_ordenados, hibrida.payloads), start=1):
                actual = mejor.setdefault(id_punto, {"payload": payload, "rango": rango, "coseno": cosenos.get(id_punto)})
                actual["rango"] = min(actual["rango"], rango)
                if cosenos.get(id_punto) is not None:
                    actual["coseno"] = max(actual["coseno"] if actual["coseno"] is not None else -1.0, cosenos[id_punto])
        por_ficha: dict[str, list[dict]] = {}
        for unidad in sorted(mejor.values(), key=lambda u: (u["rango"], u["payload"].get("chunk_id", ""))):
            por_ficha.setdefault(unidad["payload"]["media_id"], []).append(unidad)
        resultados = []
        for unidades in por_ficha.values():  # en el orden en que aparece cada ficha
            elegida = max(unidades, key=lambda u: (u["coseno"] if u["coseno"] is not None else -1.0, -u["rango"]))
            resultados.append(_contrato(elegida))
        return resultados

    def buscar(self, preguntas: list[str]) -> list[dict]:
        """Las fichas que se publican: las candidatas con coseno de al menos ``puntaje_minimo``, hasta ``max_resultados``.

        Sin ``puntaje_minimo`` no se publica nada.
        """
        if self.puntaje_minimo is None:
            return []
        publicables = [c for c in self.candidatos_agrupados(preguntas)
                       if c["score"] is not None and c["score"] >= self.puntaje_minimo]
        return publicables[:self.max_resultados]


def _contrato(unidad: dict) -> dict:
    """El contrato interno de una ficha candidata: texto literal de la ficha y de su capítulo, sin nada generado."""
    p = unidad["payload"]
    capitulo = p["tipo_unidad"] == "capitulo"
    return {
        "media_id": p["media_id"], "title": p["titulo"], "kind": p["tipo_media"], "url": p.get("url"),
        "file": p.get("archivo"), "start_seconds": p.get("inicio_segundos") if capitulo else None,
        "chapter_title": p.get("capitulo_titulo") if capitulo else None,
        "chapter_description": p.get("capitulo_descripcion") if capitulo else None,
        "description": p["descripcion"], "duration": p.get("duracion_segundos"), "version": p.get("version") or None,
        "score": unidad["coseno"], "fusion_rank": unidad["rango"],
    }


__all__ = ["BuscadorMedia", "CANDIDATOS"]
