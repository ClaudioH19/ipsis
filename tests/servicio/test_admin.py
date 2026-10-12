"""``/admin``, modos de ejecución y recarga en caliente (P12.6)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ipsis.aplicacion.modo import ModoServicio
from ipsis.cli import main
from ipsis.lenguaje.tonos import CUOTAS_PAQUETE

TOKEN = "t" * 40
REMOTA = ("203.0.113.5", 50000)  # IP de documentación (no loopback)
LOCAL = ("127.0.0.1", 50000)


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    carpeta = tmp_path / "proyecto"
    carpeta.mkdir()
    monkeypatch.chdir(carpeta)
    for variable in ("IPSIS_MODE", "IPSIS_ADMIN_TOKEN", "IPSIS_TRUSTED_PROXY", "IPSIS_ADMIN_IPS"):
        monkeypatch.delenv(variable, raising=False)
    assert main(["init", "--profile", "light"]) == 0
    datos = leer_proyecto(Path("config/assistant.yaml"))
    datos["cors_origenes"] = ["https://www.sitio.cl"]
    escribir_proyecto(Path("config/assistant.yaml"), datos)
    return carpeta


from apoyo import motor_minimo as _motor
from apoyo import escribir_proyecto, leer_proyecto


def _cliente(modo: ModoServicio, cliente=REMOTA, esquema="https", motor=None) -> TestClient:
    from ipsis.servicio.api import crear_app

    return TestClient(crear_app(motor or _motor(), modo=modo), base_url=f"{esquema}://testserver", client=cliente,
                      raise_server_exceptions=False)


def _auth(token=TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


PRODUCCION = ModoServicio(token_admin=TOKEN)


# --- existencia, token y transporte --------------------------------------------------------------
def test_sin_token_admin_no_existe(proyecto):
    assert _cliente(ModoServicio()).get("/admin/personality", headers=_auth()).status_code == 404
    corto = ModoServicio(token_admin="corto")
    assert corto.problemas and _cliente(corto).get("/admin/personality", headers=_auth("corto")).status_code == 404


def test_token_incorrecto_401_y_correcto_200(proyecto):
    c = _cliente(PRODUCCION)
    assert c.get("/admin/personality").status_code == 401
    assert c.get("/admin/personality", headers=_auth("x" * 40)).status_code == 401
    datos = c.get("/admin/personality", headers=_auth()).json()
    assert set(datos) == {"config", "tones", "situations", "events", "avatars", "avatar", "tone_warnings"}
    assert datos["tone_warnings"] == []
    assert len(datos["tones"]) == 7 and datos["config"]["tone"]["active"] == "cordial"


def test_https_obligatorio_en_produccion_salvo_desde_la_maquina(proyecto):
    assert _cliente(PRODUCCION, esquema="http").get("/admin/personality", headers=_auth()).status_code == 403
    assert _cliente(PRODUCCION, cliente=LOCAL, esquema="http").get(
        "/admin/personality", headers=_auth()).status_code == 200
    desarrollo = ModoServicio(modo="desarrollo", token_admin=TOKEN)
    assert _cliente(desarrollo, esquema="http").get("/admin/personality", headers=_auth()).status_code == 200


def test_lista_de_ips(proyecto):
    modo = ModoServicio(token_admin=TOKEN, admin_ips=("198.51.100.7",))
    assert _cliente(modo).get("/admin/personality", headers=_auth()).status_code == 403
    assert _cliente(modo, cliente=("198.51.100.7", 1)).get("/admin/personality", headers=_auth()).status_code == 200


def test_bloqueo_tras_cinco_tokens_incorrectos(proyecto):
    c = _cliente(PRODUCCION)
    codigos = [c.get("/admin/personality", headers=_auth("x" * 40)).status_code for _ in range(6)]
    assert codigos == [401] * 5 + [429]
    assert c.get("/admin/personality", headers=_auth()).status_code == 429  # el correcto también espera
    # Otra IP no está bloqueada.
    assert _cliente(PRODUCCION, cliente=("198.51.100.9", 1)).get(
        "/admin/personality", headers=_auth()).status_code == 200


def test_sin_cors_en_admin(proyecto):
    c = _cliente(PRODUCCION)
    origen = {"Origin": "https://www.sitio.cl"}
    assert "access-control-allow-origin" in c.get("/health", headers=origen).headers  # el widget sí
    r = c.get("/admin/personality", headers={**origen, **_auth()})
    assert r.status_code == 200 and "access-control-allow-origin" not in r.headers
    previa = c.options("/admin/personality", headers={**origen, "Access-Control-Request-Method": "PUT"})
    assert "access-control-allow-origin" not in previa.headers


def test_cuerpo_mayor_a_256_kib(proyecto):
    r = _cliente(PRODUCCION).put("/admin/personality", headers=_auth(),
                                 content=json.dumps({"x": "a" * (256 * 1024)}))
    assert r.status_code == 413


# --- cambios y recarga en caliente -------------------------------------------------------------
def test_put_invalido_422_sin_escribir(proyecto):
    antes = Path("config/personality.yaml").read_bytes()
    r = _cliente(PRODUCCION).put("/admin/personality", headers=_auth(), json={"tone": {"active": "turbo"}})
    assert r.status_code == 422 and r.json()["detail"]["errors"]
    assert Path("config/personality.yaml").read_bytes() == antes


def test_put_valido_cambia_el_tono_de_la_siguiente_consulta_y_audita(proyecto):
    motor = _motor()
    c = _cliente(PRODUCCION, motor=motor)
    r = c.put("/admin/personality", headers=_auth(), json={"tone": {"active": "direct"}})
    assert r.status_code == 200 and r.json()["tone"]["active"] == "direct"
    assert motor.plantillas["tono"] == "direct"
    respuesta = c.post("/ask", json={"question": "hola", "session_id": "s"}).json()["answer"]
    from ipsis.lenguaje.tonos import cargar_tono

    assert respuesta in [v.format(assistant_name="Asistente documental", domain_description="los documentos cargados")
                         for v in cargar_tono("es", "direct").variantes("greeting")]
    auditoria = Path(".ipsis/logs/admin.jsonl").read_text(encoding="utf-8")
    entrada = json.loads(auditoria.splitlines()[-1])
    assert entrada["accion"] == "personality" and entrada["claves"] == ["tone"] and entrada["ip"] == REMOTA[0]
    assert TOKEN not in auditoria


def test_cambio_por_cli_se_ve_sin_reiniciar(proyecto):
    motor = _motor()
    c = _cliente(ModoServicio(), motor=motor)
    assert c.get("/config").json()["microcopy"]["waiting"][0] == "Buscando en el documento"
    assert main(["personality", "tone", "apply", "serious"]) == 0
    assert c.get("/config").json()["microcopy"]["waiting"][0] == "Buscando"
    c.post("/ask", json={"question": "hola", "session_id": "s"})
    assert motor.plantillas["tono"] == "serious"


def test_vista_previa_y_estilos(proyecto):
    c = _cliente(PRODUCCION)
    previa = c.post("/admin/personality/preview", headers=_auth(),
                    json={"tone": "formal", "situation": "no_answer"}).json()
    assert list(previa) == ["no_answer"] and len(previa["no_answer"]) == CUOTAS_PAQUETE["no_answer"]
    r = c.put("/admin/styles", headers=_auth(), json={"placement": {"position": "top-left"}})
    assert r.status_code == 200 and r.json()["placement"]["position"] == "top-left"
    assert c.get("/config").json()["placement"]["position"] == "top-left"
    assert c.put("/admin/styles", headers=_auth(), json={"placement": {"position": "center"}}).status_code == 422


# --- avatar público ----------------------------------------------------------------------------
def test_avatar_publico_con_colores_y_rutas_seguras(proyecto):
    from apoyo import definicion_avatar

    c = _cliente(PRODUCCION)
    r = c.post("/admin/avatars", headers=_auth(), json={"name": "mi-avatar", "definition": definicion_avatar()})
    assert r.status_code == 200
    assert c.put("/admin/personality", headers=_auth(),
                 json={"avatar": {"definition": "mi-avatar", "colors": {"body": "#123456"}}}).status_code == 200
    avatar = c.get("/config").json()["avatar"]
    assert avatar["enabled"] and avatar["definition_url"] == "/avatars/mi-avatar.avatar.json"
    assert avatar["events"]["answer_ok"] == "happy"
    servida = c.get("/avatars/mi-avatar.avatar.json").json()
    assert servida["colors"]["body"] == "#123456"
    assert c.get("/avatars/../engine.yaml").status_code == 404
    assert c.get("/avatars/Mal_Nombre.avatar.json").status_code == 404
    assert c.get("/avatars/nadie.avatar.json").status_code == 404
    malo = c.post("/admin/avatars", headers=_auth(), json={"name": "x", "definition": {"expressions": {}}})
    assert malo.status_code == 422


def test_folio_por_defecto_y_avatar_faltante_inactivo(proyecto):
    c = _cliente(ModoServicio())
    avatar = c.get("/config").json()["avatar"]
    assert avatar["enabled"] and avatar["definition_url"] == "/avatars/folio.avatar.json"  # incluido
    assert c.get("/avatars/folio.avatar.json").json()["name"] == "Folio"
    assert c.get("/avatar.js").headers["content-type"].startswith("text/javascript")
    texto = Path("config/personality.yaml").read_text(encoding="utf-8")
    Path("config/personality.yaml").write_text(texto.replace("definition: folio", "definition: nadie"),
                                                       encoding="utf-8")
    avatar = _cliente(ModoServicio()).get("/config").json()["avatar"]
    assert avatar["enabled"] is False and avatar["definition_url"] is None  # el widget muestra el ícono


def test_predeterminados_de_folio_coinciden_en_panel_y_widget_y_se_personalizan(proyecto):
    c = _cliente(PRODUCCION)
    eventos = c.get("/config").json()["avatar"]["events"]
    assert eventos["greeting"] == "wake-up"
    assert eventos["idle"] == "float" and eventos["launcher"] == "float"
    assert eventos["sent"] == "paper-plane-out"
    assert eventos["answer_ok"] == "paper-plane-in"
    panel = c.get("/admin/personality", headers=_auth()).json()
    assert {e: datos["suggested"] for e, datos in panel["events"].items()} == eventos
    cambio = c.put("/admin/personality", headers=_auth(),
                   json={"avatar": {"events": {"greeting": "spin", "answer_ok": "happy"}}})
    assert cambio.status_code == 200
    eventos = c.get("/config").json()["avatar"]["events"]
    assert eventos["greeting"] == "spin" and eventos["answer_ok"] == "happy"
    assert eventos["idle"] == "float"  # Las asignaciones parciales conservan los demás predeterminados.


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
    r = produccion.post("/ask", json={"question": "x", "session_id": "s"})
    assert r.status_code == 500 and r.json()["detail"] == "internal error" and r.json()["id"]
    desarrollo = _cliente(ModoServicio(modo="desarrollo"), motor=Roto())
    assert desarrollo.get("/docs").status_code == 200
    assert "detalle secreto" in desarrollo.post("/ask", json={"question": "x", "session_id": "s"}).json()["detail"]


def test_cache_de_estaticos_segun_el_modo(proyecto):
    assert _cliente(ModoServicio(modo="desarrollo")).get("/widget.js").headers["cache-control"] == "no-store"
    produccion = _cliente(ModoServicio())
    assert produccion.get("/widget.js").headers["cache-control"] == "public, max-age=300"
    assert "immutable" in produccion.get("/widget.js?v=0.7.0").headers["cache-control"]


def test_servir_en_desarrollo_genera_un_token_temporal(proyecto, monkeypatch, capsys):
    import os

    llamadas = []
    tokens = []
    def servir(*a, **k):
        llamadas.append(k)
        tokens.append(os.environ.get("IPSIS_ADMIN_TOKEN"))
    monkeypatch.setattr("uvicorn.run", servir)
    assert main(["serve", "--mode", "development", "--no-open"]) == 0
    salida = capsys.readouterr().out
    token = tokens[0]
    assert len(token) >= 32 and token in salida and "Modo desarrollo" in salida
    assert llamadas[0]["proxy_headers"] is True and llamadas[0]["forwarded_allow_ips"] == "127.0.0.1"
    assert "IPSIS_ADMIN_TOKEN" not in os.environ
    assert "IPSIS_MODE" not in os.environ
    monkeypatch.setenv("IPSIS_TRUSTED_PROXY", "10.0.0.2")
    assert main(["serve", "--mode", "production", "--no-open"]) == 0
    assert len(tokens[1]) >= 32 and tokens[1] != token
    assert "IPSIS_ADMIN_TOKEN" not in os.environ  # temporal solo durante el servicio
    assert llamadas[1]["forwarded_allow_ips"] == "10.0.0.2"


def test_doctor_informa_el_modo(proyecto, monkeypatch):
    from ipsis.aplicacion.diagnostico import diagnosticar

    assert diagnosticar().chequeo("modo").estado.value == "ok"
    monkeypatch.setenv("IPSIS_MODE", "desarrollo")
    assert diagnosticar().chequeo("modo").estado.value == "aviso"
    monkeypatch.setenv("IPSIS_MODE", "produccion")
    monkeypatch.setenv("IPSIS_ADMIN_TOKEN", "corto")
    chequeo = diagnosticar().chequeo("modo")
    assert chequeo.estado.value == "error" and "secrets.token_urlsafe" in chequeo.acciones[0]


def test_estilo_plano_y_cambiar_por_admin(proyecto):
    c = _cliente(PRODUCCION)
    plano = {f["key"]: f["value"] for f in c.get("/admin/styles/flat", headers=_auth()).json()}
    assert plano["colors.accent"] == "#2563eb" and plano["animations.enabled"] is True
    r = c.post("/admin/styles/set", headers=_auth(),
               json={"assignments": ["colors.accent=#0ea5e9", "shape.panel_radius=10px"]})
    assert r.status_code == 200 and r.json()["colors"]["accent"] == "#0ea5e9"
    malo = c.post("/admin/styles/set", headers=_auth(), json={"assignments": ["colors.acent=#fff"]})
    assert malo.status_code == 422 and "clave desconocida" in malo.json()["detail"]["errors"][0]
    assert c.post("/admin/styles/set", json={"assignments": []}).status_code == 401
    assert "styles" in Path(".ipsis/logs/admin.jsonl").read_text(encoding="utf-8")


def test_el_panel_habla_el_idioma_de_la_interfaz(proyecto, monkeypatch):
    c = _cliente(PRODUCCION)
    monkeypatch.setenv("IPSIS_LANG", "en")
    ingles = c.get("/admin/panel").text
    assert "<title>Assistant panel</title>" in ingles and 'lang="en"' in ingles and "{{" not in ingles
    monkeypatch.setenv("IPSIS_LANG", "es")
    espanol = c.get("/admin/panel").text
    assert "<title>Panel del asistente</title>" in espanol and 'lang="es"' in espanol
