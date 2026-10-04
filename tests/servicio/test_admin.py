"""``/admin``, modos de ejecución y recarga en caliente (P12.6)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from rag.aplicacion.modo import ModoServicio
from rag.cli import main

TOKEN = "t" * 40
REMOTA = ("203.0.113.5", 50000)  # IP de documentación (no loopback)
LOCAL = ("127.0.0.1", 50000)


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    carpeta = tmp_path / "proyecto"
    carpeta.mkdir()
    monkeypatch.chdir(carpeta)
    for variable in ("RAG_MODO", "RAG_ADMIN_TOKEN", "RAG_PROXY_CONFIABLE", "RAG_ADMIN_IPS"):
        monkeypatch.delenv(variable, raising=False)
    assert main(["init", "--perfil", "light"]) == 0
    datos = yaml.safe_load(Path("configuracion/asistente.yaml").read_text(encoding="utf-8"))
    datos["cors_origenes"] = ["https://www.sitio.cl"]
    Path("configuracion/asistente.yaml").write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    return carpeta


from apoyo import motor_minimo as _motor


def _cliente(modo: ModoServicio, cliente=REMOTA, esquema="https", motor=None) -> TestClient:
    from rag.servicio.api import crear_app

    return TestClient(crear_app(motor or _motor(), modo=modo), base_url=f"{esquema}://testserver", client=cliente,
                      raise_server_exceptions=False)


def _auth(token=TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


PRODUCCION = ModoServicio(token_admin=TOKEN)


# --- existencia, token y transporte --------------------------------------------------------------
def test_sin_token_admin_no_existe(proyecto):
    assert _cliente(ModoServicio()).get("/admin/personalidad", headers=_auth()).status_code == 404
    corto = ModoServicio(token_admin="corto")
    assert corto.problemas and _cliente(corto).get("/admin/personalidad", headers=_auth("corto")).status_code == 404


def test_token_incorrecto_401_y_correcto_200(proyecto):
    c = _cliente(PRODUCCION)
    assert c.get("/admin/personalidad").status_code == 401
    assert c.get("/admin/personalidad", headers=_auth("x" * 40)).status_code == 401
    datos = c.get("/admin/personalidad", headers=_auth()).json()
    assert set(datos) == {"config", "tonos", "situaciones", "eventos", "avatares", "avatar"}
    assert len(datos["tonos"]) == 7 and datos["config"]["tono"]["activo"] == "cordial"


def test_https_obligatorio_en_produccion_salvo_desde_la_maquina(proyecto):
    assert _cliente(PRODUCCION, esquema="http").get("/admin/personalidad", headers=_auth()).status_code == 403
    assert _cliente(PRODUCCION, cliente=LOCAL, esquema="http").get(
        "/admin/personalidad", headers=_auth()).status_code == 200
    desarrollo = ModoServicio(modo="desarrollo", token_admin=TOKEN)
    assert _cliente(desarrollo, esquema="http").get("/admin/personalidad", headers=_auth()).status_code == 200


def test_lista_de_ips(proyecto):
    modo = ModoServicio(token_admin=TOKEN, admin_ips=("198.51.100.7",))
    assert _cliente(modo).get("/admin/personalidad", headers=_auth()).status_code == 403
    assert _cliente(modo, cliente=("198.51.100.7", 1)).get("/admin/personalidad", headers=_auth()).status_code == 200


def test_bloqueo_tras_cinco_tokens_incorrectos(proyecto):
    c = _cliente(PRODUCCION)
    codigos = [c.get("/admin/personalidad", headers=_auth("x" * 40)).status_code for _ in range(6)]
    assert codigos == [401] * 5 + [429]
    assert c.get("/admin/personalidad", headers=_auth()).status_code == 429  # el correcto también espera
    # Otra IP no está bloqueada.
    assert _cliente(PRODUCCION, cliente=("198.51.100.9", 1)).get(
        "/admin/personalidad", headers=_auth()).status_code == 200


def test_sin_cors_en_admin(proyecto):
    c = _cliente(PRODUCCION)
    origen = {"Origin": "https://www.sitio.cl"}
    assert "access-control-allow-origin" in c.get("/health", headers=origen).headers  # el widget sí
    r = c.get("/admin/personalidad", headers={**origen, **_auth()})
    assert r.status_code == 200 and "access-control-allow-origin" not in r.headers
    previa = c.options("/admin/personalidad", headers={**origen, "Access-Control-Request-Method": "PUT"})
    assert "access-control-allow-origin" not in previa.headers


def test_cuerpo_mayor_a_256_kib(proyecto):
    r = _cliente(PRODUCCION).put("/admin/personalidad", headers=_auth(),
                                 content=json.dumps({"x": "a" * (256 * 1024)}))
    assert r.status_code == 413


# --- cambios y recarga en caliente -------------------------------------------------------------
def test_put_invalido_422_sin_escribir(proyecto):
    antes = Path("configuracion/personalidad.yaml").read_bytes()
    r = _cliente(PRODUCCION).put("/admin/personalidad", headers=_auth(), json={"tono": {"activo": "turbo"}})
    assert r.status_code == 422 and r.json()["detail"]["errores"]
    assert Path("configuracion/personalidad.yaml").read_bytes() == antes


def test_put_valido_cambia_el_tono_de_la_siguiente_consulta_y_audita(proyecto):
    motor = _motor()
    c = _cliente(PRODUCCION, motor=motor)
    r = c.put("/admin/personalidad", headers=_auth(), json={"tono": {"activo": "directo"}})
    assert r.status_code == 200 and r.json()["tono"]["activo"] == "directo"
    assert motor.plantillas["tono"] == "directo"
    respuesta = c.post("/consultar", json={"pregunta": "hola", "id_sesion": "s"}).json()["respuesta"]
    from rag.lenguaje.tonos import cargar_tono

    assert respuesta in [v.format(nombre_asistente="Asistente documental", descripcion_dominio="los documentos cargados")
                         for v in cargar_tono("es", "directo").variantes("saludo")]
    auditoria = Path(".rag/registros/admin.jsonl").read_text(encoding="utf-8")
    entrada = json.loads(auditoria.splitlines()[-1])
    assert entrada["accion"] == "personalidad" and entrada["claves"] == ["tono"] and entrada["ip"] == REMOTA[0]
    assert TOKEN not in auditoria


def test_cambio_por_cli_se_ve_sin_reiniciar(proyecto):
    motor = _motor()
    c = _cliente(ModoServicio(), motor=motor)
    assert c.get("/config").json()["microcopia"]["esperando"][0] == "Buscando en el documento"
    assert main(["personalidad", "tono", "aplicar", "serio"]) == 0
    assert c.get("/config").json()["microcopia"]["esperando"][0] == "Buscando"
    c.post("/consultar", json={"pregunta": "hola", "id_sesion": "s"})
    assert motor.plantillas["tono"] == "serio"


def test_vista_previa_y_estilos(proyecto):
    c = _cliente(PRODUCCION)
    previa = c.post("/admin/personalidad/vista-previa", headers=_auth(),
                    json={"tono": "formal", "situacion": "sin_respuesta"}).json()
    assert list(previa) == ["sin_respuesta"] and len(previa["sin_respuesta"]) == 5
    r = c.put("/admin/estilos", headers=_auth(), json={"ubicacion": {"posicion": "arriba-izquierda"}})
    assert r.status_code == 200 and r.json()["ubicacion"]["posicion"] == "arriba-izquierda"
    assert c.get("/config").json()["ubicacion"]["posicion"] == "arriba-izquierda"
    assert c.put("/admin/estilos", headers=_auth(), json={"ubicacion": {"posicion": "centro"}}).status_code == 422


# --- avatar público ----------------------------------------------------------------------------
def test_avatar_publico_con_colores_y_rutas_seguras(proyecto):
    from apoyo import definicion_avatar

    c = _cliente(PRODUCCION)
    r = c.post("/admin/avatares", headers=_auth(), json={"nombre": "mi-avatar", "definicion": definicion_avatar()})
    assert r.status_code == 200
    assert c.put("/admin/personalidad", headers=_auth(),
                 json={"avatar": {"definicion": "mi-avatar", "colores": {"cuerpo": "#123456"}}}).status_code == 200
    avatar = c.get("/config").json()["avatar"]
    assert avatar["activo"] and avatar["url_definicion"] == "/avatares/mi-avatar.avatar.json"
    assert avatar["eventos"]["respuesta_ok"] == "contento"
    servida = c.get("/avatares/mi-avatar.avatar.json").json()
    assert servida["colors"]["body"] == "#123456"
    assert c.get("/avatares/../motor.yaml").status_code == 404
    assert c.get("/avatares/Mal_Nombre.avatar.json").status_code == 404
    assert c.get("/avatares/nadie.avatar.json").status_code == 404
    malo = c.post("/admin/avatares", headers=_auth(), json={"nombre": "x", "definicion": {"expressions": {}}})
    assert malo.status_code == 422


def test_folio_por_defecto_y_avatar_faltante_inactivo(proyecto):
    c = _cliente(ModoServicio())
    avatar = c.get("/config").json()["avatar"]
    assert avatar["activo"] and avatar["url_definicion"] == "/avatares/folio.avatar.json"  # incluido
    assert c.get("/avatares/folio.avatar.json").json()["name"] == "Folio"
    assert c.get("/avatar.js").headers["content-type"].startswith("text/javascript")
    texto = Path("configuracion/personalidad.yaml").read_text(encoding="utf-8")
    Path("configuracion/personalidad.yaml").write_text(texto.replace("definicion: folio", "definicion: nadie"),
                                                       encoding="utf-8")
    avatar = _cliente(ModoServicio()).get("/config").json()["avatar"]
    assert avatar["activo"] is False and avatar["url_definicion"] is None  # el widget muestra el ícono


# --- modos -------------------------------------------------------------------------------------
def test_docs_y_errores_segun_el_modo(proyecto):
    class Roto:
        plantillas = None

        def consultar(self, pregunta, id_sesion):
            raise RuntimeError("detalle secreto")

        def cerrar(self):
            pass

    produccion = _cliente(ModoServicio(), motor=Roto())
    assert produccion.get("/docs").status_code == 404
    r = produccion.post("/consultar", json={"pregunta": "x", "id_sesion": "s"})
    assert r.status_code == 500 and r.json()["detail"] == "error interno" and r.json()["id"]
    desarrollo = _cliente(ModoServicio(modo="desarrollo"), motor=Roto())
    assert desarrollo.get("/docs").status_code == 200
    assert "detalle secreto" in desarrollo.post("/consultar", json={"pregunta": "x", "id_sesion": "s"}).json()["detail"]


def test_cache_de_estaticos_segun_el_modo(proyecto):
    assert _cliente(ModoServicio(modo="desarrollo")).get("/widget.js").headers["cache-control"] == "no-store"
    produccion = _cliente(ModoServicio())
    assert produccion.get("/widget.js").headers["cache-control"] == "public, max-age=300"
    assert "immutable" in produccion.get("/widget.js?v=0.7.0").headers["cache-control"]


def test_servir_en_desarrollo_genera_un_token_temporal(proyecto, monkeypatch, capsys):
    import os

    llamadas = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: llamadas.append(k))
    assert main(["servir", "--modo", "desarrollo"]) == 0
    salida = capsys.readouterr().out
    token = os.environ["RAG_ADMIN_TOKEN"]
    assert len(token) >= 32 and token in salida and "Modo desarrollo" in salida
    assert llamadas[0]["proxy_headers"] is True and llamadas[0]["forwarded_allow_ips"] == "127.0.0.1"
    monkeypatch.delenv("RAG_ADMIN_TOKEN")
    monkeypatch.setenv("RAG_PROXY_CONFIABLE", "10.0.0.2")
    assert main(["servir", "--modo", "produccion"]) == 0
    assert "RAG_ADMIN_TOKEN" not in os.environ  # producción nunca inventa un token
    assert llamadas[1]["forwarded_allow_ips"] == "10.0.0.2"


def test_doctor_informa_el_modo(proyecto, monkeypatch):
    from rag.aplicacion.diagnostico import diagnosticar

    assert diagnosticar().chequeo("modo").estado.value == "ok"
    monkeypatch.setenv("RAG_MODO", "desarrollo")
    assert diagnosticar().chequeo("modo").estado.value == "aviso"
    monkeypatch.setenv("RAG_MODO", "produccion")
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "corto")
    chequeo = diagnosticar().chequeo("modo")
    assert chequeo.estado.value == "error" and "secrets.token_urlsafe" in chequeo.acciones[0]
