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


def test_preparar_documento_despacha_por_extension_y_el_pdf_sigue_en_legacy(md, tmp_path):
    assert preparar_documento(md, doc_id="a", doc_titulo="A").parser_version == "markdown-estructura-1"
    (tmp_path / "x.markdown").write_text(MD, encoding="utf-8")
    assert preparar_documento(tmp_path / "x.markdown", doc_id="b", doc_titulo="B").parser_version == "markdown-estructura-1"
    with pytest.raises(ValueError, match="PDF"):
        preparar_documento(tmp_path / "x.pdf", doc_id="c", doc_titulo="C")


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
