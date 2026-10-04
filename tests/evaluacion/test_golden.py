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
             "rag": {"subtipo": "trampa_mismo_tema", "par": "q1"}},
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


def test_separacion_por_estrato_reparte_exactas_y_parafrasis():
    """P10.3: con solo el tipo público, 3 exactas podían quedar todas en test."""
    filas = _filas(n_respondibles=6, n_trampas=0)
    estratos = {f.id: ("exacta" if i < 3 else "parafrasis") for i, f in enumerate(filas)}
    split = separar_dev_test(filas, estratos)
    for estrato in ("exacta", "parafrasis"):
        splits = {split[i] for i, e in estratos.items() if e == estrato}
        assert splits == {"dev", "test"}, estrato
    assert split == separar_dev_test(list(reversed(filas)), estratos)


def test_avisos_de_tamano_balance_y_certificacion():
    avisos = avisos_de_tamano(_filas(10, 2))
    assert any("prueba rápida" in a and "30" in a for a in avisos)  # chico: aviso, no error
    assert any("sin_respuesta o premisa_falsa" in a for a in avisos)
    assert any("no para certificar" in a and "59" in a for a in avisos)


def test_a_banco_ubica_clasifica_y_valida_contra_el_corpus():
    est, es = _est()
    filas = _filas(2, 1) + [
        FilaGolden(id="p1", pregunta="¿Cuándo vence la garantía?", tipo="respondible",
                   respuesta_literal="24 meses desde la fecha de compra"),
        FilaGolden(pregunta="hola", tipo="conversacional"),
    ]
    resultado = a_banco(filas, DOCS, CORPUS, estadisticas=est, paquete=es)
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
        FilaGolden(id="c", pregunta="¿Qué?", tipo="sin_respuesta", par="b", origen="g.csv:4"),
        FilaGolden(id="d", pregunta="¿Cuánto?", tipo="respondible", respuesta_literal="99 meses", origen="g.csv:5"),
    ]
    with pytest.raises(ErrorGolden) as exc:
        a_banco(filas, DOCS, CORPUS, estadisticas=est, paquete=es)
    texto = str(exc.value)
    assert "g.csv:2" in texto and "g.csv:3" in texto and "g.csv:4" in texto
    with pytest.raises(ErrorGolden, match="g.csv:5"):
        a_banco([filas[3]], DOCS, CORPUS, estadisticas=est, paquete=es)


def test_par_sin_completar_es_aviso_no_error():
    est, es = _est()
    filas = [FilaGolden(id="t1", pregunta="¿Qué incluye la garantía?", tipo="sin_respuesta",
                        subtipo="trampa_mismo_tema", par="r9", origen="g.csv:2")]
    resultado = a_banco(filas, DOCS, CORPUS, estadisticas=est, paquete=es)
    assert resultado.banco.casos[0].par is None
    assert any("r9" in a and "sin completar" in a for a in resultado.avisos)


# --- plantilla (P9.2) ------------------------------------------------------------
TEMAS = {
    "garantia": ["garantía cubre meses compra", "exclusiones daños golpes humedad", "boleta número serie reclamo",
                 "extensión garantía pago anual", "servicio técnico autorizado reparación", "reemplazo equipo falla"],
    "riego": ["riego goteo caudal litros hora", "presión bomba válvula filtro", "frecuencia riego verano invierno",
              "fertilizante dosis semana", "sensor humedad suelo lectura", "mantención mangueras limpieza"],
    "envios": ["envío regiones plazo días hábiles", "costo despacho tarifa peso", "seguimiento código pedido",
               "devolución producto dañado", "retiro tienda horario", "embalaje frágil recargo"],
}


def _corpus_sintetico():
    from rag.ingesta.parsear import Bloque, DocumentoParseado

    documentos = []
    for doc_id, temas in TEMAS.items():
        bloques, texto, pos = [], "", 0
        for i, tema in enumerate(temas):
            parrafo = f"La sección {i} trata de {tema}. Detalle: {tema} según el manual de {doc_id}."
            bloques.append(Bloque(indice=i, seccion_path=[f"{doc_id} {i}"], seccion_nivel=1,
                                  tipo_contenido="narrativo", texto=parrafo, offset_inicio=pos,
                                  offset_fin=pos + len(parrafo)))
            texto += parrafo + "\n"
            pos = len(texto)
        documentos.append(DocumentoParseado(doc_id=doc_id, doc_titulo=doc_id, version="1", ruta_origen="",
                                            texto_completo=texto, bloques=bloques))
    return documentos


def test_plantilla_cubre_documentos_con_pares_y_35_por_ciento_de_trampas():
    from rag.evaluacion.golden import generar_plantilla

    plantilla = generar_plantilla(_corpus_sintetico(), cargar_paquete("es"), n=20)
    filas = plantilla.filas
    assert len(filas) == 20 and plantilla.avisos == []
    assert {f["documento"] for f in filas if f["documento"]} == set(TEMAS)
    trampas = [f for f in filas if f["tipo"] == "sin_respuesta"]
    assert len(trampas) == 7  # 35% de 20
    respondibles = {f["id"]: f for f in filas if f["tipo"] == "respondible"}
    for trampa in trampas:
        assert trampa["subtipo"] == "trampa_mismo_tema"
        par = respondibles[trampa["par"]]  # cada trampa apunta a una respondible…
        assert par["documento"] == trampa["documento"]  # …de la misma sección
        assert par["fragmento_sugerido"] == trampa["fragmento_sugerido"]
        assert trampa["par"] in trampa["instrucciones"]
        assert trampa["notas"] == ""  # notas queda libre para quien completa
    conversacionales = [f for f in filas if f["tipo"] == "conversacional"]
    assert [f["pregunta"] for f in conversacionales] == ["hola", "gracias", "¿Qué puedes hacer?"]
    assert all(f["terminos_clave"] and not any(t.strip().isdigit() for t in f["terminos_clave"].split(","))
               for f in respondibles.values())


def test_plantilla_se_relee_y_se_importa_tras_completarla(tmp_path):
    from rag.evaluacion.golden import escribir_plantilla, generar_plantilla

    corpus = _corpus_sintetico()
    ruta_csv, ruta_leeme = escribir_plantilla(generar_plantilla(corpus, cargar_paquete("es"), n=20), tmp_path)
    assert "trampa_mismo_tema" in ruta_leeme.read_text(encoding="utf-8")
    assert ruta_csv.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM: Excel respeta las tildes
    assert [f.tipo for f in leer_csv(ruta_csv)] == ["conversacional"] * 3  # sin completar se ignoran

    # El cliente completa un par: la respondible y su trampa.
    import csv

    with ruta_csv.open(encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    respondible = next(f for f in filas if f["id"] == "r001")
    trampa = next(f for f in filas if f["par"] == "r001")
    documento = next(d for d in corpus if d.doc_id == respondible["documento"])
    respondible["pregunta"] = "¿De qué trata la sección?"
    respondible["respuesta_literal"] = documento.texto_completo.split(". ")[0].split(" de ", 1)[1]
    trampa["pregunta"] = "¿Quién aprueba eso?"
    with ruta_csv.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)

    leidas = leer_csv(ruta_csv)
    assert len(leidas) == 5
    textos = {d.doc_id: d.texto_completo for d in corpus}
    est = EstadisticasLexicas.construir(list(textos.values()), cargar_paquete("es"))
    resultado = a_banco(leidas, textos, CORPUS, estadisticas=est, paquete=cargar_paquete("es"))
    casos = {c.id: c for c in resultado.banco.casos}
    assert casos[trampa["id"]].par == "r001" and casos[trampa["id"]].subtipo == "trampa_mismo_tema"
    assert casos["r001"].respondible


@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_plantilla_en_cada_idioma(idioma):
    from rag.evaluacion.golden import generar_plantilla

    paquete = cargar_paquete(idioma)
    plantilla = generar_plantilla(_corpus_sintetico(), paquete, n=20)
    assert plantilla.leeme == paquete.golden_instrucciones.leeme
    assert "{" not in "".join(f["instrucciones"] for f in plantilla.filas)  # sin variables sin reemplazar
    assert [f["pregunta"] for f in plantilla.filas if f["tipo"] == "conversacional"] == \
        paquete.golden_instrucciones.conversacionales
    import re

    patrones = paquete.conversacional.patrones
    for pregunta in paquete.golden_instrucciones.conversacionales:  # el motor las reconoce como conversacionales
        assert any(re.search(p, pregunta.lower()) for lista in patrones.values() for p in lista), pregunta
