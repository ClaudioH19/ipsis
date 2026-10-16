"""Fichas multimedia (M0.1): lectura, validación y errores. Sin modelos ni índice."""
from __future__ import annotations

from copy import deepcopy

import pytest

from ipsis.ingesta.fichas import Capitulo, Ficha, a_segundos, leer_fichas, validar_ficha
from ipsis.recursos.mensajes import t

VALIDA = {
    "title": "Inducción a la plataforma de matrícula",
    "kind": "video",
    "url": "https://www.youtube.com/watch?v=XXXXXXXX",
    "description": "Cómo ingresar, inscribir asignaturas\n  y revisar el horario.\n",
    "keywords": ["matrícula", "inscripción"],
    "language": "es",
    "version": "2026-03",
    "duration": "00:14:32",
    "chapters": [
        {"at": "00:01:10", "title": "Ingresar con la clave única"},
        {"at": "00:06:45", "title": "Inscribir asignaturas", "description": "Elegir secciones y confirmar."},
    ],
}


def _con(**cambios):
    datos = deepcopy(VALIDA)
    for clave, valor in cambios.items():
        if valor is ...:
            datos.pop(clave)
        else:
            datos[clave] = valor
    return datos


def test_ficha_completa_valida():
    ficha, errores = validar_ficha("induccion-matricula", VALIDA)
    assert errores == []
    assert ficha == Ficha(
        id="induccion-matricula", titulo="Inducción a la plataforma de matrícula", tipo="video",
        descripcion="Cómo ingresar, inscribir asignaturas y revisar el horario.",
        url="https://www.youtube.com/watch?v=XXXXXXXX", archivo=None, palabras_clave=("matrícula", "inscripción"),
        idioma="es", version="2026-03", duracion=872, vigente=True,
        capitulos=(Capitulo(70, "Ingresar con la clave única"),
                   Capitulo(405, "Inscribir asignaturas", "Elegir secciones y confirmar.")))


def test_ficha_minima_valida_con_valores_por_defecto():
    ficha, errores = validar_ficha("charla", {"title": "Charla", "kind": "audio", "file": "files/charla.mp3",
                                              "description": "Una charla."})
    assert errores == [] and ficha.archivo == "files/charla.mp3" and ficha.url is None
    assert ficha.vigente is True and ficha.capitulos == () and ficha.palabras_clave == ()
    assert ficha.duracion is None and ficha.version is None and ficha.idioma is None


def test_version_numerica_se_guarda_como_texto():
    ficha, _ = validar_ficha("charla", _con(version=1.2))
    assert ficha.version == "1.2"


@pytest.mark.parametrize("valor, segundos", [
    ("14:32", 872), ("01:14:32", 4472), ("00:14:32", 872), ("75:30", 4530), ("0:05", 5),
    (872, 872),  # YAML lee 14:32 sin comillas como el entero 872: ya son segundos
    (0, 0),
])
def test_a_segundos_acepta_tiempos(valor, segundos):
    assert a_segundos(valor) == segundos


@pytest.mark.parametrize("valor", ["", "abc", "14:75", "1:2:3", "14:32:", "-1:30", -5, 1.5, True, None, [], "14:32 min"])
def test_a_segundos_rechaza_lo_que_no_es_un_tiempo(valor):
    assert a_segundos(valor) is None


def test_el_yaml_sin_comillas_funciona(tmp_path):
    (tmp_path / "v.yaml").write_text(
        "title: V\nkind: video\nurl: https://x.org/v\ndescription: D\nduration: 14:32\n"
        "chapters:\n  - {at: 06:45, title: A}\n  - {at: 10:05, title: B}\n", encoding="utf-8")
    lectura = leer_fichas(tmp_path)
    assert lectura.errores == {}
    assert lectura.fichas[0].duracion == 872
    assert [c.segundos for c in lectura.fichas[0].capitulos] == [405, 605]  # 06:45 es texto; 10:05 es el entero 605


@pytest.mark.parametrize("datos, error", [
    (_con(title=...), t("media.required", field="title")),
    (_con(title="   "), t("media.invalid_text", field="title")),
    (_con(title=5), t("media.invalid_text", field="title")),
    (_con(description=...), t("media.required", field="description")),
    (_con(description=""), t("media.invalid_text", field="description")),
    (_con(kind="podcast"), t("media.invalid_kind")),
    (_con(kind=...), t("media.invalid_kind")),
    (_con(url=...), t("media.source_exactly_one")),
    (_con(file="files/v.mp4"), t("media.source_exactly_one")),  # url y file a la vez
    (_con(url="http://x.org/v"), t("media.url_not_https")),
    (_con(url="https://"), t("media.url_not_https")),
    (_con(url=123), t("media.url_not_https")),
    (_con(url=..., file="/etc/passwd"), t("media.file_outside")),
    (_con(url=..., file="../v.mp4"), t("media.file_outside")),
    (_con(url=..., file="files/../../v.mp4"), t("media.file_outside")),
    (_con(url=..., file="v.mp4"), t("media.file_outside")),  # dentro de media/ pero fuera de files/
    (_con(url=..., file="otra/v.mp4"), t("media.file_outside")),
    (_con(url=..., file="files\\v.mp4"), t("media.file_outside")),
    (_con(url=..., file="files"), t("media.file_outside")),
    (_con(keywords="matrícula"), t("media.invalid_keywords")),
    (_con(keywords=["a", ""]), t("media.invalid_keywords")),
    (_con(keywords=["a", 3]), t("media.invalid_keywords")),
    (_con(language="Español"), t("media.invalid_language")),
    (_con(language=5), t("media.invalid_language")),
    (_con(version=True), t("media.invalid_version")),
    (_con(version=["1"]), t("media.invalid_version")),
    (_con(duration="mucho"), t("media.invalid_time", field="duration")),
    (_con(active="sí"), t("media.invalid_active")),
    (_con(rareza=1), t("media.unknown_key", key="rareza")),
    (_con(transcript="t.vtt"), t("media.transcript_unsupported")),
    (_con(chapters="uno"), t("media.invalid_chapters")),
    (_con(chapters=["uno"]), t("media.chapter_not_object", n=1)),
    (_con(chapters=[{"at": "x", "title": "A"}]), t("media.invalid_time", field="chapters[1].at")),
    (_con(chapters=[{"at": "01:00"}]), t("media.invalid_text", field="chapters[1].title")),
    (_con(chapters=[{"at": "01:00", "title": "A", "description": ""}]),
     t("media.invalid_text", field="chapters[1].description")),
    (_con(chapters=[{"at": "01:00", "title": "A", "extra": 1}]), t("media.unknown_key", key="chapters[1].extra")),
    (_con(chapters=[{"at": "05:00", "title": "A"}, {"at": "02:00", "title": "B"}]), t("media.chapter_order", n=2)),
    (_con(chapters=[{"at": "05:00", "title": "A"}, {"at": "05:00", "title": "B"}]), t("media.chapter_order", n=2)),
    (_con(chapters=[{"at": "20:00", "title": "A"}]), t("media.chapter_after_duration", n=1)),  # dura 14:32
    (_con(duration="14:32", chapters=[{"at": "14:32", "title": "A"}]), t("media.chapter_after_duration", n=1)),
])
def test_cada_error_de_la_ficha_se_informa(datos, error):
    ficha, errores = validar_ficha("ficha", datos)
    assert ficha is None
    assert error in errores


@pytest.mark.parametrize("id_ficha", ["Induccion", "con espacio", "-a", "a-", "a--b", "a_b", "año", ""])
def test_id_invalido(id_ficha):
    ficha, errores = validar_ficha(id_ficha, VALIDA)
    assert ficha is None and t("media.invalid_id", id=id_ficha) in errores


@pytest.mark.parametrize("datos", [None, [], "texto", 3])
def test_un_archivo_que_no_es_un_mapa_se_rechaza(datos):
    assert validar_ficha("ficha", datos) == (None, [t("media.not_object")])


def test_se_informan_todos_los_errores_juntos_y_en_orden_estable():
    ficha, errores = validar_ficha("ficha", {"title": "", "kind": "x", "zeta": 1, "alfa": 2})
    assert ficha is None
    assert errores == validar_ficha("ficha", {"alfa": 2, "zeta": 1, "kind": "x", "title": ""})[1]
    assert t("media.unknown_key", key="alfa") in errores and t("media.unknown_key", key="zeta") in errores
    assert errores.index(t("media.unknown_key", key="alfa")) < errores.index(t("media.unknown_key", key="zeta"))
    assert len(errores) >= 5


def _escribir(carpeta, nombre, datos=None, texto=None):
    import yaml

    (carpeta / nombre).write_text(texto if texto is not None else yaml.safe_dump(datos, allow_unicode=True),
                                  encoding="utf-8")


def test_leer_fichas_ordena_por_id_y_un_archivo_invalido_no_impide_leer_los_demas(tmp_path):
    _escribir(tmp_path, "zeta.yaml", VALIDA)
    _escribir(tmp_path, "alfa.yaml", _con(title="Alfa"))
    _escribir(tmp_path, "rota.yaml", _con(kind="podcast"))
    _escribir(tmp_path, "notas.txt", texto="no es una ficha")
    lectura = leer_fichas(tmp_path)
    assert [f.id for f in lectura.fichas] == ["alfa", "zeta"]
    assert list(lectura.errores) == ["rota"] and t("media.invalid_kind") in lectura.errores["rota"]


def test_leer_fichas_es_determinista_sin_importar_el_orden_de_creacion(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    for nombre in ("uno", "dos", "tres"):
        _escribir(a, f"{nombre}.yaml", _con(title=nombre))
    for nombre in ("tres", "dos", "uno"):
        _escribir(b, f"{nombre}.yaml", _con(title=nombre))
    assert [f.id for f in leer_fichas(a).fichas] == [f.id for f in leer_fichas(b).fichas] == ["dos", "tres", "uno"]


def test_sin_carpeta_no_hay_fichas_ni_errores(tmp_path):
    lectura = leer_fichas(tmp_path / "no-existe")
    assert lectura.fichas == [] and lectura.errores == {}


def test_un_file_debe_existir_en_la_carpeta(tmp_path):
    datos = _con(url=..., file="files/charla.mp3")
    _escribir(tmp_path, "charla.yaml", datos)
    assert leer_fichas(tmp_path).errores == {"charla": [t("media.file_missing", file="files/charla.mp3")]}
    (tmp_path / "files").mkdir()
    (tmp_path / "files" / "charla.mp3").write_bytes(b"\x00")
    lectura = leer_fichas(tmp_path)
    assert lectura.errores == {} and lectura.fichas[0].archivo == "files/charla.mp3"


def test_yaml_roto_y_archivo_vacio(tmp_path):
    _escribir(tmp_path, "roto.yaml", texto="title: [sin cerrar\n")
    _escribir(tmp_path, "vacio.yaml", texto="")
    errores = leer_fichas(tmp_path).errores
    assert errores["vacio"] == [t("media.not_object")]
    assert len(errores["roto"]) == 1 and errores["roto"][0].startswith(t("media.unreadable", error="")[:10])


def test_el_modulo_no_abre_el_archivo_multimedia(tmp_path):
    """Solo se comprueba que exista: un «video» con bytes cualesquiera sirve (no se analiza su contenido)."""
    (tmp_path / "files").mkdir()
    (tmp_path / "files" / "v.mp4").write_bytes(b"no soy un video")
    _escribir(tmp_path, "v.yaml", _con(url=..., file="files/v.mp4"))
    assert leer_fichas(tmp_path).errores == {}
