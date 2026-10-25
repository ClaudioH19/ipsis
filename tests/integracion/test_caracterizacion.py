"""Caracterización de ``POST /ask``: congela lo que publica el motor v2.

Sirve de red de seguridad para las refactorizaciones: mover código no debe
cambiar ninguna respuesta. Congela también respuestas malas conocidas; cuando
un cambio las corrija a propósito, se regenera el archivo esperado y el
cambio se explica en el commit y en ``CHANGELOG.md``.

El servidor corre en un subproceso con ``ipsis serve`` sobre el corpus sintético
de ``tests/datos/corpus``, de modo que la prueba solo depende del
contrato HTTP, no de la estructura interna del servicio. Corre con ``light`` y,
si sus modelos están en caché, con ``medium`` (un archivo esperado por perfil).

Regenerar el archivo esperado (revisar el diff antes de hacer commit)::

    IPSIS_UPDATE_CHARACTERIZATION=1 python -m pytest tests/integracion/test_caracterizacion.py
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest
from apoyo import CARACTERIZACION, CORPUS

pytestmark = pytest.mark.slow

MEDIUM = pytest.param("medium", marks=pytest.mark.modelos(
    "onnx-community/bge-reranker-v2-m3-ONNX"))
ACTUALIZAR = os.environ.get("IPSIS_UPDATE_CHARACTERIZATION") == "1"

# Tolerancia para los puntajes: absorbe diferencias numéricas entre CPUs y
# bibliotecas BLAS (del orden de 1e-5). La pregunta más cercana a un umbral
# está a ~0.0016 de él, así que el estado no depende de ese ruido.
TOLERANCIA_SCORE = 1e-3

PREGUNTAS = [
    "hola",
    "gracias",
    "¿Cada cuánto se cambia el filtro de sedimentos?",
    "¿Puedo pedir reembolso después de instalarlo?",
    "¿En cuántos días hábiles se paga el reembolso?",
    "¿Cuánto cuesta el purificador?",
    "¿Qué pasa si no estoy en la visita?",
    "¿El equipo funciona con agua caliente?",
    "¿Atienden los domingos?",
    "¿Qué recargo se cobra según el artículo 4?",
    "¿Qué hago si la presión supera 4,0 bar?",
    "¿El equipo rechaza el 12,5% del agua?",
    "¿Qué dice el artículo 99?",
    "¿Rechaza el 5% del agua?",
    "¿Cómo se prepara un asado?",
    "¿Cuál es la capital de Mongolia?",
]


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _rag(args: list[str], cwd: Path, timeout: float = 300.0) -> None:
    r = subprocess.run(
        [sys.executable, "-m", "ipsis.cli", *args], cwd=str(cwd),
        capture_output=True, text=True, timeout=timeout,
    )
    assert r.returncode == 0, f"ipsis {' '.join(args)}:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"


@pytest.fixture(scope="module", params=["light", MEDIUM])
def perfil(request) -> str:
    return request.param


@pytest.fixture(scope="module")
def url_servicio(perfil):
    proyecto = Path(tempfile.mkdtemp(prefix="rag_caracterizacion_"))
    proceso = None
    try:
        _rag(["init", "--assistant-name", "Asistente Aqualis",
              "--domain-description", "los manuales del purificador Aqualis", "--profile", perfil], proyecto)
        # El archivo esperado congela lo que publica v2 con la preparación estructural. El presupuesto de consulta
        # se amplía para que el reordenamiento progresivo termine siempre: con el de producción (2500 ms) el
        # resultado dependería de la velocidad de la CPU en que corre la prueba.
        motor = proyecto / "config" / "engine.yaml"
        motor.write_text(motor.read_text(encoding="utf-8").replace("query_budget_ms: 2500", "query_budget_ms: 30000", 1),
                         encoding="utf-8")
        _rag(["load", str(CORPUS)], proyecto)
        _rag(["index"], proyecto)

        puerto = _puerto_libre()
        proceso = subprocess.Popen(
            [sys.executable, "-m", "ipsis.cli", "serve", "--port", str(puerto)],
            cwd=str(proyecto), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{puerto}"
        limite = time.time() + 120
        while time.time() < limite:
            try:
                if httpx.get(f"{url}/ready", timeout=1.0).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            pytest.fail("el servicio no quedó listo en 120 s")
        yield url
    finally:
        if proceso is not None:
            proceso.terminate()
            try:
                proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()
        shutil.rmtree(proyecto, ignore_errors=True)


def _resumen(datos: dict) -> dict:
    """Todo lo observable salvo la latencia."""
    return {
        "status": datos["status"],
        "service_level": datos["service_level"],
        "plan": datos["plan"],
        "answer": datos["answer"],
        "confidence": {
            "top1": round(datos["confidence"]["top1"], 5),
            "margin": round(datos["confidence"]["margin"], 5),
        },
        "fragments": [
            {
                "chunk_id": f["chunk_id"],
                "doc_title": f["doc_title"],
                "section": f["section"],
                "offset_start": f["offset_start"],
                "offset_end": f["offset_end"],
                "text": f["text"],
                "score": round(f["score"], 5),
            }
            for f in datos["fragments"]
        ],
    }


@pytest.fixture(scope="module")
def observado(url_servicio, perfil):
    salida = {}
    for pregunta in PREGUNTAS:
        r = httpx.post(f"{url_servicio}/ask",
                       json={"question": pregunta, "session_id": "caracterizacion"}, timeout=60.0)
        assert r.status_code == 200, r.text
        salida[pregunta] = _resumen(r.json())
    if ACTUALIZAR:
        (CARACTERIZACION / f"{perfil}.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                                        newline="\n")
    return salida


def _sin_scores(resumen: dict) -> dict:
    copia = json.loads(json.dumps(resumen))
    copia.pop("confidence")
    for f in copia["fragments"]:
        f.pop("score")
    return copia


@pytest.mark.parametrize("pregunta", PREGUNTAS)
def test_consultar_no_cambia(observado, perfil, pregunta):
    if ACTUALIZAR:
        pytest.skip("archivo esperado regenerado")
    esperado = json.loads((CARACTERIZACION / f"{perfil}.json").read_text(encoding="utf-8"))[pregunta]
    actual = observado[pregunta]

    assert _sin_scores(actual) == _sin_scores(esperado)
    assert actual["confidence"]["top1"] == pytest.approx(esperado["confidence"]["top1"], abs=TOLERANCIA_SCORE)
    assert actual["confidence"]["margin"] == pytest.approx(esperado["confidence"]["margin"], abs=TOLERANCIA_SCORE)
    for f_act, f_esp in zip(actual["fragments"], esperado["fragments"]):
        assert f_act["score"] == pytest.approx(f_esp["score"], abs=TOLERANCIA_SCORE)


def test_caracterizacion_cubre_todos_los_estados(observado):
    """Si una pregunta cambia de estado al regenerar, la cobertura no debe perderse."""
    estados = {r["status"] for r in observado.values()}
    # v2 publica siempre las mejores fuentes: las preguntas fuera del corpus también salen «related»
    # (ver ADR 0012); «no_answer» solo aparece sin ninguna fuente recuperable.
    assert {"related", "conversational"} <= estados
    assert "ok" not in estados, "v2 publica fuentes; nunca responde «ok»"


def test_respuestas_son_texto_literal_del_corpus(observado):
    """Invariante que la refactorización debe preservar: cada fragmento citado
    es una subcadena exacta del corpus parseado, en los offsets declarados."""
    from ipsis.ingesta.parsear import parsear_markdown

    textos = {}
    for ruta in CORPUS.glob("*.md"):
        doc = parsear_markdown(str(ruta), doc_id="x", doc_titulo="x", version="1")
        textos[ruta.stem] = doc.texto_completo
    for pregunta, resumen in observado.items():
        for f in resumen["fragments"]:
            assert any(
                t[f["offset_start"]:f["offset_end"]] == f["text"] for t in textos.values()
            ), (pregunta, f["chunk_id"])
