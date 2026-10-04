"""Prueba de portabilidad desde una instalación y carpeta externas.

Recorre ``init -> cargar -> indexar -> preguntar`` por
SUBPROCESOS reales de la CLI (``python -m ipsis.cli ...``), sobre un dominio
SINTÉTICO ficticio ("Equipo X100", inventado para este test, sin nombres de
organizaciones ni personas reales), en un directorio temporal **fuera del
árbol de este repositorio** -- a propósito NO usa el fixture ``tmp_path`` de
pytest, porque ``pytest.ini::addopts`` fija ``--basetemp=.cache/pytest_tmp``,
que sigue viviendo DENTRO de ``ipsis/``.

Por qué esto es necesario y ``tests/cli/test_cli.py`` no alcanza: ese archivo
corre en el MISMO proceso de pytest (con el intérprete, las cachés de
módulos y el `cwd` original ya cargados) y, antes de la corrección de esta
tanda, copiaba a mano ``configuracion/dominios/_generico/`` y ``configuracion/dominios/idiomas/`` a la
fixture -- lo que enmascaraba exactamente el defecto que una revisión
independiente encontró corriendo la CLI de verdad en un directorio limpio.
Un subproceso nuevo, en un directorio nuevo, sin ningún archivo del repo
alrededor, es la única forma honesta de probar "la librería funciona desde
cualquier carpeta".
"""
from __future__ import annotations

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

from apoyo import _combinar_con_outline, _pdf_pagina_con_texto, _pdf_pagina_vacia

PYTHON = sys.executable


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _rag(args: list[str], cwd: Path, timeout: float = 60.0) -> subprocess.CompletedProcess:
    """Corre ``ipsis <args>`` como SUBPROCESO real (``python -m ipsis.cli``), en
    ``cwd``, con su propio intérprete y estado global -- nunca comparte el
    perfil de dominio activo ni ninguna caché con otro paso, a diferencia de
    llamar ``ipsis.cli.main()`` en el mismo proceso."""
    return subprocess.run(
        [PYTHON, "-m", "ipsis.cli", *args], cwd=str(cwd), capture_output=True, text=True,
        timeout=timeout, env=dict(os.environ),
    )


@pytest.fixture()
def proyecto_externo():
    """Directorio temporal FUERA del árbol de este repo (``tempfile.mkdtemp``
    del sistema, no ``tmp_path`` de pytest -- ver docstring del módulo)."""
    d = Path(tempfile.mkdtemp(prefix="rag_portabilidad_"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _construir_documentos(destino: Path) -> dict[str, Path]:
    """Documentos FICTICIOS de un dominio sintético (equipo X100), inventados
    para este test -- sin nombres de organizaciones ni personas reales.
    Reusa los constructores de PDF mínimo de ``tests/ingesta/test_parsear.py``
    en vez de reimplementarlos (regla del proyecto: una sola implementación
    de cada cosa)."""
    manual = destino / "manual_x100.md"
    manual.write_text(
        "# Manual del Equipo Ficticio X100\n\n"
        "Este manual describe el mantenimiento del equipo X100, inventado "
        "solo para pruebas de este proyecto.\n\n"
        "## Garantia\n\n"
        "La garantia del equipo X100 cubre 18 meses desde la fecha de compra. "
        "No cubre danios por mal uso ni por apertura no autorizada.\n",
        encoding="utf-8",
    )

    ficha_pdf = destino / "ficha_x100.pdf"
    pagina = _pdf_pagina_con_texto(
        "Ficha tecnica del equipo X100: peso 3.2 kilogramos, potencia 150 watts."
    )
    ficha_pdf.write_bytes(_combinar_con_outline([pagina], [("Especificaciones", 0)]))

    notas = destino / "notas_soporte.txt"
    notas.write_text(
        "El soporte tecnico del equipo X100 atiende de lunes a viernes.\n"
        "\n"
        "Para reclamos de garantia, conserva la boleta de compra.\n",
        encoding="utf-8",
    )

    escaneado = destino / "escaneado.pdf"
    escaneado.write_bytes(_pdf_pagina_vacia())

    return {"manual": manual, "ficha": ficha_pdf, "notas": notas, "escaneado": escaneado}


def _init_cargar_indexar(proyecto: Path, docs: dict[str, Path]) -> None:
    r = _rag(["init", "--nombre-asistente", "Asistente X100",
              "--descripcion-dominio", "el manual del equipo ficticio X100"], cwd=proyecto)
    assert r.returncode == 0, f"'ipsis init' fallo:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    assert "Traceback" not in r.stderr

    for clave in ("manual", "ficha", "notas"):
        r = _rag(["cargar", str(docs[clave])], cwd=proyecto)
        assert r.returncode == 0, f"'ipsis cargar {clave}' fallo:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
        assert "Traceback" not in r.stderr

    r = _rag(["indexar"], cwd=proyecto, timeout=300.0)
    assert r.returncode == 0, f"'ipsis indexar' fallo:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    assert "Traceback" not in r.stderr


def test_portabilidad_pdf_escaneado_se_rechaza_sin_traceback(proyecto_externo: Path):
    """Criterio de cierre 1 (parte): un PDF escaneado se rechaza con una
    falla CONTROLADA (código de salida distinto de cero, mensaje que nombra
    el problema), nunca con un traceback ni indexado vacío en silencio."""
    docs = _construir_documentos(proyecto_externo)
    assert _rag(["init"], cwd=proyecto_externo).returncode == 0

    r = _rag(["cargar", str(docs["escaneado"])], cwd=proyecto_externo)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
    assert "escane" in (r.stdout + r.stderr).lower()

    # No debe haber quedado catalogado ni indexado en silencio.
    catalogo = (proyecto_externo / "documentos" / "catalogo.yaml").read_text(encoding="utf-8")
    assert "escaneado" not in catalogo


def test_portabilidad_init_cargar_indexar_subprocesos(proyecto_externo: Path):
    """Criterio de cierre 1: en un directorio temporal vacío, init -> cargar
    -> indexar completa sin traceback, con un dominio .md + .pdf + .txt."""
    docs = _construir_documentos(proyecto_externo)
    _init_cargar_indexar(proyecto_externo, docs)

    # El andamiaje que 'ipsis init' debe ESCRIBIR (DEFECTO 1) quedó ahí.
    assert (proyecto_externo / "configuracion" / "dominio.yaml").exists()
    assert not (proyecto_externo / "configuracion" / "dominios").exists()
    assert not (proyecto_externo / "configuracion" / "textos.yaml").exists()


@pytest.mark.slow
def test_portabilidad_preguntar_de_punta_a_punta(proyecto_externo: Path):
    """Criterio de cierre 1 (completo): init -> cargar -> indexar -> servir
    -> preguntar, con el servicio real levantado en un puerto libre y
    cerrado al final. Comprueba que una pregunta respondible da 'ok' con una
    cita literal del documento fuente, y que una pregunta ajena NO da 'ok'."""
    docs = _construir_documentos(proyecto_externo)
    _init_cargar_indexar(proyecto_externo, docs)

    puerto = _puerto_libre()
    proceso = subprocess.Popen(
        [PYTHON, "-m", "ipsis.cli", "servir", "--port", str(puerto)],
        cwd=str(proyecto_externo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        listo = False
        t0 = time.time()
        while time.time() - t0 < 90:
            try:
                resp = httpx.get(f"http://127.0.0.1:{puerto}/ready", timeout=1.0)
                if resp.status_code == 200:
                    listo = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        assert listo, "el servicio no quedó listo en 90s"

        # Caso literal: 'ok' + cita literal del manual (usa el vocabulario del documento).
        resp = httpx.post(
            f"http://127.0.0.1:{puerto}/consultar",
            json={"pregunta": "¿Cuántos meses cubre la garantía del equipo X100?", "id_sesion": "portabilidad"},
            timeout=30.0,
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["estado"] == "ok", datos
        assert "18 meses" in datos["respuesta"]
        assert len(datos["fragmentos"]) >= 1
        # "Literal" significa substring exacto de lo que el parser extrajo
        # del documento (`texto_completo`) -- NO de los bytes crudos del
        # .md, que traen sintaxis ('# ', líneas en blanco) que el parser ya
        # normaliza; es el mismo criterio que usan
        # tests/ingesta/test_parsear_docx.py y tests/ingesta/test_parsear.py.
        from ipsis.ingesta.parsear import parsear_markdown
        doc_manual = parsear_markdown(str(docs["manual"]), doc_id="x", doc_titulo="x", version="1")
        frag_manual = next((f for f in datos["fragmentos"] if "18 meses" in f["texto"]), None)
        assert frag_manual is not None, datos["fragmentos"]
        assert frag_manual["texto"] in doc_manual.texto_completo  # cita LITERAL, substring exacto de la fuente

        # Caso paráfrasis: «dura» no está en el corpus (dice «cubre»). Con tres chunks
        # su s_oov es 0,74 y cascada_v1 hoy la deja en relacionado (docs/metodologia/lexico.md: sinónimos).
        # Se conserva para que una regresión sea visible: puede mejorar a 'ok', pero
        # nunca perder el pasaje con «18 meses».
        resp = httpx.post(
            f"http://127.0.0.1:{puerto}/consultar",
            json={"pregunta": "¿Cuánto dura la garantía del equipo X100?", "id_sesion": "portabilidad"},
            timeout=30.0,
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["estado"] in {"ok", "relacionado"}, datos
        assert any("18 meses" in f["texto"] for f in datos["fragmentos"]), datos["fragmentos"]
        assert "18 meses" in datos["respuesta"]

        # Pregunta ajena: nunca debe llegar a 'ok'.
        resp = httpx.post(
            f"http://127.0.0.1:{puerto}/consultar",
            json={"pregunta": "¿Cuál es la capital de Mongolia?", "id_sesion": "portabilidad"},
            timeout=30.0,
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] != "ok", resp.json()
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proceso.kill()


@pytest.mark.slow
def test_portabilidad_pythonioencoding_cp1252_no_falla(proyecto_externo: Path):
    """Criterio de cierre 2: los mismos comandos, forzando
    PYTHONIOENCODING=cp1252 (la codificación real de una consola de Windows
    en español, la que reprodujo el DEFECTO 2 -- un '⚠' en una advertencia
    de 'ipsis cargar' mataba el comando con UnicodeEncodeError), terminan en
    código de salida 0. Ejercita explícitamente la ruta CON advertencia
    (el .txt sin estructura de secciones)."""
    entorno = dict(os.environ)
    entorno["PYTHONIOENCODING"] = "cp1252"

    def _rag_cp1252(args: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
        return subprocess.run(
            [PYTHON, "-m", "ipsis.cli", *args], cwd=str(proyecto_externo), capture_output=True, text=True,
            timeout=timeout, env=entorno,
        )

    docs = _construir_documentos(proyecto_externo)

    r = _rag_cp1252(["init"])
    assert r.returncode == 0, f"STDOUT:{r.stdout}\nSTDERR:{r.stderr}"

    # 'notas' (.txt) SIEMPRE trae la advertencia "sin estructura de
    # secciones" -- es la ruta que crasheaba antes de la corrección.
    r = _rag_cp1252(["cargar", str(docs["notas"])])
    assert r.returncode == 0, f"STDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    assert "UnicodeEncodeError" not in r.stderr
    assert "Traceback" not in r.stderr

    r = _rag_cp1252(["cargar", str(docs["manual"])])
    assert r.returncode == 0, f"STDOUT:{r.stdout}\nSTDERR:{r.stderr}"

    r = _rag_cp1252(["indexar"], timeout=300.0)
    assert r.returncode == 0, f"STDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    assert "UnicodeEncodeError" not in r.stderr

    r = _rag_cp1252(["doctor"])
    assert "UnicodeEncodeError" not in r.stderr
    assert "Traceback" not in r.stderr
