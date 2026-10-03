"""Perfiles de instalación y su fusión por capas."""
from __future__ import annotations

import pytest
import yaml

from rag.configuracion.carga import config_recuperacion
from rag.configuracion.esquemas import validar_asistente
from rag.configuracion.perfiles import PERFILES_INSTALABLES, cargar_perfil_instalacion, perfil_efectivo


def test_perfiles_cumplen_presupuestos_y_modelos():
    light, medium, heavy = (cargar_perfil_instalacion(p) for p in PERFILES_INSTALABLES)
    assert light.presupuesto_p95_ms <= 150 and light.modelos.reranker is None and light.modelos.lector is None
    assert medium.presupuesto_p95_ms <= 1000 and medium.modelos.reranker and medium.modelos.lector
    assert heavy.presupuesto_p95_ms <= 5000
    assert "reranking" not in light.etapas and "lectura" in medium.etapas
    assert light.modelos.denso == medium.modelos.denso  # comparten índice


def test_perfil_desconocido():
    with pytest.raises(ValueError, match="disponibles"):
        cargar_perfil_instalacion("ultra")


def test_ajustes_del_proyecto_se_fusionan(tmp_path):
    perfil = perfil_efectivo("medium", {"cascada": {"rerank_k": 6}}, tmp_path / "no_existe.yaml")
    assert perfil.cascada.rerank_k == 6 and perfil.cascada.leer_m == 2
    assert perfil.origen_umbrales == "perfil"


def _calibracion(tmp_path, perfil, modelos):
    ruta = tmp_path / "calibracion.yaml"
    ruta.write_text(yaml.safe_dump({
        "perfil": perfil, "procedencia": {"modelos": modelos}, "umbrales": {"ok": 0.71},
    }), encoding="utf-8")
    return ruta


def test_calibracion_con_la_misma_procedencia_reemplaza_umbrales(tmp_path):
    modelos = cargar_perfil_instalacion("medium").modelos.model_dump()
    perfil = perfil_efectivo("medium", ruta_calibracion=_calibracion(tmp_path, "medium", modelos))
    assert perfil.umbrales_por_defecto["ok"] == 0.71 and perfil.origen_umbrales == "calibracion"


def test_calibracion_de_otro_perfil_o_modelo_se_ignora(tmp_path):
    modelos = cargar_perfil_instalacion("medium").modelos.model_dump()
    assert perfil_efectivo("medium", ruta_calibracion=_calibracion(tmp_path, "light", modelos)).origen_umbrales == "perfil"
    otros = {**modelos, "lector": "otro/modelo"}
    assert perfil_efectivo("medium", ruta_calibracion=_calibracion(tmp_path, "medium", otros)).origen_umbrales == "perfil"


def test_el_modelo_denso_sale_del_perfil_si_no_se_fija():
    cfg = {"recuperacion": {"modelo": None, "coleccion_base": "x"}}
    assert config_recuperacion(cfg, perfil="heavy")["modelo"] == "intfloat/multilingual-e5-base"
    cfg["recuperacion"]["modelo"] = "intfloat/multilingual-e5-small"
    assert config_recuperacion(cfg, perfil="heavy")["modelo"] == "intfloat/multilingual-e5-small"


def test_migracion_v2_asigna_light():
    v2 = {"config_version": 2, "nombre_asistente": "X", "perfil": "_generico"}
    assert validar_asistente(v2)["perfil"] == "light"
