"""Migración de un proyecto v2 a la estructura v3."""
from __future__ import annotations

from pathlib import Path

import yaml

from rag.configuracion.migraciones import migrar_proyecto
from rag.lenguaje.dominio import cargar_perfil
from rag.ingesta.metadata import cargar_taxonomia


def _proyecto_v2(raiz: Path) -> None:
    conf = raiz / "configuracion"
    (conf / "dominios" / "equipos").mkdir(parents=True)
    (conf / "asistente.yaml").write_text(
        "# Identidad del asistente.\nconfig_version: 2\nnombre_asistente: Demo\n"
        "descripcion_dominio: manuales\nidioma: es\nperfil: equipos\n"
        "cors_origenes: []\nclaves_widget: []\n",
        encoding="utf-8",
    )
    (conf / "dominios" / "equipos" / "perfil.yaml").write_text(
        "nombre_asistente: Demo\norganismos: [Mesa Técnica]\n"
        "extractores_regex:\n  - tipo: ciclo\n    patron: 'ciclo (?P<n>\\d+)'\n    valor_norm: 'ciclo_{n}'\n",
        encoding="utf-8",
    )
    (conf / "categorias.yaml").write_text(
        "dominio: manuales\ncategorias:\n  - id: equipo\n    descripcion: Equipos\n  - id: otro\n    descripcion: Otro\n",
        encoding="utf-8",
    )
    (conf / "motor.yaml").write_text(
        "config_version: 2\nrecuperacion:\n  modelo: m\n  estrategia_chunking: CH-F256\n"
        "  coleccion_base: demo\n  qdrant_path: .cache/qdrant_local\n",
        encoding="utf-8",
    )
    (raiz / ".cache" / "qdrant_local").mkdir(parents=True)
    (raiz / ".cache" / "qdrant_local" / "meta.json").write_text("{}", encoding="utf-8")
    (raiz / ".cache" / "vocab_bm25").mkdir(parents=True)
    (raiz / ".cache" / "vocab_bm25" / "demo.json").write_text("{}", encoding="utf-8")
    (raiz / "data" / "golden").mkdir(parents=True)
    (raiz / "data" / "golden" / "manifiesto.json").write_text("{}", encoding="utf-8")


def test_migra_un_proyecto_v2_y_es_idempotente(tmp_path: Path):
    _proyecto_v2(tmp_path)

    cambios = migrar_proyecto(tmp_path)

    assert cambios
    conf = tmp_path / "configuracion"
    asistente = yaml.safe_load((conf / "asistente.yaml").read_text(encoding="utf-8"))
    assert asistente["config_version"] == 3 and "perfil" not in asistente
    assert (conf / "asistente.yaml").read_text(encoding="utf-8").startswith("# Identidad")
    assert not (conf / "categorias.yaml").exists()
    assert not (conf / "dominios" / "equipos").exists()
    perfil = cargar_perfil(str(conf / "dominio.yaml"))
    assert perfil.organismos == ["Mesa Técnica"]
    assert [e.valor_norm for e in perfil.extraer_entidades_extra("el ciclo 4")] == ["ciclo_4"]
    assert [c["id"] for c in cargar_taxonomia(str(conf / "dominio.yaml"))["categorias"]] == ["equipo", "otro"]
    motor = yaml.safe_load((conf / "motor.yaml").read_text(encoding="utf-8"))
    assert motor["config_version"] == 3
    assert motor["recuperacion"]["qdrant_path"] == ".rag/indice/qdrant"
    assert (tmp_path / ".rag" / "indice" / "qdrant" / "meta.json").is_file()
    assert (tmp_path / ".rag" / "indice" / "demo.json").is_file()
    assert (tmp_path / "golden" / "banco" / "manifiesto.json").is_file()
    assert not (tmp_path / ".cache").exists() and not (tmp_path / "data").exists()

    assert migrar_proyecto(tmp_path) == []


def test_sin_proyecto_no_hace_nada(tmp_path: Path):
    assert migrar_proyecto(tmp_path) == []


def test_textos_personalizados_pasan_a_idioma_yaml(tmp_path: Path):
    conf = tmp_path / "configuracion"
    conf.mkdir()
    (conf / "asistente.yaml").write_text("config_version: 3\nidioma: es\n", encoding="utf-8")
    (conf / "textos.yaml").write_text(
        "abstencion:\n  generico: Nada por aquí.\n"
        "  premisa_no_encontrada: \"No encontré información sobre \\\"{entidad}\\\" en los documentos disponibles. "
        "Puede que no exista o que esté fuera de lo que cubren tus documentos.\"\n",
        encoding="utf-8",
    )

    cambios = migrar_proyecto(tmp_path)

    assert not (conf / "textos.yaml").exists()
    idioma = yaml.safe_load((conf / "idioma.yaml").read_text(encoding="utf-8"))
    assert idioma == {"mensajes": {"sin_respuesta": "Nada por aquí."}}
    assert any("idioma.yaml" in c for c in cambios)
