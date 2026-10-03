"""Golden del cliente: lectura, ubicación de respuestas y conversión al banco."""
from __future__ import annotations

import json

import pytest

from rag.evaluacion.banco import CategoriaPregunta, CorpusBanco, ArchivoCorpus, validar_evidencias_contra_corpus
from rag.evaluacion.golden import (
    ErrorGolden,
    FilaGolden,
    a_banco,
    avisos_de_tamano,
    leer_csv,
    leer_golden,
    leer_jsonl,
    leer_squad2,
    oracion_de,
    separar_dev_test,
    ubicar_respuesta,
)
from rag.indice.estadisticas import EstadisticasLexicas
from rag.lenguaje.paquete import cargar_paquete

DOCS = {
    "manual": "Garantía\nLa garantía cubre 24 meses desde la fecha de compra. No cubre golpes.\n"
              "Filtros\nEl filtro de sedimentos se cambia cada 6 meses.",
    "reglamento": "Reembolsos\nEl reembolso se paga en un plazo de 10 días hábiles.\n"
                  "La visita técnica se agenda en 10 días hábiles.",
}
CORPUS = CorpusBanco(directorio="../documentos", archivos=[ArchivoCorpus(ruta="m.md", doc_id="manual")],
                     sha256="0" * 64)


def _est():
    es = cargar_paquete("es")
    return EstadisticasLexicas.construir(list(DOCS.values()), es), es


# --- ubicación ---------------------------------------------------------------
def test_ubica_la_respuesta_literal_con_offsets_exactos():
    ubicacion, avisos = ubicar_respuesta("24 meses desde la fecha de compra", DOCS)
    assert ubicacion.doc_id == "manual"
    assert DOCS["manual"][ubicacion.inicio:ubicacion.fin] == "24 meses desde la fecha de compra"
    assert avisos == []


def test_ubica_con_espacios_colapsados_y_devuelve_el_texto_original():
    docs = {"d": "El equipo  produce\nhasta 190 litros por día."}
    ubicacion, _ = ubicar_respuesta("produce hasta 190 litros", docs)
    assert ubicacion.texto == "produce\nhasta 190 litros"
    assert docs["d"][ubicacion.inicio:ubicacion.fin] == ubicacion.texto


def test_respuesta_ausente_falla():
    with pytest.raises(ValueError, match="no aparece"):
        ubicar_respuesta("36 meses", DOCS)


def test_respuesta_repetida_avisa_y_documento_desambigua():
    ubicacion, avisos = ubicar_respuesta("10 días hábiles", DOCS)
    assert avisos and "2 veces" in avisos[0]
    ubicacion, avisos = ubicar_respuesta("6 meses", DOCS, documento="Manual del equipo",
                                          alias={"Manual del equipo": "manual"})
    assert ubicacion.doc_id == "manual" and avisos == []
    with pytest.raises(ValueError, match="documento desconocido"):
        ubicar_respuesta("6 meses", DOCS, documento="otro")


def test_la_evidencia_es_la_oracion_de_su_linea_sin_el_titulo():
    texto = DOCS["manual"]
    ini = texto.index("24 meses")
    a, b = oracion_de(texto, ini, ini + len("24 meses"))
    assert texto[a:b] == "La garantía cubre 24 meses desde la fecha de compra."


# --- lectura -------------------------------------------------------------------
def test_leer_csv_con_bom_y_punto_y_coma(tmp_path):
    ruta = tmp_path / "golden.csv"
    ruta.write_text("id;pregunta;tipo;respuesta_literal\nr1;¿Cuánto dura la garantía?;respondible;24 meses\n"
                    ";;;\n", encoding="utf-8-sig")
    filas = leer_csv(ruta)
    assert len(filas) == 1  # la fila vacía de la plantilla se ignora
    assert (filas[0].id, filas[0].tipo, filas[0].respuesta_literal) == ("r1", "respondible", "24 meses")
    assert filas[0].origen == "golden.csv:2"


def test_leer_csv_sin_columnas_obligatorias_falla(tmp_path):
    ruta = tmp_path / "g.csv"
    ruta.write_text("id,texto\n1,hola\n", encoding="utf-8")
    with pytest.raises(ErrorGolden, match="faltan las columnas"):
        leer_csv(ruta)


def test_leer_jsonl_y_squad2(tmp_path):
    jsonl = tmp_path / "g.jsonl"
    jsonl.write_text(json.dumps({"pregunta": "¿Y?", "tipo": "ambigua"}) + "\n", encoding="utf-8")
    assert leer_jsonl(jsonl)[0].tipo == "ambigua"

    squad = tmp_path / "g.json"
    squad.write_text(json.dumps({"version": "v2.0", "data": [{"title": "manual", "paragraphs": [{
        "context": "…", "qas": [
            {"id": "q1", "question": "¿Cuánto dura?", "answers": [{"text": "24 meses", "answer_start": 0}],
             "is_impossible": False},
            {"id": "q2", "question": "¿Qué incluye?", "answers": [], "is_impossible": True,
             "rag_subtipo": "trampa_mismo_tema", "rag_par": "q1"},
        ]}]}]}), encoding="utf-8")
    filas = leer_squad2(squad)
    assert [(f.tipo, f.documento, f.respuesta_literal) for f in filas] == [
        ("respondible", "manual", "24 meses"), ("sin_respuesta", "manual", None)]
    assert (filas[1].subtipo, filas[1].par) == ("trampa_mismo_tema", "q1")
    assert len(leer_golden(squad)) == 2
    with pytest.raises(ErrorGolden, match="formato no soportado"):
        leer_golden(tmp_path / "g.xlsx")


# --- separación y banco ----------------------------------------------------------
def _filas(n_respondibles=10, n_trampas=6):
    filas = [FilaGolden(id=f"r{i}", pregunta="¿Cuántos meses cubre la garantía?", tipo="respondible",
                        respuesta_literal="24 meses") for i in range(n_respondibles)]
    filas += [FilaGolden(id=f"t{i}", pregunta=f"¿Qué incluye la garantía {i}?", tipo="sin_respuesta",
                         subtipo="trampa_mismo_tema", par="r0") for i in range(n_trampas)]
    return filas


def test_separacion_estratificada_y_estable():
    filas = _filas()
    primera = separar_dev_test(filas)
    assert primera == separar_dev_test(list(reversed(filas)))
    for prefijo in ("r", "t"):
        splits = [s for i, s in primera.items() if i.startswith(prefijo)]
        assert splits.count("dev") == splits.count("test")


def test_avisos_de_tamano_balance_y_certificacion():
    errores, avisos = avisos_de_tamano(_filas(10, 2), minimo=30)
    assert errores and "al menos 30" in errores[0]
    assert any("sin_respuesta o premisa_falsa" in a for a in avisos)
    assert any("no para certificar" in a and "59" in a for a in avisos)


def test_a_banco_ubica_clasifica_y_valida_contra_el_corpus():
    est, es = _est()
    filas = _filas(2, 1) + [
        FilaGolden(id="p1", pregunta="¿Cuándo vence la garantía?", tipo="respondible",
                   respuesta_literal="24 meses desde la fecha de compra"),
        FilaGolden(pregunta="hola", tipo="conversacional"),
    ]
    resultado = a_banco(filas, DOCS, CORPUS, estadisticas=est, paquete=es, minimo=1)
    casos = {c.id: c for c in resultado.banco.casos}
    assert casos["r0"].categoria == CategoriaPregunta.EXACTA  # meses, cubre, garantía: en la oración
    assert casos["p1"].categoria == CategoriaPregunta.PARAFRASIS  # «vence» no está
    assert casos["t0"].subtipo == "trampa_mismo_tema" and casos["t0"].par == "r0"
    assert any(i.startswith("conversacional_") for i in casos)
    validar_evidencias_contra_corpus(resultado.banco, DOCS)


def test_a_banco_junta_todos_los_errores():
    est, es = _est()
    filas = [
        FilaGolden(id="a", pregunta="¿Precio?", tipo="respondible", origen="g.csv:2"),
        FilaGolden(id="b", pregunta="¿Otra?", tipo="inventado", origen="g.csv:3"),
        FilaGolden(id="c", pregunta="¿Qué?", tipo="sin_respuesta", par="zzz", origen="g.csv:4"),
        FilaGolden(id="d", pregunta="¿Cuánto?", tipo="respondible", respuesta_literal="99 meses", origen="g.csv:5"),
    ]
    with pytest.raises(ErrorGolden) as exc:
        a_banco(filas, DOCS, CORPUS, estadisticas=est, paquete=es, minimo=1)
    texto = str(exc.value)
    assert "g.csv:2" in texto and "g.csv:3" in texto and "g.csv:4" in texto
    with pytest.raises(ErrorGolden, match="g.csv:5"):
        a_banco([filas[3]], DOCS, CORPUS, estadisticas=est, paquete=es, minimo=1)
