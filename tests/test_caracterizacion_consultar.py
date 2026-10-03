"""Caracterización de ``POST /consultar``: congela el comportamiento actual.

Sirve de red de seguridad para las refactorizaciones de ``docs/plan/``: mover
código no debe cambiar ninguna respuesta. Congela también respuestas malas
conocidas; cuando una tarea las corrija a propósito, se regenera el archivo
esperado y el cambio se documenta en ``docs/plan/avance.md``.

El servidor corre en un subproceso con ``rag servir`` sobre el corpus sintético
de ``tests/caracterizacion/corpus``, de modo que la prueba solo depende del
contrato HTTP, no de la estructura interna del servicio.

Regenerar el archivo esperado (revisar el diff antes de hacer commit)::

    RAG_ACTUALIZAR_CARACTERIZACION=1 python -m pytest tests/test_caracterizacion_consultar.py
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

pytestmark = pytest.mark.slow

DIR = Path(__file__).parent / "caracterizacion"
ESPERADO = DIR / "consultar_esperado.json"
ACTUALIZAR = os.environ.get("RAG_ACTUALIZAR_CARACTERIZACION") == "1"

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
        [sys.executable, "-m", "rag.cli", *args], cwd=str(cwd),
        capture_output=True, text=True, timeout=timeout,
    )
    assert r.returncode == 0, f"rag {' '.join(args)}:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"


@pytest.fixture(scope="module")
def url_servicio():
    proyecto = Path(tempfile.mkdtemp(prefix="rag_caracterizacion_"))
    proceso = None
    try:
        _rag(["init", "--nombre-asistente", "Asistente Aqualis",
              "--descripcion-dominio", "los manuales del purificador Aqualis"], proyecto)
        _rag(["cargar", str(DIR / "corpus")], proyecto)
        _rag(["indexar"], proyecto)

        puerto = _puerto_libre()
        proceso = subprocess.Popen(
            [sys.executable, "-m", "rag.cli", "servir", "--port", str(puerto)],
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
        "estado": datos["estado"],
        "nivel_servicio": datos["nivel_servicio"],
        "plan": datos["plan"],
        "respuesta": datos["respuesta"],
        "confianza": {
            "top1": round(datos["confianza"]["top1"], 5),
            "margen": round(datos["confianza"]["margen"], 5),
        },
        "fragmentos": [
            {
                "chunk_id": f["chunk_id"],
                "doc_titulo": f["doc_titulo"],
                "seccion": f["seccion"],
                "offset_inicio": f["offset_inicio"],
                "offset_fin": f["offset_fin"],
                "texto": f["texto"],
                "score": round(f["score"], 5),
            }
            for f in datos["fragmentos"]
        ],
    }


@pytest.fixture(scope="module")
def observado(url_servicio):
    salida = {}
    for pregunta in PREGUNTAS:
        r = httpx.post(f"{url_servicio}/consultar",
                       json={"pregunta": pregunta, "id_sesion": "caracterizacion"}, timeout=60.0)
        assert r.status_code == 200, r.text
        salida[pregunta] = _resumen(r.json())
    if ACTUALIZAR:
        ESPERADO.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return salida


def _sin_scores(resumen: dict) -> dict:
    copia = json.loads(json.dumps(resumen))
    copia.pop("confianza")
    for f in copia["fragmentos"]:
        f.pop("score")
    return copia


@pytest.mark.parametrize("pregunta", PREGUNTAS)
def test_consultar_no_cambia(observado, pregunta):
    if ACTUALIZAR:
        pytest.skip("archivo esperado regenerado")
    esperado = json.loads(ESPERADO.read_text(encoding="utf-8"))[pregunta]
    actual = observado[pregunta]

    assert _sin_scores(actual) == _sin_scores(esperado)
    assert actual["confianza"]["top1"] == pytest.approx(esperado["confianza"]["top1"], abs=TOLERANCIA_SCORE)
    assert actual["confianza"]["margen"] == pytest.approx(esperado["confianza"]["margen"], abs=TOLERANCIA_SCORE)
    for f_act, f_esp in zip(actual["fragmentos"], esperado["fragmentos"]):
        assert f_act["score"] == pytest.approx(f_esp["score"], abs=TOLERANCIA_SCORE)


def test_caracterizacion_cubre_todos_los_estados(observado):
    """Si una pregunta cambia de estado al regenerar, la cobertura no debe perderse."""
    estados = {r["estado"] for r in observado.values()}
    assert {"ok", "relacionado", "sin_respuesta", "conversacional"} <= estados


def test_respuestas_son_texto_literal_del_corpus(observado):
    """Invariante que la refactorización debe preservar: cada fragmento citado
    es una subcadena exacta del corpus parseado, en los offsets declarados."""
    from rag.ingesta.parsear import parsear_markdown

    textos = {}
    for ruta in (DIR / "corpus").glob("*.md"):
        doc = parsear_markdown(str(ruta), doc_id="x", doc_titulo="x", version="1")
        textos[ruta.stem] = doc.texto_completo
    for pregunta, resumen in observado.items():
        for f in resumen["fragmentos"]:
            assert any(
                t[f["offset_inicio"]:f["offset_fin"]] == f["texto"] for t in textos.values()
            ), (pregunta, f["chunk_id"])
