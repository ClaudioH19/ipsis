"""Índice del carril multimedia (M1): colección propia, manifiesto propio y el índice de documentos intacto."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from ipsis.indice.manifiesto import cargar_manifiesto
from ipsis.ingesta.fichas import leer_fichas
from ipsis.ingesta.indice_media import (
    es_coleccion_media, huella_fichas, indexar_fichas, media_desactualizado, nombre_coleccion_media,
    unidades_de_fichas)

E5 = "intfloat/multilingual-e5-small"
MODELO = "modelo/falso"

FICHA = {
    "title": "Inducción a la plataforma de matrícula", "kind": "video", "url": "https://www.youtube.com/watch?v=X",
    "description": "Cómo ingresar, inscribir asignaturas y revisar el horario.",
    "keywords": ["matrícula", "inscripción"], "language": "es", "version": "2026-03", "duration": "00:14:32",
    "chapters": [{"at": "00:01:10", "title": "Ingresar con la clave única"},
                 {"at": "00:06:45", "title": "Inscribir asignaturas", "description": "Elegir secciones y confirmar."}],
}


class CodificadorFalso:
    """Vectores deterministas por hash de palabra: sin modelos, suficiente para indexar."""

    dimension = 8

    def codificar_documentos(self, textos):
        filas = []
        for texto in textos:
            v = np.zeros(self.dimension, dtype="float32")
            for palabra in texto.lower().split():
                v[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % self.dimension] += 1
            filas.append(v / (np.linalg.norm(v) or 1.0))
        return np.array(filas)


def _escribir(carpeta: Path, nombre: str, datos: dict) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")


def _ficha(**cambios) -> dict:
    datos = json.loads(json.dumps(FICHA))
    for clave, valor in cambios.items():
        datos.pop(clave) if valor is ... else datos.__setitem__(clave, valor)
    return datos


@pytest.fixture
def media(tmp_path, monkeypatch):
    """Carpeta ``media/`` en un proyecto vacío (el índice se escribe en ``.ipsis/index`` de esa carpeta)."""
    monkeypatch.chdir(tmp_path)
    return tmp_path / "media"


def _indexar(carpeta, tmp_path, **extra):
    from qdrant_client import QdrantClient

    cliente = QdrantClient(path=str(tmp_path / "qdrant"))
    try:
        resumen = indexar_fichas(modelo=MODELO, coleccion="proyecto", qdrant_path=str(tmp_path / "qdrant"),
                                 version_coleccion=extra.pop("version_coleccion", 1), codificador=CodificadorFalso(),
                                 client=cliente, permitir_recrear=True, carpeta=carpeta, **extra)
        puntos = []
        if resumen is not None and resumen.nombre_coleccion:
            puntos = [p.payload for p in cliente.scroll(resumen.nombre_coleccion, limit=100, with_payload=True)[0]]
        return resumen, puntos
    finally:
        cliente.close()


# --- unidades ---------------------------------------------------------------

def test_una_unidad_por_ficha_y_una_por_capitulo(media):
    _escribir(media, "induccion.yaml", FICHA)
    unidades = unidades_de_fichas(leer_fichas(media).fichas)
    assert [u["chunk_id"] for u in unidades] == ["induccion", "induccion#1", "induccion#2"]
    ficha, cap1, cap2 = unidades
    assert ficha["tipo_unidad"] == "ficha" and ficha["capitulo"] is None and ficha["inicio_segundos"] is None
    assert ficha["texto"] == f"{FICHA['title']}\n{FICHA['description']}"  # literal: lo que se mostrará
    assert "matrícula, inscripción" in ficha["texto_embebido"]  # las palabras clave se buscan
    assert cap1["tipo_unidad"] == "capitulo" and cap1["capitulo"] == 1 and cap1["inicio_segundos"] == 70
    assert cap2["inicio_segundos"] == 405 and cap2["capitulo_descripcion"] == "Elegir secciones y confirmar."
    assert cap2["texto"] == "Inscribir asignaturas\nElegir secciones y confirmar."
    # el capítulo se busca con el título de su ficha, y se cita su propio texto
    assert cap2["texto_embebido"].startswith(FICHA["title"]) and "Inscribir asignaturas" in cap2["texto_embebido"]
    for u in unidades:
        assert u["media_id"] == u["doc_id"] == "induccion" and u["tipo_media"] == "video" and u["vigente"] is True
        assert u["url"] == FICHA["url"] and u["version"] == "2026-03" and u["duracion_segundos"] == 872


def test_las_fichas_retiradas_no_se_indexan_y_el_orden_es_por_id(media):
    _escribir(media, "zeta.yaml", _ficha(title="Zeta", chapters=...))
    _escribir(media, "alfa.yaml", _ficha(title="Alfa", chapters=...))
    _escribir(media, "baja.yaml", {**_ficha(title="Baja", chapters=...), "active": False})
    unidades = unidades_de_fichas(leer_fichas(media).fichas)
    assert [u["chunk_id"] for u in unidades] == ["alfa", "zeta"]


def test_las_unidades_son_deterministas(media):
    _escribir(media, "a.yaml", FICHA)
    una = unidades_de_fichas(leer_fichas(media).fichas)
    assert una == unidades_de_fichas(leer_fichas(media).fichas)


# --- indexación -------------------------------------------------------------

def test_indexa_en_una_coleccion_propia_con_su_manifiesto_y_estadisticas(media, tmp_path):
    _escribir(media, "induccion.yaml", FICHA)
    _escribir(media, "charla.yaml", _ficha(title="Charla de bienvenida", chapters=..., url=...,
                                         file="files/charla.mp3", kind="audio"))
    (media / "files").mkdir()
    (media / "files" / "charla.mp3").write_bytes(b"x")
    resumen, puntos = _indexar(media, tmp_path)
    assert resumen.nombre_coleccion == "proyecto_modelo-falso_v1__media"
    assert (resumen.n_fichas, resumen.n_capitulos, resumen.errores) == (2, 2, {})
    assert sorted(p["chunk_id"] for p in puntos) == ["charla", "induccion", "induccion#1", "induccion#2"]
    manifiesto = cargar_manifiesto(resumen.nombre_coleccion)
    assert manifiesto.n_chunks == 4 and manifiesto.modelo_denso == MODELO and manifiesto.dimension == 8
    assert manifiesto.hash_archivos == huella_fichas(media) and manifiesto.inventario_entidades == []
    assert Path(f".ipsis/index/{resumen.nombre_coleccion}.stats.json").is_file()


def test_reindexar_dos_veces_da_el_mismo_resultado(media, tmp_path):
    _escribir(media, "a.yaml", FICHA)
    primero, puntos1 = _indexar(media, tmp_path)
    segundo, puntos2 = _indexar(media, tmp_path)
    assert primero.nombre_coleccion == segundo.nombre_coleccion
    assert sorted(p["chunk_id"] for p in puntos1) == sorted(p["chunk_id"] for p in puntos2)
    assert cargar_manifiesto(segundo.nombre_coleccion).hash_corpus == cargar_manifiesto(primero.nombre_coleccion).hash_corpus


def test_una_ficha_invalida_se_informa_y_no_impide_indexar_las_demas(media, tmp_path):
    _escribir(media, "buena.yaml", _ficha(chapters=...))
    _escribir(media, "mala.yaml", _ficha(kind="podcast"))
    resumen, puntos = _indexar(media, tmp_path)
    assert [p["chunk_id"] for p in puntos] == ["buena"]
    assert list(resumen.errores) == ["mala"] and resumen.n_fichas == 1


def test_sin_fichas_utilizables_no_se_crea_coleccion(media, tmp_path):
    _escribir(media, "mala.yaml", _ficha(kind="podcast"))
    resumen, puntos = _indexar(media, tmp_path)
    assert resumen.nombre_coleccion == "" and puntos == [] and list(resumen.errores) == ["mala"]
    assert not list(Path(".ipsis/index").glob("*.manifest.json")) if Path(".ipsis/index").exists() else True


def test_solo_fichas_retiradas_no_crea_coleccion_ni_errores(media, tmp_path):
    _escribir(media, "baja.yaml", {**_ficha(chapters=...), "active": False})
    resumen, _ = _indexar(media, tmp_path)
    assert resumen.nombre_coleccion == "" and resumen.errores == {}


def test_sin_media_no_hace_nada(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _indexar(tmp_path / "no-hay-media", tmp_path)[0] is None
    assert not (tmp_path / ".ipsis").exists()  # ni carpeta de índice ni colección


# --- nombres, huella y desactualización -------------------------------------

@pytest.mark.parametrize("nombre, es_media", [
    ("base_modelo_v1__media", True), ("base_modelo_v12__media", True), ("base_modelo_v2__exp_media", True),
    ("base_modelo_v1", False), ("base_modelo_v1__estructura", False), ("media_modelo_v1", False),
])
def test_reconoce_las_colecciones_del_carril(nombre, es_media):
    assert es_coleccion_media(nombre) is es_media


def test_el_nombre_de_la_coleccion_del_carril_comparte_version_con_documentos():
    assert nombre_coleccion_media("asistente", E5, 3) == "asistente_intfloat-multilingual-e5-small_v3__media"
    assert nombre_coleccion_media("asistente", E5, 3, "exp") == "asistente_intfloat-multilingual-e5-small_v3__exp_media"


def test_huella_de_fichas(media):
    assert huella_fichas(media) is None  # sin carpeta
    _escribir(media, "a.yaml", FICHA)
    _escribir(media, "b.yaml", _ficha(title="B"))
    huella = huella_fichas(media)
    assert huella.startswith("sha256:") and huella == huella_fichas(media)
    _escribir(media, "b.yaml", _ficha(title="B cambiada"))
    assert huella_fichas(media) != huella


def test_la_huella_no_depende_del_orden_de_creacion(tmp_path):
    uno, dos = tmp_path / "uno", tmp_path / "dos"
    for nombre in ("a", "b"):
        _escribir(uno, f"{nombre}.yaml", _ficha(title=nombre))
    for nombre in ("b", "a"):
        _escribir(dos, f"{nombre}.yaml", _ficha(title=nombre))
    assert huella_fichas(uno) == huella_fichas(dos)


def test_media_desactualizado_sigue_a_las_fichas(media, tmp_path):
    cfg = {"coleccion_base": "proyecto", "modelo": MODELO, "version_coleccion": 1}
    assert media_desactualizado(cfg, media) is False  # sin carpeta
    _escribir(media, "a.yaml", FICHA)
    assert media_desactualizado(cfg, media) is True  # hay fichas y no hay índice
    _indexar(media, tmp_path)
    assert media_desactualizado(cfg, media) is False
    _escribir(media, "a.yaml", _ficha(title="Otro título"))
    assert media_desactualizado(cfg, media) is True
    assert media_desactualizado({**cfg, "version_coleccion": 2}, media) is True  # otra versión: otro índice


def test_con_solo_fichas_invalidas_no_se_pide_reindexar_siempre(media):
    _escribir(media, "mala.yaml", _ficha(kind="podcast"))
    cfg = {"coleccion_base": "proyecto", "modelo": MODELO, "version_coleccion": 1}
    assert media_desactualizado(cfg, media) is False


# --- los documentos no se enteran -------------------------------------------

def test_el_manifiesto_del_carril_no_se_confunde_con_otro_indice_de_documentos(tmp_path, monkeypatch, capsys):
    """Sin índice de documentos, un manifiesto ``…__media`` de la misma base no debe contar como «otro índice»."""
    from ipsis.aplicacion.proyecto import estado_indice
    from ipsis.cli import main
    from ipsis.configuracion.carga import cargar_proyecto, config_recuperacion
    from ipsis.indice.manifiesto import ManifiestoIndice, guardar_manifiesto

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light", "--language", "es"]) == 0
    cfg = config_recuperacion(cargar_proyecto())
    assert estado_indice("light").estado == "sin_indice"
    nombre = nombre_coleccion_media(cfg["coleccion_base"], cfg["modelo"], cfg["version_coleccion"])
    guardar_manifiesto(ManifiestoIndice(coleccion=nombre, modelo_denso=cfg["modelo"], dimension=384,
                                        hash_corpus="sha256:x", n_chunks=3))
    assert estado_indice("light").estado == "sin_indice"


def test_sync_avisa_de_fichas_nuevas_sin_tocar_nada(tmp_path, monkeypatch, capsys):
    from ipsis.aplicacion.sincronizar import sincronizar
    from ipsis.cli import main
    from ipsis.recursos.mensajes import t

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light", "--language", "es"]) == 0
    assert sincronizar(solo_plan=True).media_cambio is False
    capsys.readouterr()
    assert main(["sync", "--dry-run"]) == 0 and t("sync.media_changed") not in capsys.readouterr().out
    _escribir(tmp_path / "media", "a.yaml", FICHA)
    assert sincronizar(solo_plan=True).media_cambio is True
    capsys.readouterr()
    assert main(["sync", "--dry-run"]) == 0
    assert t("sync.media_changed") in capsys.readouterr().out
    assert not (tmp_path / ".ipsis" / "index").exists()  # --dry-run no indexa
