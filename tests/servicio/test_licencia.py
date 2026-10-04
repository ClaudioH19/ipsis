"""Licencia AGPL-3.0 y enlace al código fuente (P12.8)."""
from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ipsis.aplicacion.modo import URL_FUENTE_POR_DEFECTO, modo_servicio

RAIZ = Path(__file__).resolve().parents[2]


def _cliente(modo, proyecto):
    from apoyo import motor_minimo as _motor

    from ipsis.servicio.api import crear_app

    return TestClient(crear_app(_motor(), modo=modo), base_url="https://testserver")


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from ipsis.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--perfil", "light"]) == 0
    return tmp_path


def test_licencia_declarada():
    texto = (RAIZ / "LICENSE").read_text(encoding="utf-8")
    assert texto.lstrip().startswith("GNU AFFERO GENERAL PUBLIC LICENSE") and "Version 3, 19 November 2007" in texto
    assert len(texto.splitlines()) == 661
    assert re.search(r'(?m)^license = "AGPL-3.0-only"$', (RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    aviso = (RAIZ / "ipsis/servicio/estaticos/avatar.js.LICENSE.txt").read_text(encoding="utf-8")
    for paquete in ("@bible-strong/avatar-web@0.1.0", "@bible-strong/avatar-core@0.1.0", "ajv@"):
        assert paquete in aviso


def test_fuente_redirige_a_la_url_configurada(proyecto):
    r = _cliente(modo_servicio(entorno={}), proyecto).get("/fuente", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == URL_FUENTE_POR_DEFECTO
    propia = modo_servicio(entorno={"IPSIS_SOURCE_URL": "https://git.mi-sitio.cl/asistente"})
    r = _cliente(propia, proyecto).get("/fuente", follow_redirects=False)
    assert r.headers["location"] == "https://git.mi-sitio.cl/asistente"


def test_url_fuente_invalida_se_avisa_y_no_redirige_a_ella(proyecto):
    mala = modo_servicio(entorno={"IPSIS_SOURCE_URL": "javascript:alert(1)"})
    assert any("IPSIS_SOURCE_URL" in p for p in mala.problemas)
    r = _cliente(mala, proyecto).get("/fuente", follow_redirects=False)
    assert r.headers["location"] == URL_FUENTE_POR_DEFECTO


def test_el_widget_enlaza_al_codigo_fuente():
    codigo = (RAIZ / "ipsis/servicio/estaticos/widget.js").read_text(encoding="utf-8")
    assert 'API_BASE + "/fuente"' in codigo and 'texto("codigo_fuente")' in codigo
    from ipsis.lenguaje.paquete import cargar_paquete

    for idioma in ("es", "en", "pt"):
        assert cargar_paquete(idioma).interfaz["codigo_fuente"]


def test_el_wheel_incluye_las_licencias(tmp_path: Path):
    subprocess.run([sys.executable, "-m", "pip", "wheel", str(RAIZ), "--no-deps", "--no-build-isolation",
                    "-q", "-w", str(tmp_path)], check=True, capture_output=True)
    wheel = next(tmp_path.glob("ipsis-*.whl"))
    nombres = zipfile.ZipFile(wheel).namelist()
    assert any(n.endswith(".dist-info/licenses/LICENSE") for n in nombres), nombres
    assert "ipsis/servicio/estaticos/avatar.js.LICENSE.txt" in nombres
    assert "ipsis/servicio/estaticos/admin/panel.js" in nombres
    assert not any("herramientas" in n or "node_modules" in n for n in nombres)
    # Todo recurso que no es Python (perfiles, idiomas, tonos, plantillas, estáticos…) viaja en el wheel.
    recursos = {p.relative_to(RAIZ).as_posix() for p in (RAIZ / "ipsis").rglob("*")
                if p.is_file() and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts}
    assert recursos - set(nombres) == set()
    metadatos = next(zipfile.ZipFile(wheel).read(n) for n in nombres if n.endswith("METADATA")).decode()
    assert "License-Expression: AGPL-3.0-only" in metadatos
