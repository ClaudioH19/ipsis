"""``ipsis sync`` sin modelos: simulación, solo catálogo y la subida de versión de la colección."""
from __future__ import annotations

import pytest

from ipsis.aplicacion.sincronizar import podar_versiones_antiguas, subir_version_coleccion
from ipsis.cli import main
from ipsis.recursos.mensajes import t
from ipsis.ingesta.catalogo import agregar_documentos_al_catalogo, cargar_catalogo, plantilla_catalogo_vacio


@pytest.fixture()
def proyecto(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "catalog.yaml").write_text(plantilla_catalogo_vacio(), encoding="utf-8")
    (tmp_path / "a.md").write_text("# A\n\nTexto de A.\n", encoding="utf-8")
    agregar_documentos_al_catalogo([str(tmp_path / "a.md")])
    return tmp_path


def test_simulacion_no_toca_nada(proyecto, capsys):
    (proyecto / "documents" / "a.md").unlink()
    antes = (proyecto / "documents" / "catalog.yaml").read_text(encoding="utf-8")
    assert main(["sync", "--dry-run"]) == 0
    salida = capsys.readouterr().out
    assert "a.md" in salida and "active: false" in salida
    assert (proyecto / "documents" / "catalog.yaml").read_text(encoding="utf-8") == antes


def test_no_index_actualiza_solo_el_catalogo(proyecto, capsys):
    (proyecto / "documents" / "a.md").unlink()
    (proyecto / "documents" / "b.md").write_text("# B\n\nTexto de B.\n", encoding="utf-8")
    assert main(["sync", "--no-index"]) == 0
    estado = {e["archivo"]: e.get("vigente", True) for e in cargar_catalogo("documents/catalog.yaml")}
    assert estado == {"a.md": False, "b.md": True}
    assert "ipsis index" in capsys.readouterr().out


def test_sin_cambios_lo_dice(proyecto, capsys):
    assert main(["sync", "--no-index"]) == 0
    assert t("sync.unchanged", n=1) in capsys.readouterr().out


def test_subir_version_edita_solo_esa_linea(tmp_path):
    motor = tmp_path / "engine.yaml"
    motor.write_text("# comentario\nretrieval:\n  collection_version: 3  # versión\n  otra: 1\n", encoding="utf-8")
    assert subir_version_coleccion(str(motor)) == (3, 4)
    assert motor.read_text(encoding="utf-8") == "# comentario\nretrieval:\n  collection_version: 4  # versión\n  otra: 1\n"


def test_podar_borra_solo_las_versiones_menores_de_la_misma_serie(tmp_path, monkeypatch):
    for nombre in ("col_e5_v1", "col_e5_v2", "col_e5_v3", "col_e5_v1__extra", "otra_e5_v1"):
        (tmp_path / f"{nombre}.manifest.json").write_text("{}", encoding="utf-8")
        (tmp_path / f"{nombre}.stats.json").write_text("{}", encoding="utf-8")
    borradas = []

    class Cliente:
        def collection_exists(self, n): return True
        def delete_collection(self, n): borradas.append(n)
        def close(self): pass

    import ipsis.indice.qdrant as q
    monkeypatch.setattr(q, "crear_cliente_qdrant", lambda **kw: Cliente())
    assert podar_versiones_antiguas("col_e5_v3", {"qdrant_path": "x"}, str(tmp_path)) == ["col_e5_v1", "col_e5_v2"]
    assert borradas == ["col_e5_v1", "col_e5_v2"]
    quedan = sorted(p.name for p in tmp_path.glob("*.manifest.json"))
    assert quedan == ["col_e5_v1__extra.manifest.json", "col_e5_v3.manifest.json", "otra_e5_v1.manifest.json"]
    assert not list(tmp_path.glob("col_e5_v1.*")) and not list(tmp_path.glob("col_e5_v2.*"))
