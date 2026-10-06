"""Las plantillas y los estáticos deben viajar dentro del paquete."""
from importlib.resources import files

import yaml

from ipsis.recursos import leer_plantilla
from apoyo import plantilla_interna


PLANTILLAS_YAML = [
    "assistant.yaml",
    "domain.yaml",
    "engine.yaml",
    "styles.yaml",
]


def test_todas_las_plantillas_globales_estan_empaquetadas_y_son_yaml():
    for nombre in PLANTILLAS_YAML:
        texto = leer_plantilla(nombre)
        assert texto.strip(), nombre
        assert isinstance(yaml.safe_load(texto), dict), nombre


def test_plantilla_de_dominio_parte_sin_reglas_propias():
    asistente = plantilla_interna("assistant.yaml")
    dominio = plantilla_interna("domain.yaml")
    assert asistente["perfil"] == "medium"
    assert dominio["organismos"] == []
    assert dominio["extractores_regex"] == []
    assert any(c["id"] == "otro" for c in dominio["taxonomia"]["categorias"])


def test_widget_y_demo_estan_dentro_del_paquete():
    estaticos = files("ipsis.servicio").joinpath("estaticos")
    assert estaticos.joinpath("widget.js").is_file()
    assert estaticos.joinpath("demo.html").is_file()
