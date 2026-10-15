"""Banco de pasajes: pruebas estructurales (sin modelos ni red).

Mide el orden de pasajes dentro de documentos largos; ver
tests/datos/banco_pasajes/README.md y docs/plan/precision-ingesta-tareas.md (F0.1).
"""
from __future__ import annotations

import importlib.util
import statistics
from collections import Counter
from pathlib import Path

import pytest

from ipsis.evaluacion.banco import cargar_banco, validar_evidencias_contra_corpus
from ipsis.ingesta.chunking import ESTRATEGIAS
from ipsis.ingesta.parsear import parsear_documento

BANCO = Path(__file__).resolve().parents[1] / "datos" / "banco_pasajes"
PRINCIPALES = {
    "reglamento-reembolsos", "garantia-equipos", "reglamento-permisos",
    "manual-compras", "protocolo-laboratorios", "politica-viajes",
}


def _construir():
    spec = importlib.util.spec_from_file_location("banco_pasajes_construir", BANCO / "construir.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def banco():
    return cargar_banco(BANCO / "es" / "manifiesto.json")


@pytest.fixture(scope="module")
def documentos(banco):
    carpeta = BANCO / "es" / "corpus"
    return {a.doc_id: parsear_documento(str(carpeta / a.ruta), doc_id=a.doc_id, doc_titulo=a.doc_id, version="1")
            for a in banco.manifiesto.corpus.archivos}


def test_los_derivados_estan_al_dia():
    manifiesto, casos = _construir().construir("es")
    assert (BANCO / "es" / "manifiesto.json").read_text(encoding="utf-8") == manifiesto
    assert (BANCO / "es" / "banco.jsonl").read_text(encoding="utf-8") == casos


def test_conteos_por_tipo(banco):
    clases = Counter(c.id.split("-")[1] for c in banco.casos)
    assert clases["segunda"] >= 40
    assert clases["hermana"] >= 40
    assert clases["parafrasis"] >= 20
    assert clases["trampa"] >= 15
    respondibles = [c for c in banco.casos if c.respondible]
    assert len(respondibles) >= 100


def test_particion_60_40_y_trampas_con_su_par(banco):
    por_id = {c.id: c for c in banco.casos}
    respondibles = [c for c in banco.casos if c.respondible]
    dev = sum(c.split == "dev" for c in respondibles)
    assert 0.55 <= dev / len(respondibles) <= 0.65
    for caso in banco.casos:
        if not caso.respondible:
            assert caso.subtipo == "trampa_mismo_tema"
            assert por_id[caso.par].split == caso.split and por_id[caso.par].respondible


def test_las_evidencias_son_texto_literal_del_corpus(banco, documentos):
    validar_evidencias_contra_corpus(banco, {doc_id: d.texto_completo for doc_id, d in documentos.items()})
    for caso in banco.casos:
        if caso.respondible:
            assert len(caso.evidencias) == 1
            assert caso.respuesta_literal in caso.evidencias[0].texto


def test_la_respuesta_es_unica_en_su_documento(banco, documentos):
    for caso in banco.casos:
        if caso.respondible:
            texto = documentos[caso.evidencias[0].doc_id].texto_completo
            assert texto.count(caso.respuesta_literal) == 1, caso.id


def test_los_documentos_principales_son_largos(documentos):
    for doc_id in PRINCIPALES:
        assert len(documentos[doc_id].texto_completo.split()) > 1500, doc_id


def test_las_preguntas_de_segunda_mitad_caen_en_secciones_largas(banco, documentos):
    for caso in banco.casos:
        if not caso.id.startswith("es-segunda-"):
            continue
        ev = caso.evidencias[0]
        doc = documentos[ev.doc_id]
        bloque = next(b for b in doc.bloques if b.offset_inicio <= ev.offset_inicio < b.offset_fin)
        seccion = [b for b in doc.bloques if b.seccion_path == bloque.seccion_path and b.tipo_contenido != "titulo"]
        inicio = seccion[0].offset_inicio
        fin = seccion[-1].offset_fin
        assert len(doc.texto_completo[inicio:fin].split()) > 300, caso.id
        assert (ev.offset_inicio - inicio) / (fin - inicio) > 0.5, caso.id


def test_ch_f256_da_al_menos_6_fragmentos_por_documento_de_mediana(documentos):
    cantidades = [len(ESTRATEGIAS["CH-F256"](doc)) for doc in documentos.values()]
    assert statistics.median(cantidades) >= 6
