"""Pruebas del motor genérico de perfiles declarativos."""
from __future__ import annotations

from pathlib import Path

import pytest

from rag.dominio import cargar_perfil, cargar_perfil_generico
from rag.reglas_extraccion import extraer_notas, extraer_porcentajes


@pytest.fixture()
def perfil_sintetico(tmp_path: Path):
    base = tmp_path / "dominios"
    ruta = base / "equipos" / "perfil.yaml"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(
        """nombre_asistente: Asistente de equipos
descripcion_dominio: manuales ficticios
idioma: es
organismos: [Mesa Técnica]
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
    return cargar_perfil("equipos", str(base))


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


def test_perfil_inexistente_lista_disponibles(tmp_path: Path):
    base = tmp_path / "dominios"
    generico = base / "_generico"
    generico.mkdir(parents=True)
    (generico / "perfil.yaml").write_text("extractores_regex: []\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError) as exc_info:
        cargar_perfil("no_existe", str(base))
    assert "no_existe" in str(exc_info.value)
    assert "_generico" in str(exc_info.value)


def test_perfil_generico_no_aporta_entidades():
    assert cargar_perfil_generico().extraer_entidades_extra("modelo 3, 20%") == []
    assert cargar_perfil_generico().tipos_aportados() == set()


def test_entidades_del_nucleo_no_dependen_del_perfil():
    texto = "la nota final es 3,9 y cubre el 20%"
    assert [e.valor_norm for e in extraer_notas(texto)] == ["3.9"]
    assert [e.valor_norm for e in extraer_porcentajes(texto)] == ["20_pct"]


def test_tipos_y_glosas_de_perfil_sintetico(perfil_sintetico):
    assert perfil_sintetico.tipos_aportados() == {"ciclo", "modelo", "organismo"}
    assert perfil_sintetico.glosas_extra() == {"ciclo": "ciclo de mantenimiento"}
