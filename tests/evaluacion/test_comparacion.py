from __future__ import annotations

import pytest

from ipsis.evaluacion.comparacion import comparar_artefactos
from ipsis.evaluacion.metricas import ArtefactoEvaluacion, ReporteMetricas


def _artefacto(backend: str, *, dataset_sha256: str = "a" * 64):
    reporte = ReporteMetricas(
        dataset_id="banco",
        dataset_version="1.0.0",
        k=3,
        n_casos=12,
        recall_at_k=0.75,
        mrr=0.7,
        tasa_falsos_ok=0.0,
        precision_abstencion=1.0,
        exactitud_estado=0.8,
        exactitud_literal=0.75,
        exactitud_offsets=1.0,
        tasa_respuestas_excesivas=0.1,
        distribucion_estados={"respuesta_directa": 4, "sin_respuesta": 8},
        latencia_media_ms=10.0,
        latencia_p95_ms=15.0,
        latencia_etapas_media_ms={"recuperacion_ms": 2.0},
        por_backend={},
        por_categoria={},
        guardia_falsos_ok=True,
    )
    return ArtefactoEvaluacion(
        backend=backend,
        dataset_id="banco",
        dataset_version="1.0.0",
        dataset_sha256=dataset_sha256,
        configuracion_sha256=("b" if backend == "qdrant_vectorial" else "c") * 64,
        configuracion={"componentes": {"retriever": backend}},
        indice={"version": 1},
        reporte=reporte,
    )


def test_compara_sin_elegir_ganador_y_conserva_procedencia():
    informe = comparar_artefactos([
        _artefacto("qdrant_vectorial"), _artefacto("qdrant_hibrida")
    ])

    assert [fila.backend for fila in informe.filas] == [
        "qdrant_vectorial", "qdrant_hibrida"
    ]
    assert informe.dataset_version == "1.0.0"
    assert informe.decisiones == []
    assert all(fila.configuracion_sha256 for fila in informe.filas)


def test_rechaza_comparar_corpus_distintos():
    with pytest.raises(ValueError, match="mismo dataset, corpus y k"):
        comparar_artefactos([
            _artefacto("qdrant_vectorial"),
            _artefacto("qdrant_hibrida", dataset_sha256="d" * 64),
        ])


def test_cli_comparar_escribe_informe(tmp_path):
    from ipsis.cli import main

    rutas = []
    for backend in ("qdrant_vectorial", "qdrant_hibrida"):
        ruta = tmp_path / f"{backend}.json"
        ruta.write_text(_artefacto(backend).model_dump_json(indent=2), encoding="utf-8")
        rutas.append(str(ruta))
    salida = tmp_path / "comparacion.json"

    assert main(["compare", *rutas, "--output", str(salida)]) == 0
    assert '"decisiones": []' in salida.read_text(encoding="utf-8")
