"""PDF escaneados: uno que no se puede leer no bloquea a los demás, y las páginas
sin texto de un PDF mixto se avisan en vez de perderse en silencio."""
from __future__ import annotations

import io
from pathlib import Path

import pypdf

from apoyo import _pdf_pagina_con_lineas, _pdf_pagina_vacia
from ipsis.ingesta.catalogo import agregar_documentos_al_catalogo, cargar_catalogo
from ipsis.ingesta.parsear import parsear_pdf


def test_un_pdf_escaneado_no_impide_cargar_los_demas(tmp_path: Path):
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "a_escaneado.pdf").write_bytes(_pdf_pagina_vacia())
    (origen / "b_notas.md").write_text("# Notas\n\nEl plazo es de diez dias.\n", encoding="utf-8")
    corpus, catalogo = tmp_path / "documents", tmp_path / "documents" / "catalog.yaml"

    resultado = agregar_documentos_al_catalogo([str(p) for p in sorted(origen.iterdir())],
                                               carpeta_corpus=str(corpus), ruta_catalogo=str(catalogo))

    rechazado, cargado = resultado
    assert rechazado.archivo == "a_escaneado.pdf" and "OCR" in rechazado.rechazo
    assert cargado.rechazo is None and cargado.archivo == "b_notas.md"
    assert [e["archivo"] for e in cargar_catalogo(str(catalogo))] == ["b_notas.md"]
    assert not (corpus / "a_escaneado.pdf").exists()  # no queda un archivo huérfano


def test_pdf_mixto_avisa_las_paginas_sin_texto(tmp_path: Path):
    escritor = pypdf.PdfWriter()
    for pagina in (_pdf_pagina_con_lineas([("Garantia", 18), ("La garantia dura dos anos desde la compra.", 11)]),
                   _pdf_pagina_vacia(),
                   _pdf_pagina_con_lineas([("Uso", 18), ("Encienda el equipo con el boton verde.", 11)])):
        escritor.append(pypdf.PdfReader(io.BytesIO(pagina)))
    ruta = tmp_path / "mixto.pdf"
    with open(ruta, "wb") as f:
        escritor.write(f)

    doc = parsear_pdf(str(ruta), doc_id="m", doc_titulo="M", version="1")

    assert any("1" in a and "3" in a and ": 2." in a for a in doc.advertencias), doc.advertencias
    assert any("Encienda" in b.texto for b in doc.bloques)  # lo que sí tiene texto se indexa


# --- OCR -------------------------------------------------------------------------------------
def test_con_ocr_un_pdf_escaneado_se_lee_y_se_avisa(tmp_path: Path, monkeypatch):
    import ipsis.ingesta.ocr as ocr

    leido = "Garantia\n\nLa garantia dura dos anos desde la compra del equipo."
    monkeypatch.setattr(ocr, "motor_ocr", lambda idioma: (ocr.MotorOCR("spa+eng"), ""))
    monkeypatch.setattr(ocr, "leer_paginas", lambda ruta, indices, motor: {i: leido for i in indices})
    ruta = tmp_path / "escaneado.pdf"
    ruta.write_bytes(_pdf_pagina_vacia())

    doc = parsear_pdf(str(ruta), doc_id="e", doc_titulo="E", version="1")

    assert [b.texto for b in doc.bloques if b.tipo_contenido != "titulo"] == [
        "La garantia dura dos anos desde la compra del equipo."]
    assert any("OCR" in a and "spa+eng" in a for a in doc.advertencias)
    assert doc.texto_completo[doc.bloques[-1].offset_inicio:doc.bloques[-1].offset_fin] == doc.bloques[-1].texto


def test_las_lineas_en_blanco_del_ocr_no_parten_los_parrafos(tmp_path: Path, monkeypatch):
    """Salida real de Tesseract con renglones separados: una línea en blanco entre cada uno."""
    import ipsis.ingesta.ocr as ocr

    leido = ("Garantía\n\nLa cafetera Brio tiene una garantía de veinticuatro\n\nmeses desde la fecha de compra."
             "\n\nLa garantía cubre:\n- el motor y la bomba de presión;\n\n- el depósito de agua.\n")
    monkeypatch.setattr(ocr, "motor_ocr", lambda idioma: (ocr.MotorOCR("spa+eng"), ""))
    monkeypatch.setattr(ocr, "leer_paginas", lambda ruta, indices, motor: {i: leido for i in indices})
    ruta = tmp_path / "escaneado.pdf"
    ruta.write_bytes(_pdf_pagina_vacia())

    doc = parsear_pdf(str(ruta), doc_id="e", doc_titulo="E", version="1")

    assert [(b.tipo_contenido, b.texto) for b in doc.bloques] == [
        ("titulo", "Garantía"),
        ("narrativo", "La cafetera Brio tiene una garantía de veinticuatro meses desde la fecha de compra."),
        ("narrativo", "La garantía cubre:"),
        ("lista", "- el motor y la bomba de presión;"),
        ("lista", "- el depósito de agua."),
    ]


def test_sin_ocr_el_rechazo_explica_como_activarlo(tmp_path: Path, monkeypatch):
    import pytest

    from ipsis.ingesta.parsear import DocumentoEscaneadoError

    ruta = tmp_path / "escaneado.pdf"
    ruta.write_bytes(_pdf_pagina_vacia())
    monkeypatch.setenv("IPSIS_OCR", "off")
    with pytest.raises(DocumentoEscaneadoError, match="IPSIS_OCR=off"):
        parsear_pdf(str(ruta), doc_id="e", doc_titulo="E", version="1")
    monkeypatch.delenv("IPSIS_OCR")
    import ipsis.ingesta.ocr as ocr

    motor, motivo = ocr.motor_ocr("es")
    if motor is None:  # sin el extra o sin Tesseract: el motivo dice qué instalar
        assert "Tesseract" in motivo


def test_ocr_real_si_tesseract_esta_instalado(tmp_path: Path):
    import pytest

    from PIL import Image, ImageDraw, ImageFont

    import ipsis.ingesta.ocr as ocr

    motor, motivo = ocr.motor_ocr("es")
    if motor is None:
        pytest.skip(motivo)
    imagen = Image.new("RGB", (1700, 600), "white")
    dibujo = ImageDraw.Draw(imagen)
    dibujo.text((80, 120), "La garantía dura veinticuatro meses.", fill="black",
                font=ImageFont.load_default(size=64))
    dibujo.text((80, 300), "Cambie el filtro cada seis meses.", fill="black",
                font=ImageFont.load_default(size=64))
    ruta = tmp_path / "foto.pdf"
    imagen.save(ruta, "PDF", resolution=200)

    doc = parsear_pdf(str(ruta), doc_id="f", doc_titulo="F", version="1")
    texto = doc.texto_completo.lower()
    assert "veinticuatro" in texto and "filtro" in texto
    assert any("OCR" in a for a in doc.advertencias)
