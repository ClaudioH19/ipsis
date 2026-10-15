"""Preparación estructural de Markdown y texto plano (F2.3)."""
from __future__ import annotations

import pytest

from ipsis.ingesta.preparacion import preparar_documento, preparar_markdown, preparar_texto
from ipsis.ingesta.unidades import unidades_documento

MD = """# Manual

Introducción al manual.

## Reembolsos

Para personal de planta el plazo es de 30 días. Se paga por transferencia.

- Primer requisito
- Segundo requisito

### Excepciones

| Grupo | Plazo |
|---|---|
| Planta | 30 |
| Honorarios | 15 |

## Compras

Las compras menores las aprueba la jefatura.
"""

TXT = """Reglamento general

Primer párrafo del reglamento con varias palabras.

Segundo párrafo del reglamento.
"""


@pytest.fixture
def md(tmp_path):
    ruta = tmp_path / "manual.md"
    ruta.write_text(MD, encoding="utf-8")
    return ruta


def test_markdown_conserva_titulos_secciones_y_offsets_literales(md):
    d = preparar_markdown(md, doc_id="manual", doc_titulo="Manual")
    assert d.parser_version == "markdown-estructura-1" and d.preparation_version == "estructura-1"
    for e in d.elementos:  # la validación del modelo ya lo exige; aquí se ve explícito
        assert d.texto_completo[e.offset_inicio:e.offset_fin] == e.texto
    titulos = [(e.texto, e.metadata["nivel"], e.seccion_path) for e in d.elementos if e.tipo == "titulo"]
    assert titulos == [
        ("Manual", 1, ["Manual"]),
        ("Reembolsos", 2, ["Manual", "Reembolsos"]),
        ("Excepciones", 3, ["Manual", "Reembolsos", "Excepciones"]),
        ("Compras", 2, ["Manual", "Compras"]),
    ]
    por_id = {e.element_id: e for e in d.elementos}
    compras = next(e for e in d.elementos if e.texto == "Compras")
    assert por_id[compras.metadata["parent_id"]].texto == "Manual"
    parrafo = next(e for e in d.elementos if e.texto.startswith("Para personal"))
    assert parrafo.tipo == "parrafo" and parrafo.seccion_path == ["Manual", "Reembolsos"]
    assert por_id[parrafo.metadata["parent_id"]].texto == "Reembolsos"
    assert {e.tipo for e in d.elementos if e.texto.startswith("- ") or "requisito" in e.texto} == {"lista"}


def test_las_tablas_markdown_quedan_como_parrafos_y_se_avisa(md):
    d = preparar_markdown(md, doc_id="manual", doc_titulo="Manual")
    assert d.tablas == []
    filas = [e for e in d.elementos if e.metadata.get("origen") == "fila_tabla_markdown"]
    assert len(filas) == 3 and all(e.tipo == "parrafo" for e in filas)
    assert all(e.seccion_path == ["Manual", "Reembolsos", "Excepciones"] for e in filas)
    assert any("tablas Markdown" in a for a in d.advertencias)


def test_los_hijos_no_cruzan_de_seccion_y_apuntan_a_su_padre(md):
    d = preparar_markdown(md, doc_id="manual", doc_titulo="Manual")
    hijos, padres = unidades_documento(d, max_palabras=400, palabras_hijo=8)
    assert hijos and padres
    for hijo in hijos:
        padre = padres[hijo.parent_id]
        assert d.texto_completo[hijo.offset_inicio:hijo.offset_fin] == hijo.texto_fuente
        assert hijo.seccion_path == padre.seccion_path
        assert padre.offset_inicio <= hijo.offset_inicio <= hijo.offset_fin <= padre.offset_fin
        assert d.texto_completo[padre.offset_inicio:padre.offset_fin] == padre.texto_fuente
        # el padre completo está en una sola sección: ningún título dentro de su texto
        assert not any(t.texto in padre.texto_fuente.splitlines() for t in d.elementos if t.tipo == "titulo")
    assert {tuple(p.seccion_path) for p in padres.values()} >= {("Manual", "Reembolsos"), ("Manual", "Compras")}
    # el prefijo de búsqueda lleva el título del documento y la sección, no el texto citado
    assert hijos[0].texto_embedding.startswith("Manual\n")


def test_texto_plano_usa_los_titulos_que_reconoce_el_parser(tmp_path):
    ruta = tmp_path / "reglamento.txt"
    ruta.write_text(TXT, encoding="utf-8")
    d = preparar_texto(ruta, doc_id="reg", doc_titulo="Reglamento")
    assert d.parser_version == "texto-estructura-1"
    assert [e.tipo for e in d.elementos] == ["titulo", "parrafo", "parrafo"]
    assert d.elementos[1].seccion_path == ["Reglamento general"]
    hijos, padres = unidades_documento(d)
    assert len(padres) == 1 and all(h.parent_id in padres for h in hijos)


def test_preparar_documento_despacha_por_extension_y_rechaza_otros_formatos(md, tmp_path):
    assert preparar_documento(md, doc_id="a", doc_titulo="A").parser_version == "markdown-estructura-1"
    (tmp_path / "x.markdown").write_text(MD, encoding="utf-8")
    assert preparar_documento(tmp_path / "x.markdown", doc_id="b", doc_titulo="B").parser_version == "markdown-estructura-1"
    with pytest.raises(ValueError, match="DOCX"):
        preparar_documento(tmp_path / "x.rtf", doc_id="c", doc_titulo="C")


def test_es_determinista_y_el_hash_cambia_con_el_contenido(md, tmp_path):
    a = preparar_markdown(md, doc_id="m", doc_titulo="M")
    b = preparar_markdown(md, doc_id="m", doc_titulo="M")
    assert a.structure_hash == b.structure_hash and a.source_hash == b.source_hash
    otro = tmp_path / "otro.md"
    otro.write_text(MD.replace("30 días", "31 días"), encoding="utf-8")
    c = preparar_markdown(otro, doc_id="m", doc_titulo="M")
    assert c.structure_hash != a.structure_hash and c.source_hash != a.source_hash


def test_documento_sin_encabezados_se_prepara_con_aviso(tmp_path):
    ruta = tmp_path / "plano.md"
    ruta.write_text("Solo un párrafo sin encabezados.\n\nOtro párrafo.\n", encoding="utf-8")
    d = preparar_markdown(ruta, doc_id="p", doc_titulo="P")
    assert d.advertencias and all(e.seccion_path == [] for e in d.elementos)


def test_ipsis_prepare_funciona_con_un_proyecto_markdown(tmp_path, monkeypatch):
    from ipsis.aplicacion.preparacion import preparar_proyecto
    from ipsis.cli import main

    proyecto = tmp_path / "proyecto"
    proyecto.mkdir()
    monkeypatch.chdir(proyecto)
    assert main(["init", "--profile", "light"]) == 0
    fuente = tmp_path / "manual.md"
    fuente.write_text(MD, encoding="utf-8")
    assert main(["load", str(fuente)]) == 0
    resumen = preparar_proyecto(proyecto, tmp_path / "estructural")
    assert resumen.documentos == 1 and resumen.unidades >= 2 and resumen.hijos >= 2
    assert resumen.vista_previa.is_file() and any("tablas Markdown" in a for a in resumen.advertencias)


def test_la_ingesta_estructural_arma_payloads_de_markdown_sin_modelos(tmp_path, monkeypatch):
    from ipsis.cli import main
    from ipsis.ingesta.ingesta import parsear_corpus
    from ipsis.ingesta.metadata import cargar_taxonomia
    from ipsis.ingesta.unidades import construir_payloads_estructurados

    proyecto = tmp_path / "proyecto"
    proyecto.mkdir()
    monkeypatch.chdir(proyecto)
    assert main(["init", "--profile", "light"]) == 0
    fuente = tmp_path / "manual.md"
    fuente.write_text(MD, encoding="utf-8")
    assert main(["load", str(fuente)]) == 0
    docs = parsear_corpus("documents", "estructural_v1")
    opciones = {"modo": "estructural_v1", "max_palabras_unidad": 400, "palabras_hijo": 80}
    hijos, payloads, padres, preparados = construir_payloads_estructurados(docs, cargar_taxonomia(), opciones)
    assert preparados[0].parser_version == "markdown-estructura-1"
    assert all(p["preparacion"]["parser_version"] == "markdown-estructura-1" for p in payloads)
    assert all(p["texto"] == preparados[0].texto_completo[p["offset_inicio"]:p["offset_fin"]] for p in payloads)


# ---------------------------------------------------------------------------
# PDF (F2.4)
# ---------------------------------------------------------------------------
from apoyo import _combinar_con_outline, _pdf_pagina_con_lineas, _pdf_pagina_con_texto

from ipsis.ingesta.preparacion import preparar_pdf


def test_pdf_con_outline_usa_los_marcadores_como_secciones(tmp_path):
    ruta = tmp_path / "manual.pdf"
    ruta.write_bytes(_combinar_con_outline([_pdf_pagina_con_texto("Contenido de la introduccion de prueba."),
                                            _pdf_pagina_con_texto("Contenido del capitulo dos de prueba.")],
                                           [("Introduccion", 0), ("Capitulo Dos", 1)]))
    d = preparar_pdf(ruta, doc_id="m", doc_titulo="M")
    assert d.parser_version == "pdf-estructura-1" and d.tablas == []
    assert [e.texto for e in d.elementos if e.tipo == "titulo"] == ["Introduccion", "Capitulo Dos"]
    cap2 = next(e for e in d.elementos if "capitulo dos de prueba" in e.texto.lower())
    assert cap2.seccion_path == ["Capitulo Dos"]
    hijos, padres = unidades_documento(d)
    assert {tuple(p.seccion_path) for p in padres.values()} == {("Introduccion",), ("Capitulo Dos",)}
    for h in hijos:
        assert d.texto_completo[h.offset_inicio:h.offset_fin] == h.texto_fuente


def test_pdf_sin_outline_toma_titulos_por_tamano_y_listas(tmp_path):
    ruta = tmp_path / "manual.pdf"
    ruta.write_bytes(_pdf_pagina_con_lineas([
        ("Garantia", 18),
        ("El equipo tiene una garantia de dos anos desde la fecha de compra del", 11),
        ("cliente en la tienda.", 11),
        ("- Cubre las piezas.", 11),
        ("Mantenimiento", 18),
        ("Cambie el filtro cada seis meses para conservar la calidad del agua y", 11),
        ("evitar obstrucciones.", 11),
    ]))
    d = preparar_pdf(ruta, doc_id="m", doc_titulo="M")
    assert [(e.tipo, e.seccion_path) for e in d.elementos] == [
        ("titulo", ["Garantia"]), ("parrafo", ["Garantia"]), ("lista", ["Garantia"]),
        ("titulo", ["Mantenimiento"]), ("parrafo", ["Mantenimiento"])]
    assert d.advertencias == []


def test_pdf_sin_estructura_conserva_el_aviso_del_parser(tmp_path):
    ruta = tmp_path / "plano.pdf"
    ruta.write_bytes(_pdf_pagina_con_texto("Texto de una pagina cualquiera sin marcadores."))
    d = preparar_pdf(ruta, doc_id="p", doc_titulo="P")
    assert all(e.seccion_path == [] for e in d.elementos)
    assert any("estructura de secciones" in a for a in d.advertencias)


def test_pdf_escaneado_sigue_rechazandose(tmp_path):
    from apoyo import _pdf_pagina_vacia
    from ipsis.ingesta.parsear import DocumentoEscaneadoError

    ruta = tmp_path / "escaneado.pdf"
    ruta.write_bytes(_pdf_pagina_vacia())
    with pytest.raises(DocumentoEscaneadoError):
        preparar_pdf(ruta, doc_id="e", doc_titulo="E")


def test_pdf_real_del_banco_general_se_prepara_con_offsets_literales():
    from pathlib import Path

    ruta = Path(__file__).resolve().parents[1] / "datos/banco_general/bueno/corpus/compras.pdf"
    d = preparar_documento(ruta, doc_id="compras", doc_titulo="Compras")
    assert d.parser_version == "pdf-estructura-1" and len(d.elementos) > 3
    for e in d.elementos:
        assert d.texto_completo[e.offset_inicio:e.offset_fin] == e.texto
    hijos, padres = unidades_documento(d)
    assert hijos and all(h.parent_id in padres for h in hijos)
