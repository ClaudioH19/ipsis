"""Una única herramienta de instalación Python en las instrucciones vigentes."""
from pathlib import Path
import re

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("ruta", [
    "README.md", "README.es.md", "CONTRIBUTING.md",
    "docs/es/guia/instalacion.md", "docs/guide/installation.md",
    "docs/es/guia/despliegue.md", "docs/guide/deployment.md",
    "docs/es/guia/configuracion.md", "docs/guide/configuration.md",
    "ipsis/recursos/mensajes/es.yaml", "ipsis/recursos/mensajes/en.yaml",
    ".github/workflows/regresion-general.yml", "ipsis/recursos/despliegue/preparar/Dockerfile",
])
def test_las_instrucciones_de_instalacion_son_con_uv(ruta):
    texto = (RAIZ / ruta).read_text(encoding="utf-8")
    assert not re.search(r"(?<!uv )\bpip install|pipx|python(?:3)? -m (?:pip|venv)", texto), ruta
    assert "uv " in texto, ruta


def test_el_lockfile_existe_y_fija_dependencias_del_proyecto():
    import tomllib
    datos = tomllib.loads((RAIZ / "uv.lock").read_text(encoding="utf-8"))
    paquetes = {p["name"] for p in datos["package"]}
    assert {"ipsis", "prompt-toolkit", "rich", "onnxruntime", "pytest"} <= paquetes
