"""Banco universal (tests/datos/banco_universal): regresión del software en es, en y pt.

Las pruebas estructurales no usan modelos ni red. La prueba lenta evalúa cada
perfil con v2 y comprueba que ningún caso salga «ok» (v2 publica fuentes).
"""
from __future__ import annotations

import importlib.util
import json
import re
import socket
from collections import Counter
from pathlib import Path

import pytest

from ipsis.evaluacion.banco import cargar_banco, validar_evidencias_contra_corpus
from ipsis.ingesta.parsear import parsear_documento

RAIZ = Path(__file__).resolve().parents[1] / "datos" / "banco_universal"
IDIOMAS = ("es", "en", "pt")
CAPACIDADES = {"cantidad", "duracion", "fecha", "persona", "ubicacion", "condicion", "causa", "procedimiento",
               "lista", "si_no"}


def _modulo(nombre: str):
    spec = importlib.util.spec_from_file_location(f"banco_universal_{nombre}", RAIZ / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def bancos():
    return {i: cargar_banco(RAIZ / i / "manifiesto.json") for i in IDIOMAS}


def _textos(idioma: str, banco) -> dict[str, str]:
    carpeta = RAIZ / idioma / banco.manifiesto.corpus.directorio
    return {a.doc_id: parsear_documento(str(carpeta / a.ruta), doc_id=a.doc_id, doc_titulo=a.doc_id,
                                        version="1").texto_completo for a in banco.manifiesto.corpus.archivos}


def test_se_carga_sin_red(monkeypatch):
    def sin_red(*_a, **_k):
        raise AssertionError("el banco universal no debe usar la red")

    monkeypatch.setattr(socket, "socket", sin_red)
    for idioma in IDIOMAS:
        assert cargar_banco(RAIZ / idioma / "manifiesto.json").casos


def test_derivados_coinciden_con_las_fuentes():
    construir = _modulo("construir")
    for idioma in IDIOMAS:
        manifiesto, casos = construir.construir(idioma)
        assert (RAIZ / idioma / "manifiesto.json").read_text(encoding="utf-8") == manifiesto, idioma
        assert (RAIZ / idioma / "banco.jsonl").read_text(encoding="utf-8") == casos, idioma


def test_tamano_balance_e_ids(bancos):
    ids = [c.id for b in bancos.values() for c in b.casos]
    assert len(ids) == 90 and len(set(ids)) == 90
    distribucion = {i: Counter(c.id.split("-")[1] for c in b.casos) for i, b in bancos.items()}
    esperado = {"exacta": 10, "parafrasis": 5, "trampa": 10, "fuera": 3, "premisa": 1, "ambigua": 1}
    assert all(d == esperado for d in distribucion.values()), distribucion
    for idioma, banco in bancos.items():
        assert all(c.id.startswith(f"{idioma}-") for c in banco.casos)  # sin cruce de idiomas
        assert banco.manifiesto.dataset_id == f"universal_{idioma}"


def test_respondibles_literales_en_sus_offsets(bancos):
    for idioma, banco in bancos.items():
        textos = _textos(idioma, banco)
        validar_evidencias_contra_corpus(banco, textos)
        for caso in banco.casos:
            if caso.respondible:
                evidencia = caso.evidencias[0]
                assert evidencia.doc_id in textos
                assert caso.respuesta_literal in evidencia.texto
                assert textos[evidencia.doc_id].count(caso.respuesta_literal) >= 1


def test_trampas_sin_respuesta_y_en_par_con_una_respondible(bancos):
    for banco in bancos.values():
        por_id = {c.id: c for c in banco.casos}
        trampas = [c for c in banco.casos if c.subtipo == "trampa_mismo_tema"]
        assert len(trampas) == 10
        for trampa in trampas:
            assert not trampa.respondible and trampa.respuesta_literal is None and not trampa.evidencias
            par = por_id[trampa.par]
            assert par.respondible and par.evidencias  # mismo documento: el de su par
            assert par.split == trampa.split  # el par se mide en el mismo split


def test_cubre_las_capacidades_en_cada_idioma(bancos):
    for idioma, banco in bancos.items():
        capacidades = {c.notas.removeprefix("capacidad: ") for c in banco.casos if c.respondible}
        assert capacidades == CAPACIDADES, idioma


def test_el_banco_universal_es_de_regresion(bancos):
    for banco in bancos.values():
        assert banco.manifiesto.uso == "regresion"
    golden = cargar_banco(Path(__file__).resolve().parents[1] / "datos" / "banco" / "manifiesto.json")
    assert golden.manifiesto.uso == "evaluacion"
    # Ningún código del producto apunta al banco universal: no se usa por defecto.
    raiz_rag = Path(__file__).resolve().parents[2] / "ipsis"
    assert not [p for p in raiz_rag.rglob("*.py") if re.search(r"banco_universal", p.read_text(encoding="utf-8"))]


# --- invariante de v2 por perfil (lenta, requiere modelos) ---------------------------------
E5 = "intfloat/multilingual-e5-small"
MEDIUM = ("onnx-community/bge-reranker-v2-m3-ONNX", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")


@pytest.mark.slow
@pytest.mark.parametrize("perfil", [
    pytest.param("light", marks=pytest.mark.modelos(E5)),
    pytest.param("medium", marks=pytest.mark.modelos(E5, *MEDIUM)),
])
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_v2_nunca_responde_ok_y_cada_caso_deja_su_decision(perfil, idioma):
    """v2 publica fuentes y no decide «ok» (ADR 0012): ningún caso del banco puede salir «ok»,
    así que tampoco hay falsos ok. La calidad de la recuperación se vigila con ``tests/datos/banco_general``."""
    linea_base = _modulo("linea_base")
    artefacto = linea_base.evaluar_artefacto(idioma, perfil)
    actual = linea_base.resumir(artefacto)
    assert actual["falsos_ok"] == [] and actual["directas_sin_literal"] == []
    assert all(g["ok"] == 0 for g in actual["grupos"].values()), actual["grupos"]
    # Las observaciones guardan la decisión auditable de cada caso.
    cobertura = artefacto.reporte.cobertura
    assert set(cobertura.por_idioma) == {idioma}
    for fila in cobertura.casos:
        if fila.grupo != "conversacional":
            assert fila.regla, fila.caso_id
    assert cargar_banco(RAIZ / idioma / "manifiesto.json").manifiesto.uso == "regresion"  # medirlo no lo vuelve evaluación
