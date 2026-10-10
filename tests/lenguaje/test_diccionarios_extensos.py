"""Instantáneas pequeñas: streaming, tipos léxicos y procedencia sin red."""
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[2] / "herramientas/sinonimos/diccionarios.py"
SPEC = importlib.util.spec_from_file_location("diccionarios_extensos", RUTA)
diccionarios = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diccionarios)


def _spec(nombre, datos):
    return {"filename": nombre, "bytes": len(datos), "sha256": hashlib.sha256(datos).hexdigest()}


@pytest.fixture
def snapshot(tmp_path):
    entries = [
        {"word": "aceptar", "lang_code": "es", "pos": "verb", "senses": [{"id": "s1", "glosses": ["fixture"],
          "synonyms": [{"word": "admitir", "tags": ["rare"]}], "antonyms": [{"word": "rechazar"}]}],
         "forms": [{"form": "aceptan", "tags": ["plural"]}, {"form": "header", "tags": ["table-tags"]},
                   {"form": "-", "tags": []}], "translations": [{"word": "accept", "lang_code": "en"}]},
        {"word": "aceptaron", "lang_code": "es", "pos": "verb", "senses": [{"tags": ["form-of"], "form_of": [{"word": "aceptar"}]}]},
        {"word": "aceptár", "lang_code": "es", "pos": "verb", "senses": [{"alt_of": [{"word": "aceptar"}]}]},
    ]
    data = gzip.compress(b"\n" + b"".join(diccionarios._json(e) for e in entries), mtime=0)
    parts = []
    for i, start in enumerate(range(0, len(data), 31)):
        block = data[start:start + 31]
        name = f"es.{i:04}.part"
        (tmp_path / name).write_bytes(block)
        parts.append(_spec(name, block))
    notice = b"Synthetic fixture\n"
    (tmp_path / "NOTICE.txt").write_bytes(notice)
    fuente = {"id": "fixture", "data": {**_spec("es.jsonl.gz", data), "url": "https://invalid.example/es.jsonl.gz"},
              "parts": parts, "notices": [_spec("NOTICE.txt", notice)]}
    return fuente, tmp_path, entries


def _tsv(artefactos, nombre):
    return list(csv.reader(io.StringIO(gzip.decompress(artefactos[nombre]).decode()), delimiter="\t"))


def test_lector_concatena_partes_sin_necesitar_el_archivo_completo(snapshot):
    fuente, root, entries = snapshot
    assert [entry for _, entry in diccionarios.entradas(fuente, root)] == entries
    assert not (root / "es.jsonl.gz").exists()


def test_conversion_separa_flexiones_alternativas_y_sinonimos(snapshot):
    fuente, root, _ = snapshot
    antes = b"# vocabulary\naceptar\tlegacy\nentidad\tlegacy\n"
    artefactos, reporte = diccionarios.construir("es", fuente, antes, root)
    indice = {fila[0]: fila[1] for fila in _tsv(artefactos, "diccionarios/es.vocabulary.tsv.gz")[1:]}
    assert indice == {"aceptar": "lemma,legacy_vocabulary", "aceptan": "inflected_form", "aceptaron": "inflected_entry",
                      "aceptár": "alternative", "admitir": "explicit_synonym", "entidad": "legacy_vocabulary"}
    edges = _tsv(artefactos, "diccionarios/es.synonym-edges.tsv.gz")[1:]
    assert len(edges) == 1 and edges[0][3:5] == ["aceptar", "admitir"]
    assert json.loads(edges[0][5]) == {"tags": ["rare"]}
    assert reporte["statistics"]["combined_unique_forms"] == 6
    assert reporte["statistics"]["additional_forms"] == 4
    assert reporte["statistics"]["dictionary_lemma_forms"] == 1
    assert reporte["statistics"]["form_records"] == 1
    entries = [json.loads(line) for line in gzip.decompress(artefactos["diccionarios/es.entries.0001.jsonl.gz"]).splitlines()]
    assert "translations" not in entries[0]
    assert entries[0]["forms"][1]["form"] == "header"  # original léxico conservado, índice filtrado
    assert entries[1]["senses"][0]["form_of"] == [{"word": "aceptar"}]


def test_derivados_reproducibles_y_hashes(snapshot):
    fuente, root, _ = snapshot
    a, reporte = diccionarios.construir("es", fuente, b"# empty\n", root)
    b, _ = diccionarios.construir("es", fuente, b"# empty\n", root)
    assert a == b
    for spec in reporte["files"]:
        assert hashlib.sha256(a[spec["filename"]]).hexdigest() == spec["sha256"]
    assert a["diccionarios/es.vocabulary.tsv.gz"][4:8] == b"\0\0\0\0"


def test_parte_o_aviso_corruptos_son_rechazados(snapshot):
    fuente, root, _ = snapshot
    (root / "NOTICE.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        list(diccionarios.entradas(fuente, root))


def test_hash_del_original_completo_verifica_orden_de_partes(snapshot):
    fuente, root, _ = snapshot
    fuente["parts"] = list(reversed(fuente["parts"]))
    with pytest.raises(ValueError, match="Complete"):
        list(diccionarios.entradas(fuente, root))


def test_no_mezcla_idiomas(snapshot):
    fuente, root, _ = snapshot
    with pytest.raises(ValueError, match="unexpected language"):
        diccionarios.construir("pt", fuente, b"# empty\n", root)


def test_limite_de_descompresion_y_linea(snapshot, monkeypatch):
    fuente, root, _ = snapshot
    monkeypatch.setattr(diccionarios, "MAX_LINEA", 16)
    with pytest.raises(ValueError, match="budget"):
        list(diccionarios.entradas(fuente, root))


def test_manifiesto_rechaza_rutas_fuera_del_archivo(snapshot):
    fuente, root, _ = snapshot
    cfg = {"schema_version": 1, "sources": {"es": fuente}}
    path = root / "manifest.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    assert diccionarios.cargar_fuentes(path)["sources"]["es"]["id"] == "fixture"
    fuente["parts"][0]["filename"] = "../outside.part"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid"):
        diccionarios.cargar_fuentes(path)


def test_proyeccion_lexica_reproduce_los_derivados_del_original(snapshot):
    fuente, root, _ = snapshot
    previo = b"# vocabulary\naceptar\tlegacy\n"
    primero, _ = diccionarios.construir("es", fuente, previo, root)
    archivo = primero["diccionarios/es.entries.0001.jsonl.gz"]
    (root / "es.lexical.0001.jsonl.gz").write_bytes(archivo)
    fuente["lexical_parts"] = [_spec("es.lexical.0001.jsonl.gz", archivo)]
    fuente["lexical_schema_version"] = diccionarios.VERSION
    rapido, _ = diccionarios.construir("es", fuente, previo, root)
    completo, _ = diccionarios.construir("es", fuente, previo, root, usar_lexico=False)
    assert rapido == completo
    # El atajo no deja de verificar la descarga original completa.
    (root / fuente["parts"][0]["filename"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        diccionarios.construir("es", fuente, previo, root)


def test_archivar_no_altera_el_gzip_original(snapshot, tmp_path):
    fuente, root, _ = snapshot
    datos = b"".join((root / p["filename"]).read_bytes() for p in fuente["parts"])
    original = root / "complete.gz"
    original.write_bytes(datos)
    destino = tmp_path / "nuevo"
    partes = diccionarios.archivar(original, fuente["data"], destino, "es")
    assert b"".join((destino / p["filename"]).read_bytes() for p in partes) == datos
    (destino / partes[0]["filename"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs"):
        diccionarios.archivar(original, fuente["data"], destino, "es")
