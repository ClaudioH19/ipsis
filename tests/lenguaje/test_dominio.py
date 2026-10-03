"""Pruebas del motor genérico de perfiles declarativos."""
from __future__ import annotations

from pathlib import Path

import pytest

from rag.lenguaje.dominio import cargar_perfil
from rag.lenguaje.entidades import extraer_decimales, extraer_porcentajes


@pytest.fixture()
def perfil_sintetico(tmp_path: Path):
    ruta = tmp_path / "dominio.yaml"
    ruta.write_text(
        """organismos: [Mesa Técnica]
extractores_regex:
  - tipo: ciclo
    patron: '\\bciclos?\\s+(?P<n1>\\d+)(\\s+(?P<conector>y|a)\\s+(?P<n2>\\d+))?\\b'
    valor_norm: 'ciclo_{n1}[_{conector}_{n2}]'
    glosa: ciclo de mantenimiento
  - tipo: modelo
    patron: '\\bmodelo\\s+(?P<num>I{1,3}|IV|[1-4])\\b'
    transform: {num: romano_a_num}
    valor_norm: 'modelo_{num}'
""",
        encoding="utf-8",
    )
    return cargar_perfil(str(ruta))


def test_segmento_opcional_omitido(perfil_sintetico):
    entidades = perfil_sintetico.extraer_entidades_extra("revisar en el ciclo 4")
    assert entidades[0].valor_norm == "ciclo_4"


def test_segmento_opcional_presente(perfil_sintetico):
    entidades = perfil_sintetico.extraer_entidades_extra("revisar en los ciclos 7 a 10")
    assert entidades[0].valor_norm == "ciclo_7_a_10"


def test_transform_romano_a_num(perfil_sintetico):
    entidades = perfil_sintetico.extraer_entidades_extra("El modelo III requiere mantenimiento")
    assert next(e for e in entidades if e.tipo == "modelo").valor_norm == "modelo_3"


def test_transform_no_afecta_digito(perfil_sintetico):
    entidades = perfil_sintetico.extraer_entidades_extra("El modelo 2 está activo")
    assert next(e for e in entidades if e.tipo == "modelo").valor_norm == "modelo_2"


def test_sin_dominio_yaml_el_perfil_no_aporta_entidades(tmp_path: Path):
    perfil = cargar_perfil(str(tmp_path / "no_existe.yaml"))
    assert perfil.extraer_entidades_extra("modelo 3, 20%") == []
    assert perfil.tipos_aportados() == set()


def test_plantilla_de_dominio_no_aporta_entidades(tmp_path: Path):
    from rag.recursos import leer_plantilla

    ruta = tmp_path / "dominio.yaml"
    ruta.write_text(leer_plantilla("dominio.yaml"), encoding="utf-8")
    assert cargar_perfil(str(ruta)).tipos_aportados() == set()


def test_ejemplo_comentado_del_perfil_generico_funciona(tmp_path: Path):
    """El ejemplo de regla documentado en la plantilla debe seguir siendo válido."""
    from rag.recursos import leer_plantilla

    lineas = leer_plantilla("dominio.yaml").splitlines()
    inicio = lineas.index("# extractores_regex:")
    ejemplo = []
    for linea in lineas[inicio:]:
        if not linea.startswith("#"):
            break
        ejemplo.append(linea[2:])
    ruta = tmp_path / "dominio.yaml"
    ruta.write_text("\n".join(ejemplo) + "\n", encoding="utf-8")

    perfil = cargar_perfil(str(ruta))
    valores = [e.valor_norm for e in perfil.extraer_entidades_extra("con nota 3,9 reprueba")]
    assert valores == ["nota_3.9"]


def test_entidades_del_nucleo_no_dependen_del_perfil():
    texto = "la nota final es 3,9 y cubre el 20%"
    assert [e.valor_norm for e in extraer_decimales(texto)] == ["3.9"]
    assert [e.valor_norm for e in extraer_porcentajes(texto)] == ["20_pct"]


def test_tipos_y_glosas_de_perfil_sintetico(perfil_sintetico):
    assert perfil_sintetico.tipos_aportados() == {"ciclo", "modelo", "organismo"}
    assert perfil_sintetico.glosas_extra() == {"ciclo": "ciclo de mantenimiento"}
