"""Perfiles de instalación y su fusión por capas."""
from __future__ import annotations

import pytest

from ipsis.configuracion.carga import config_recuperacion
from ipsis.configuracion.esquemas import validar_asistente, validar_motor
from ipsis.configuracion.perfiles import PERFILES_INSTALABLES, cargar_perfil_instalacion, perfil_efectivo


def test_modelo_denso_del_ajuste_se_usa_al_indexar_y_consultar():
    from ipsis.configuracion.variantes_modelos import ajustes_variante

    cfg = {"recuperacion": {"modelo": None, "modo": "hibrida"}, "ajustes_perfil": ajustes_variante("harrier")}
    assert config_recuperacion(cfg, perfil="medium")["modelo"] == "onnx-community/harrier-oss-v1-270m-ONNX"


def test_perfiles_cumplen_presupuestos_y_modelos():
    light, medium = (cargar_perfil_instalacion(p) for p in PERFILES_INSTALABLES)
    assert light.presupuesto_p95_ms <= 150 and light.modelos.reranker is None and light.modelos.lector is None
    assert medium.presupuesto_p95_ms <= 1000 and medium.modelos.reranker and medium.modelos.lector
    assert light.modelos.denso == medium.modelos.denso  # comparten índice


def test_perfil_desconocido():
    with pytest.raises(ValueError, match="disponibles"):
        cargar_perfil_instalacion("ultra")


def test_ajustes_del_proyecto_se_fusionan():
    perfil = perfil_efectivo("medium", {"modelos": {"reranker": "Horizon-Labs/multilingual-reranker-small"}})
    assert perfil.modelos.reranker == "Horizon-Labs/multilingual-reranker-small"
    assert perfil.modelos.lector == cargar_perfil_instalacion("medium").modelos.lector  # lo demás se conserva


def test_el_perfil_ya_no_tiene_cascada_ni_umbrales():
    campos = set(cargar_perfil_instalacion("medium").model_dump())
    assert not campos & {"cascada", "etapas", "lexico", "umbrales_por_defecto", "alternativas", "origen_umbrales"}


def test_un_engine_yaml_con_ajustes_de_la_cascada_v1_los_ignora_al_cargar():
    antiguo = {"config_version": 8, "pipeline": "v2", "recuperacion": {"estrategia_chunking": "CH-F256", "coleccion_base": "x"},
               "ajustes_perfil": {"modelos": {"reranker": None},
                                  "cascada": {"rerank_k": 6}, "umbrales_por_defecto": {"ok": 0.7},
                                  "default_thresholds": {"ok": 0.7}, "alternativas": {"umbral": 0.4}}}
    ajustes = validar_motor(antiguo)["ajustes_perfil"]
    assert ajustes == {"modelos": {"reranker": None}}
    perfil_efectivo("medium", ajustes)  # los ajustes que quedan son válidos


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
        assert perfil_efectivo("medium", ajustes).modelos.reranker == BGE


def test_otros_idiomas_y_light_conservan_el_reranker_del_perfil():
    assert ajustes_de_idioma("medium", None, "en") == (None, None)
    assert ajustes_de_idioma("medium", None, None) == (None, None)
    assert ajustes_de_idioma("light", None, "es") == (None, None)
    assert perfil_efectivo("medium", None).modelos.reranker == MMARCO


def test_un_proyecto_que_fija_su_reranker_lo_conserva_sin_candidatos_del_idioma():
    propio = {"modelos": {"reranker": "Horizon-Labs/multilingual-reranker-small"}}
    assert ajustes_de_idioma("medium", propio, "es") == (propio, None)


def test_los_ajustes_del_proyecto_se_fusionan_con_el_reranker_del_idioma():
    ajustes, _ = ajustes_de_idioma("medium", {"recuperacion_modo": "vectorial"}, "es")
    efectivo = perfil_efectivo("medium", ajustes)
    assert efectivo.modelos.reranker == BGE and efectivo.recuperacion_modo == "vectorial"


def test_el_perfil_declara_un_modelo_del_catalogo_por_idioma():
    from ipsis.modelos.catalogo import CATALOGO

    perfil = perfil_efectivo("medium", None)
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
