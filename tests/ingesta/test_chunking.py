"""Tests de chunking sobre un documento sintético."""

import pytest

from ipsis.ingesta.parsear import parsear_docx, DocumentoParseado
from ipsis.ingesta.chunking import ESTRATEGIAS

@pytest.fixture(scope="module")
def documento(ruta_docx_sintetico) -> DocumentoParseado:
    return parsear_docx(
        str(ruta_docx_sintetico), doc_id="manual-x100",
        doc_titulo="Manual del Equipo X100", version="1",
    )


def _texto_bloques_contenido(doc: DocumentoParseado) -> set:
    return {(b.indice, b.texto) for b in doc.bloques if b.tipo_contenido != "titulo"}


@pytest.mark.parametrize("nombre_estrategia", list(ESTRATEGIAS.keys()))
def test_chunk_offsets_coinciden_con_texto_completo(documento, nombre_estrategia):
    chunks = ESTRATEGIAS[nombre_estrategia](documento)
    assert len(chunks) > 0
    for ch in chunks:
        extraido = documento.texto_completo[ch.offset_inicio:ch.offset_fin]
        assert extraido == ch.texto


@pytest.mark.parametrize("nombre_estrategia", list(ESTRATEGIAS.keys()))
def test_no_pierde_bloques_de_contenido(documento, nombre_estrategia):
    """Todo bloque de contenido (no título) debe quedar cubierto por al menos un chunk."""
    chunks = ESTRATEGIAS[nombre_estrategia](documento)
    indices_cubiertos = set()
    for ch in chunks:
        indices_cubiertos.update(ch.bloques_origen)
    indices_contenido = {b.indice for b in documento.bloques if b.tipo_contenido != "titulo"}
    faltantes = indices_contenido - indices_cubiertos
    assert not faltantes, f"Bloques de contenido no incluidos en ningún chunk: {faltantes}"


@pytest.mark.parametrize("nombre_estrategia", ["CH-PAR", "CH-SEC", "CH-ORA"])
def test_estrategias_no_solapadas_no_duplican_texto(documento, nombre_estrategia):
    """CH-PAR, CH-SEC y CH-ORA no solapan (a diferencia de CH-F*, que solapa
    deliberadamente): cada carácter de contenido debe aparecer en exactamente
    un chunk."""
    chunks = ESTRATEGIAS[nombre_estrategia](documento)
    rangos = sorted((c.offset_inicio, c.offset_fin) for c in chunks)
    for (ini1, fin1), (ini2, fin2) in zip(rangos, rangos[1:]):
        assert fin1 <= ini2, f"Chunks solapados: [{ini1},{fin1}) y [{ini2},{fin2})"


def test_chunking_tamano_fijo_solapa_pero_no_pierde_contenido(documento):
    chunks = ESTRATEGIAS["CH-F256"](documento)
    # el solape es deliberado: verifica que la unión de rangos cubre todo el contenido
    cobertura = [False] * len(documento.texto_completo)
    for ch in chunks:
        for i in range(ch.offset_inicio, ch.offset_fin):
            cobertura[i] = True
    indices_contenido = [b for b in documento.bloques if b.tipo_contenido != "titulo"]
    for b in indices_contenido:
        assert all(cobertura[b.offset_inicio:b.offset_fin]), f"Bloque {b.indice} no cubierto"



@pytest.mark.parametrize("nombre_estrategia", list(ESTRATEGIAS.keys()))
def test_cada_chunk_sabe_donde_empieza_cada_seccion(documento, nombre_estrategia):
    for ch in ESTRATEGIAS[nombre_estrategia](documento):
        assert ch.secciones and ch.secciones[0][2] == ch.seccion_path
        assert ch.secciones[0][0] == ch.offset_inicio and ch.secciones[-1][1] <= ch.offset_fin
        for (_, fin, ruta), (ini, _, siguiente) in zip(ch.secciones, ch.secciones[1:]):
            assert fin <= ini and ruta != siguiente


# ---------------------------------------------------------------------------
# CH-F256S: respeta secciones y oraciones
# ---------------------------------------------------------------------------
from pathlib import Path

from ipsis.ingesta.chunking import _oraciones, chunking_tamano_fijo_secciones
from ipsis.ingesta.parsear import parsear_documento


def _md(tmp_path, texto, nombre="doc.md"):
    ruta = Path(tmp_path) / nombre
    ruta.write_text(texto, encoding="utf-8")
    return parsear_documento(str(ruta), doc_id="d", doc_titulo="D", version="1")


def _oracion(n, prefijo="Esta"):
    return f"{prefijo} oración número {n} tiene exactamente nueve palabras en total."


def _documento_largo(tmp_path):
    secciones = []
    for s in range(3):
        parrafos = [" ".join(_oracion(s * 100 + p * 10 + k) for k in range(8)) for p in range(7)]
        secciones.append(f"## Sección {s}\n\n" + "\n\n".join(parrafos))
    return _md(tmp_path, "# Doc\n\n" + "\n\n".join(secciones) + "\n")


def test_f256s_esta_registrada_y_no_cambia_f256():
    assert "CH-F256S" in ESTRATEGIAS
    assert "CH-F256" in ESTRATEGIAS


def test_f256s_nunca_cruza_de_seccion(tmp_path):
    doc = _documento_largo(tmp_path)
    chunks = chunking_tamano_fijo_secciones(doc, 256)
    por_indice = {b.indice: b for b in doc.bloques}
    assert len(chunks) > 3
    for ch in chunks:
        assert len({tuple(por_indice[i].seccion_path) for i in ch.bloques_origen}) == 1
        assert ch.seccion_path == por_indice[ch.bloques_origen[0]].seccion_path
        assert ch.secciones == [(ch.offset_inicio, ch.offset_fin, ch.seccion_path)]


def test_f256s_no_pasa_del_maximo_ni_corta_oraciones(tmp_path):
    doc = _documento_largo(tmp_path)
    chunks = chunking_tamano_fijo_secciones(doc, 256)
    for ch in chunks:
        assert doc.texto_completo[ch.offset_inicio:ch.offset_fin] == ch.texto
        assert len(ch.texto.split()) <= 256
        assert ch.texto.rstrip().endswith(".") and ch.texto[0].isupper()


def test_f256s_cubre_todo_el_contenido_y_sin_solape_no_lo_duplica(tmp_path):
    doc = _documento_largo(tmp_path)
    contenido = [b for b in doc.bloques if b.tipo_contenido != "titulo"]
    cubierto = [0] * len(doc.texto_completo)
    for ch in chunking_tamano_fijo_secciones(doc, 256, solape_pct=0):
        for i in range(ch.offset_inicio, ch.offset_fin):
            cubierto[i] += 1
    for b in contenido:
        for i in range(b.offset_inicio, b.offset_fin):
            if not doc.texto_completo[i].isspace():
                assert cubierto[i] == 1, (b.indice, i)


def test_f256s_solapa_en_oraciones_completas_dentro_de_la_seccion(tmp_path):
    doc = _documento_largo(tmp_path)
    chunks = [c for c in chunking_tamano_fijo_secciones(doc, 256) if c.seccion_path == ["Doc", "Sección 0"]]
    assert len(chunks) >= 2
    for a, b in zip(chunks, chunks[1:]):
        assert b.offset_inicio < a.offset_fin  # hay solape
        assert b.offset_inicio > a.offset_inicio  # y siempre avanza
        # el solape es de ~15 %: entre 1 y 38 palabras, en oraciones completas
        solape = doc.texto_completo[b.offset_inicio:a.offset_fin]
        assert 0 < len(solape.split()) <= 38 and solape.rstrip().endswith(".")


def test_f256s_parte_un_parrafo_largo_en_oraciones(tmp_path):
    parrafo = " ".join(_oracion(k) for k in range(60))  # ~540 palabras en un solo bloque
    doc = _md(tmp_path, f"# T\n\n## S\n\n{parrafo}\n")
    chunks = chunking_tamano_fijo_secciones(doc, 256)
    assert len(chunks) >= 3
    assert all(len(c.texto.split()) <= 256 for c in chunks)
    assert all(c.bloques_origen == chunks[0].bloques_origen for c in chunks)


def test_f256s_una_oracion_mas_larga_que_el_maximo_queda_sola(tmp_path):
    larga = "Esta oración " + "muy " * 300 + "larga termina aquí."
    doc = _md(tmp_path, f"# T\n\n## S\n\nUna corta. {larga} Otra corta.\n")
    chunks = chunking_tamano_fijo_secciones(doc, 256)
    excedidos = [c for c in chunks if len(c.texto.split()) > 256]
    assert len(excedidos) == 1 and excedidos[0].texto == larga


@pytest.mark.parametrize("texto,esperadas", [
    ("Ver el art. 5 de la ley. Luego siga.", ["Ver el art. 5 de la ley.", "Luego siga."]),
    ("Contacte al Sr. Pérez hoy. Gracias.", ["Contacte al Sr. Pérez hoy.", "Gracias."]),
    ("Presente el Nº 4 completo. Después firme.", ["Presente el Nº 4 completo.", "Después firme."]),
    ("Use papel, p. ej. carta u oficio. Fin.", ["Use papel, p. ej. carta u oficio.", "Fin."]),
    ("Use files, e.g. Word or PDF. Done.", ["Use files, e.g. Word or PDF.", "Done."]),
    ("Pregunte a J. Pérez ahora. ¿Quién firma? Nadie; Todos firman.", ["Pregunte a J. Pérez ahora.", "¿Quién firma?", "Nadie;", "Todos firman."]),
    ("Primera línea\nSegunda línea sin punto", ["Primera línea", "Segunda línea sin punto"]),
    ("Costo de 3.5 UF por mes. Fin.", ["Costo de 3.5 UF por mes.", "Fin."]),
])
def test_separador_de_oraciones_y_abreviaturas(texto, esperadas):
    rangos = _oraciones(texto, 100)
    assert [texto[a - 100:b - 100] for a, b in rangos] == esperadas


def test_f256s_es_determinista(tmp_path):
    doc = _documento_largo(tmp_path)
    a = [(c.chunk_id, c.offset_inicio, c.offset_fin) for c in chunking_tamano_fijo_secciones(doc, 256)]
    b = [(c.chunk_id, c.offset_inicio, c.offset_fin) for c in chunking_tamano_fijo_secciones(doc, 256)]
    assert a == b
