"""Tests de chunking sobre un documento sintético."""

import pytest

from rag.parsear import parsear_docx, DocumentoParseado
from rag.chunking import ESTRATEGIAS

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
