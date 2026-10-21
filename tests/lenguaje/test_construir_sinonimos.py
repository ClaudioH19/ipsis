"""Conversión léxica reproducible: fuentes sintéticas, sin red ni modelos."""
from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("construir_sinonimos", RAIZ / "herramientas/sinonimos/construir.py")
construir = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(construir)
FILTROS = {"max_members": 8, "max_senses": 1, "max_output_bytes": 2097152}


@pytest.mark.parametrize("etiqueta", ["lemma", "spa:lemma"])
def test_omw_usa_solo_pertenencia_a_synsets(etiqueta):
    entrada = (f"# fuente sintética\n00000001-v\t{etiqueta}\taceptar\n"
               f"00000001-v\t{etiqueta}\tadmitir\n00000002-v\t{etiqueta}\trechazar\n"
               "00000001-v\tantonym\t00000002-v\n"
               "00000001-v\tspa:def\t0\tuna definición con cuatro columnas\n").encode()
    grupos = construir.leer_omw(entrada, etiqueta)
    assert grupos[("00000001-v", "v")] == {"aceptar", "admitir"}
    assert grupos[("00000002-v", "v")] == {"rechazar"}


@pytest.mark.parametrize("fila", ["sin-tab", "00000001-n\tlemma\ta\tb", "invalid\tlemma\ta"])
def test_omw_rechaza_entrada_malformada(fila):
    with pytest.raises(ValueError):
        construir.leer_omw(fila.encode(), "lemma")


def _xml(idioma="en", version="2025", prefijo=""):
    return gzip.compress((prefijo + f'''<LexicalResource><Lexicon language="{idioma}" version="{version}">
      <LexicalEntry id="a"><Lemma writtenForm="accept" partOfSpeech="v"/>
        <Sense id="a1" synset="test-1-v"><SenseRelation relType="antonym" target="r1"/></Sense>
      </LexicalEntry>
      <LexicalEntry id="b"><Lemma writtenForm="admit" partOfSpeech="v"/><Sense id="b1" synset="test-1-v"/></LexicalEntry>
      <LexicalEntry id="r"><Lemma writtenForm="reject" partOfSpeech="v"/><Sense id="r1" synset="test-2-v"/></LexicalEntry>
      <Synset id="test-1-v" partOfSpeech="v"><SynsetRelation relType="hypernym" target="test-2-v"/></Synset>
      <Synset id="test-2-v" partOfSpeech="v"/>
    </Lexicon></LexicalResource>''').encode(), mtime=0)


def test_lmf_lee_synsets_sin_seguir_relaciones_ni_descargar_dtd():
    grupos = construir.leer_lmf(_xml(prefijo='<!DOCTYPE LexicalResource SYSTEM "https://invalid.example/no.dtd">'), "en", "2025")
    assert grupos == {("test-1-v", "v"): {"accept", "admit"}, ("test-2-v", "v"): {"reject"}}


@pytest.mark.parametrize("idioma,version", [("pt", "2025"), ("en", "2024")])
def test_lmf_exige_idioma_y_version_fijados(idioma, version):
    with pytest.raises(ValueError):
        construir.leer_lmf(_xml(idioma, version), "en", "2025")


def test_lmf_rechaza_entidades_internas():
    with pytest.raises(ValueError, match="entities"):
        construir.leer_lmf(_xml(prefijo='<!DOCTYPE LexicalResource [<!ENTITY a "accept">]>'), "en", "2025")


def test_lmf_adjetivo_satelite_conserva_la_categoria_del_synset():
    xml = '''<LexicalResource><Lexicon language="en" version="2025">
      <LexicalEntry><Lemma writtenForm="bright" partOfSpeech="a"/><Sense synset="test-1-s"/></LexicalEntry>
      <LexicalEntry><Lemma writtenForm="brilliant" partOfSpeech="s"/><Sense synset="test-1-s"/></LexicalEntry>
      <Synset id="test-1-s" partOfSpeech="s"/>
    </Lexicon></LexicalResource>'''
    assert construir.leer_lmf(gzip.compress(xml.encode()), "en", "2025") == {
        ("test-1-s", "s"): {"bright", "brilliant"}}


def test_polisemia_se_cuenta_antes_de_descartar_grupos_grandes():
    grupos = {("1", "n"): {"banco", "asiento"},
              ("2", "n"): {"banco", "entidad", "finanzas", "capital", "deposito", "credito", "dinero", "prestamo", "ahorro"},
              ("3", "v"): {"aceptar", "admitir"}}
    filas, reporte = construir.filtrar(grupos, FILTROS)
    assert filas == [("3", "v", ("aceptar", "admitir"))]
    assert reporte["excluded_polysemous_lemmas"] == 1
    assert reporte["discarded_groups"]["oversized"] == 1


def test_no_fusiona_sentidos_por_palabras_compartidas():
    grupos = {("1", "n"): {"banco", "asiento"}, ("2", "n"): {"banco", "entidad"}}
    filas, _ = construir.filtrar(grupos, {**FILTROS, "max_senses": 2})
    assert filas == [("1", "n", ("asiento", "banco")), ("2", "n", ("banco", "entidad"))]


def test_no_une_acepciones_de_distinta_categoria():
    filas, _ = construir.filtrar({("1", "n"): {"canto", "canción"},
                                ("2", "v"): {"canto", "entonar"}}, FILTROS)
    assert filas == []


def test_unicode_nfc_sin_perder_tildes_y_exclusion_de_locuciones():
    assert construir.normalizar("asignacio\u0301n") == "asignación"
    assert construir.normalizar("asignacion") == "asignacion"
    for palabra in ["orden de compra", "orden_de_compra", "dos-días", "Madrid", "OC", "100"]:
        assert construir.normalizar(palabra) is None


def _especificacion(nombre, contenido):
    return {"filename": nombre, "url": "https://invalid.example/" + nombre,
            "sha256": construir.sha256(contenido), "bytes": len(contenido)}


@pytest.fixture
def fuente(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    entrada = b"00000001-v\tlemma\tadmitir\n00000001-v\tlemma\taceptar\n"
    aviso = b"Synthetic fixture created for this test, no external data.\n"
    (cache / "es.tab").write_bytes(entrada)
    (cache / "es.LICENSE").write_bytes(aviso)
    cfg = {"schema_version": 1, "reviewed_on": "2026-10-06", "filters": FILTROS,
           "sources": {"es": {"id": "synthetic", "label": "Synthetic fixture", "version": "1",
                              "homepage": "https://invalid.example", "license": "synthetic",
                              "attribution": "Test authors", "format": "omw-tab", "lemma_tag": "lemma",
                              "data": _especificacion("es.tab", entrada),
                              "notices": [_especificacion("es.LICENSE", aviso)]}}}
    return cfg, cache, tmp_path / "salida"


def test_cualquier_cache_corrupta_falla_incluyendo_avisos(fuente):
    cfg, cache, salida = fuente
    (cache / "es.LICENSE").write_bytes(b"alterado")
    with pytest.raises(ValueError, match="checksum"):
        construir.ejecutar(["es"], cfg, cache, salida, offline=True)
    assert not salida.exists()


def test_descarga_verifica_antes_de_escribir_cache(tmp_path, monkeypatch):
    import io

    spec = _especificacion("es.tab", b"correcto")
    monkeypatch.setattr(construir, "urlopen", lambda *a, **kw: io.BytesIO(b"alterado"))
    with pytest.raises(ValueError, match="checksum"):
        construir.obtener_archivo(spec, tmp_path)
    assert not (tmp_path / "es.tab").exists()
    monkeypatch.setattr(construir, "urlopen", lambda *a, **kw: io.BytesIO(b"correcto"))
    assert construir.obtener_archivo(spec, tmp_path) == b"correcto"
    assert (tmp_path / "es.tab").read_bytes() == b"correcto"


def test_offline_y_check_no_usan_red(fuente, monkeypatch):
    cfg, cache, salida = fuente

    def prohibido(*args, **kwargs):
        pytest.fail("Network used in offline/check mode")

    monkeypatch.setattr(construir, "urlopen", prohibido)
    construir.ejecutar(["es"], cfg, cache, salida, offline=True)
    construir.ejecutar(["es"], cfg, cache, salida, comprobar=True)
    (cache / "es.tab").unlink()
    with pytest.raises(ValueError, match="Missing cached"):
        construir.ejecutar(["es"], cfg, cache, salida, comprobar=True)


def test_salida_reproducible_y_comprobacion_detecta_cambios(fuente):
    cfg, cache, salida = fuente
    construir.ejecutar(["es"], cfg, cache, salida, offline=True)
    antes = {p.relative_to(salida): p.read_bytes() for p in salida.rglob("*") if p.is_file()}
    construir.ejecutar(["es"], cfg, cache, salida, offline=True)
    assert antes == {p.relative_to(salida): p.read_bytes() for p in salida.rglob("*") if p.is_file()}
    reporte = json.loads((salida / "es.manifest.json").read_text(encoding="utf-8"))
    tsv = (salida / "es.tsv").read_bytes()
    assert b"00000001-v\tv\taceptar\tadmitir\n" in tsv
    assert b"\r" not in tsv
    assert reporte["output"]["sha256"] == construir.sha256(tsv)
    assert "licencias/es.LICENSE" in (salida / "FUENTES.md").read_text(encoding="utf-8")
    (salida / "es.tsv").write_bytes(tsv + b"alterado\n")
    with pytest.raises(ValueError, match="es.tsv"):
        construir.ejecutar(["es"], cfg, cache, salida, comprobar=True)
    assert (salida / "es.tsv").read_bytes().endswith(b"alterado\n")


def test_presupuesto_de_salida_falla_sin_publicar(fuente):
    cfg, cache, salida = fuente
    cfg["filters"] = {**FILTROS, "max_output_bytes": 1}
    with pytest.raises(ValueError, match="budget"):
        construir.ejecutar(["es"], cfg, cache, salida, offline=True)
    assert not salida.exists()


def test_manifiesto_real_tiene_fuentes_y_hashes_por_idioma():
    cfg = construir.cargar_fuentes()
    assert set(cfg["sources"]) == {"es", "en", "pt"}
    assert cfg["filters"]["max_senses"] == 3
    assert cfg["approved_on"] == "2026-10-06"
    for fuente in cfg["sources"].values():
        assert fuente["license"] and fuente["attribution"] and fuente["notices"]


@pytest.mark.slow
def test_reproducibilidad_de_fuentes_reales_solo_si_estan_en_cache(tmp_path):
    if not (construir.RAIZ / "herramientas/sinonimos/datos/diccionarios").is_dir():
        pytest.skip("Faltan las descargas completas; ver herramientas/sinonimos/README.md")
    cfg = construir.cargar_fuentes()
    cache = construir.ORIGINALES
    construir.ejecutar(["es", "en", "pt"], cfg, cache, tmp_path, offline=True)
    construir.ejecutar(["es", "en", "pt"], cfg, cache, tmp_path, comprobar=True)


def test_archivo_original_comprimido_permite_reconstruir_sin_cache(fuente, tmp_path, monkeypatch):
    cfg, cache, salida = fuente
    archivo = tmp_path / "originales"
    construir.archivar_fuentes(cfg, cache, archivo)
    assert not (archivo / "es.tab").exists()
    assert (archivo / "es.tab.gz").exists()

    def prohibido(*args, **kwargs):
        pytest.fail("Archived sources must not use the network")

    monkeypatch.setattr(construir, "urlopen", prohibido)
    (cache / "es.tab").unlink()
    (cache / "es.LICENSE").unlink()
    construir.ejecutar(["es"], cfg, archivo, salida, offline=True)
    construir.ejecutar(["es"], cfg, archivo, salida, comprobar=True)
    assert not (archivo / "es.tab").exists()  # no necesita extraer el original en disco
    manifest = json.loads((archivo / "manifest.json").read_text(encoding="utf-8"))
    for nombre, info in manifest["files"].items():
        assert construir.sha256((archivo / nombre).read_bytes()) == info["sha256"]


def test_lexico_maestro_conserva_polisemia_locuciones_y_mayusculas():
    import csv
    import io

    grupos = {("1", "n"): {"banco", "asiento", "Banco Central"},
              ("2", "n"): {"banco", "entidad", "orden de compra"},
              ("3", "n"): {"singleton"}}
    fuente = {"id": "test", "version": "1", "data": {"sha256": "0" * 64}}
    tsv = construir.serializar_lexico(grupos, "es", fuente).decode("utf-8")
    filas = list(csv.reader(io.StringIO(tsv), delimiter="\t"))[3:]
    restaurado = {(f[0], f[1]): set(f[2:]) for f in filas}
    assert restaurado == grupos
    assert sum("banco" in f[2:] for f in filas) == 2


def test_comando_es_offline_por_defecto(fuente, tmp_path, monkeypatch):
    cfg, cache, salida = fuente
    ruta_cfg = tmp_path / "fuentes.json"
    ruta_cfg.write_text(json.dumps(cfg), encoding="utf-8")

    def prohibido(*args, **kwargs):
        pytest.fail("CLI must be offline unless --download was explicitly passed")

    monkeypatch.setattr(construir, "urlopen", prohibido)
    (cache / "es.tab").unlink()
    assert construir.main(["es", "--sources", str(ruta_cfg), "--cache", str(cache), "--output", str(salida)]) == 1
    assert not salida.exists()


def test_archivado_no_sobrescribe_originales_distintos(fuente, tmp_path):
    cfg, cache, _ = fuente
    destino = tmp_path / "archive"
    construir.archivar_fuentes(cfg, cache, destino)
    (destino / "es.LICENSE").write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs"):
        construir.archivar_fuentes(cfg, cache, destino)
    assert (destino / "es.LICENSE").read_bytes() == b"changed"


@pytest.mark.parametrize("encoding", ["UTF-8", "ISO8859-1"])
def test_mythes_conserva_etiquetas_acentos_sentidos_y_relaciones(encoding):
    entrada = encoding.encode() + b"\n" + (
        "rápido|2\n(adj)|veloz|lento (antonym)|movimiento (related term)\n"
        "(adj)|inmediato|rápido\n").encode(encoding)
    filas = construir.leer_mythes(entrada)
    assert filas == [("2:1", "rápido", "(adj)", ("veloz", "lento (antonym)", "movimiento (related term)")),
                     ("2:2", "rápido", "(adj)", ("inmediato", "rápido"))]
    assert construir.vocabulario_mythes(filas) == {"rápido", "veloz", "inmediato"}


@pytest.mark.parametrize("entrada", [b"UTF-16\na|1\n-|b\n", b"UTF-8\na|2\n-|b\n",
                                    b"UTF-8\na|0\n", b"UTF-8\na|x\n-|b\n",
                                    b"UTF-8\na|1\n-|\n", b"UTF-8\n"])
def test_mythes_rechaza_codificacion_conteos_y_filas_invalidas(entrada):
    with pytest.raises(ValueError):
        construir.leer_mythes(entrada)


def test_vocabulario_no_promueve_relaciones_ni_anotaciones_a_sinonimos():
    filas = [("1", "aceptar", "(verb)", ("admitir", "rechazar (antonym)",
                                         "acción (generic term)", "permitir (similar term)")),
             ("2", "rápido", "(Antônimo)", ("lento",))]
    assert construir.vocabulario_mythes(filas) == {"aceptar", "admitir", "rápido"}


@pytest.fixture
def fuente_con_tesauro(fuente):
    cfg, cache, salida = fuente
    entrada = b"UTF-8\naceptar|1\n(verb)|consentir|rechazar (antonym)\n"
    (cache / "test.dat").write_bytes(entrada)
    extra = dict(cfg["sources"]["es"], id="test-thes", format="mythes",
                 data=_especificacion("test.dat", entrada), notices=[])
    cfg["supplements"] = {"es": [extra]}
    return cfg, cache, salida


def test_suplementos_amplian_vocabulario_sin_cambiar_synsets(fuente_con_tesauro, monkeypatch):
    import csv

    cfg, cache, salida = fuente_con_tesauro
    monkeypatch.setattr(construir, "urlopen", lambda *a, **kw: pytest.fail("Network used"))
    construir.ejecutar(["es"], cfg, cache, salida, offline=True, cache_suplementos=cache)
    reporte = json.loads((salida / "es.manifest.json").read_text(encoding="utf-8"))
    assert reporte["lexicon"]["unique_lemmas"] == 2
    assert reporte["statistics"]["output_unique_lemmas"] == 2
    assert reporte["vocabulary"]["unique_forms"] == 3
    assert reporte["vocabulary"]["additional_forms"] == 1
    assert reporte["vocabulary"]["additional_single_lowercase_forms"] == 1
    with (salida / "es.vocabulary.tsv").open(encoding="utf-8", newline="") as f:
        filas = list(csv.reader(f, delimiter="\t"))[2:]
    assert filas == [["aceptar", "synthetic", "test-thes"], ["admitir", "synthetic"], ["consentir", "test-thes"]]
    assert "rechazar (antonym)" in (salida / "es.thesaurus.tsv").read_text(encoding="utf-8")
    construir.ejecutar(["es"], cfg, cache, salida, comprobar=True, cache_suplementos=cache)
    with (salida / "es.vocabulary.tsv").open("a", encoding="utf-8") as f:
        f.write("changed\n")
    with pytest.raises(ValueError, match="vocabulary.tsv"):
        construir.ejecutar(["es"], cfg, cache, salida, comprobar=True, cache_suplementos=cache)


def test_suplemento_corrupto_o_grande_falla_antes_de_publicar(fuente_con_tesauro):
    cfg, cache, salida = fuente_con_tesauro
    cfg["max_supplement_bytes"] = 1
    with pytest.raises(ValueError, match="budget"):
        construir.ejecutar(["es"], cfg, cache, salida, offline=True, cache_suplementos=cache)
    assert not salida.exists()
    cfg["max_supplement_bytes"] = 10000
    (cache / "test.dat").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        construir.ejecutar(["es"], cfg, cache, salida, offline=True, cache_suplementos=cache)
    assert not salida.exists()


def test_archivado_de_suplementos_permite_reconstruccion_offline(fuente_con_tesauro, tmp_path):
    cfg, cache, salida = fuente_con_tesauro
    archivo = tmp_path / "tesauros"
    construir.archivar_fuentes(cfg, cache, archivo, suplementos=True)
    assert (archivo / "test.dat.gz").is_file()
    (cache / "test.dat").unlink()
    construir.ejecutar(["es"], cfg, cache, salida, offline=True, cache_suplementos=archivo)
    construir.ejecutar(["es"], cfg, cache, salida, comprobar=True, cache_suplementos=archivo)


def test_manifiesto_rechaza_colision_de_nombres_entre_fuentes(fuente_con_tesauro, tmp_path):
    cfg, _, _ = fuente_con_tesauro
    cfg["supplements"]["es"][0]["notices"] = cfg["sources"]["es"]["notices"]
    ruta = tmp_path / "duplicado.json"
    ruta.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="specification"):
        construir.cargar_fuentes(ruta)
