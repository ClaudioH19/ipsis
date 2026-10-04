"""Catálogo y descarga de modelos, con la descarga simulada (sin red)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ipsis.modelos import descarga
from ipsis.modelos.catalogo import CATALOGO, obtener


def test_catalogo_tiene_un_modelo_por_tarea_y_licencias_permitidas():
    tareas = {spec.tarea for spec in CATALOGO.values()}
    assert tareas == {"denso", "reranker", "lector"}
    for spec in CATALOGO.values():
        assert "NC" not in spec.licencia  # ningún modelo no comercial


def test_archivo_onnx_por_arquitectura():
    spec = obtener("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    assert spec.archivo_onnx("AMD64") == "onnx/model_quint8_avx2.onnx"
    assert spec.archivo_onnx("aarch64") == "onnx/model_qint8_arm64.onnx"
    assert obtener("intfloat/multilingual-e5-small").archivo_onnx("arm64") == "onnx/model.onnx"


def test_modelo_desconocido_lista_los_disponibles():
    with pytest.raises(KeyError, match="disponibles"):
        obtener("nadie/modelo")


@pytest.fixture()
def hub_falso(tmp_path, monkeypatch):
    llamadas = []

    def snapshot_download(repo_id, allow_patterns, cache_dir, local_files_only):
        llamadas.append((repo_id, local_files_only, cache_dir))
        carpeta = Path(cache_dir) / repo_id.replace("/", "--")
        if local_files_only and not carpeta.exists():
            raise OSError("no está en caché")
        for patron in allow_patterns:
            if patron.endswith(".onnx") or patron.endswith(".json"):
                (carpeta / patron).parent.mkdir(parents=True, exist_ok=True)
                (carpeta / patron).write_text("x", encoding="utf-8")
        return str(carpeta)

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", snapshot_download)
    monkeypatch.setenv("IPSIS_MODELS_DIR", str(tmp_path / "cache"))
    return llamadas


def test_descarga_usa_la_cache_global(hub_falso, tmp_path):
    spec = obtener("intfloat/multilingual-e5-small")
    assert descarga.ruta_cache() == tmp_path / "cache"
    assert not descarga.esta_en_cache(spec)
    carpeta = descarga.descargar(spec)
    assert (carpeta / "onnx/model.onnx").is_file()
    assert descarga.esta_en_cache(spec)
    assert [solo_local for _, solo_local, _ in hub_falso] == [True, False, True]


def test_sin_cache_el_error_dice_que_comando_ejecutar(hub_falso):
    with pytest.raises(FileNotFoundError, match="ipsis modelos descargar"):
        descarga.ruta_local(obtener("dewdev/mdeberta-v3-base-squad2-onnx"))
