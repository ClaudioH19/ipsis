"""La presentación por forma y el carril multimedia están encendidos por defecto, en proyectos nuevos y existentes."""
from __future__ import annotations

from ipsis.configuracion.archivos import interpretar
from ipsis.configuracion.esquemas import PipelineV2Config, validar_motor
from ipsis.recursos import leer_plantilla


def test_la_plantilla_de_un_proyecto_nuevo_enciende_la_presentacion_y_deja_clear_apagada():
    motor = validar_motor(interpretar(leer_plantilla("engine.yaml"), "motor"))
    presentacion = motor["v2"]["presentacion"]
    assert presentacion["activo"] is True
    assert presentacion["margen_claro"] is None and presentacion["margen_claro_por_perfil"] == {}


def test_un_proyecto_existente_sin_los_bloques_los_recibe_encendidos_sin_migrar():
    """El valor por defecto del esquema es encendido: no hace falta agregar nada ni subir ``config_version``."""
    existente = validar_motor({"config_version": 8, "pipeline": "v2", "v2": {"resultados_n": 3},
                                "recuperacion": {"estrategia_chunking": "CH-F256", "coleccion_base": "demo"}})
    assert existente["config_version"] == 8
    assert existente["v2"]["presentacion"]["activo"] is True and existente["v2"]["presentacion"]["margen_claro"] is None
    assert existente["media"]["activo"] is True and existente["media"]["puntaje_minimo"] == 0.874


def test_se_puede_apagar_en_el_proyecto():
    cfg = interpretar(leer_plantilla("engine.yaml").replace("    enabled: true", "    enabled: false", 1), "motor")
    assert validar_motor(cfg)["v2"]["presentacion"]["activo"] is False


def test_la_plantilla_de_un_proyecto_nuevo_enciende_el_carril_multimedia_con_el_umbral_medido():
    media = validar_motor(interpretar(leer_plantilla("engine.yaml"), "motor"))["media"]
    assert media == {"activo": True, "puntaje_minimo": 0.874, "max_resultados": 1, "presupuesto_ms": 150}


def test_se_puede_apagar_el_carril_multimedia_en_el_proyecto():
    cfg = interpretar(leer_plantilla("engine.yaml").replace("media:\n  enabled: true", "media:\n  enabled: false", 1), "motor")
    assert validar_motor(cfg)["media"]["activo"] is False
