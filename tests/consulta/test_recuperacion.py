"""Contrato ``Retriever`` para la implementación Qdrant.

Sin modelo real: Qdrant en memoria y un codificador falso determinista (bolsa
de palabras con hash). Los payloads salen del mismo pipeline de ingesta que
usa ``ipsis index``, sobre el corpus de caracterización.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pytest

from ipsis.ingesta.chunking import ESTRATEGIAS
from ipsis.nucleo.contratos import Retriever
from ipsis.nucleo.esquemas import FiltroEntidad, QueryAnalysis
from ipsis.ingesta.metadata import construir_payload
from ipsis.ingesta.parsear import parsear_markdown
from ipsis.indice.payload import chunk_desde_payload, payload_desde_chunk
from ipsis.recursos import leer_plantilla
from apoyo import CORPUS
from apoyo import plantilla_interna

DIM = 64


class CodificadorFalso:
    """Vector normalizado de conteos de palabras, con hash estable."""

    def __init__(self) -> None:
        self.llamadas = 0

    dimension = DIM

    def codificar_documentos(self, textos):
        return self._vectores(textos)

    def codificar_consultas(self, textos):
        self.llamadas += 1
        return self._vectores(textos)

    def _vectores(self, textos):
        salida = np.zeros((len(textos), DIM), dtype=np.float32)
        for i, texto in enumerate(textos):
            for palabra in re.findall(r"\w+", texto.lower()):
                salida[i, int(hashlib.md5(palabra.encode()).hexdigest(), 16) % DIM] += 1.0
            norma = np.linalg.norm(salida[i])
            if norma:
                salida[i] /= norma
        return salida


def _payloads() -> list[dict]:
    taxonomia = plantilla_interna("domain.yaml")["taxonomia"]
    payloads = []
    for ruta in sorted(CORPUS.glob("*.md")):
        doc = parsear_markdown(str(ruta), doc_id=ruta.stem, doc_titulo=ruta.stem, version="1")
        for chunk in ESTRATEGIAS["CH-SEC"](doc):
            payloads.append(construir_payload(chunk, ruta.stem, "1", True, taxonomia, chunk.texto))
    return payloads


@pytest.fixture(scope="module")
def payloads() -> list[dict]:
    return _payloads()


@pytest.fixture()
def retriever(payloads):
    from qdrant_client import QdrantClient

    from ipsis.indice.qdrant import indexar_qdrant
    from ipsis.indice.qdrant import ColeccionQdrant
    from ipsis.consulta.etapas.recuperacion import RetrieverQdrant

    codificador = CodificadorFalso()
    client, modelo, estadisticas, nombre = indexar_qdrant(
        payloads, "falso", "prueba", qdrant_path="", usar_texto_embebido=False,
        codificador=codificador, client=QdrantClient(":memory:"),
    )
    coleccion = ColeccionQdrant(client=client, codificador=modelo, estadisticas=estadisticas, nombre=nombre, qdrant_path="")
    return RetrieverQdrant(coleccion, inventario_entidades={"articulo_4"})


def _consulta(texto: str) -> QueryAnalysis:
    return QueryAnalysis(pregunta_original=texto, pregunta_normalizada=texto)


def test_payload_ida_y_vuelta_es_exacta(payloads):
    for payload in payloads:
        assert payload_desde_chunk(chunk_desde_payload(payload)) == payload


def test_payload_tipa_los_campos_que_usa_el_servicio(payloads):
    con_entidades = next(p for p in payloads if p["entidades"])
    chunk = chunk_desde_payload(con_entidades)
    assert chunk.texto_fuente == con_entidades["texto"]
    assert chunk.doc_titulo == con_entidades["doc_titulo"]
    assert chunk.entidades == con_entidades["entidades"]
    assert "texto" not in chunk.metadata and "categoria" in chunk.metadata


def test_cumple_el_protocolo(retriever):
    assert isinstance(retriever, Retriever)


def test_recuperar_ordena_por_score_y_rellena_senales(retriever):
    candidatos = retriever.recuperar(_consulta("cambio del filtro de sedimentos"), limite=3)
    assert 1 <= len(candidatos) <= 3
    assert [c.signals.fusion_rank for c in candidatos] == list(range(1, len(candidatos) + 1))
    scores = [c.score for c in candidatos]
    assert scores == sorted(scores, reverse=True)
    assert all(c.signals.fusion_score is not None and c.signals.dense_score is None for c in candidatos)


def test_modo_vectorial_rellena_senales_densas(retriever):
    retriever.modo = "vectorial"
    candidatos = retriever.recuperar(_consulta("garantía"), limite=2)
    assert all(c.signals.dense_score is not None and c.signals.fusion_score is None for c in candidatos)


def test_recuperar_es_determinista(retriever):
    consulta = _consulta("reembolso después de instalar")
    primera = [c.chunk.chunk_id for c in retriever.recuperar(consulta, limite=3)]
    assert primera == [c.chunk.chunk_id for c in retriever.recuperar(consulta, limite=3)]


def test_filtro_por_entidad_restringe_los_candidatos(retriever, payloads):
    con_articulo_4 = {p["chunk_id"] for p in payloads
                      if any(e["valor_norm"] == "articulo_4" for e in p["entidades"])}
    assert con_articulo_4, "el corpus debe contener el artículo 4"
    candidatos = retriever.recuperar(_consulta("filtros del purificador"), limite=5,
                                     filtro=FiltroEntidad(valor_norm="articulo_4"))
    assert candidatos and {c.chunk.chunk_id for c in candidatos} <= con_articulo_4


def test_senales_usan_el_coseno_denso(retriever):
    senales = retriever.estimar_confianza(_consulta("garantía del equipo"), limite=2)
    assert 0.0 < senales.confianza_top1 <= 1.0 + 1e-6
    assert senales.margen_top1_top2 >= 0.0


def test_la_pregunta_se_codifica_una_sola_vez_por_texto(retriever):
    codificador = retriever.coleccion.codificador
    antes = codificador.llamadas
    consulta = _consulta("¿cuánto dura la membrana?")
    retriever.estimar_confianza(consulta, limite=2)
    retriever.recuperar(consulta, limite=3)
    retriever.recuperar(consulta, limite=1, filtro=FiltroEntidad(valor_norm="articulo_4"))
    assert codificador.llamadas == antes + 1


def test_expone_inventarios_y_tamano(retriever, payloads):
    assert retriever.n_chunks() == len(payloads)
    assert retriever.inventario_entidades() == {"articulo_4"}
    assert retriever.estadisticas_lexico().n_chunks == retriever.n_chunks()


def test_modo_invalido_falla_al_construir(retriever):
    from ipsis.consulta.etapas.recuperacion import RetrieverQdrant

    with pytest.raises(ValueError, match="modo desconocido"):
        RetrieverQdrant(retriever.coleccion, modo="magico")


def test_registry_expone_qdrant_como_unico_retriever_base():
    from ipsis.nucleo.registro import RegistroComponentes
    from ipsis.aplicacion.registro_base import registrar_componentes_base

    assert registrar_componentes_base(RegistroComponentes()).disponibles("retriever") == ["qdrant"]


@pytest.mark.slow
@pytest.mark.parametrize(("pregunta", "fragmento"), [
    ("¿Cada cuánto se cambia el filtro de sedimentos?", "filtro de sedimentos"),
    ("¿Cuánto dura la garantía?", "garantía"),
    ("¿En cuántos días hábiles se paga el reembolso?", "reembolso"),
])
def test_bm25_solo_recupera_el_chunk_correcto(payloads, pregunta, fragmento):
    """El vector disperso por sí solo (sin denso) encuentra el pasaje: BM25 con
    stemmer del español, ids por hash e IDF aplicado por Qdrant."""
    from qdrant_client import QdrantClient

    from ipsis.indice.qdrant import indexar_qdrant, paquete_del_indice, vector_disperso
    from ipsis.lenguaje.lexico import bm25_consulta
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.lenguaje.texto import terminos

    client, _modelo, estadisticas, nombre = indexar_qdrant(
        payloads, "falso", "bm25", qdrant_path="", usar_texto_embebido=False,
        codificador=CodificadorFalso(), client=QdrantClient(":memory:"), paquete=cargar_paquete("es"),
    )
    consulta = vector_disperso(bm25_consulta(terminos(pregunta, paquete_del_indice(estadisticas))))
    resultado = client.query_points(nombre, query=consulta, using="bm25", limit=1, with_payload=True)
    assert fragmento in resultado.points[0].payload["texto"].lower()
