"""Aislamiento del comparador real: jamás abrir el índice servido para consultar."""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


def comparador():
    ruta = Path(__file__).resolve().parents[2] / "herramientas/evaluacion/comparar_motores.py"
    spec = importlib.util.spec_from_file_location("comparador_motores", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_copia_sqlite_sin_escribir_original_ni_heredar_lock(tmp_path):
    proyecto, replica = tmp_path / "servido", tmp_path / "replica"
    for ruta in ("config", "documents", ".ipsis/index/qdrant"):
        (proyecto / ruta).mkdir(parents=True)
    original = proyecto / ".ipsis/index/qdrant/storage.sqlite"
    with sqlite3.connect(original) as db:
        db.execute("CREATE TABLE contenido (texto TEXT)")
        db.execute("INSERT INTO contenido VALUES ('fuente original')")
    (original.parent / ".lock").write_text("servido")
    contenido = original.read_bytes()
    comparador().copiar_proyecto(proyecto, replica)
    copia = replica / original.relative_to(proyecto)
    with sqlite3.connect(copia) as db:
        assert db.execute("SELECT texto FROM contenido").fetchone() == ("fuente original",)
        db.execute("DELETE FROM contenido")
    assert original.read_bytes() == contenido
    assert not (copia.parent / ".lock").exists()


def test_indice_copiado_prevalece_sobre_entorno_servidor(tmp_path, monkeypatch):
    monkeypatch.setenv("QDRANT_MODE", "server")
    cfg = {"recuperacion": {"qdrant_path": ".ipsis/index/qdrant"}}
    comparador().aislar_indice(cfg, tmp_path)
    assert cfg["qdrant"]["modo"] == "local"
    assert Path(cfg["recuperacion"]["qdrant_path"]).is_relative_to(tmp_path)
    assert __import__("os").environ["QDRANT_MODE"] == "local"


@pytest.mark.parametrize("ruta,modo", [("../servido/index", "local"), (".ipsis/index/qdrant", "servidor")])
def test_rechaza_indice_externo_o_servidor(tmp_path, ruta, modo):
    cfg = {"recuperacion": {"qdrant_path": ruta}, "qdrant": {"modo": modo}}
    with pytest.raises(ValueError, match="local"):
        comparador().aislar_indice(cfg, tmp_path)


@pytest.mark.parametrize("casos", [[{"id": "a", "question": "x"}, {"id": "a", "question": "y"}],
                                     [{"question": "x", "required": "20%"}], [False], []])
def test_rechaza_casos_ambiguos_para_la_comparacion(tmp_path, casos):
    ruta = tmp_path / "casos.json"
    ruta.write_text(json.dumps(casos), encoding="utf-8")
    with pytest.raises(ValueError):
        comparador().preguntas_desde_json(ruta)


def test_codigo_ausente_no_recurre_silenciosamente_a_instalacion_editable(tmp_path):
    with pytest.raises(ValueError, match="no contiene"):
        comparador().preparar_codigo(tmp_path / "ausente")


def test_codigo_de_otro_snapshot_no_reutiliza_paquete_ya_importado(tmp_path, monkeypatch):
    import ipsis
    import sys

    assert Path(ipsis.__file__).is_file()
    (tmp_path / "ipsis").mkdir()
    (tmp_path / "ipsis/__init__.py").write_text("")
    monkeypatch.setattr(sys, "path", list(sys.path))
    with pytest.raises(ValueError, match="código cargado"):
        comparador().preparar_codigo(tmp_path)
