"""Retriever sobre Qdrant: embeddings densos + BM25 sparse con fusión RRF.

Adapta ``ipsis.indice.qdrant`` al contrato ``ipsis.nucleo.contratos.Retriever`` sin cambiar
cómo se consulta Qdrant. Qdrant y onnxruntime se importan solo al
construir el retriever desde la configuración.
"""
from __future__ import annotations

import functools
import os
from typing import Any

from ipsis.nucleo.esquemas import FiltroEntidad, QueryAnalysis, RetrievalCandidate, RetrievalSignals
from ipsis.indice.qdrant import ColeccionQdrant, buscar, construir_filtro_entidad
from ipsis.indice.payload import chunk_desde_payload
from ipsis.recursos.mensajes import t

MODOS = ("vectorial", "hibrida", "dispersa")  # «dispersa»: solo BM25 (perfil de diagnóstico bm25)


class RetrieverQdrant:
    def __init__(self, coleccion: ColeccionQdrant, *, modo: str = "hibrida",
                 inventario_entidades: set[str] | None = None,
                 cache_consultas: int = 256) -> None:
        if modo not in MODOS:
            raise ValueError(f"modo desconocido: {modo!r}; disponibles: {', '.join(MODOS)}")
        self.coleccion = coleccion
        self.modo = modo
        self._inventario = set(inventario_entidades or ())
        # Una petición consulta la misma pregunta hasta tres veces (señal,
        # recuperación y recuperación dirigida); se codifica una sola vez.
        self._vector_consulta = functools.lru_cache(maxsize=cache_consultas)(self._codificar)

    @classmethod
    def desde_configuracion(cls, recuperacion: dict[str, Any], qdrant: dict[str, Any] | None = None,
                            **opciones: Any) -> "RetrieverQdrant":
        """Conecta con la colección que dejó ``ipsis index`` y carga sus
        artefactos. Falla si la colección no existe: nunca sirve un índice vacío."""
        from ipsis.indice.qdrant import (
            cargar_estadisticas,
            crear_cliente_qdrant,
            modo_del_entorno,
            nombre_coleccion_versionada,
        )

        qdrant = qdrant or {}
        modo_cliente = modo_del_entorno() or qdrant.get("modo")
        url_servidor = os.environ.get("QDRANT_URL") or qdrant.get("url_servidor")
        client = crear_cliente_qdrant(qdrant_path=recuperacion["qdrant_path"], modo=modo_cliente,
                                      url_servidor=url_servidor)
        nombre = nombre_coleccion_versionada(recuperacion["coleccion_base"], recuperacion["modelo"],
                                             recuperacion["version_coleccion"])
        from ipsis.indice.manifiesto import cargar_manifiesto
        from ipsis.modelos.catalogo import obtener
        from ipsis.modelos.denso import CodificadorDenso

        if not client.collection_exists(nombre):
            raise RuntimeError(t("core.collection_missing", name=nombre))

        manifiesto = cargar_manifiesto(nombre)
        coleccion = ColeccionQdrant(
            client=client, codificador=CodificadorDenso(obtener(recuperacion["modelo"])),
            estadisticas=cargar_estadisticas(nombre), nombre=nombre,
            qdrant_path=recuperacion["qdrant_path"],
        )
        return cls(
            coleccion,
            modo=opciones.pop("modo", recuperacion.get("modo", "hibrida")),
            inventario_entidades=set(manifiesto.inventario_entidades),
            **opciones,
        )

    @property
    def codificador(self):
        """Modelo denso cargado, reutilizable por otros componentes."""
        return self.coleccion.codificador

    def _codificar(self, texto: str):
        return self.coleccion.codificador.codificar_consultas([texto])[0]

    def vector_consulta(self, texto: str):
        """El mismo vector memoizado que utiliza la recuperación."""
        return self._vector_consulta(texto)

    def recuperar(self, consulta: QueryAnalysis, limite: int,
                  filtro: FiltroEntidad | None = None) -> list[RetrievalCandidate]:
        pregunta = consulta.contexto.get("pregunta_recuperacion", consulta.pregunta_original)
        filtro_qdrant = construir_filtro_entidad(filtro.valor_norm) if filtro else None
        res = buscar(self.coleccion, pregunta, modo=self.modo, limit=limite,
                     vector_precomputado=self._vector_consulta(consulta.pregunta_original), query_filter=filtro_qdrant)
        candidatos = []
        for rango, (payload, score) in enumerate(zip(res.payloads, res.scores), start=1):
            if self.modo == "hibrida":
                senales = RetrievalSignals(fusion_score=score, fusion_rank=rango)
            else:
                senales = RetrievalSignals(dense_score=score, dense_rank=rango)
            candidatos.append(RetrievalCandidate(chunk=chunk_desde_payload(payload), signals=senales))
        return candidatos

    def n_chunks(self) -> int:
        return self.coleccion.client.count(collection_name=self.coleccion.nombre, exact=True).count

    def inventario_entidades(self) -> set[str]:
        return self._inventario

    def estadisticas_lexico(self):
        """Estadísticas léxicas del índice (``EstadisticasLexicas``)."""
        return self.coleccion.estadisticas

    def calentar(self) -> None:
        """Una inferencia real antes de aceptar tráfico, para que la primera
        pregunta no pague la carga en frío del modelo."""
        self._codificar("calentamiento del modelo")

    def cerrar(self) -> None:
        cerrar = getattr(self.coleccion.client, "close", None)
        if callable(cerrar):
            cerrar()
