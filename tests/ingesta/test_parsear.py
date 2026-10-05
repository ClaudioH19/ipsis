"""Tests del despacho por extensión de `ipsis/ingesta/parsear.py`: PDF, Markdown y texto
plano. Cada documento de prueba lo construye el propio test, en un directorio temporal, sin material institucional -- nunca
se toca `documents/`.

La propiedad que se verifica en TODOS los formatos es la misma que ya prueba
`tests/ingesta/test_parsear_docx.py` para `.docx`: cada bloque debe reconstruirse
leyendo su rango de offsets en `texto_completo` (es la base del sistema de
citas). El propio parser ya lo verifica con `assert`; aquí se repite desde
afuera para que un futuro cambio que rompa esa invariante falle también en
la suite de tests, no solo en producción.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from apoyo import _combinar_con_outline, _pdf_pagina_con_texto, _pdf_pagina_vacia
from ipsis.ingesta.parsear import (
    DocumentoEscaneadoError,
    parsear_documento,
    parsear_markdown,
    parsear_pdf,
    parsear_texto_plano,
)


def _verifica_offsets(doc) -> None:
    assert len(doc.bloques) > 0
    for b in doc.bloques:
        extraido = doc.texto_completo[b.offset_inicio:b.offset_fin]
        assert extraido == b.texto


# ---------------------------------------------------------------------------
# Construcción de PDFs mínimos a mano (sin reportlab/fpdf, no son
# dependencias del proyecto): un PDF válido con un solo objeto de página, un
# stream de contenido con operadores de texto (`BT ... Tj ET`) y una tabla
# xref con offsets calculados en Python -- suficiente para que `pypdf` lo
# lea con `extract_text()` real, sin inventar la extracción.
# ---------------------------------------------------------------------------

def test_pdf_con_outline_asigna_seccion_path_por_marcador(tmp_path: Path):
    pagina1 = _pdf_pagina_con_texto("Contenido de la introduccion de prueba.")
    pagina2 = _pdf_pagina_con_texto("Contenido del capitulo dos de prueba.")
    datos = _combinar_con_outline(
        [pagina1, pagina2],
        [("Introduccion", 0), ("Capitulo Dos", 1)],
    )
    ruta = tmp_path / "manual.pdf"
    ruta.write_bytes(datos)

    doc = parsear_pdf(str(ruta), doc_id="manual", doc_titulo="Manual de prueba", version="1")
    _verifica_offsets(doc)

    # cada bloque narrativo queda bajo el título de SU página
    b_intro = next(b for b in doc.bloques if "introduccion" in b.texto.lower())
    assert b_intro.seccion_path == ["Introduccion"]
    b_cap2 = next(b for b in doc.bloques if "capitulo dos" in b.texto.lower())
    assert b_cap2.seccion_path == ["Capitulo Dos"]
    # con outline real, no se advierte por falta de secciones
    assert doc.advertencias == []


def test_pdf_sin_outline_no_tiene_secciones_y_advierte(tmp_path: Path):
    pagina1 = _pdf_pagina_con_texto("Texto de una pagina cualquiera sin marcadores.")
    ruta = tmp_path / "sin_outline.pdf"
    ruta.write_bytes(pagina1)

    doc = parsear_pdf(str(ruta), doc_id="d", doc_titulo="D", version="1")
    _verifica_offsets(doc)
    assert all(b.seccion_path == [] for b in doc.bloques)
    assert any("estructura de secciones" in a for a in doc.advertencias)


def test_pdf_escaneado_se_rechaza_en_vez_de_indexar_vacio(tmp_path: Path):
    ruta = tmp_path / "escaneado.pdf"
    ruta.write_bytes(_pdf_pagina_vacia())

    with pytest.raises(DocumentoEscaneadoError, match="(?i)escaneado"):
        parsear_pdf(str(ruta), doc_id="d", doc_titulo="D", version="1")


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

MARKDOWN_DOC = """# Manual del Equipo Ficticio X100

Este manual describe el mantenimiento del equipo ficticio X100, usado solo
para pruebas de este proyecto.

## Encendido

Para encender el equipo, presiona el botón verde durante tres segundos.

## Mantenimiento

### Limpieza semanal

Limpia el filtro con un paño seco cada semana.

### Revision mensual

Revisa las conexiones electricas una vez al mes.
"""


def test_markdown_headings_dan_seccion_path(tmp_path: Path):
    ruta = tmp_path / "manual.md"
    ruta.write_text(MARKDOWN_DOC, encoding="utf-8")

    doc = parsear_markdown(str(ruta), doc_id="manual", doc_titulo="Manual X100", version="1")
    _verifica_offsets(doc)

    b_encendido = next(b for b in doc.bloques if "botón verde" in b.texto)
    assert b_encendido.seccion_path == ["Manual del Equipo Ficticio X100", "Encendido"]

    b_limpieza = next(b for b in doc.bloques if "filtro" in b.texto)
    assert b_limpieza.seccion_path == [
        "Manual del Equipo Ficticio X100", "Mantenimiento", "Limpieza semanal",
    ]

    b_revision = next(b for b in doc.bloques if "conexiones" in b.texto)
    assert b_revision.seccion_path == [
        "Manual del Equipo Ficticio X100", "Mantenimiento", "Revision mensual",
    ]
    assert doc.advertencias == []


def test_markdown_sin_encabezados_advierte(tmp_path: Path):
    ruta = tmp_path / "plano.md"
    ruta.write_text("Solo un párrafo de texto, sin ningún encabezado '#'.", encoding="utf-8")

    doc = parsear_markdown(str(ruta), doc_id="d", doc_titulo="D", version="1")
    _verifica_offsets(doc)
    assert all(b.seccion_path == [] for b in doc.bloques)
    assert any("estructura de secciones" in a for a in doc.advertencias)


# ---------------------------------------------------------------------------
# Texto plano
# ---------------------------------------------------------------------------

def test_texto_plano_parrafos_separados_por_linea_en_blanco(tmp_path: Path):
    contenido = (
        "Primer párrafo del manual ficticio, sin estructura declarada.\n"
        "\n"
        "Segundo párrafo, con otra idea distinta del primero.\n"
        "\n\n"
        "Tercer párrafo, después de dos líneas en blanco seguidas.\n"
    )
    ruta = tmp_path / "notas.txt"
    ruta.write_text(contenido, encoding="utf-8")

    doc = parsear_texto_plano(str(ruta), doc_id="notas", doc_titulo="Notas", version="1")
    _verifica_offsets(doc)
    assert len(doc.bloques) == 3
    assert all(b.seccion_path == [] for b in doc.bloques)
    assert all(b.tipo_contenido == "narrativo" for b in doc.bloques)
    assert "Primer párrafo" in doc.bloques[0].texto
    assert "Segundo párrafo" in doc.bloques[1].texto
    assert "Tercer párrafo" in doc.bloques[2].texto
    assert any("estructura de secciones" in a for a in doc.advertencias)


# ---------------------------------------------------------------------------
# Despacho por extensión
# ---------------------------------------------------------------------------

def test_parsear_documento_despacha_por_extension(tmp_path: Path):
    md = tmp_path / "a.md"
    md.write_text("# Título\n\nContenido.\n", encoding="utf-8")
    doc_md = parsear_documento(str(md), doc_id="a", doc_titulo="A", version="1")
    assert doc_md.bloques[0].seccion_path == ["Título"]

    txt = tmp_path / "b.txt"
    txt.write_text("Un párrafo cualquiera.\n", encoding="utf-8")
    doc_txt = parsear_documento(str(txt), doc_id="b", doc_titulo="B", version="1")
    assert doc_txt.bloques[0].tipo_contenido == "narrativo"


def test_parsear_documento_formato_no_soportado_falla_explicito(tmp_path: Path):
    ruta = tmp_path / "archivo.rtf"
    ruta.write_text("contenido", encoding="utf-8")
    with pytest.raises(ValueError, match="no soportado"):
        parsear_documento(str(ruta), doc_id="x", doc_titulo="X", version="1")
