"""Estructura del banco multimedia sintético (M0.2): fichas válidas, casos coherentes y particiones fijas."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from ipsis.ingesta.fichas import leer_fichas

BANCO = Path(__file__).resolve().parents[1] / "datos" / "banco_multimedia" / "es"
CORPUS = BANCO.parents[1] / "banco_terminos" / "validacion" / "es" / "corpus"


@pytest.fixture(scope="module")
def fichas():
    return leer_fichas(BANCO / "fichas")


@pytest.fixture(scope="module")
def casos():
    return [json.loads(linea) for linea in (BANCO / "casos.jsonl").read_text(encoding="utf-8").splitlines()]


def test_las_veinte_fichas_validan_y_diez_tienen_capitulos(fichas):
    assert fichas.errores == {} and len(fichas.fichas) == 20
    assert sum(1 for f in fichas.fichas if f.capitulos) == 10
    assert all(2 <= len(f.capitulos) <= 5 for f in fichas.fichas if f.capitulos)
    assert {f.tipo for f in fichas.fichas} == {"audio", "video"}
    assert all(f.url and not f.archivo for f in fichas.fichas)


def test_noventa_casos_treinta_de_cada_tipo_diez_informales(casos):
    assert len(casos) == 90 and len({c["id"] for c in casos}) == 90 and len({c["pregunta"] for c in casos}) == 90
    assert Counter(c["tipo"] for c in casos) == {"ficha": 30, "mismo_tema": 30, "fuera": 30}
    assert sum(c["informal"] for c in casos) == 10


def test_particion_60_40_fijada_y_con_los_tres_tipos_en_las_dos(casos):
    assert Counter(c["particion"] for c in casos) == {"dev": 54, "test": 36}
    for particion in ("dev", "test"):
        assert Counter(c["tipo"] for c in casos if c["particion"] == particion) == \
            {"ficha": 18 if particion == "dev" else 12, "mismo_tema": 18 if particion == "dev" else 12,
             "fuera": 18 if particion == "dev" else 12}


def test_cada_caso_de_ficha_apunta_a_una_ficha_y_un_capitulo_que_existen(fichas, casos):
    por_id = {f.id: f for f in fichas.fichas}
    usadas = set()
    for c in (c for c in casos if c["tipo"] == "ficha"):
        ficha = por_id[c["media_id"]]
        usadas.add(ficha.id)
        if c["capitulo_segundos"] is not None:
            assert c["capitulo_segundos"] in {cap.segundos for cap in ficha.capitulos}, c["id"]
    assert usadas == set(por_id)  # ninguna ficha queda sin pregunta


def test_los_casos_de_mismo_tema_citan_un_documento_del_corpus(casos):
    documentos = {p.stem for p in CORPUS.glob("*.md")}
    citados = {c["documento"] for c in casos if c["tipo"] == "mismo_tema"}
    assert citados <= documentos and len(citados) >= 9
    assert all("media_id" not in c for c in casos if c["tipo"] != "ficha")
