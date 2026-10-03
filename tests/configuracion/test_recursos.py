"""Las plantillas y los estáticos deben viajar dentro del paquete."""
from importlib.resources import files

import yaml

from rag.recursos import leer_plantilla


PLANTILLAS_YAML = [
    "asistente.yaml",
    "dominio.yaml",
    "motor.yaml",
    "estilos.yaml",
]


def test_todas_las_plantillas_globales_estan_empaquetadas_y_son_yaml():
    for nombre in PLANTILLAS_YAML:
        texto = leer_plantilla(nombre)
        assert texto.strip(), nombre
        assert isinstance(yaml.safe_load(texto), dict), nombre


def test_plantilla_de_dominio_parte_sin_reglas_propias():
    asistente = yaml.safe_load(leer_plantilla("asistente.yaml"))
    dominio = yaml.safe_load(leer_plantilla("dominio.yaml"))
    assert "perfil" not in asistente
    assert dominio["organismos"] == []
    assert dominio["extractores_regex"] == []
    assert any(c["id"] == "otro" for c in dominio["taxonomia"]["categorias"])


def test_widget_y_demo_estan_dentro_del_paquete():
    estaticos = files("rag.servicio").joinpath("estaticos")
    assert estaticos.joinpath("widget.js").is_file()
    assert estaticos.joinpath("demo.html").is_file()
