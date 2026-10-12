"""Migración de proyectos anteriores (v2 y v4, en español) a la estructura vigente (v5, en inglés)."""
from __future__ import annotations

from pathlib import Path

import yaml

from apoyo import leer_proyecto
from ipsis.configuracion.migraciones import migrar_proyecto
from ipsis.lenguaje.dominio import cargar_perfil
from ipsis.ingesta.metadata import cargar_taxonomia


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
    conf = tmp_path / "config"
    assert not (tmp_path / "configuracion").exists()
    crudo = yaml.safe_load((conf / "assistant.yaml").read_text(encoding="utf-8"))
    assert crudo["config_version"] == 7 and crudo["profile"] == "light" and crudo["assistant_name"] == "Demo"
    assert (conf / "assistant.yaml").read_text(encoding="utf-8").startswith("# Identidad")
    assert not (conf / "categorias.yaml").exists()
    assert not (conf / "dominios" / "equipos").exists()
    perfil = cargar_perfil(str(conf / "domain.yaml"))
    assert perfil.organismos == ["Mesa Técnica"]
    assert [e.valor_norm for e in perfil.extraer_entidades_extra("el ciclo 4")] == ["ciclo_4"]
    assert [c["id"] for c in cargar_taxonomia(str(conf / "domain.yaml"))["categorias"]] == ["equipo", "otro"]
    assert "regex_extractors" in yaml.safe_load((conf / "domain.yaml").read_text(encoding="utf-8"))
    motor = leer_proyecto(conf / "engine.yaml")
    assert motor["config_version"] == 7
    assert motor["recuperacion"]["qdrant_path"] == ".ipsis/index/qdrant"
    assert (tmp_path / ".ipsis" / "index" / "qdrant" / "meta.json").is_file()
    assert (tmp_path / ".ipsis" / "index" / "demo.json").is_file()
    assert (tmp_path / "golden" / "bank" / "manifest.json").is_file()
    assert not (tmp_path / ".cache").exists() and not (tmp_path / "data").exists()

    assert migrar_proyecto(tmp_path) == []


def _proyecto_v4(raiz: Path) -> None:
    conf = raiz / "configuracion"
    conf.mkdir()
    (conf / "asistente.yaml").write_text(
        "# Identidad.\nconfig_version: 4\nnombre_asistente: Demo\nidioma: es\nperfil: medium\n"
        "registro:\n  activo: true\n",
        encoding="utf-8",
    )
    (conf / "motor.yaml").write_text(
        "config_version: 4\nrecuperacion:\n  modelo: m\n  modo: hibrida\n  coleccion_base: demo\n"
        "  qdrant_path: .rag/indice/qdrant\ncomponentes:\n  abstention_policy: cascada_v1\n"
        "redaccion:\n  cita_en_texto: breve\n",
        encoding="utf-8",
    )
    (conf / "estilos.yaml").write_text(
        "preset: contraste\npresentacion:\n  densidad: compacta\nubicacion:\n  posicion: incrustado\n"
        "colores:\n  acento: '#ff0000'\ncss_extra: ''\n",
        encoding="utf-8",
    )
    (conf / "personalidad.yaml").write_text(
        "config_version: 1\ntono:\n  activo: serio\n  variedad: fija\n"
        "  plantillas:\n    sin_respuesta: ['No está en {descripcion_dominio}.']\n"
        "avatar:\n  activo: true\n  ubicacion: cabecera\n  eventos:\n    respuesta_ok: contento\n",
        encoding="utf-8",
    )
    (conf / "calibracion.yaml").write_text(
        "version: 1\nestado: calibrado\nalfa: 0.05\numbrales:\n  dominio: 0.5\n", encoding="utf-8")
    (raiz / "documentos").mkdir()
    (raiz / "documentos" / "catalogo.yaml").write_text(
        "# Catálogo.\ndocumentos:\n  - archivo: a.md\n    doc_id: a\n    doc_titulo: A\n    version: '1'\n"
        "    vigente: true\n    hash_contenido: abc\n",
        encoding="utf-8",
    )
    (raiz / "documentos" / "a.md").write_text("# A\n", encoding="utf-8")
    (raiz / ".rag" / "indice").mkdir(parents=True)
    (raiz / ".rag" / "indice" / "demo.manifiesto.json").write_text("{}", encoding="utf-8")
    (raiz / ".rag" / "indice" / "demo.estadisticas.json").write_text("{}", encoding="utf-8")
    (raiz / ".rag" / "registros").mkdir()
    (raiz / ".rag" / "registros" / "consultas.jsonl").write_text("", encoding="utf-8")
    (raiz / "golden" / "banco").mkdir(parents=True)
    (raiz / "golden" / "banco" / "manifiesto.json").write_text("{}", encoding="utf-8")


def test_migra_un_proyecto_v4_a_nombres_en_ingles(tmp_path: Path):
    _proyecto_v4(tmp_path)

    cambios = migrar_proyecto(tmp_path)

    assert cambios
    for viejo in ("configuracion", "documentos", ".rag", "golden/banco"):
        assert not (tmp_path / viejo).exists(), viejo
    for nuevo in ("config/assistant.yaml", "config/engine.yaml", "config/styles.yaml", "config/personality.yaml",
                  "config/calibration.yaml", "documents/catalog.yaml", "documents/a.md",
                  ".ipsis/index/demo.manifest.json", ".ipsis/index/demo.stats.json", ".ipsis/logs/queries.jsonl",
                  "golden/bank/manifest.json"):
        assert (tmp_path / nuevo).is_file(), nuevo

    def crudo(relativa):
        return yaml.safe_load((tmp_path / relativa).read_text(encoding="utf-8"))

    asistente = crudo("config/assistant.yaml")
    assert asistente == {"config_version": 7, "assistant_name": "Demo", "language": "es", "profile": "medium",
                         "query_log": {"enabled": True}}
    assert (tmp_path / "config/assistant.yaml").read_text(encoding="utf-8").startswith("# Identidad.")
    motor = crudo("config/engine.yaml")
    assert motor["retrieval"] == {"model": "m", "mode": "hybrid", "collection_base": "demo",
                                  "qdrant_path": ".ipsis/index/qdrant"}
    assert motor["components"] == {"abstention_policy": "cascade_v1"}
    assert motor["rendering"] == {"inline_citation": "short"}
    assert crudo("config/styles.yaml") == {"preset": "contrast", "presentation": {"density": "compact"},
                                          "placement": {"position": "embedded"}, "colors": {"accent": "#ff0000"},
                                          "custom_css": ""}
    personalidad = crudo("config/personality.yaml")
    assert personalidad["tone"] == {"active": "serious", "variety": "fixed",
                                    "templates": {"no_answer": ["No está en {domain_description}."]}}
    assert personalidad["avatar"] == {"enabled": True, "placement": "header", "events": {"answer_ok": "happy"}}
    assert crudo("config/calibration.yaml") == {"version": 1, "status": "calibrated", "alpha": 0.05,
                                               "thresholds": {"domain": 0.5}}
    catalogo = crudo("documents/catalog.yaml")
    assert catalogo == {"documents": [{"file": "a.md", "doc_id": "a", "doc_title": "A", "version": "1",
                                       "active": True, "content_hash": "abc"}]}

    # Lo que lee el código no cambió: los mismos valores con los nombres internos.
    assert leer_proyecto(tmp_path / "config/engine.yaml")["recuperacion"]["modo"] == "hibrida"
    assert leer_proyecto(tmp_path / "config/styles.yaml")["ubicacion"]["posicion"] == "incrustado"

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

    assert not (tmp_path / "config" / "textos.yaml").exists()
    idioma = yaml.safe_load((tmp_path / "config" / "language.yaml").read_text(encoding="utf-8"))
    assert idioma == {"mensajes": {"sin_respuesta": "Nada por aquí."}}
    assert any("language.yaml" in c for c in cambios)
