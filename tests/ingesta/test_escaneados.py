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
