"""Perfiles de instalación y su fusión por capas."""
from __future__ import annotations

import pytest
import yaml

from ipsis.configuracion.carga import config_recuperacion
from ipsis.configuracion.esquemas import validar_asistente
from ipsis.configuracion.perfiles import PERFILES_INSTALABLES, cargar_perfil_instalacion, perfil_efectivo


def test_perfiles_cumplen_presupuestos_y_modelos():
    light, medium, heavy = (cargar_perfil_instalacion(p) for p in PERFILES_INSTALABLES)
    assert light.presupuesto_p95_ms <= 150 and light.modelos.reranker is None and light.modelos.lector is None
    assert medium.presupuesto_p95_ms <= 1000 and medium.modelos.reranker and medium.modelos.lector
    assert heavy.presupuesto_p95_ms <= 5000
    assert "reranking" not in light.etapas  # medium y heavy suman reranking y lectura en P7
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
    ruta = tmp_path / "calibracion.yaml"
    ruta.write_text(yaml.safe_dump({
        "estado": estado, "alfa": 0.05, "confianza": 0.95,
        "procedencia": {"perfil": perfil, "modelos": modelos, "hash_corpus": hash_corpus,
                        "banco": "golden@1.0.0", "hash_banco": "x"},
        # «oov» es el nombre anterior: vale para oov_dominio y oov_ok.
        "umbrales": {"ok": 0.71, "oov": 0.55},
    }), encoding="utf-8")
    return ruta


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


def test_el_modelo_denso_sale_del_perfil_si_no_se_fija():
    cfg = {"recuperacion": {"modelo": None, "coleccion_base": "x"}}
    assert config_recuperacion(cfg, perfil="heavy")["modelo"] == "intfloat/multilingual-e5-base"
    cfg["recuperacion"]["modelo"] = "intfloat/multilingual-e5-small"
    assert config_recuperacion(cfg, perfil="heavy")["modelo"] == "intfloat/multilingual-e5-small"


def test_migracion_v2_asigna_light():
    v2 = {"config_version": 2, "nombre_asistente": "X", "perfil": "_generico"}
    assert validar_asistente(v2)["perfil"] == "light"
