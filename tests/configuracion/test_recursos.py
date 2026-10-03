"""Las plantillas y los estáticos deben viajar dentro del paquete."""
from importlib.resources import files

import yaml

from rag.recursos import leer_plantilla


PLANTILLAS_YAML = [
    "asistente.yaml",
    "categorias.yaml",
    "motor.yaml",
    "textos.yaml",
    "estilos.yaml",
    "dominios/_generico/perfil.yaml",
    "dominios/idiomas/es.yaml",
]


def test_todas_las_plantillas_globales_estan_empaquetadas_y_son_yaml():
    for nombre in PLANTILLAS_YAML:
        texto = leer_plantilla(nombre)
        assert texto.strip(), nombre
        assert isinstance(yaml.safe_load(texto), dict), nombre


def test_recursos_parten_del_perfil_generico():
    asistente = yaml.safe_load(leer_plantilla("asistente.yaml"))
    perfil = yaml.safe_load(leer_plantilla("dominios/_generico/perfil.yaml"))
    assert asistente["perfil"] == "_generico"
    assert perfil["organismos"] == []
    assert perfil["extractores_regex"] == []


def test_widget_y_demo_estan_dentro_del_paquete():
    estaticos = files("rag.servicio").joinpath("estaticos")
    assert estaticos.joinpath("widget.js").is_file()
    assert estaticos.joinpath("demo.html").is_file()
