"""``/admin``: estado, umbrales, documentos y reindexado (pestañas Estado y Documentos)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from apoyo import motor_minimo
from ipsis.aplicacion.modo import ModoServicio
from ipsis.cli import main

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class _MotorRecargado:
    """El motor que construye una recarga: se calienta y se cierra, sin modelos."""

    politica_abstencion = None

    def calentar(self):
        pass

    def cerrar(self):
        pass


@pytest.fixture
def cliente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    carpeta = tmp_path / "proyecto"
    carpeta.mkdir()
    monkeypatch.chdir(carpeta)
    for variable in ("IPSIS_MODE", "IPSIS_ADMIN_TOKEN", "IPSIS_TRUSTED_PROXY", "IPSIS_ADMIN_IPS"):
        monkeypatch.delenv(variable, raising=False)
    assert main(["init", "--profile", "medium"]) == 0
    # La recarga construye el motor de producción: aquí, uno mínimo.
    monkeypatch.setattr("ipsis.servicio.api._construir_motor_produccion", _MotorRecargado)
    from ipsis.servicio.api import crear_app

    return TestClient(crear_app(motor_minimo(), modo=ModoServicio(token_admin=TOKEN)),
                      base_url="https://testserver", client=("203.0.113.5", 1), raise_server_exceptions=False)


def _esperar_tarea(cliente: TestClient) -> dict:
    for _ in range(100):
        tarea = cliente.get("/admin/task", headers=AUTH).json()["task"]
        if tarea["state"] != "running":
            return tarea
        time.sleep(0.05)
    raise AssertionError("la recarga no terminó")


def test_las_rutas_nuevas_exigen_el_token_y_bloquean_tras_cinco_fallos(cliente):
    for metodo, ruta in (("get", "/admin/status"), ("put", "/admin/thresholds"), ("get", "/admin/documents"),
                         ("post", "/admin/documents?name=a.md"), ("post", "/admin/reindex")):
        assert getattr(cliente, metodo)(ruta).status_code == 401, ruta
    assert cliente.get("/admin/task").status_code == 429  # la IP queda bloqueada 15 minutos


def test_estado_muestra_perfil_umbrales_documentos_y_diagnostico(cliente):
    datos = cliente.get("/admin/status", headers=AUTH).json()
    assert datos["profile"] == "medium" and datos["documents"] == []
    umbrales = {u["key"]: u for u in datos["thresholds"]}
    assert {"ok", "focus", "oov_ok", "ok_strong"} <= set(umbrales)
    assert umbrales["ok"]["profile"] == 0.8 and umbrales["ok"]["source"] == "profile"
    assert datos["doctor"] and {"key", "level", "message"} <= set(datos["doctor"][0])


def test_umbrales_se_guardan_en_engine_yaml_validan_y_recargan_el_motor(cliente):
    r = cliente.put("/admin/thresholds", headers=AUTH, json={"thresholds": {"ok": 0.85}})
    assert r.status_code == 200
    assert _esperar_tarea(cliente)["state"] == "done"
    motor = yaml.safe_load(Path("config/engine.yaml").read_text(encoding="utf-8"))
    assert motor["profile_overrides"]["default_thresholds"]["ok"] == 0.85
    fila = next(u for u in cliente.get("/admin/status", headers=AUTH).json()["thresholds"] if u["key"] == "ok")
    assert fila["project"] == 0.85 and fila["source"] == "project"
    assert cliente.put("/admin/thresholds", headers=AUTH, json={"thresholds": {"nada": 0.5}}).status_code == 422
    assert cliente.put("/admin/thresholds", headers=AUTH, json={"thresholds": {"ok": 1.5}}).status_code == 422
    assert cliente.put("/admin/thresholds", headers=AUTH, json={"thresholds": {"ok": None}}).status_code == 200
    _esperar_tarea(cliente)
    motor = yaml.safe_load(Path("config/engine.yaml").read_text(encoding="utf-8"))
    assert "ok" not in ((motor.get("profile_overrides") or {}).get("default_thresholds") or {})


def test_subir_un_documento_lo_cataloga_y_rechaza_lo_que_no_sirve(cliente, monkeypatch):
    contenido = "# Guía\n\n## Horario\n\nLa oficina abre de 9:00 a 18:00 horas.\n".encode("utf-8")
    r = cliente.post("/admin/documents?name=..%2F..%2Fguia.md", headers=AUTH, content=contenido)
    assert r.status_code == 200 and r.json()["file"] == "guia.md" and not r.json()["rejected"]
    assert Path("documents/guia.md").is_file() and not Path("../guia.md").exists()
    assert [d["file"] for d in cliente.get("/admin/documents", headers=AUTH).json()] == ["guia.md"]
    assert cliente.post("/admin/documents?name=guia.md", headers=AUTH, content=contenido).json()["duplicate"]
    assert cliente.post("/admin/documents?name=script.exe", headers=AUTH, content=b"MZ").status_code == 422
    assert cliente.post("/admin/documents?name=vacio.txt", headers=AUTH, content=b"").status_code == 422
    monkeypatch.setattr("ipsis.aplicacion.panel.LIMITE_SUBIDA", 10)
    assert cliente.post("/admin/documents?name=grande.txt", headers=AUTH, content=b"x" * 20).status_code == 413


def test_reindexar_corre_en_segundo_plano_y_no_se_duplica(cliente, monkeypatch):
    llamadas = []
    monkeypatch.setattr("ipsis.aplicacion.corpus.indexar_proyecto",
                        lambda carpeta: (time.sleep(0.3), llamadas.append(carpeta)))
    assert cliente.post("/admin/reindex", headers=AUTH).status_code == 200
    assert cliente.post("/admin/reindex", headers=AUTH).status_code == 409
    assert _esperar_tarea(cliente)["state"] == "done" and llamadas == ["documents"]


def test_inventario_xlsx_subido_se_cataloga_con_coordenadas(cliente):
    from io import BytesIO
    from openpyxl import Workbook
    from ipsis.ingesta.ingesta import parsear_corpus

    libro = Workbook()
    libro.active.title = "Bodega"
    libro.active.append(["SKU", "Producto", "Stock"])
    libro.active.append(["0007", "Taladro", 0])
    datos = BytesIO()
    libro.save(datos)
    libro.close()
    r = cliente.post("/admin/documents?name=inventario.xlsx", headers=AUTH, content=datos.getvalue())
    assert r.status_code == 200 and not r.json()["rejected"]
    d = parsear_corpus("documents", "legacy")[0]
    assert "0007 | Taladro | 0" in d.texto_completo
    assert d.bloques[-1].metadata["cells"][2]["locator"] == "'Bodega'!C2"


def test_una_recarga_fallida_queda_en_la_tarea_sin_tumbar_el_servicio(cliente, monkeypatch):
    def falla():
        raise RuntimeError("modelo faltante")

    monkeypatch.setattr("ipsis.servicio.api._construir_motor_produccion", falla)
    monkeypatch.setattr("ipsis.aplicacion.corpus.indexar_proyecto", lambda carpeta: None)
    cliente.post("/admin/reindex", headers=AUTH)
    tarea = _esperar_tarea(cliente)
    assert tarea["state"] == "error" and "modelo faltante" in tarea["message"]
    assert cliente.get("/health").status_code == 200
