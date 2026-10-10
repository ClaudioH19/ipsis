"""Separación entre recuperación léxica y aceptación de una respuesta literal."""
from types import SimpleNamespace

import pytest

from ipsis.lenguaje import sinonimos as recursos
from ipsis.lenguaje.consultas import equivalentes, sinonimos_presentes, terminos_de_contenido
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.texto import terminos


def _proyecto(tmp_path, grupos):
    import yaml

    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config/domain.yaml").write_text(yaml.safe_dump({"synonyms": grupos}), encoding="utf-8")
    return cargar_paquete("es", proyecto=tmp_path)


def _grupo(paquete, sentido="uno", formas=("edificio", "inmueble")):
    return recursos.GrupoLexico("fuente", sentido, "n", formas,
                                tuple(terminos(f, paquete)[0] for f in formas))


def test_automaticos_solo_expanden_recuperacion_y_conservan_foco(monkeypatch):
    p = cargar_paquete("es")
    g = _grupo(p)
    monkeypatch.setattr(recursos, "indice_automatico", lambda *_: {r: (g,) for r in g.raices})
    est = SimpleNamespace(df={g.raices[1]: 1})
    expansion, detalles = recursos.expansion_automatica("¿Qué edificio?", p, est)
    assert expansion == {"edificio": ["inmueble"]}
    assert detalles[0]["sentido"] == "uno" and detalles[0]["pos"] == "n"
    assert g.raices[0] in terminos_de_contenido("¿Qué edificio?", p, est)
    assert g.raices[0] not in equivalentes([g.raices[1]], p)
    est.df[g.raices[0]] = 1
    assert recursos.expansion_automatica("edificio", p, est) == ({}, [])


def test_colision_de_sentidos_o_stems_se_abstiene(monkeypatch):
    p = cargar_paquete("es")
    g = _grupo(p)
    otro = _grupo(p, "dos", ("edificio", "transporte"))
    monkeypatch.setattr(recursos, "indice_automatico", lambda *_: {g.raices[0]: (g, otro)})
    assert recursos.expansion_automatica("edificio", p, SimpleNamespace(df={g.raices[1]: 1})) == ({}, [])


def test_reemplazo_con_raiz_ambigua_no_se_expande(monkeypatch):
    p = cargar_paquete("es")
    g = _grupo(p)
    otro = _grupo(p, "dos", ("inmueble", "motorizado"))
    indice = {g.raices[0]: (g,), g.raices[1]: (g, otro)}
    monkeypatch.setattr(recursos, "indice_automatico", lambda *_: indice)
    assert recursos.expansion_automatica("edificio", p, SimpleNamespace(df={g.raices[1]: 1})) == ({}, [])


def test_relacion_y_manuales_tienen_prioridad(monkeypatch):
    p = cargar_paquete("es")
    g = _grupo(p, formas=("empieza", "inicia"))
    h = _grupo(p, formas=("necesita", "requiere"))
    monkeypatch.setattr(recursos, "indice_automatico", lambda *_: {g.raices[0]: (g,), h.raices[0]: (h,)})
    est = SimpleNamespace(df={g.raices[1]: 1, h.raices[1]: 1})
    assert recursos.expansion_automatica("¿Cuándo empieza la compra?", p, est) == ({}, [])
    assert recursos.expansion_automatica("necesita", p, est) == ({}, [])


def test_analisis_preserva_pregunta_y_guarda_expansion_aparte(monkeypatch):
    from ipsis.consulta.contexto import ContextoConsulta
    from ipsis.consulta.etapas.analisis import EtapaAnalisis
    from ipsis.nucleo.esquemas import QueryAnalysis

    p = cargar_paquete("es")
    g = _grupo(p)
    monkeypatch.setattr(recursos, "indice_automatico", lambda *_: {r: (g,) for r in g.raices})
    est = SimpleNamespace(df={g.raices[1]: 1})
    motor = SimpleNamespace(idioma=p, retriever=SimpleNamespace(estadisticas_lexico=lambda: est),
                            _analizar=lambda pregunta, sesion: QueryAnalysis(pregunta_original=pregunta,
                                                                          pregunta_normalizada=pregunta))
    ctx = ContextoConsulta(pregunta="¿Qué edificio?", id_sesion="uno")
    EtapaAnalisis(motor).ejecutar(ctx)
    assert ctx.consulta.pregunta_original == ctx.pregunta == "¿Qué edificio?"
    assert ctx.consulta.contexto["pregunta_recuperacion"] == "¿Qué edificio? inmueble"
    assert ctx.diagnostico["recursos_lexicos"][0]["sentido"] == "uno"


def test_recuperacion_bm25_expandida_reutiliza_vector_original(monkeypatch):
    from ipsis.consulta.etapas import recuperacion
    from ipsis.nucleo.esquemas import QueryAnalysis

    consultas, busquedas = [], []
    retriever = recuperacion.RetrieverQdrant(SimpleNamespace())
    retriever._vector_consulta = lambda texto: consultas.append(texto) or [0.5]
    def buscar(*args, **kwargs):
        busquedas.append((args[1], kwargs["vector_precomputado"]))
        return SimpleNamespace(payloads=[], scores=[])
    monkeypatch.setattr(recuperacion, "buscar", buscar)
    q = QueryAnalysis(pregunta_original="edificio", pregunta_normalizada="edificio",
                      contexto={"pregunta_recuperacion": "edificio inmueble"})
    assert retriever.recuperar(q, 3) == []
    assert consultas == ["edificio"] and busquedas == [("edificio inmueble", [0.5])]


@pytest.mark.parametrize("codigo", ["es", "en", "pt"])
def test_tabla_real_indexada_una_vez(codigo):
    p = cargar_paquete(codigo)
    indice = recursos.indice_automatico(codigo, p.stemmer)
    assert len(indice) > 1000
    assert recursos.indice_automatico(codigo, p.stemmer) is indice
    assert all(g.fuente and g.sentido and g.pos for gs in indice.values() for g in gs)


def test_sentido_descartado_sigue_bloqueando_lema(tmp_path, monkeypatch):
    (tmp_path / "sinonimos").mkdir()
    (tmp_path / "sinonimos/zz.tsv").write_text("# source\tfuente\nuno\tn\tedificio\tinmueble\n", encoding="utf-8")
    (tmp_path / "sinonimos/zz.lexicon.tsv").write_text(
        "uno\tn\tedificio\tinmueble\ndos\tn\tedificio\n", encoding="utf-8")
    monkeypatch.setattr(recursos, "files", lambda *_: tmp_path)
    p = cargar_paquete("es")
    assert terminos("edificio", p)[0] not in recursos.indice_automatico("zz", p.stemmer)


def test_respaldo_no_hereda_diccionario_ingles(monkeypatch):
    monkeypatch.setattr(recursos, "indice_automatico", lambda *_: pytest.fail("no debe cargar"))
    assert recursos.expansion_automatica("word", cargar_paquete("ru"), SimpleNamespace(df={})) == ({}, [])


@pytest.mark.parametrize("codigo,palabra,presente", [
    ("es", "neumoconiosis", "pneumoconiosis"),
    ("en", "pneumoconiosis", "pneumonoconiosis"),
    ("pt", "glicose", "glucose"),
])
def test_expansion_con_datos_reales_y_estadisticas_del_corpus(codigo, palabra, presente):
    from ipsis.indice.estadisticas import EstadisticasLexicas

    p = cargar_paquete(codigo)
    est = EstadisticasLexicas.construir([presente], p)
    expansion, detalles = recursos.expansion_automatica(palabra, p, est)
    assert presente in expansion[palabra]
    assert detalles[0]["fuente"] and detalles[0]["sentido"] and detalles[0]["pos"] == "n"
    assert terminos(palabra, p)[0] in terminos_de_contenido(palabra, p, est)


def test_sigla_del_proyecto_requiere_frase_completa(tmp_path):
    p = _proyecto(tmp_path, [["OC", "orden de compra"]])
    est = SimpleNamespace(df={r: 1 for r in terminos("orden de compra", p)})
    assert sinonimos_presentes("¿Dónde envío la OC?", p, est) == {"oc": ["orden de compra"]}
    assert "de" not in terminos_de_contenido("OC", p, est)
    assert sinonimos_presentes("orden", p, SimpleNamespace(df={"oc": 1})) == {}
    # Un único token presente de la frase no basta.
    assert sinonimos_presentes("OC", p, SimpleNamespace(df={"orden": 1})) == {}
    propio = p.model_copy(update={"sinonimos": [["orden", "mandato"]]})
    est = SimpleNamespace(df={r: 1 for r in terminos("mandato", p)})
    assert sinonimos_presentes("orden", propio, est) == {"orden": ["mandato"]}


def test_dominio_reemplaza_equivalencias_generales(tmp_path):
    p = _proyecto(tmp_path, [["necesita", "exige"]])
    est = SimpleNamespace(df={r: 1 for r in terminos("requieren exigen", p)})
    assert sinonimos_presentes("necesita", p, est) == {"necesita": ["exige"]}


def test_frase_resuelta_no_expande_tambien_sus_componentes(tmp_path, monkeypatch):
    p = _proyecto(tmp_path, [["oficina central", "sede"]])
    g = _grupo(p, formas=("oficina", "despacho"))
    monkeypatch.setattr(recursos, "indice_automatico", lambda *_: {r: (g,) for r in g.raices})
    est = SimpleNamespace(df={r: 1 for r in terminos("sede despacho", p)})
    assert sinonimos_presentes("oficina central", p, est) == {"oficina central": ["sede"]}
    assert recursos.expansion_automatica("oficina central", p, est) == ({}, [])
    assert recursos.expansion_automatica("oficina", p, est)[0] == {"oficina": ["despacho"]}


def test_cache_de_stopwords_respeta_configuracion_y_stemmer():
    from ipsis.lenguaje.lexico import terminos_pregunta

    p = SimpleNamespace(stemmer="english", stopwords=["the", "running"])
    assert terminos_pregunta("the running cats", p) == ["cat"]
    p.stopwords[:] = ["the", "cats"]
    assert terminos_pregunta("the running cats", p) == ["run"]
    p.stemmer = None
    assert terminos_pregunta("the running cats", p) == ["running"]


def test_huella_cambia_con_dominio_y_reglas(tmp_path):
    p = cargar_paquete("es")
    assert recursos.huella_lexica(p) == recursos.huella_lexica(cargar_paquete("es"))
    assert recursos.huella_lexica(p) != recursos.huella_lexica(_proyecto(tmp_path, [["OC", "orden de compra"]]))
    assert recursos.huella_lexica(p) != recursos.huella_lexica(p.model_copy(update={"sinonimos": []}))
    invertidas = dict(reversed(list(p.intenciones.items())))
    assert recursos.huella_lexica(p) != recursos.huella_lexica(p.model_copy(update={"intenciones": invertidas}))
    assert recursos.huella_lexica(p) != recursos.huella_lexica(p.model_copy(update={"numeros": {}}))
    assert recursos.huella_lexica(p) == recursos.huella_lexica(p.model_copy(update={"nombre": "Otro título"}))


@pytest.mark.parametrize("grupos", [[["solo"]], [[""]], "OC", [["OC", 7]]])
def test_dominio_invalido_falla_al_cargar(tmp_path, grupos):
    with pytest.raises(ValueError, match="synonyms"):
        _proyecto(tmp_path, grupos)
