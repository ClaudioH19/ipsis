"""Cabecera contextual básica y extendida (F3.1): idiomas, orden fijo y texto citado intacto."""
from __future__ import annotations

import pytest

from ipsis.ingesta import ingesta as ing
from ipsis.ingesta.chunking import construir_texto_embebido
from ipsis.ingesta.metadata import cargar_taxonomia, senales_de_texto
from ipsis.ingesta.parsear import parsear_documento
from ipsis.lenguaje.entidades import configurar_idioma
from ipsis.lenguaje.paquete import cargar_paquete


@pytest.fixture
def idioma():
    def usar(codigo):
        paquete = cargar_paquete(codigo)
        configurar_idioma(paquete)
        return paquete
    yield usar
    configurar_idioma(cargar_paquete("es"))


ESPERADO = {
    "es": ("Documento: Manual | Sección: A > B", "Contiene: monto, plazo | condición | excepción"),
    "en": ("Document: Manual | Section: A > B", "Contains: amount, deadline | condition | exception"),
    "pt": ("Documento: Manual | Seção: A > B", "Contém: prazo, valor | condição | exceção"),
}


@pytest.mark.parametrize("codigo", ["es", "en", "pt"])
def test_cabecera_extendida_en_los_tres_idiomas(idioma, codigo):
    paquete = idioma(codigo)
    # Repetidos y desordenados: salen una vez y en orden fijo.
    texto = construir_texto_embebido("Manual", ["A", "B"], "cuerpo", paquete,
                                     tipos_entidad=["plazo", "monto", "plazo"], condicion=True, excepcion=True)
    primera, segunda = ESPERADO[codigo]
    assert texto == f"{primera}\n{segunda}\ncuerpo"


def test_sin_senales_la_cabecera_extendida_es_la_basica(idioma):
    paquete = idioma("es")
    basica = construir_texto_embebido("Manual", ["A"], "cuerpo", paquete)
    assert construir_texto_embebido("Manual", ["A"], "cuerpo", paquete, tipos_entidad=[]) == basica
    assert basica == "Documento: Manual | Sección: A\ncuerpo"


def test_solo_marcas_y_tipo_desconocido(idioma):
    paquete = idioma("es")
    texto = construir_texto_embebido("M", [], "x", paquete, tipos_entidad=["saber"], excepcion=True)
    assert texto.splitlines()[:2] == ["Documento: M | Sección: (sin sección)", "Contiene: saber | excepción"]


def test_senales_de_texto_detecta_tipos_y_marcas(idioma):
    idioma("es")
    entidades, excepcion, condicion = senales_de_texto(
        "Si el cliente paga antes de 10 días hábiles, se descuenta 5 %, salvo en feriados.")
    assert {e["tipo"] for e in entidades} >= {"plazo", "porcentaje"}
    assert excepcion and condicion


def _payloads(tmp_path, monkeypatch, detalle):
    md = tmp_path / "doc.md"
    md.write_text("# Manual\n\n## Pagos\n\nSi el cliente paga antes de 10 días hábiles, se descuenta 5 %, "
                  "salvo en feriados.\n\n## Otros\n\nEl horario es amplio y la atención es amable.\n",
                  encoding="utf-8")
    doc = parsear_documento(str(md), doc_id="d", doc_titulo="Manual", version="1")
    monkeypatch.setattr(ing, "entradas_vigentes",
                        lambda: [{"doc_id": "d", "doc_titulo": "Manual", "version": "1", "vigente": True}])
    return doc, ing.construir_chunks_y_payloads([doc], "CH-SEC", True, cargar_taxonomia(), detalle)


def test_el_texto_citado_y_los_offsets_no_cambian_con_la_cabecera_extendida(idioma, tmp_path, monkeypatch):
    idioma("es")
    doc, (chunks_b, basicos) = _payloads(tmp_path, monkeypatch, "basico")
    _, (chunks_e, extendidos) = _payloads(tmp_path, monkeypatch, "extendido")
    assert len(basicos) == len(extendidos) >= 2
    for b, e in zip(basicos, extendidos):
        for campo in ("texto", "offset_inicio", "offset_fin", "hash_texto", "entidades", "keywords",
                      "tiene_condicion", "tiene_excepcion", "chunk_id"):
            assert b[campo] == e[campo]
        assert doc.texto_completo[e["offset_inicio"]:e["offset_fin"]] == e["texto"]
        assert e["texto_embebido"].endswith("\n" + e["texto"])
    pagos = next(p for p in extendidos if "Pagos" in p["seccion_path"])
    segunda_linea = pagos["texto_embebido"].splitlines()[1]
    assert segunda_linea.startswith("Contiene: ") and "condición" in segunda_linea and "excepción" in segunda_linea
    otros = next(p for p in extendidos if "Otros" in p["seccion_path"])
    assert otros["texto_embebido"] == next(p for p in basicos if "Otros" in p["seccion_path"])["texto_embebido"]


def test_la_cabecera_extendida_es_determinista(idioma, tmp_path, monkeypatch):
    idioma("es")
    a = _payloads(tmp_path, monkeypatch, "extendido")[1][1]
    b = _payloads(tmp_path, monkeypatch, "extendido")[1][1]
    assert [p["texto_embebido"] for p in a] == [p["texto_embebido"] for p in b]


def test_sin_cabecera_el_detalle_no_aplica(idioma, tmp_path, monkeypatch):
    idioma("es")
    _, (_, payloads) = _payloads(tmp_path, monkeypatch, "extendido")
    md_sin = ing.construir_chunks_y_payloads
    # con_header=False: el texto embebido es el texto del fragmento.
    doc = parsear_documento(str(tmp_path / "doc.md"), doc_id="d", doc_titulo="Manual", version="1")
    _, sin = md_sin([doc], "CH-SEC", False, cargar_taxonomia(), "extendido")
    assert all(p["texto_embebido"] == p["texto"] for p in sin)


def test_la_huella_cambia_solo_con_el_detalle_extendido(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ing, "entradas_vigentes", lambda: [])
    base = {"estrategia_chunking": "CH-F256", "con_header": True}
    sin_campo = ing.huella_archivos(str(tmp_path), dict(base))
    assert ing.huella_archivos(str(tmp_path), {**base, "detalle_cabecera": "basico"}) == sin_campo
    assert ing.huella_archivos(str(tmp_path), {**base, "detalle_cabecera": "extendido"}) != sin_campo


def test_la_opcion_se_acepta_en_la_configuracion_con_su_nombre_publico():
    from ipsis.configuracion.esquemas import RecuperacionConfig

    cfg = RecuperacionConfig(estrategia_chunking="CH-F256", coleccion_base="c", detalle_cabecera="extendido")
    assert cfg.detalle_cabecera == "extendido"
    assert RecuperacionConfig(estrategia_chunking="CH-F256", coleccion_base="c").detalle_cabecera == "basico"
