"""Caracterización de v2 sin modelos: congela lo que responde ``POST /ask``.

Es la red de seguridad de las limpiezas (por ejemplo, retirar el motor v1): si mover o
borrar código cambia una respuesta de v2, esta prueba falla. A diferencia de
``tests/integracion/test_caracterizacion.py`` no necesita modelos descargados ni un
servidor: usa la fábrica real de ``ipsis serve`` con un índice en memoria
(``tests/apoyo_v2.py``), por lo que corre en cualquier máquina y en cada commit.

Cuando un cambio modifica una respuesta a propósito, se regenera el archivo esperado,
se revisa el diff y se explica en el commit y en ``CHANGELOG.md``::

    IPSIS_UPDATE_CHARACTERIZATION=1 python -m pytest tests/consulta/test_caracterizacion_v2.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from apoyo import CARACTERIZACION
from apoyo_v2 import construir_motor_en_memoria
from fastapi.testclient import TestClient

ESPERADO = CARACTERIZACION / "v2_memoria.json"
ACTUALIZAR = os.environ.get("IPSIS_UPDATE_CHARACTERIZATION") == "1"

PREGUNTAS = [
    "hola",
    "gracias",
    "¿Cada cuánto se cambia el filtro del purificador?",
    "¿En cuántos días se paga el reembolso?",
    "¿Cuánto cuesta el purificador P2?",
    "¿Qué pasa si no estoy en la visita?",
    "¿Cuál es la capital de Mongolia?",
    "equipo",
]
# Estados que ningún cambio debe alterar sin explicarlo: son el contrato con el widget.
ESTADOS_PUBLICOS = {"conversational", "related", "no_answer"}


@pytest.fixture(scope="module")
def cliente(proyecto_suite: Path, tmp_path_factory):
    """El servicio con el motor v2 en memoria, construido una vez para todo el módulo."""
    anterior = Path.cwd()
    os.chdir(proyecto_suite)
    mp = pytest.MonkeyPatch()
    mp.setenv("IPSIS_MODELS_DIR", str(tmp_path_factory.mktemp("modelos-vacios")))
    # La disponibilidad del proyecto de disco se verifica en el smoke real, no aquí.
    mp.setattr("ipsis.servicio.api._calcular_diagnostico", lambda: None)
    try:
        from ipsis.servicio.api import crear_app

        with TestClient(crear_app(construir_motor_en_memoria())) as c:
            yield c
    finally:
        mp.undo()
        os.chdir(anterior)


def _normalizar(valor):
    """Quita lo que cambia entre corridas (tiempos) y sustituye los cursores por una marca."""
    if isinstance(valor, dict):
        return {k: ("<cursor>" if k == "continuation" and v else _normalizar(v))
                for k, v in valor.items() if k != "latency_ms" and not k.endswith("_ms")}
    if isinstance(valor, list):
        return [_normalizar(v) for v in valor]
    return valor


def _preguntar(cliente, pregunta, **extra):
    r = cliente.post("/ask", json={"question": pregunta, "session_id": "caracterizacion", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _capturar(cliente) -> dict:
    capturado = {}
    for pregunta in PREGUNTAS:
        capturado[pregunta] = _normalizar(_preguntar(cliente, pregunta))
    # Paginación: «equipo» tiene más resultados que la primera página; el cursor lleva a la segunda.
    primera = _preguntar(cliente, "equipo")
    assert primera["has_more"] and primera["continuation"], "la caracterización necesita una segunda página"
    segunda = _preguntar(cliente, "equipo", continuation=primera["continuation"])
    capturado["equipo (página 2)"] = _normalizar(segunda)
    return capturado


def test_las_respuestas_de_v2_no_cambian(cliente):
    obtenido = _capturar(cliente)
    if ACTUALIZAR:
        ESPERADO.write_text(json.dumps(obtenido, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    esperado = json.loads(ESPERADO.read_text(encoding="utf-8"))
    assert set(obtenido) == set(esperado), "cambió el conjunto de preguntas caracterizadas"
    for pregunta in esperado:
        assert obtenido[pregunta] == esperado[pregunta], f"cambió la respuesta de v2 a {pregunta!r}"


def test_los_estados_publicos_siguen_siendo_los_del_contrato(cliente):
    estados = {_preguntar(cliente, p)["status"] for p in PREGUNTAS}
    assert estados <= ESTADOS_PUBLICOS
    assert {"conversational", "related"} <= estados


def test_la_cortesia_no_busca_y_una_pregunta_sin_coincidencias_no_inventa_fuentes(cliente):
    saludo = _preguntar(cliente, "hola")
    assert saludo["status"] == "conversational" and saludo["fragments"] == []
    fuera = _preguntar(cliente, "¿Cuál es la capital de Mongolia?")
    assert fuera["fragments"] == [] and fuera["status"] != "related"


def test_cada_fuente_publicada_es_un_tramo_literal_con_rango(cliente):
    respuesta = _preguntar(cliente, "¿Cada cuánto se cambia el filtro del purificador?")
    assert respuesta["response_mode"] == "ranked_sources" and respuesta["fragments"]
    assert [f["rank"] for f in respuesta["fragments"]] == list(range(1, len(respuesta["fragments"]) + 1))
    for f in respuesta["fragments"]:
        assert f["offset_start"] <= f["match_start"] <= f["match_end"] <= f["offset_end"]
        assert f["text"] and f["doc_title"] == "Manual del purificador"


def test_el_estado_listo_y_la_configuracion_publica_anuncian_v2(cliente):
    listo = cliente.get("/ready")
    assert listo.status_code == 200 and listo.json()["pipeline"] == "v2"
    assert cliente.get("/config").json()["response_mode"] == "ranked_sources"


def test_la_auditoria_del_motor_describe_solo_lo_que_v2_ejecuta():
    motor = construir_motor_en_memoria()
    auditoria = motor.metadatos_auditoria
    assert auditoria["pipeline"] == "v2"
    assert auditoria["etapas_efectivas"] == list(motor.etapas_efectivas) == [
        "cortesia", "preparacion", "recuperacion", "contexto", "reranking", "lectura", "evidencia", "redaccion"]
    assert auditoria["componentes"]["response_renderer"] == "fuentes_ordenadas_v2"
    assert auditoria["componentes"]["answer_reader"] is None and auditoria["componentes"]["reranker"] is None
    assert auditoria["calibracion_aplicada"] is False
    assert set(auditoria["presupuestos_v2"]) == set(motor.opciones)
