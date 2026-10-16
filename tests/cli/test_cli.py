"""Tests de la CLI de la librería: ``init → cargar → configurar → indexar``,
en un directorio temporal, sin tocar el corpus ni la configuración del repo.

El proyecto se distribuye como paquete instalable (ver `pyproject.toml`) y el
código lee rutas relativas al directorio de trabajo, igual que los scripts
numerados. Antes de la corrección de esta tanda (revisión independiente),
`ipsis init` ASUMÍA que `config/dominios/_generico/perfil.yaml` y
`config/dominios/idiomas/es.yaml` ya existían en el directorio de trabajo -- lo que
solo funcionaba DENTRO de una copia de este repo, no como librería
reutilizable. Ahora `ipsis init` los ESCRIBE desde plantillas embebidas en
Python (`ipsis/lenguaje/dominio.py::escribir_perfil_generico_si_falta`,
`ipsis/lenguaje/texto.py::escribir_idioma_es_si_falta`), así que este fixture ya
NO los copia a mano -- si algún test de este archivo fallara por su
ausencia, sería una señal real de que la corrección se rompió. La prueba
DEFINITIVA de portabilidad, por subprocesos y fuera del árbol de este
proyecto, vive en `tests/integracion/test_portabilidad.py`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ipsis.cli import main
from apoyo import escribir_proyecto, leer_proyecto

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_abrir_navegador_real(monkeypatch):
    from threading import Event
    monkeypatch.setattr("ipsis.aplicacion.vista_servicio.abrir_cuando_listo", lambda url: Event())


@pytest.fixture(autouse=True)
def _restaurar_perfil_activo():
    """``ipsis index``/``ipsis load`` configuran el perfil de dominio activo
    como estado de PROCESO (``ipsis.lenguaje.entidades.configurar_perfil``,
    mismo criterio que ``ipsis/servicio/api.py::startup`` -- ver
    ``tests/conftest.py``). Sin restaurarlo, un test de este archivo que
    indexa con el perfil ``_generico`` dejaría ese perfil activo para el
    resto de la sesión de pytest, rompiendo tests de otros archivos que
    dependen del perfil que fija la fixture de sesión."""
    from ipsis.lenguaje.entidades import configurar_perfil, perfil_activo

    anterior = perfil_activo()
    yield
    configurar_perfil(anterior)


@pytest.fixture()
def proyecto_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un directorio de trabajo AISLADO y VACÍO -- ni siquiera se copia
    `config/dominios/_generico/` ni `config/dominios/idiomas/`, a propósito: es lo que
    debe funcionar solo con `ipsis init` desde la corrección de esta tanda."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _doc_prueba_md(tmp_path: Path) -> Path:
    ruta = tmp_path / "manual_x100.md"
    ruta.write_text(
        "# Manual del Equipo Ficticio X100\n\n"
        "Este manual describe el mantenimiento del equipo X100, usado solo "
        "para pruebas de este proyecto.\n\n"
        "## Encendido\n\n"
        "Para encender el equipo, presiona el botón verde durante tres segundos.\n\n"
        "## Mantenimiento\n\n"
        "Limpia el filtro con un paño seco cada semana.\n",
        encoding="utf-8",
    )
    return ruta


def _doc_prueba_txt(tmp_path: Path) -> Path:
    ruta = tmp_path / "notas_garantia.txt"
    ruta.write_text(
        "La garantía del equipo X100 cubre 12 meses desde la fecha de compra.\n"
        "\n"
        "No cubre daños por mal uso ni por apertura no autorizada del equipo.\n",
        encoding="utf-8",
    )
    return ruta


def test_init_crea_configuracion_minima(proyecto_temporal: Path):
    codigo = main(["init", "--assistant-name", "Asistente X100"])
    assert codigo == 0
    assert (proyecto_temporal / "config" / "assistant.yaml").exists()
    assert (proyecto_temporal / "config" / "engine.yaml").exists()
    assert (proyecto_temporal / "config" / "domain.yaml").exists()
    assert (proyecto_temporal / "documents" / "catalog.yaml").exists()
    assert (proyecto_temporal / "documents").is_dir()

    # Corrección de esta tanda (revisión independiente, DEFECTO 1): en un
    # directorio VACÍO, 'ipsis init' debe ESCRIBIR el andamiaje del perfil y
    # del recurso de idioma, no asumir que ya existen.
    assert not (proyecto_temporal / "config" / "dominios").exists()

    dominio = leer_proyecto((proyecto_temporal / "config" / "assistant.yaml"))
    assert dominio["nombre_asistente"] == "Asistente X100"
    assert dominio["perfil"] == "medium"  # perfil de instalación por defecto
    motor = leer_proyecto((proyecto_temporal / "config" / "engine.yaml"))
    assert motor["recuperacion"]["coleccion_base"] == "asistente_x100"


def test_init_cors_y_claves_widget_vacios_por_defecto(proyecto_temporal: Path):
    """Corrección de seguridad de esta tanda: un
    dominio recién creado NUNCA trae 'cors_origenes: [\"*\"]' -- eso
    expondría el servicio a cualquier sitio que copie la plantilla. Ambas
    listas empiezan vacías; se abren a mano con 'ipsis configure'."""
    assert main(["init"]) == 0
    dominio = leer_proyecto((proyecto_temporal / "config" / "assistant.yaml"))
    assert dominio["cors_origenes"] == []
    assert dominio["claves_widget"] == []


def test_init_no_pisa_configuracion_existente_sin_force(proyecto_temporal: Path):
    assert main(["init"]) == 0
    (proyecto_temporal / "config" / "assistant.yaml").write_text(
        "nombre_asistente: Tocado\ndescripcion_dominio: x\nidioma: es\nperfil: _generico\n"
        "cors_origenes: []\n", encoding="utf-8",
    )
    codigo = main(["init"])
    assert codigo == 1
    dominio = leer_proyecto((proyecto_temporal / "config" / "assistant.yaml"))
    assert dominio["nombre_asistente"] == "Tocado"  # no se pisó


def test_cargar_infiere_doc_id_y_titulo_y_conserva_comentarios(proyecto_temporal: Path):
    main(["init"])
    md = _doc_prueba_md(proyecto_temporal)
    txt = _doc_prueba_txt(proyecto_temporal)

    assert main(["load", str(md)]) == 0
    assert main(["load", str(txt)]) == 0

    contenido_catalogo = (proyecto_temporal / "documents" / "catalog.yaml").read_text(encoding="utf-8")
    assert contenido_catalogo.startswith("# Documents in the corpus.")  # comentario original intacto

    catalogo = leer_proyecto(proyecto_temporal / "documents" / "catalog.yaml")["documentos"]
    assert len(catalogo) == 2
    ids = {e["doc_id"] for e in catalogo}
    assert "manual-x100" in ids
    entrada_md = next(e for e in catalogo if e["doc_id"] == "manual-x100")
    assert entrada_md["doc_titulo"] == "Manual del Equipo Ficticio X100"
    assert "hash_contenido" in entrada_md
    assert (proyecto_temporal / "documents" / "manual_x100.md").exists()


def test_cargar_mismo_contenido_dos_veces_no_duplica(proyecto_temporal: Path):
    main(["init"])
    md = _doc_prueba_md(proyecto_temporal)
    assert main(["load", str(md)]) == 0
    assert main(["load", str(md)]) == 0  # misma ruta, mismo contenido

    catalogo = leer_proyecto((proyecto_temporal / "documents" / "catalog.yaml"))["documentos"]
    assert len(catalogo) == 1


def test_cargar_archivo_modificado_no_sobrescribe_la_version_anterior(
    proyecto_temporal: Path,
):
    main(["init"])
    md = _doc_prueba_md(proyecto_temporal)
    assert main(["load", str(md)]) == 0
    md.write_text(md.read_text(encoding="utf-8") + "\nVersión nueva.\n", encoding="utf-8")

    assert main(["load", str(md)]) == 0

    catalogo = leer_proyecto((proyecto_temporal / "documents" / "catalog.yaml"))["documentos"]
    assert len(catalogo) == 2
    assert catalogo[0]["archivo"] == "manual_x100.md"
    assert catalogo[1]["archivo"].startswith("manual_x100-")
    assert (proyecto_temporal / "documents" / catalogo[0]["archivo"]).is_file()
    assert (proyecto_temporal / "documents" / catalogo[1]["archivo"]).is_file()


def test_cargar_avisa_el_homonimo_y_vigente_false_lo_saca_del_indice(proyecto_temporal: Path, capsys):
    from ipsis.ingesta.ingesta import parsear_corpus

    main(["init"])
    md = _doc_prueba_md(proyecto_temporal)
    assert main(["load", str(md)]) == 0
    md.write_text(md.read_text(encoding="utf-8") + "\nVersión nueva.\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["load", str(md)]) == 0
    salida = capsys.readouterr().out
    assert "ya había un documento con ese nombre" in salida and "ipsis sync" in salida
    assert len(parsear_corpus("documents")) == 2  # mientras no se retire, se indexan ambos

    ruta = proyecto_temporal / "documents" / "catalog.yaml"
    datos = leer_proyecto(ruta)
    datos["documentos"][0]["vigente"] = False
    escribir_proyecto(ruta, datos)
    vigentes = parsear_corpus("documents")
    assert [d.doc_id for d in vigentes] == [datos["documentos"][1]["doc_id"]]


def test_cargar_formato_no_soportado_falla_sin_tocar_catalogo(proyecto_temporal: Path):
    main(["init"])
    ruta = proyecto_temporal / "archivo.rtf"
    ruta.write_text("contenido", encoding="utf-8")
    codigo = main(["load", str(ruta)])
    assert codigo == 1


def test_configurar_clave_desconocida_falla(proyecto_temporal: Path):
    main(["init"])
    assert main(["configure", "clave_rara=1"]) == 1


def test_configurar_cors_origenes_como_lista(proyecto_temporal: Path):
    main(["init"])
    assert main(["configure", "cors_origins=https://a.cl,https://b.cl"]) == 0
    dominio = leer_proyecto((proyecto_temporal / "config" / "assistant.yaml"))
    assert dominio["cors_origenes"] == ["https://a.cl", "https://b.cl"]


def test_configurar_claves_widget_como_lista(proyecto_temporal: Path):
    main(["init"])
    assert main(["configure", "widget_keys=clave-sitio-a,clave-sitio-b"]) == 0
    dominio = leer_proyecto((proyecto_temporal / "config" / "assistant.yaml"))
    assert dominio["claves_widget"] == ["clave-sitio-a", "clave-sitio-b"]


def test_la_postura_es_proactiva_por_defecto_y_se_configura(proyecto_temporal: Path):
    """ADR 0008: ``posture`` en assistant.yaml, en inglés en el disco."""
    main(["init"])
    ruta = proyecto_temporal / "config" / "assistant.yaml"
    assert leer_proyecto(ruta)["postura"] == {"modo": "proactiva", "max_alternativas": 3}
    assert main(["configure", "posture.mode=strict", "posture.max_alternatives=2"]) == 0
    assert leer_proyecto(ruta)["postura"] == {"modo": "estricta", "max_alternativas": 2}
    assert "mode: strict" in ruta.read_text(encoding="utf-8")
    assert main(["configure", "posture.mode=agresiva"]) == 1
    assert main(["configure", "posture.max_alternatives=9"]) == 1


def test_doctor_sin_indice_reporta_falla_accionable(proyecto_temporal: Path, capsys):
    main(["init"])
    main(["load", str(_doc_prueba_md(proyecto_temporal))])
    capsys.readouterr()
    codigo = main(["doctor"])
    assert codigo == 1  # hay un documento cargado y el índice todavía no existe
    assert "Acción: ipsis index" in capsys.readouterr().out


def test_doctor_avisa_si_cors_vacio_con_claves_widget_configuradas(proyecto_temporal: Path, capsys):
    """'ipsis doctor' debe avisar cuando cors_origenes está vacío Y ya
    hay claves de widget configuradas -- la señal concreta de que alguien
    preparó el widget para un sitio real y se olvidó de abrirle CORS."""
    main(["init"])
    main(["configure", "widget_keys=clave-sitio-a"])
    capsys.readouterr()  # descarta lo impreso por init/configurar
    main(["doctor"])
    salida = capsys.readouterr().out
    assert "CORS" in salida
    assert "cors_origins" in salida.lower()


def test_doctor_reporta_textos_de_idioma_invalidos(proyecto_temporal: Path, capsys):
    """Un config/language.yaml inválido rompería '/consultar' en la
    primera pregunta: 'ipsis doctor' debe decirlo antes."""
    main(["init"])
    (proyecto_temporal / "config" / "language.yaml").write_text("mensajes: [1, 2]\n", encoding="utf-8")
    capsys.readouterr()
    codigo = main(["doctor"])
    salida = capsys.readouterr().out
    assert codigo == 1
    assert "[ERROR]   Idioma" in salida


def test_doctor_reporta_politica_abstencion_desconocida(proyecto_temporal: Path, capsys):
    main(["init"])
    ruta_motor = proyecto_temporal / "config" / "engine.yaml"
    motor = leer_proyecto(ruta_motor)
    motor["componentes"]["abstention_policy"] = "inexistente"
    ruta_motor.write_text(
        yaml.safe_dump(motor, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    capsys.readouterr()

    codigo = main(["doctor"])
    salida = capsys.readouterr().out

    assert codigo == 1
    assert "política de abstención" in salida
    assert "inexistente" in salida


def test_evaluar_sin_golden_set_no_falla(proyecto_temporal: Path):
    main(["init"])
    assert main(["evaluate"]) == 0


@pytest.mark.slow
def test_indexar_dominio_sintetico_multiformato(proyecto_temporal: Path):
    """El flujo completo `init → cargar (md + txt) → indexar` sobre un
    dominio SINTÉTICO y aislado -- usa el modelo de
    embeddings real (ya en caché) y un índice
    Qdrant local real en el directorio temporal. Es la prueba de que el
    despacho multiformato y la CLI funcionan juntas de
    punta a punta, no solo por separado."""
    main(["init"])
    main(["load", str(_doc_prueba_md(proyecto_temporal))])
    main(["load", str(_doc_prueba_txt(proyecto_temporal))])

    codigo = main(["index"])
    assert codigo == 0

    # el índice quedó donde 'ipsis doctor' y el servicio lo esperan
    assert main(["doctor"]) == 0


def test_servir_sin_carpeta_conserva_el_modo_actual(monkeypatch, proyecto_temporal):
    llamadas = []
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: llamadas.append((args, kwargs)))

    assert main(["serve", "--port", "8123"]) == 0

    assert llamadas[0][0] == ("ipsis.servicio.api:crear_app",)
    assert llamadas[0][1]["factory"] is True
    assert llamadas[0][1]["port"] == 8123
    assert Path.cwd() == proyecto_temporal


def test_servir_carpeta_crea_proyecto_privado_y_carga_documentos(
    monkeypatch, proyecto_temporal
):
    fuente = proyecto_temporal / "fuente"
    fuente.mkdir()
    _doc_prueba_md(fuente)
    llamadas = []
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: llamadas.append(Path.cwd()))
    monkeypatch.setattr("ipsis.cli.comandos.corpus.ComandoIndexar.ejecutar", lambda _self, _args: 0)
    monkeypatch.setattr(
        "ipsis.aplicacion.diagnostico.verificar_indice",
        lambda: type("Chequeo", (), {"ok": False})(),
    )

    assert main(["serve", str(fuente)]) == 0

    proyecto = fuente / ".ipsis-project"
    assert llamadas == [proyecto]
    assert (proyecto / "config" / "assistant.yaml").is_file()
    catalogo = leer_proyecto((proyecto / "documents" / "catalog.yaml"))
    assert [entrada["doc_id"] for entrada in catalogo["documentos"]] == ["manual-x100"]
    assert Path.cwd() == proyecto_temporal


def test_servir_carpeta_reutiliza_indice_vigente(monkeypatch, proyecto_temporal):
    assert main(["init"]) == 0
    indexaciones = []
    servidores = []
    monkeypatch.setattr("ipsis.cli.comandos.corpus.ComandoIndexar.ejecutar",
                        lambda _self, args: indexaciones.append(args) or 0)
    monkeypatch.setattr(
        "ipsis.aplicacion.diagnostico.verificar_indice",
        lambda: type("Chequeo", (), {"ok": True})(),
    )
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: servidores.append(Path.cwd()))

    assert main(["serve", str(proyecto_temporal)]) == 0

    assert indexaciones == []
    assert servidores == [proyecto_temporal]


def test_servir_completa_proyecto_parcial_sin_pisar_asistente(
    monkeypatch, proyecto_temporal
):
    anterior = proyecto_temporal / "configuracion"  # estructura anterior, en español: se migra
    anterior.mkdir()
    (anterior / "asistente.yaml").write_text(
        "config_version: 2\n"
        "nombre_asistente: Parcial\n"
        "descripcion_dominio: documentación parcial\n"
        "idioma: es\nperfil: _generico\ncors_origenes: []\nclaves_widget: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("ipsis.cli.comandos.corpus.ComandoIndexar.ejecutar", lambda _self, _args: 0)
    monkeypatch.setattr(
        "ipsis.aplicacion.diagnostico.verificar_indice",
        lambda: type("Chequeo", (), {"ok": False})(),
    )
    monkeypatch.setattr("uvicorn.run", lambda *_args, **_kwargs: None)

    assert main(["serve", str(proyecto_temporal)]) == 0

    configuracion = proyecto_temporal / "config"
    assert not anterior.exists()
    assert leer_proyecto(configuracion / "assistant.yaml")["nombre_asistente"] == "Parcial"
    assert (configuracion / "engine.yaml").is_file()
    assert not (configuracion / "textos.yaml").exists()
    assert (configuracion / "styles.yaml").is_file()
    assert (proyecto_temporal / "documents" / "catalog.yaml").is_file()


def test_servir_rechaza_carpeta_sin_documentos(monkeypatch, proyecto_temporal):
    fuente = proyecto_temporal / "vacia"
    fuente.mkdir()
    monkeypatch.setattr("uvicorn.run", lambda *_args, **_kwargs: pytest.fail("no debe servir"))

    assert main(["serve", str(fuente)]) == 1
    assert not (fuente / ".ipsis-project").exists()
    assert Path.cwd() == proyecto_temporal


# ---------------------------------------------------------------------------
# ipsis ask -- código de salida:
# cualquier fallo de conexión o de HTTP debe devolver código ≠ 0, o un
# script que use la CLI no se entera de que la pregunta no se respondió.
# Se monkeypatchea 'httpx.post' en vez de levantar un servicio real: más
# rápido y determinista, y prueba exactamente la rama de manejo de errores
# de 'cmd_preguntar' sin depender de temporizaciones de red reales.
# ---------------------------------------------------------------------------
class _RespuestaFalsa:
    def __init__(self, status_code: int, cuerpo: dict | None = None, texto: str = ""):
        self.status_code = status_code
        self._cuerpo = cuerpo or {}
        self.text = texto or str(cuerpo)

    def json(self):
        return self._cuerpo


def test_preguntar_codigo_no_cero_si_no_conecta(monkeypatch: pytest.MonkeyPatch):
    import httpx

    def _post_falla(*_args, **_kwargs):
        raise httpx.ConnectError("conexión rechazada")

    monkeypatch.setattr(httpx, "post", _post_falla)
    assert main(["ask", "¿algo?"]) != 0


def test_preguntar_codigo_no_cero_si_hay_timeout(monkeypatch: pytest.MonkeyPatch):
    import httpx

    def _post_timeout(*_args, **_kwargs):
        raise httpx.TimeoutException("se agotó el tiempo")

    monkeypatch.setattr(httpx, "post", _post_timeout)
    assert main(["ask", "¿algo?"]) != 0


def test_preguntar_codigo_no_cero_si_http_no_200(monkeypatch: pytest.MonkeyPatch):
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _RespuestaFalsa(500, texto="error interno"))
    assert main(["ask", "¿algo?"]) != 0


def test_preguntar_usa_el_contrato_publico_de_ask(monkeypatch: pytest.MonkeyPatch, capsys):
    """Regresión: tras el renombre la CLI seguía llamando a /consultar con el
    cuerpo anterior; contra un servidor actual eso es un 404."""
    import httpx

    llamadas = []
    cuerpo = {"status": "ok", "answer": "texto de prueba", "fragments": [
        {"chunk_id": "c1", "doc_title": "Manual", "section": "Garantía", "version": "1", "page": None,
         "offset_start": 10, "offset_end": 40, "text": "texto de prueba", "score": 0.9}]}

    def _post(url, json, timeout):
        llamadas.append((url, json))
        return _RespuestaFalsa(200, cuerpo)

    monkeypatch.setattr(httpx, "post", _post)
    assert main(["ask", "¿algo?", "--url", "http://127.0.0.1:9000/"]) == 0
    assert llamadas == [("http://127.0.0.1:9000/ask", {"question": "¿algo?", "session_id": "ipsis-cli"})]
    salida = capsys.readouterr().out
    assert "texto de prueba" in salida and "Manual" in salida and "Garantía" in salida


# ---------------------------------------------------------------------------
# Ayuda de la CLI: cada opción de cada
# subcomando debe traer 'help=' en castellano -- antes 'ipsis serve --help'
# mostraba '--host HOST'/'--port PORT' sin ninguna explicación.
# ---------------------------------------------------------------------------
def _subcomandos(parser, ruta=()):
    """(ruta, parser) de cada comando del árbol, incluidos los anidados."""
    import argparse

    for accion in parser._actions:
        if isinstance(accion, argparse._SubParsersAction):
            for nombre, sub in accion.choices.items():
                yield ruta + (nombre,), sub
                yield from _subcomandos(sub, ruta + (nombre,))


def test_todas_las_opciones_de_todos_los_subcomandos_tienen_ayuda():
    """Recorre todo el árbol (también ``ipsis golden …`` y ``ipsis widget theme …``)."""
    from ipsis.cli import construir_parser

    rutas = list(_subcomandos(construir_parser()))
    assert len(rutas) >= 23
    for ruta, subparser in rutas:
        for accion in subparser._actions:
            if accion.dest == "help":  # el propio '-h/--help' automático
                continue
            assert accion.help and len(accion.help.strip()) > 10, f"ipsis {' '.join(ruta)}: {accion.dest!r} sin ayuda útil"
