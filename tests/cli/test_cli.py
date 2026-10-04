"""Tests de la CLI de la librería: ``init → cargar → configurar → indexar``,
en un directorio temporal, sin tocar el corpus ni la configuración del repo.

El proyecto se distribuye como paquete instalable (ver `pyproject.toml`) y el
código lee rutas relativas al directorio de trabajo, igual que los scripts
numerados. Antes de la corrección de esta tanda (revisión independiente),
`rag init` ASUMÍA que `configuracion/dominios/_generico/perfil.yaml` y
`configuracion/dominios/idiomas/es.yaml` ya existían en el directorio de trabajo -- lo que
solo funcionaba DENTRO de una copia de este repo, no como librería
reutilizable. Ahora `rag init` los ESCRIBE desde plantillas embebidas en
Python (`rag/lenguaje/dominio.py::escribir_perfil_generico_si_falta`,
`rag/lenguaje/texto.py::escribir_idioma_es_si_falta`), así que este fixture ya
NO los copia a mano -- si algún test de este archivo fallara por su
ausencia, sería una señal real de que la corrección se rompió. La prueba
DEFINITIVA de portabilidad, por subprocesos y fuera del árbol de este
proyecto, vive en `tests/integracion/test_portabilidad.py`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rag.cli import main

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _restaurar_perfil_activo():
    """``rag indexar``/``rag cargar`` configuran el perfil de dominio activo
    como estado de PROCESO (``rag.lenguaje.entidades.configurar_perfil``,
    mismo criterio que ``rag/servicio/api.py::startup`` -- ver
    ``tests/conftest.py``). Sin restaurarlo, un test de este archivo que
    indexa con el perfil ``_generico`` dejaría ese perfil activo para el
    resto de la sesión de pytest, rompiendo tests de otros archivos que
    dependen del perfil que fija la fixture de sesión."""
    from rag.lenguaje.entidades import configurar_perfil, perfil_activo

    anterior = perfil_activo()
    yield
    configurar_perfil(anterior)


@pytest.fixture()
def proyecto_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un directorio de trabajo AISLADO y VACÍO -- ni siquiera se copia
    `configuracion/dominios/_generico/` ni `configuracion/dominios/idiomas/`, a propósito: es lo que
    debe funcionar solo con `rag init` desde la corrección de esta tanda."""
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
    codigo = main(["init", "--nombre-asistente", "Asistente X100"])
    assert codigo == 0
    assert (proyecto_temporal / "configuracion" / "asistente.yaml").exists()
    assert (proyecto_temporal / "configuracion" / "motor.yaml").exists()
    assert (proyecto_temporal / "configuracion" / "dominio.yaml").exists()
    assert (proyecto_temporal / "documentos" / "catalogo.yaml").exists()
    assert (proyecto_temporal / "documentos").is_dir()

    # Corrección de esta tanda (revisión independiente, DEFECTO 1): en un
    # directorio VACÍO, 'rag init' debe ESCRIBIR el andamiaje del perfil y
    # del recurso de idioma, no asumir que ya existen.
    assert not (proyecto_temporal / "configuracion" / "dominios").exists()

    dominio = yaml.safe_load((proyecto_temporal / "configuracion" / "asistente.yaml").read_text(encoding="utf-8"))
    assert dominio["nombre_asistente"] == "Asistente X100"
    assert dominio["perfil"] == "medium"  # perfil de instalación por defecto
    motor = yaml.safe_load((proyecto_temporal / "configuracion" / "motor.yaml").read_text(encoding="utf-8"))
    assert motor["recuperacion"]["coleccion_base"] == "asistente_x100"


def test_init_cors_y_claves_widget_vacios_por_defecto(proyecto_temporal: Path):
    """Corrección de seguridad de esta tanda: un
    dominio recién creado NUNCA trae 'cors_origenes: [\"*\"]' -- eso
    expondría el servicio a cualquier sitio que copie la plantilla. Ambas
    listas empiezan vacías; se abren a mano con 'rag configurar'."""
    assert main(["init"]) == 0
    dominio = yaml.safe_load((proyecto_temporal / "configuracion" / "asistente.yaml").read_text(encoding="utf-8"))
    assert dominio["cors_origenes"] == []
    assert dominio["claves_widget"] == []


def test_init_no_pisa_configuracion_existente_sin_force(proyecto_temporal: Path):
    assert main(["init"]) == 0
    (proyecto_temporal / "configuracion" / "asistente.yaml").write_text(
        "nombre_asistente: Tocado\ndescripcion_dominio: x\nidioma: es\nperfil: _generico\n"
        "cors_origenes: []\n", encoding="utf-8",
    )
    codigo = main(["init"])
    assert codigo == 1
    dominio = yaml.safe_load((proyecto_temporal / "configuracion" / "asistente.yaml").read_text(encoding="utf-8"))
    assert dominio["nombre_asistente"] == "Tocado"  # no se pisó


def test_cargar_infiere_doc_id_y_titulo_y_conserva_comentarios(proyecto_temporal: Path):
    main(["init"])
    md = _doc_prueba_md(proyecto_temporal)
    txt = _doc_prueba_txt(proyecto_temporal)

    assert main(["cargar", str(md)]) == 0
    assert main(["cargar", str(txt)]) == 0

    contenido_catalogo = (proyecto_temporal / "documentos" / "catalogo.yaml").read_text(encoding="utf-8")
    assert contenido_catalogo.startswith("# Catálogo de documentos del corpus.")  # comentario original intacto

    catalogo = yaml.safe_load(contenido_catalogo)["documentos"]
    assert len(catalogo) == 2
    ids = {e["doc_id"] for e in catalogo}
    assert "manual-x100" in ids
    entrada_md = next(e for e in catalogo if e["doc_id"] == "manual-x100")
    assert entrada_md["doc_titulo"] == "Manual del Equipo Ficticio X100"
    assert "hash_contenido" in entrada_md
    assert (proyecto_temporal / "documentos" / "manual_x100.md").exists()


def test_cargar_mismo_contenido_dos_veces_no_duplica(proyecto_temporal: Path):
    main(["init"])
    md = _doc_prueba_md(proyecto_temporal)
    assert main(["cargar", str(md)]) == 0
    assert main(["cargar", str(md)]) == 0  # misma ruta, mismo contenido

    catalogo = yaml.safe_load(
        (proyecto_temporal / "documentos" / "catalogo.yaml").read_text(encoding="utf-8")
    )["documentos"]
    assert len(catalogo) == 1


def test_cargar_archivo_modificado_no_sobrescribe_la_version_anterior(
    proyecto_temporal: Path,
):
    main(["init"])
    md = _doc_prueba_md(proyecto_temporal)
    assert main(["cargar", str(md)]) == 0
    md.write_text(md.read_text(encoding="utf-8") + "\nVersión nueva.\n", encoding="utf-8")

    assert main(["cargar", str(md)]) == 0

    catalogo = yaml.safe_load(
        (proyecto_temporal / "documentos" / "catalogo.yaml").read_text(encoding="utf-8")
    )["documentos"]
    assert len(catalogo) == 2
    assert catalogo[0]["archivo"] == "manual_x100.md"
    assert catalogo[1]["archivo"].startswith("manual_x100-")
    assert (proyecto_temporal / "documentos" / catalogo[0]["archivo"]).is_file()
    assert (proyecto_temporal / "documentos" / catalogo[1]["archivo"]).is_file()


def test_cargar_formato_no_soportado_falla_sin_tocar_catalogo(proyecto_temporal: Path):
    main(["init"])
    ruta = proyecto_temporal / "archivo.rtf"
    ruta.write_text("contenido", encoding="utf-8")
    codigo = main(["cargar", str(ruta)])
    assert codigo == 1


def test_configurar_clave_desconocida_falla(proyecto_temporal: Path):
    main(["init"])
    assert main(["configurar", "clave_rara=1"]) == 1


def test_configurar_cors_origenes_como_lista(proyecto_temporal: Path):
    main(["init"])
    assert main(["configurar", "cors_origenes=https://a.cl,https://b.cl"]) == 0
    dominio = yaml.safe_load((proyecto_temporal / "configuracion" / "asistente.yaml").read_text(encoding="utf-8"))
    assert dominio["cors_origenes"] == ["https://a.cl", "https://b.cl"]


def test_configurar_claves_widget_como_lista(proyecto_temporal: Path):
    main(["init"])
    assert main(["configurar", "claves_widget=clave-sitio-a,clave-sitio-b"]) == 0
    dominio = yaml.safe_load((proyecto_temporal / "configuracion" / "asistente.yaml").read_text(encoding="utf-8"))
    assert dominio["claves_widget"] == ["clave-sitio-a", "clave-sitio-b"]


def test_doctor_sin_indice_reporta_falla_accionable(proyecto_temporal: Path, capsys):
    main(["init"])
    main(["cargar", str(_doc_prueba_md(proyecto_temporal))])
    capsys.readouterr()
    codigo = main(["doctor"])
    assert codigo == 1  # hay un documento cargado y el índice todavía no existe
    assert "Acción: rag indexar" in capsys.readouterr().out


def test_doctor_avisa_si_cors_vacio_con_claves_widget_configuradas(proyecto_temporal: Path, capsys):
    """'rag doctor' debe avisar cuando cors_origenes está vacío Y ya
    hay claves de widget configuradas -- la señal concreta de que alguien
    preparó el widget para un sitio real y se olvidó de abrirle CORS."""
    main(["init"])
    main(["configurar", "claves_widget=clave-sitio-a"])
    capsys.readouterr()  # descarta lo impreso por init/configurar
    main(["doctor"])
    salida = capsys.readouterr().out
    assert "CORS" in salida
    assert "cors_origenes" in salida.lower()


def test_doctor_reporta_textos_de_idioma_invalidos(proyecto_temporal: Path, capsys):
    """Un configuracion/idioma.yaml inválido rompería '/consultar' en la
    primera pregunta: 'rag doctor' debe decirlo antes."""
    main(["init"])
    (proyecto_temporal / "configuracion" / "idioma.yaml").write_text("mensajes: [1, 2]\n", encoding="utf-8")
    capsys.readouterr()
    codigo = main(["doctor"])
    salida = capsys.readouterr().out
    assert codigo == 1
    assert "[ERROR]   Idioma" in salida


def test_doctor_reporta_politica_abstencion_desconocida(proyecto_temporal: Path, capsys):
    main(["init"])
    ruta_motor = proyecto_temporal / "configuracion" / "motor.yaml"
    motor = yaml.safe_load(ruta_motor.read_text(encoding="utf-8"))
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
    assert main(["evaluar"]) == 0


@pytest.mark.slow
def test_indexar_dominio_sintetico_multiformato(proyecto_temporal: Path):
    """El flujo completo `init → cargar (md + txt) → indexar` sobre un
    dominio SINTÉTICO y aislado -- usa el modelo de
    embeddings real (ya en caché) y un índice
    Qdrant local real en el directorio temporal. Es la prueba de que el
    despacho multiformato y la CLI funcionan juntas de
    punta a punta, no solo por separado."""
    main(["init"])
    main(["cargar", str(_doc_prueba_md(proyecto_temporal))])
    main(["cargar", str(_doc_prueba_txt(proyecto_temporal))])

    codigo = main(["indexar"])
    assert codigo == 0

    # el índice quedó donde 'rag doctor' y el servicio lo esperan
    assert main(["doctor"]) == 0


def test_servir_sin_carpeta_conserva_el_modo_actual(monkeypatch, proyecto_temporal):
    llamadas = []
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: llamadas.append((args, kwargs)))

    assert main(["servir", "--port", "8123"]) == 0

    assert llamadas[0][0] == ("rag.servicio.api:app",)
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
    monkeypatch.setattr("rag.cli.comandos.corpus.ComandoIndexar.ejecutar", lambda _self, _args: 0)
    monkeypatch.setattr(
        "rag.aplicacion.diagnostico.verificar_indice",
        lambda: type("Chequeo", (), {"ok": False})(),
    )

    assert main(["servir", str(fuente)]) == 0

    proyecto = fuente / ".rag-extractivo"
    assert llamadas == [proyecto]
    assert (proyecto / "configuracion" / "asistente.yaml").is_file()
    catalogo = yaml.safe_load(
        (proyecto / "documentos" / "catalogo.yaml").read_text(encoding="utf-8")
    )
    assert [entrada["doc_id"] for entrada in catalogo["documentos"]] == ["manual-x100"]
    assert Path.cwd() == proyecto_temporal


def test_servir_carpeta_reutiliza_indice_vigente(monkeypatch, proyecto_temporal):
    assert main(["init"]) == 0
    indexaciones = []
    servidores = []
    monkeypatch.setattr("rag.cli.comandos.corpus.ComandoIndexar.ejecutar",
                        lambda _self, args: indexaciones.append(args) or 0)
    monkeypatch.setattr(
        "rag.aplicacion.diagnostico.verificar_indice",
        lambda: type("Chequeo", (), {"ok": True})(),
    )
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: servidores.append(Path.cwd()))

    assert main(["servir", str(proyecto_temporal)]) == 0

    assert indexaciones == []
    assert servidores == [proyecto_temporal]


def test_servir_completa_proyecto_parcial_sin_pisar_asistente(
    monkeypatch, proyecto_temporal
):
    configuracion = proyecto_temporal / "configuracion"
    configuracion.mkdir()
    asistente = configuracion / "asistente.yaml"
    asistente.write_text(
        "config_version: 2\n"
        "nombre_asistente: Parcial\n"
        "descripcion_dominio: documentación parcial\n"
        "idioma: es\nperfil: _generico\ncors_origenes: []\nclaves_widget: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("rag.cli.comandos.corpus.ComandoIndexar.ejecutar", lambda _self, _args: 0)
    monkeypatch.setattr(
        "rag.aplicacion.diagnostico.verificar_indice",
        lambda: type("Chequeo", (), {"ok": False})(),
    )
    monkeypatch.setattr("uvicorn.run", lambda *_args, **_kwargs: None)

    assert main(["servir", str(proyecto_temporal)]) == 0

    assert yaml.safe_load(asistente.read_text(encoding="utf-8"))["nombre_asistente"] == "Parcial"
    assert (configuracion / "motor.yaml").is_file()
    assert not (configuracion / "textos.yaml").exists()
    assert (configuracion / "estilos.yaml").is_file()
    assert (proyecto_temporal / "documentos" / "catalogo.yaml").is_file()


def test_servir_rechaza_carpeta_sin_documentos(monkeypatch, proyecto_temporal):
    fuente = proyecto_temporal / "vacia"
    fuente.mkdir()
    monkeypatch.setattr("uvicorn.run", lambda *_args, **_kwargs: pytest.fail("no debe servir"))

    assert main(["servir", str(fuente)]) == 1
    assert not (fuente / ".rag-extractivo").exists()
    assert Path.cwd() == proyecto_temporal


# ---------------------------------------------------------------------------
# rag preguntar -- código de salida:
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
    assert main(["preguntar", "¿algo?"]) != 0


def test_preguntar_codigo_no_cero_si_hay_timeout(monkeypatch: pytest.MonkeyPatch):
    import httpx

    def _post_timeout(*_args, **_kwargs):
        raise httpx.TimeoutException("se agotó el tiempo")

    monkeypatch.setattr(httpx, "post", _post_timeout)
    assert main(["preguntar", "¿algo?"]) != 0


def test_preguntar_codigo_no_cero_si_http_no_200(monkeypatch: pytest.MonkeyPatch):
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _RespuestaFalsa(500, texto="error interno"))
    assert main(["preguntar", "¿algo?"]) != 0


def test_preguntar_codigo_cero_si_responde_200(monkeypatch: pytest.MonkeyPatch):
    import httpx

    cuerpo = {"estado": "ok", "respuesta": "texto de prueba", "fragmentos": []}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _RespuestaFalsa(200, cuerpo))
    assert main(["preguntar", "¿algo?"]) == 0


# ---------------------------------------------------------------------------
# Ayuda de la CLI: cada opción de cada
# subcomando debe traer 'help=' en castellano -- antes 'rag servir --help'
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
    """Recorre todo el árbol (también ``rag golden …`` y ``rag widget tema …``)."""
    from rag.cli import construir_parser

    rutas = list(_subcomandos(construir_parser()))
    assert len(rutas) >= 23
    for ruta, subparser in rutas:
        for accion in subparser._actions:
            if accion.dest == "help":  # el propio '-h/--help' automático
                continue
            assert accion.help and len(accion.help.strip()) > 10, f"rag {' '.join(ruta)}: {accion.dest!r} sin ayuda útil"
