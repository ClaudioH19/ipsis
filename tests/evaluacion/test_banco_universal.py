"""Banco universal (tests/datos/banco_universal): regresión del software en es, en y pt.

Las pruebas estructurales no usan modelos ni red. La prueba lenta mide cada
perfil y falla si los falsos ok superan la línea base registrada: detecta
regresiones sin exigir hoy un resultado que corresponde a P10.
"""
from __future__ import annotations

import importlib.util
import json
import re
import socket
from collections import Counter
from pathlib import Path

import pytest

from rag.evaluacion.banco import cargar_banco, exigir_calibrable, validar_evidencias_contra_corpus
from rag.ingesta.parsear import parsear_documento

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


def test_el_banco_universal_no_calibra(bancos):
    for banco in bancos.values():
        assert banco.manifiesto.uso == "regresion"
        with pytest.raises(ValueError, match="no para calibrar"):
            exigir_calibrable(banco)
    golden = cargar_banco(Path(__file__).resolve().parents[1] / "datos" / "banco" / "manifiesto.json")
    exigir_calibrable(golden)  # un banco de evaluación sí
    # Ningún código del producto apunta al banco universal: no se usa por defecto.
    raiz_rag = Path(__file__).resolve().parents[2] / "rag"
    assert not [p for p in raiz_rag.rglob("*.py") if re.search(r"banco_universal", p.read_text(encoding="utf-8"))]


# --- línea base por perfil (lenta, requiere modelos) ---------------------------------
E5 = "intfloat/multilingual-e5-small"
MEDIUM = ("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "dewdev/mdeberta-v3-base-squad2-onnx")


@pytest.mark.slow
@pytest.mark.parametrize("perfil", [
    pytest.param("light", marks=pytest.mark.modelos(E5)),
    pytest.param("medium", marks=pytest.mark.modelos(E5, *MEDIUM)),
])
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_falsos_ok_no_superan_la_linea_base(perfil, idioma):
    """Regresión, no objetivo de seguridad: la línea base registra los falsos ok
    de hoy para detectar uno nuevo; no los declara aceptables."""
    linea_base = _modulo("linea_base")
    referencia = json.loads((RAIZ / "linea_base.json").read_text(encoding="utf-8"))[perfil][idioma]
    artefacto = linea_base.evaluar_artefacto(idioma, perfil)
    actual = linea_base.resumir(artefacto)
    nuevos = sorted(set(actual["falsos_ok"]) - set(referencia["falsos_ok"]))
    assert not nuevos, f"falsos ok nuevos respecto de la línea base: {nuevos}"
    # La evidencia mostrada en cada ok respondible sigue siendo literal.
    for nombre in ("exacta", "parafrasis"):
        grupo = actual["grupos"][nombre]
        assert grupo["ok_literal"] == grupo["ok"], (nombre, grupo)
    # Las observaciones guardan la decisión auditable de cada caso…
    cobertura = artefacto.reporte.cobertura
    assert set(cobertura.por_idioma) == {idioma}
    for fila in cobertura.casos:
        if fila.grupo != "conversacional":
            assert fila.regla and fila.senales is not None, fila.caso_id
            assert (fila.senales.s_qa is None) == (perfil == "light")  # sin lector no hay s_qa
    # La calibración re-decide con la misma regla que producción: con los
    # umbrales del perfil reproduce exactamente cada estado observado.
    from rag.configuracion.perfiles import perfil_efectivo
    from rag.evaluacion.calibracion import redecidir

    umbrales = perfil_efectivo(perfil).umbrales_por_defecto
    for obs in artefacto.observaciones:
        assert redecidir(obs, umbrales).estado == obs.estado, (obs.caso_id, obs.regla)
    # …y medir el banco universal no lo vuelve calibrable.
    with pytest.raises(ValueError, match="no para calibrar"):
        exigir_calibrable(cargar_banco(RAIZ / idioma / "manifiesto.json"))
