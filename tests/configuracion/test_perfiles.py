"""Perfiles de instalación y su fusión por capas."""
from __future__ import annotations

import pytest
import yaml

from ipsis.configuracion.carga import config_recuperacion
from ipsis.configuracion.esquemas import validar_asistente
from ipsis.configuracion.perfiles import PERFILES_INSTALABLES, cargar_perfil_instalacion, perfil_efectivo


def test_modelo_denso_del_ajuste_se_usa_al_indexar_y_consultar():
    from ipsis.configuracion.variantes_modelos import ajustes_variante

    cfg = {"recuperacion": {"modelo": None, "modo": "hibrida"}, "ajustes_perfil": ajustes_variante("harrier")}
    assert config_recuperacion(cfg, perfil="medium")["modelo"] == "onnx-community/harrier-oss-v1-270m-ONNX"


def test_perfiles_cumplen_presupuestos_y_modelos():
    light, medium = (cargar_perfil_instalacion(p) for p in PERFILES_INSTALABLES)
    assert light.presupuesto_p95_ms <= 150 and light.modelos.reranker is None and light.modelos.lector is None
    assert medium.presupuesto_p95_ms <= 1000 and medium.modelos.reranker and medium.modelos.lector
    assert "reranking" not in light.etapas  # medium suma reranking y lectura
    assert light.modelos.denso == medium.modelos.denso  # comparten índice


def test_perfil_desconocido():
    with pytest.raises(ValueError, match="disponibles"):
        cargar_perfil_instalacion("ultra")


def test_ajustes_del_proyecto_se_fusionan(tmp_path):
    perfil = perfil_efectivo("medium", {"cascada": {"rerank_k": 6}}, tmp_path / "no_existe.yaml")
    assert perfil.cascada.rerank_k == 6 and perfil.cascada.leer_m == 2
    assert perfil.origen_umbrales == "perfil"


HASH = "sha256:corpus"


def _calibracion(tmp_path, perfil, modelos, estado="calibrado", hash_corpus=HASH):
    ruta = tmp_path / "calibration.yaml"
    ruta.write_text(yaml.safe_dump({
        "version": 2,
        "estado": estado, "alfa": 0.05, "confianza": 0.95,
        "procedencia": {"perfil": perfil, "modelos": modelos, "hash_corpus": hash_corpus,
                        "banco": "golden@1.0.0", "hash_banco": "x"},
        # «oov» es el nombre anterior: vale para oov_dominio y oov_ok.
        "umbrales": {"ok": 0.71, "oov": 0.55},
    }), encoding="utf-8")
    return ruta


@pytest.mark.parametrize("version", [None, 1])
def test_calibraciones_con_criterio_anterior_exigen_recalibrar(tmp_path, version):
    modelos = cargar_perfil_instalacion("medium").modelos.model_dump()
    ruta = _calibracion(tmp_path, "medium", modelos)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    if version is None:
        datos.pop("version")
    else:
        datos["version"] = version
    ruta.write_text(yaml.safe_dump(datos), encoding="utf-8")
    assert perfil_efectivo("medium", ruta_calibracion=ruta, hash_corpus=HASH).origen_umbrales == "perfil"


def test_calibracion_con_la_misma_procedencia_reemplaza_umbrales(tmp_path):
    modelos = cargar_perfil_instalacion("medium").modelos.model_dump()
    perfil = perfil_efectivo("medium", ruta_calibracion=_calibracion(tmp_path, "medium", modelos), hash_corpus=HASH)
    u = perfil.umbrales_por_defecto
    assert (u["ok"], u["oov_dominio"], u["oov_ok"]) == (0.71, 0.55, 0.55)
    assert perfil.origen_umbrales == "calibracion"


@pytest.mark.parametrize("cambio", ["perfil", "modelos", "corpus", "sin_indice", "estado"])
def test_calibracion_de_otra_procedencia_o_no_calibrada_se_ignora(tmp_path, cambio):
    modelos = cargar_perfil_instalacion("medium").modelos.model_dump()
    argumentos = {
        "perfil": ("light", modelos, "calibrado"),
        "modelos": ("medium", {**modelos, "lector": "otro/modelo"}, "calibrado"),
        "corpus": ("medium", modelos, "calibrado"),
        "sin_indice": ("medium", modelos, "calibrado"),
        "estado": ("medium", modelos, "muestra_insuficiente"),
    }[cambio]
    ruta = _calibracion(tmp_path, *argumentos)
    hash_actual = {"corpus": "sha256:otro", "sin_indice": None}.get(cambio, HASH)
    perfil = perfil_efectivo("medium", ruta_calibracion=ruta, hash_corpus=hash_actual)
    assert perfil.origen_umbrales == "perfil"
    assert perfil.umbrales_por_defecto["ok"] == cargar_perfil_instalacion("medium").umbrales_por_defecto["ok"]


def test_ajustes_con_oov_anterior_se_migran_a_los_dos_umbrales():
    perfil = perfil_efectivo("light", {"umbrales_por_defecto": {"oov": 0.7}})
    assert (perfil.umbrales_por_defecto["oov_dominio"], perfil.umbrales_por_defecto["oov_ok"]) == (0.7, 0.7)
    assert "oov" not in perfil.umbrales_por_defecto


@pytest.mark.parametrize("guardada", [None, "sha256:anterior", "sha256:actual"])
def test_calibracion_exige_la_huella_lexica_efectiva(tmp_path, guardada):
    modelos = cargar_perfil_instalacion("medium").modelos.model_dump()
    ruta = _calibracion(tmp_path, "medium", modelos)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    datos["procedencia"]["hash_lexico"] = guardada
    ruta.write_text(yaml.safe_dump(datos), encoding="utf-8")
    perfil = perfil_efectivo("medium", ruta_calibracion=ruta, hash_corpus=HASH, hash_lexico="sha256:actual")
    assert perfil.origen_umbrales == ("calibracion" if guardada == "sha256:actual" else "perfil")


def test_el_modelo_denso_sale_del_perfil_si_no_se_fija():
    cfg = {"recuperacion": {"modelo": None, "coleccion_base": "x"}}
    assert config_recuperacion(cfg, perfil="medium")["modelo"] == cargar_perfil_instalacion("medium").modelos.denso
    cfg["recuperacion"]["modelo"] = "intfloat/multilingual-e5-base"
    assert config_recuperacion(cfg, perfil="medium")["modelo"] == "intfloat/multilingual-e5-base"


def test_proyecto_con_heavy_se_carga_como_medium():
    assert validar_asistente({"config_version": 5, "nombre_asistente": "X", "perfil": "heavy"})["perfil"] == "medium"


def test_migracion_v2_asigna_light():
    v2 = {"config_version": 2, "nombre_asistente": "X", "perfil": "_generico"}
    assert validar_asistente(v2)["perfil"] == "light"


# --- reranker propio de cada idioma (medium) ----------------------------------------------------------
from ipsis.configuracion.perfiles import ajustes_de_idioma

BGE = "onnx-community/bge-reranker-v2-m3-ONNX"
MMARCO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def test_medium_usa_bge_con_10_candidatos_en_espanol_y_portugues():
    for idioma in ("es", "pt", "es-CL", "PT"):
        ajustes, candidatos = ajustes_de_idioma("medium", None, idioma)
        assert ajustes == {"modelos": {"reranker": BGE}} and candidatos == 10
        assert perfil_efectivo("medium", ajustes, ruta_calibracion=None).modelos.reranker == BGE


def test_otros_idiomas_y_light_conservan_el_reranker_del_perfil():
    assert ajustes_de_idioma("medium", None, "en") == (None, None)
    assert ajustes_de_idioma("medium", None, None) == (None, None)
    assert ajustes_de_idioma("light", None, "es") == (None, None)
    assert perfil_efectivo("medium", None, ruta_calibracion=None).modelos.reranker == MMARCO


def test_un_proyecto_que_fija_su_reranker_lo_conserva_sin_candidatos_del_idioma():
    propio = {"modelos": {"reranker": "Horizon-Labs/multilingual-reranker-small"}}
    assert ajustes_de_idioma("medium", propio, "es") == (propio, None)


def test_los_ajustes_del_proyecto_se_fusionan_con_el_reranker_del_idioma():
    ajustes, _ = ajustes_de_idioma("medium", {"umbrales_por_defecto": {"ok": 0.7}}, "es")
    efectivo = perfil_efectivo("medium", ajustes, ruta_calibracion=None)
    assert efectivo.modelos.reranker == BGE and efectivo.umbrales_por_defecto["ok"] == 0.7


def test_el_perfil_declara_un_modelo_del_catalogo_por_idioma():
    from ipsis.modelos.catalogo import CATALOGO

    perfil = perfil_efectivo("medium", None, ruta_calibracion=None)
    assert set(perfil.reranker_por_idioma) == set(perfil.rerank_candidatos_por_idioma) == {"es", "pt"}
    assert all(modelo in CATALOGO and CATALOGO[modelo].tarea == "reranker"
               for modelo in perfil.reranker_por_idioma.values())


def test_perfil_de_instalacion_resuelve_el_idioma_del_proyecto(tmp_path, monkeypatch):
    import re
    from ipsis.aplicacion.proyecto import perfil_de_instalacion
    from ipsis.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "medium", "--language", "es"]) == 0
    assert perfil_de_instalacion("medium").modelos.reranker == BGE
    asistente = (tmp_path / "config/assistant.yaml")
    asistente.write_text(re.sub(r"(?m)^language: .*", "language: en", asistente.read_text(encoding="utf-8")),
                         encoding="utf-8")
    assert perfil_de_instalacion("medium").modelos.reranker == MMARCO
