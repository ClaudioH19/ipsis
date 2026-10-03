"""Tests de ``rag/aplicacion/diagnostico.py`` -- chequeos de CORS vacío con claves de widget configuradas, y
``configuracion/textos.yaml`` faltante. No existían tests directos de este
módulo antes de esta tanda (se probaba solo indirectamente vía
``rag doctor`` en ``tests/test_cli.py``); estos son unitarios sobre las
funciones de chequeo mismas, en un directorio temporal aislado."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture()
def directorio_dominio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "configuracion").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _escribir_dominio(raiz: Path, **overrides) -> None:
    datos = {
        "nombre_asistente": "Asistente de prueba",
        "descripcion_dominio": "documentos de prueba",
        "idioma": "es",
        "perfil": "_generico",
        "cors_origenes": [],
        "claves_widget": [],
    }
    datos.update(overrides)
    (raiz / "configuracion" / "asistente.yaml").write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# verificar_cors
# ---------------------------------------------------------------------------

def test_cors_vacio_sin_claves_widget_es_informativo_no_falla(directorio_dominio: Path):
    from rag.aplicacion.diagnostico import verificar_cors

    _escribir_dominio(directorio_dominio, cors_origenes=[], claves_widget=[])
    r = verificar_cors()
    assert r.ok is True


def test_cors_vacio_con_claves_widget_configuradas_es_falla(directorio_dominio: Path):
    """Caso concreto: alguien preparó el widget
    (configuró una clave) pero se olvidó de abrir CORS -- el navegador
    bloqueará las peticiones aunque la clave sea válida."""
    from rag.aplicacion.diagnostico import verificar_cors

    _escribir_dominio(directorio_dominio, cors_origenes=[], claves_widget=["clave-sitio-a"])
    r = verificar_cors()
    assert r.ok is False
    assert "cors_origenes" in r.comando_sugerido


def test_cors_configurado_es_ok(directorio_dominio: Path):
    from rag.aplicacion.diagnostico import verificar_cors

    _escribir_dominio(directorio_dominio, cors_origenes=["https://mi-sitio.cl"], claves_widget=["clave-sitio-a"])
    r = verificar_cors()
    assert r.ok is True


# ---------------------------------------------------------------------------
# verificar_plantillas
# ---------------------------------------------------------------------------

def test_plantillas_ausente_es_falla_accionable(directorio_dominio: Path):
    from rag.aplicacion.diagnostico import verificar_plantillas

    assert not (directorio_dominio / "configuracion" / "textos.yaml").exists()
    r = verificar_plantillas()
    assert r.ok is False
    assert r.comando_sugerido


def test_plantillas_presente_es_ok(directorio_dominio: Path):
    from rag.aplicacion.diagnostico import verificar_plantillas

    (directorio_dominio / "configuracion" / "textos.yaml").write_text("planes: {}\n", encoding="utf-8")
    r = verificar_plantillas()
    assert r.ok is True


def test_ejecutar_diagnostico_incluye_los_chequeos_nuevos(directorio_dominio: Path):
    from rag.aplicacion.diagnostico import ejecutar_diagnostico

    _escribir_dominio(directorio_dominio)
    nombres = {r.nombre for r in ejecutar_diagnostico()}
    assert "CORS" in nombres
    assert "plantillas de respuesta" in nombres
