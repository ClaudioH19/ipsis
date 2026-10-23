"""v2 no depende del motor v1: servirlo no carga ni una línea de la cascada.

Dos garantías complementarias:

* la **regla estática** (``tests/test_arquitectura.py``) mira todos los imports, también los
  diferidos dentro de funciones, que una ejecución puede no recorrer;
* esta prueba **ejecuta** el recorrido real de ``ipsis serve`` (fábrica, ``/ask``, cortesía,
  paginación, ``/ready``, ``/config``) en un intérprete limpio y comprueba qué módulos
  quedaron cargados.

Un intérprete limpio es necesario: dentro de la suite, otras pruebas ya importaron v1.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from apoyo_v2 import MODULOS_V1, es_modulo_v1

TESTS = Path(__file__).resolve().parents[1]

RECORRIDO = """
import json, os, sys, tempfile
sys.path.insert(0, sys.argv[1])
os.environ["IPSIS_MODELS_DIR"] = tempfile.mkdtemp()
import ipsis.cli  # la superficie de la CLI
import ipsis.servicio.api as api
api._calcular_diagnostico = lambda: None
from apoyo_v2 import construir_motor_en_memoria
from fastapi.testclient import TestClient

with TestClient(api.crear_app(construir_motor_en_memoria())) as c:
    assert c.get("/ready").json()["pipeline"] == "v2"
    assert c.get("/config").status_code == 200
    for pregunta in ("hola", "¿Cuánto cuesta el purificador P2?", "capital de Mongolia"):
        r = c.post("/ask", json={"question": pregunta, "session_id": "s"})
        assert r.status_code == 200, r.text
    primera = c.post("/ask", json={"question": "equipo", "session_id": "s"}).json()
    segunda = c.post("/ask", json={"question": "equipo", "session_id": "s",
                                   "continuation": primera["continuation"]})
    assert segunda.status_code == 200, segunda.text
print(json.dumps(sorted(m for m in sys.modules if m.startswith("ipsis."))))
"""


def test_servir_v2_no_carga_ningun_modulo_del_motor_v1():
    proceso = subprocess.run(
        [sys.executable, "-I", "-c", RECORRIDO, str(TESTS)], cwd=os.getcwd(),
        capture_output=True, text=True, timeout=180, env={**os.environ, "IPSIS_LANG": "es"})
    assert proceso.returncode == 0, f"STDOUT:{proceso.stdout}\nSTDERR:{proceso.stderr}"
    cargados = json.loads(proceso.stdout.strip().splitlines()[-1])
    assert "ipsis.consulta.v2.motor" in cargados, "el recorrido no pasó por MotorV2"
    v1 = [m for m in cargados if es_modulo_v1(m)]
    assert not v1, "servir v2 cargó módulos del motor v1:\n" + "\n".join(v1)


def test_la_lista_de_modulos_v1_no_incluye_lo_que_v2_necesita():
    # Si v2 empieza a necesitar uno de estos módulos, esta lista (y la regla) están mal:
    # se mueve el módulo a un lugar neutral en vez de permitir la dependencia.
    necesarios = {"ipsis.consulta.v2.motor", "ipsis.consulta.salida", "ipsis.consulta.errores",
                  "ipsis.consulta.variantes", "ipsis.consulta.admision", "ipsis.consulta.media"}
    assert not any(es_modulo_v1(m) for m in necesarios)
    assert len(MODULOS_V1) == len(set(MODULOS_V1))


def test_v2_en_memoria_no_importa_dependencias_pesadas():
    """Con un recuperador propio, v2 no necesita Qdrant ni librerías de modelos al consultar."""
    codigo = """
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])
for nombre in ('qdrant_client', 'torch', 'transformers', 'sentence_transformers', 'onnxruntime'):
    sys.modules[nombre] = None
os.environ["IPSIS_MODELS_DIR"] = tempfile.mkdtemp()
from apoyo_v2 import construir_motor_en_memoria
resultado = construir_motor_en_memoria().consultar('¿Cada cuánto se cambia el filtro?', 'aislado')
assert resultado.contrato_http['fragmentos'], resultado.contrato_http
"""
    proceso = subprocess.run([sys.executable, "-I", "-c", codigo, str(TESTS)], cwd=os.getcwd(),
                             capture_output=True, text=True, timeout=120, env={**os.environ, "IPSIS_LANG": "es"})
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
