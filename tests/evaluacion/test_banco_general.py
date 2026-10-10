"""Corpus congelado y guardia por caso: se ejecuta siempre, sin modelos ni red."""
import importlib.util
from pathlib import Path

import pytest

from ipsis.evaluacion.banco import cargar_banco, exigir_calibrable, validar_evidencias_contra_corpus
from ipsis.ingesta.parsear import parsear_documento

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "tests/datos/banco_general"


def general():
    spec = importlib.util.spec_from_file_location("regresion_general", RAIZ / "herramientas/evaluacion/general.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("calidad", ["bueno", "medio", "malo"])
def test_cada_calidad_tiene_mismos_hechos_preguntas_y_offsets_congelados(calidad):
    ruta = BANCO / calidad
    banco = cargar_banco(ruta / "manifiesto.json")
    base = cargar_banco(BANCO / "bueno/manifiesto.json")
    assert len(banco.casos) == 28
    assert banco.manifiesto.dataset_version == "1.1.0"
    assert {c.pregunta for c in banco.casos if c.id.startswith("referencia-")} == {"¿Quién lo aprueba?", "¿Cuánto es?"}
    assert sum(c.respondible for c in banco.casos) == 12
    assert {a.doc_id for a in banco.manifiesto.corpus.archivos} == {"rrhh", "compras", "tecnico", "logistica"}
    assert {Path(a.ruta).suffix for a in banco.manifiesto.corpus.archivos} == {".md", ".pdf", ".docx", ".txt"}
    assert [(c.id, c.pregunta, c.respuesta_literal) for c in banco.casos] == [(c.id, c.pregunta, c.respuesta_literal) for c in base.casos]
    textos = {a.doc_id: parsear_documento(str(ruta / "corpus" / a.ruta), doc_id=a.doc_id, doc_titulo=a.doc_id,
                                         version="1").texto_completo for a in banco.manifiesto.corpus.archivos}
    validar_evidencias_contra_corpus(banco, textos)
    with pytest.raises(ValueError):
        exigir_calibrable(banco)


def fila(id_, correcta=True, error=False):
    return {"caso_id": id_, "directa": correcta or error, "falso_ok": error, "directa_sin_literal": False}


def reporte(casos, sha="mismo", p95=100):
    return {"criterio": "respuesta_completa_v2", "hardware": {"cpu": "misma"}, "resultados": [
        {"nombre": "medium", "dataset_id": "general", "dataset_sha256": sha,
         "casos": casos, "latencia": {"p95": p95}, "presupuesto_p95_ms": 150}]}


def test_un_acierto_nuevo_no_oculta_la_perdida_de_otro():
    m = general()
    base = reporte([fila("a"), fila("b", False)])
    actual = reporte([fila("a", False), fila("b")])
    assert any("perdió aciertos" in f for f in m.comparar(actual, base))


def test_cambiar_el_error_entre_casos_no_pasa_por_conservar_el_total():
    m = general()
    base = reporte([fila("a", False, True), fila("b", False)])
    actual = reporte([fila("a", False), fila("b", False, True)])
    assert any("nuevos errores" in f for f in m.comparar(actual, base))


def test_referencia_distinta_y_casos_omitidos_se_rechazan():
    m = general()
    base = reporte([fila("a"), fila("b")])
    assert m.comparar(reporte([fila("a")]), base)
    assert m.comparar(reporte([fila("a"), fila("b")], sha="otro"), base)


def test_presupuesto_relativo_admite_ruido_y_detecta_degradacion():
    m = general()
    base = reporte([fila("a")], p95=200)
    assert not m.comparar(reporte([fila("a")], p95=230), base)
    assert m.comparar(reporte([fila("a")], p95=300), base)


def test_no_permite_perder_aclaracion_aunque_ninguna_respuesta_sea_directa():
    m = general()
    anterior = {**fila("a", False), "respondible": False,
                "estado": "necesita_aclaracion", "estado_esperado": "necesita_aclaracion"}
    actual = {**anterior, "estado": "fuera_dominio"}
    assert any("aclaraciones" in f for f in m.comparar(reporte([actual]), reporte([anterior])))


def test_ejecucion_sin_resultados_no_puede_pasar():
    m = general()
    assert m.comparar({**reporte([]), "resultados": []}, reporte([fila("a")]))
