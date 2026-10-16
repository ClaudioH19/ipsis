"""``ipsis sync``: clasificación de lo que cambió en la carpeta y edición del catálogo sin perder comentarios."""
from __future__ import annotations

from pathlib import Path

import pytest

from ipsis.ingesta.catalogo import (
    actualizar_entrada_catalogo, agregar_documentos_al_catalogo, cargar_catalogo, plantilla_catalogo_vacio)
from ipsis.ingesta.sincronizar import aplicar, planificar


def _md(titulo: str, cuerpo: str) -> str:
    return f"# {titulo}\n\n{cuerpo}\n"


@pytest.fixture()
def proyecto(tmp_path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "catalog.yaml").write_text(plantilla_catalogo_vacio(), encoding="utf-8")
    origen = tmp_path / "origen"
    origen.mkdir()
    for nombre, texto in (("a.md", _md("Plazos", "El plazo es de cinco dias habiles.")),
                          ("b.md", _md("Garantia", "La garantia dura doce meses.")),
                          ("c.md", _md("Pagos", "El pago es en tres cuotas."))):
        (origen / nombre).write_text(texto, encoding="utf-8")
    agregar_documentos_al_catalogo([str(origen / n) for n in ("a.md", "b.md", "c.md")])
    return tmp_path


def _estado():
    return {e["archivo"]: (e["doc_id"], e.get("vigente", True)) for e in cargar_catalogo("documents/catalog.yaml")}


def test_sin_cambios(proyecto):
    plan = planificar()
    assert not plan.hay_cambios and plan.sin_cambios == 3


def test_clasifica_nuevo_renombrado_modificado_y_retirado(proyecto):
    docs = proyecto / "documents"
    (docs / "a.md").rename(docs / "plazos.md")                       # renombrado
    (docs / "b.md").unlink()                                          # retirado
    (docs / "c.md").write_text(_md("Pagos", "El pago es en cuatro cuotas."), encoding="utf-8")   # modificado
    (docs / "d.md").write_text(_md("Envios", "Salen los martes."), encoding="utf-8")             # nuevo
    plan = planificar()
    assert [p.name for p in plan.nuevos] == ["d.md"]
    assert [(e["archivo"], n.name) for e, n in plan.renombrados] == [("a.md", "plazos.md")]
    assert [e["archivo"] for e, _ in plan.modificados] == ["c.md"]
    assert [e["archivo"] for e in plan.retirados] == ["b.md"]
    assert plan.sin_cambios == 0 and plan.hay_cambios


def test_aplicar_conserva_doc_id_en_el_renombre_y_retira_sin_borrar_la_entrada(proyecto):
    docs = proyecto / "documents"
    id_a = _estado()["a.md"][0]
    (docs / "a.md").rename(docs / "plazos.md")
    (docs / "b.md").unlink()
    (docs / "d.md").write_text(_md("Envios", "Salen los martes."), encoding="utf-8")
    resultado = aplicar(planificar())
    estado = _estado()
    assert estado["plazos.md"] == (id_a, True)                        # mismo doc_id: no es un documento nuevo
    assert estado["b.md"][1] is False                                 # retirado, la entrada queda
    assert "d.md" in estado and estado["d.md"][1] is True
    assert [d.archivo for d in resultado.agregados] == ["d.md"]
    assert not planificar().hay_cambios                               # idempotente: una segunda pasada no hace nada


def test_un_archivo_que_vuelve_reactiva_la_entrada_retirada(proyecto):
    docs = proyecto / "documents"
    contenido = (docs / "b.md").read_bytes()
    (docs / "b.md").unlink()
    aplicar(planificar())
    assert _estado()["b.md"][1] is False
    (docs / "b.md").write_bytes(contenido)
    plan = planificar()
    assert [(e["archivo"], n.name) for e, n in plan.reactivados] == [("b.md", "b.md")] and not plan.nuevos
    aplicar(plan)
    assert _estado()["b.md"][1] is True


def test_subcarpetas_se_ignoran_y_se_informan(proyecto):
    (proyecto / "documents" / "sub").mkdir()
    (proyecto / "documents" / "sub" / "e.md").write_text(_md("E", "texto"), encoding="utf-8")
    plan = planificar()
    assert [p.name for p in plan.ignorados] == ["e.md"] and not plan.nuevos


def test_dos_archivos_nuevos_con_el_mismo_contenido_no_se_duplican(proyecto):
    docs = proyecto / "documents"
    (docs / "x.md").write_text(_md("X", "mismo contenido"), encoding="utf-8")
    (docs / "y.md").write_text(_md("X", "mismo contenido"), encoding="utf-8")
    aplicar(planificar())
    nuevos = [a for a in _estado() if a in {"x.md", "y.md"}]
    assert len(nuevos) == 1                                           # el segundo es un duplicado exacto del primero


def test_actualizar_entrada_conserva_comentarios_y_el_resto(proyecto):
    ruta = proyecto / "documents" / "catalog.yaml"
    ruta.write_text("# mi comentario\n" + ruta.read_text(encoding="utf-8").replace("documents:", "documents:  # lista"),
                    encoding="utf-8")
    id_b = _estado()["b.md"][0]
    actualizar_entrada_catalogo(str(ruta), id_b, vigente=False, archivo="otro nombre.md")
    texto = ruta.read_text(encoding="utf-8")
    assert texto.startswith("# mi comentario\n") and "documents:  # lista" in texto
    assert 'file: "otro nombre.md"' in texto
    assert _estado()["otro nombre.md"] == (id_b, False)
    with pytest.raises(KeyError):
        actualizar_entrada_catalogo(str(ruta), "no-existe", vigente=True)


def test_actualizar_entrada_entiende_las_claves_antiguas_en_espanol(tmp_path):
    ruta = tmp_path / "catalog.yaml"
    ruta.write_text('documents:\n\n  - archivo: "a.md"\n    doc_id: a\n    doc_titulo: "A"\n    version: "1"\n'
                    '    vigente: true\n    hash_contenido: abc\n', encoding="utf-8")
    actualizar_entrada_catalogo(str(ruta), "a", vigente=False, hash_contenido="def")
    texto = ruta.read_text(encoding="utf-8")
    assert "vigente: false" in texto and "hash_contenido: def" in texto and 'archivo: "a.md"' in texto
