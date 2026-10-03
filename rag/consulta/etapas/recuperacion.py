"""Retriever sobre Qdrant: embeddings densos + BM25 sparse con fusión RRF.

Adapta ``rag.indice.qdrant`` al contrato ``rag.nucleo.contratos.Retriever`` sin cambiar
cómo se consulta Qdrant. Qdrant y onnxruntime se importan solo al
construir el retriever desde la configuración.
"""
from __future__ import annotations

import functools
import os
from typing import Any

from rag.consulta.etapas.base import _Etapa
from rag.nucleo.esquemas import (
    FiltroEntidad, QueryAnalysis, RetrievalCandidate, RetrievalSignals, SenalesRecuperacion,
)
from rag.indice.qdrant import ColeccionQdrant, buscar, construir_filtro_entidad
from rag.indice.payload import chunk_desde_payload

MODOS = ("vectorial", "hibrida")


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
        """Conecta con la colección que dejó ``rag indexar`` y carga sus
        artefactos. Falla si la colección no existe: nunca sirve un índice vacío."""
        from rag.indice.qdrant import (
            cargar_estadisticas,
            crear_cliente_qdrant,
            nombre_coleccion_versionada,
        )

        qdrant = qdrant or {}
        modo_cliente = os.environ.get("QDRANT_MODO") or qdrant.get("modo")
        url_servidor = os.environ.get("QDRANT_URL") or qdrant.get("url_servidor")
        client = crear_cliente_qdrant(qdrant_path=recuperacion["qdrant_path"], modo=modo_cliente,
                                      url_servidor=url_servidor)
        nombre = nombre_coleccion_versionada(recuperacion["coleccion_base"], recuperacion["modelo"],
                                             recuperacion["version_coleccion"])
        from rag.indice.manifiesto import cargar_manifiesto
        from rag.modelos.catalogo import obtener
        from rag.modelos.denso import CodificadorDenso

        if not client.collection_exists(nombre):
            raise RuntimeError(
                f"la colección Qdrant {nombre!r} no existe todavía. Corré 'rag indexar' primero "
                f"(lee la misma configuracion/motor.yaml::recuperacion que este servicio)."
            )

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
        """Modelo denso cargado, reutilizable por otras etapas (selección de
        oraciones)."""
        return self.coleccion.codificador

    def _codificar(self, texto: str):
        return self.coleccion.codificador.codificar_consultas([texto])[0]

    def estimar_confianza(self, consulta: QueryAnalysis, limite: int = 2) -> SenalesRecuperacion:
        """Coseno denso del mejor chunk y su margen sobre el segundo.

        Usa siempre una búsqueda solo densa: un score RRF es un rango relativo
        dentro de la consulta y no mide cobertura absoluta."""
        pregunta = consulta.pregunta_original
        res = buscar(self.coleccion, pregunta, modo="vectorial", limit=max(limite, 2),
                     vector_precomputado=self._vector_consulta(pregunta))
        s1 = res.scores[0] if res.scores else 0.0
        s2 = res.scores[1] if len(res.scores) > 1 else 0.0
        return SenalesRecuperacion(
            confianza_top1=s1,
            margen_top1_top2=s1 - s2,
            metodo_confianza="cosine_top1_v1",
            estado_calibracion="sin_calibrar",
        )

    def recuperar(self, consulta: QueryAnalysis, limite: int,
                  filtro: FiltroEntidad | None = None) -> list[RetrievalCandidate]:
        pregunta = consulta.pregunta_original
        filtro_qdrant = construir_filtro_entidad(filtro.valor_norm) if filtro else None
        res = buscar(self.coleccion, pregunta, modo=self.modo, limit=limite,
                     vector_precomputado=self._vector_consulta(pregunta), query_filter=filtro_qdrant)
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


class EtapaSenales(_Etapa):
    """Señales de confianza de la recuperación (coseno denso del mejor pasaje)."""

    nombre = "confianza"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        ctx.senales = m.retriever.estimar_confianza(ctx.consulta, max(m.top_k, 2))
        ctx.confianza = m._confianza(ctx.senales)
        ctx.diagnostico["senales"] = ctx.senales.model_dump(mode="python")


class EtapaRecuperacion(_Etapa):
    """Candidatos de producción más la recuperación dirigida por entidad."""

    nombre = "recuperacion"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        ctx.candidatos = m._completar_premisa(ctx.consulta, m._recuperar(ctx.consulta))
        ctx.diagnostico["candidatos"] = [
            {
                "chunk_id": candidato.chunk.chunk_id,
                "score": candidato.score,
                "signals": candidato.signals.model_dump(mode="python"),
            }
            for candidato in ctx.candidatos
        ]
        if not ctx.candidatos:
            ctx.resultado = m._abstener("sin_fragmentos", ctx.confianza, ctx.latencia_ms(), diagnostico=ctx.diagnostico)


__all__ = ["EtapaRecuperacion", "EtapaSenales", "RetrieverQdrant"]
