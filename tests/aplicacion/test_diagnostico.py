"""Tests de ``rag/aplicacion/diagnostico.py`` -- chequeos de CORS vacío con claves de widget configuradas, y
textos del idioma inválidos. No existían tests directos de este
módulo antes de esta tanda (se probaba solo indirectamente vía
``rag doctor`` en ``tests/cli/test_cli.py``); estos son unitarios sobre las
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
# verificar_textos_idioma
# ---------------------------------------------------------------------------

def test_textos_del_idioma_por_defecto_son_validos(directorio_dominio: Path):
    from rag.aplicacion.diagnostico import verificar_textos_idioma

    _escribir_dominio(directorio_dominio)
    assert verificar_textos_idioma().ok is True


def test_idioma_yaml_invalido_es_falla_accionable(directorio_dominio: Path):
    from rag.aplicacion.diagnostico import verificar_textos_idioma

    _escribir_dominio(directorio_dominio)
    (directorio_dominio / "configuracion" / "idioma.yaml").write_text("mensajes: [1, 2]\n", encoding="utf-8")
    r = verificar_textos_idioma()
    assert r.ok is False
    assert r.comando_sugerido


def test_ejecutar_diagnostico_incluye_los_chequeos_nuevos(directorio_dominio: Path):
    from rag.aplicacion.diagnostico import ejecutar_diagnostico

    _escribir_dominio(directorio_dominio)
    nombres = {r.nombre for r in ejecutar_diagnostico()}
    assert "CORS" in nombres
    assert "textos del idioma" in nombres
