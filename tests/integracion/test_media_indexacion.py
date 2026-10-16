"""El carril multimedia con el modelo real (M1): el índice de documentos no cambia y ``sync`` maneja las dos series."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ipsis.cli import main
from ipsis.recursos.mensajes import t

E5 = "intfloat/multilingual-e5-small"
pytestmark = [pytest.mark.slow, pytest.mark.modelos(E5)]

MANUAL = """# Manual de matrícula

## Inscripción

Para inscribir asignaturas ingresa con tu clave única y elige las secciones disponibles.

## Pagos

El arancel se paga en cuotas durante el semestre.
"""
FICHA = {"title": "Inducción a la matrícula", "kind": "video", "url": "https://example.org/induccion",
         "description": "Cómo ingresar e inscribir asignaturas.", "version": "2026-03", "duration": "10:00",
         "chapters": [{"at": "01:00", "title": "Ingresar con la clave única"}]}


def _proyecto(carpeta: Path, con_media: bool, monkeypatch) -> None:
    carpeta.mkdir()
    monkeypatch.chdir(carpeta)
    (carpeta / "manual.md").write_text(MANUAL, encoding="utf-8")
    assert main(["init", "--profile", "light", "--language", "es"]) == 0
    assert main(["load", str(carpeta / "manual.md")]) == 0
    if con_media:
        _ficha(carpeta, FICHA)


def _ficha(carpeta: Path, datos: dict) -> None:
    (carpeta / "media").mkdir(exist_ok=True)
    (carpeta / "media" / "induccion.yaml").write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")


def _manifiestos(carpeta: Path) -> dict[str, dict]:
    return {p.name[:-len(".manifest.json")]: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((carpeta / ".ipsis" / "index").glob("*.manifest.json"))}


def test_el_indice_de_documentos_es_el_mismo_con_y_sin_media(tmp_path, monkeypatch, capsys):
    sin, con = tmp_path / "sin", tmp_path / "con"
    resultados = {}
    for carpeta, con_media in ((sin, False), (con, True)):
        _proyecto(carpeta, con_media, monkeypatch)
        capsys.readouterr()
        assert main(["index"]) == 0
        resultados[carpeta.name] = (capsys.readouterr().out, _manifiestos(carpeta))
    salida_sin, manifiestos_sin = resultados["sin"]
    salida_con, manifiestos_con = resultados["con"]
    # Sin media/ no hay ni una palabra del carril en la salida ni una colección de más.
    assert "media" not in salida_sin.lower() and all("__media" not in n for n in manifiestos_sin)
    # Con media/: la colección de documentos es la misma y aparece el carril aparte.
    nombres_media = [n for n in manifiestos_con if n.endswith("__media")]
    assert len(nombres_media) == 1 and nombres_media[0].startswith(next(iter(manifiestos_sin)))
    documentos = next(iter(manifiestos_sin))
    for campo in ("hash_corpus", "n_chunks", "modelo_denso", "dimension", "stemmer", "inventario_entidades"):
        assert manifiestos_con[documentos][campo] == manifiestos_sin[documentos][campo], campo
    assert t("index.media_indexed", cards=1, chapters=1, collection=nombres_media[0]) in salida_con
    assert manifiestos_con[nombres_media[0]]["n_chunks"] == 2  # la ficha y su capítulo


def test_sync_reindexa_cuando_cambian_las_fichas_y_poda_las_dos_series(tmp_path, monkeypatch, capsys):
    carpeta = tmp_path / "p"
    _proyecto(carpeta, True, monkeypatch)
    assert main(["index"]) == 0
    v1 = set(_manifiestos(carpeta))
    capsys.readouterr()

    # Sin cambios (ni en documentos ni en fichas): no se reindexa.
    assert main(["sync"]) == 0
    assert t("sync.nothing") in capsys.readouterr().out and set(_manifiestos(carpeta)) == v1

    # Cambia solo una ficha: sync lo avisa, reindexa y crea la versión siguiente de las dos colecciones.
    _ficha(carpeta, {**FICHA, "description": "Otra descripción de la inducción."})
    assert main(["sync"]) == 0
    salida = capsys.readouterr().out
    assert t("sync.media_changed") in salida and t("sync.version_bumped", old=1, new=2) in salida
    v2 = set(_manifiestos(carpeta))
    assert len(v2 - v1) == 2 and any(n.endswith("_v2__media") for n in v2) and any(n.endswith("_v2") for n in v2)

    # Y con --prune se borran las versiones antiguas de las dos series (documentos y carril).
    _ficha(carpeta, {**FICHA, "description": "Una tercera descripción."})
    assert main(["sync", "--prune"]) == 0
    salida = capsys.readouterr().out
    quedan = set(_manifiestos(carpeta))
    assert quedan == {n for n in quedan if "_v3" in n} and len(quedan) == 2 and any(n.endswith("__media") for n in quedan)
    assert t("sync.pruned", names=", ".join(sorted((v1 | v2) - quedan))) in salida


def _motor_del_proyecto():
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

    return construir_motor(cargar_proyecto(), cfg_dominio=cargar_dominio())


def _configurar_carril(**media) -> None:
    from ipsis.configuracion import rutas
    from ipsis.configuracion.archivos import escribir, leer

    cfg = leer(rutas.MOTOR, "motor")
    cfg["media"] = media
    escribir(rutas.MOTOR, cfg, "motor")


def test_el_motor_publica_la_ficha_y_las_mismas_fuentes_que_sin_carril(tmp_path, monkeypatch):
    _proyecto(tmp_path / "p", True, monkeypatch)
    assert main(["index"]) == 0
    pregunta = "¿Cómo inscribo asignaturas?"

    def consultar(**media):
        _configurar_carril(**media)
        motor = _motor_del_proyecto()
        try:
            motor.calentar()
            return motor.consultar(pregunta, "s")
        finally:
            motor.cerrar()

    apagado = consultar(activo=False)
    sin_umbral = consultar(activo=True, puntaje_minimo=None)  # encendido pero sin puntaje_minimo: no se publica nada
    con_umbral = consultar(activo=True, puntaje_minimo=-1.0, max_resultados=2)

    assert "multimedia" not in apagado.contrato_http
    assert sin_umbral.contrato_http["multimedia"] == []
    fichas = con_umbral.contrato_http["multimedia"]
    assert [f["media_id"] for f in fichas] == ["induccion"] and fichas[0]["kind"] == "video"
    assert fichas[0]["url"] == FICHA["url"] and fichas[0]["description"] == FICHA["description"]
    assert isinstance(fichas[0]["score"], float) and fichas[0]["score"] > 0.5
    # las fuentes de documentos no se enteran del carril
    documentos = lambda r: [(f["chunk_id"], f["rango"], f["score"], f["offset_inicio"], f["offset_fin"])
                            for f in r.contrato_http["fragmentos"]]
    assert documentos(apagado) and documentos(apagado) == documentos(sin_umbral) == documentos(con_umbral)


def test_un_proyecto_nuevo_muestra_la_ficha_que_corresponde_y_no_una_ajena_sin_tocar_la_configuracion(tmp_path, monkeypatch):
    """Los valores por defecto de ``ipsis init`` (``media.enabled`` y ``min_score``): el carril ya funciona."""
    from ipsis.servicio.api import respuesta_publica

    _proyecto(tmp_path / "p", True, monkeypatch)
    assert main(["index"]) == 0
    motor = _motor_del_proyecto()
    try:
        motor.calentar()
        propia = respuesta_publica(motor.consultar("¿Cómo inscribo asignaturas en la plataforma?", "s").contrato_http)
        ajena = respuesta_publica(motor.consultar("¿Cuál es la capital de Australia?", "s").contrato_http)
    finally:
        motor.cerrar()
    assert [f["media_id"] for f in propia["media"]] == ["induccion"] and propia["media"][0]["url"] == FICHA["url"]
    assert "media" not in ajena
