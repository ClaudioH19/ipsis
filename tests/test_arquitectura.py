"""Reglas de dependencia entre las capas de ``rag/``.

Un módulo solo importa de su capa o de capas inferiores. Las capas base no
cargan librerías pesadas al importarse. Ver ``docs/README.md`` (Arquitectura).
"""
from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "rag"

CAPAS = {
    "nucleo": 0,
    "recursos": 0,
    "configuracion": 1,
    "lenguaje": 2,
    "ingesta": 3,
    "modelos": 3,
    "indice": 3,
    "consulta": 4,
    "evaluacion": 5,
    "aplicacion": 6,
    "cli": 7,
    "servicio": 7,
}
CAPAS_LIVIANAS = {"nucleo", "recursos", "configuracion", "lenguaje"}
PESADAS = ("onnxruntime", "qdrant_client", "fastapi", "torch", "sentence_transformers")


def _capa(partes: list[str]) -> str | None:
    if len(partes) < 2 or partes[0] != "rag":
        return None
    return partes[1].removesuffix(".py")


def _modulos():
    for archivo in sorted(RAIZ.rglob("*.py")):
        partes = ["rag", *archivo.relative_to(RAIZ).with_suffix("").parts]
        capa = _capa(partes)
        if capa is None or capa == "__init__":
            continue
        yield archivo, capa, ast.parse(archivo.read_text(encoding="utf-8"))


def _imports(arbol: ast.AST):
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            yield nodo, nodo.module
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield nodo, alias.name


def test_todo_modulo_pertenece_a_una_capa_conocida():
    desconocidas = {capa for _, capa, _ in _modulos() if capa not in CAPAS}
    assert not desconocidas, f"capas sin declarar en CAPAS: {sorted(desconocidas)}"


def test_ninguna_capa_importa_de_una_capa_superior():
    violaciones = []
    for archivo, capa, arbol in _modulos():
        for nodo, modulo in _imports(arbol):
            destino = _capa(modulo.split("."))
            if destino in CAPAS and CAPAS[destino] > CAPAS[capa]:
                rel = archivo.relative_to(RAIZ.parent).as_posix()
                violaciones.append(f"{rel}:{nodo.lineno} {capa} -> {modulo}")
    assert not violaciones, "imports que suben de capa:\n" + "\n".join(violaciones)


def test_capas_base_no_importan_librerias_pesadas_al_cargarse():
    violaciones = []
    for archivo, capa, arbol in _modulos():
        if capa not in CAPAS_LIVIANAS:
            continue
        # Solo cuentan los imports de nivel de módulo: dentro de una función se
        # cargan recién al usarse.
        for nodo in arbol.body:
            if isinstance(nodo, (ast.Import, ast.ImportFrom)):
                for _, modulo in _imports(nodo):
                    if modulo.split(".")[0] in PESADAS:
                        violaciones.append(f"{archivo.relative_to(RAIZ.parent).as_posix()}: {modulo}")
    assert not violaciones, "\n".join(violaciones)


# Desde P11.1: la CLI y el servicio son presentación; solo hablan con la capa
# de aplicación (y con nucleo/recursos). Nunca directo con configuración,
# lenguaje, ingesta, modelos, índice, consulta ni evaluación.
FRONTERA = {"cli", "servicio"}
PERMITIDAS_EN_FRONTERA = {"aplicacion", "nucleo", "recursos"}


def violaciones_de_frontera(capa: str, arbol: ast.AST) -> list[tuple[int, str]]:
    """``(línea, módulo)`` de cada import de ``capa`` a una capa ``rag`` no
    permitida. Ignora la biblioteca estándar y dependencias externas."""
    if capa not in FRONTERA:
        return []
    salida = []
    for nodo, modulo in _imports(arbol):
        destino = _capa(modulo.split("."))
        if destino in CAPAS and destino != capa and destino not in PERMITIDAS_EN_FRONTERA:
            salida.append((nodo.lineno, modulo))
    return salida


def test_cli_y_servicio_solo_importan_aplicacion_nucleo_y_recursos():
    violaciones = [f"{archivo.relative_to(RAIZ.parent).as_posix()}:{linea} {capa} -> {modulo}"
                   for archivo, capa, arbol in _modulos()
                   for linea, modulo in violaciones_de_frontera(capa, arbol)]
    assert not violaciones, "la presentación debe pasar por rag.aplicacion:\n" + "\n".join(violaciones)


def test_la_regla_de_frontera_detecta_un_import_prohibido():
    codigo = ast.parse(
        "import argparse\nfrom pathlib import Path\nimport yaml\n"
        "from rag.aplicacion.golden import importar_golden\nfrom rag.nucleo.registro import RegistroComponentes\n"
        "from rag.cli.base import Comando\n"
        "from rag.evaluacion.golden import ErrorGolden\n"
        "def f():\n    from rag.configuracion.carga import cargar_dominio\n"
    )
    assert violaciones_de_frontera("cli", codigo) == [(7, "rag.evaluacion.golden"), (9, "rag.configuracion.carga")]
    # Para el servicio, importar la CLI también es una violación (presentación → presentación).
    assert [m for _, m in violaciones_de_frontera("servicio", codigo)] == [
        "rag.cli.base", "rag.evaluacion.golden", "rag.configuracion.carga"]
    assert violaciones_de_frontera("aplicacion", codigo) == []  # la regla es solo para la presentación
