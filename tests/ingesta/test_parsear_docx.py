"""Tests del parser DOCX con un documento sintético."""
from rag.ingesta.parsear import parsear_docx


def _parsear(ruta_docx_sintetico):
    return parsear_docx(
        str(ruta_docx_sintetico), doc_id="manual-x100",
        doc_titulo="Manual del Equipo X100", version="1",
    )


def test_offsets_reconstructivos_todos_los_bloques(ruta_docx_sintetico):
    doc = _parsear(ruta_docx_sintetico)
    assert doc.bloques
    for bloque in doc.bloques:
        assert doc.texto_completo[bloque.offset_inicio:bloque.offset_fin] == bloque.texto


def test_offsets_son_crecientes_y_no_se_solapan(ruta_docx_sintetico):
    doc = _parsear(ruta_docx_sintetico)
    for anterior, actual in zip(doc.bloques, doc.bloques[1:]):
        assert actual.offset_inicio >= anterior.offset_fin


def test_seccion_path_se_actualiza_con_encabezados(ruta_docx_sintetico):
    doc = _parsear(ruta_docx_sintetico)
    bloque = next(b for b in doc.bloques if "botón verde" in b.texto)
    assert bloque.seccion_path[-1] == "Operación"


def test_captura_encabezados(ruta_docx_sintetico):
    doc = _parsear(ruta_docx_sintetico)
    secciones = {b.seccion_path[-1] for b in doc.bloques if b.seccion_path}
    assert {"Operación", "Mantenimiento"} <= secciones


def test_tablas_se_capturan_como_filas(ruta_docx_sintetico):
    doc = _parsear(ruta_docx_sintetico)
    filas = [b for b in doc.bloques if b.tipo_contenido == "tabla"]
    assert filas
    assert any("30 días" in b.texto for b in filas)


def test_hash_documento_es_determinista(ruta_docx_sintetico):
    assert _parsear(ruta_docx_sintetico).hash_documento == _parsear(ruta_docx_sintetico).hash_documento
