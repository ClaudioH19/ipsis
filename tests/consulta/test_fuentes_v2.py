"""La búsqueda ofrece evidencia verificable sin convertir ranking en respuesta."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ipsis.configuracion.esquemas import validar_motor
from ipsis.indice.contextos import RecuperadorConContextos
from ipsis.servicio.api import RespuestaConsulta, respuesta_publica
from tests.consulta.test_motor_v2 import candidato, motor, Recuperador


def test_tres_fuentes_sin_qa_y_con_rangos_publicos():
    cs = [candidato(f"Producto {i}: stock {10+i}.", f"producto-{i}", inicio=100*i) for i in range(7)]
    resultado = motor(candidatos=cs).consultar("productos disponibles", "s")
    publica = respuesta_publica(resultado.contrato_http)
    RespuestaConsulta.model_validate(publica)
    assert publica["response_mode"] == "ranked_sources"
    assert publica["status"] == "related" and "exact_answer" not in publica
    assert [f["rank"] for f in publica["fragments"]] == [1, 2, 3]
    assert all(f["offset_start"] <= f["match_start"] <= f["match_end"] <= f["offset_end"]
               for f in publica["fragments"])
    assert resultado.diagnostico["lecturas"] is None


def test_contexto_se_amplia_despues_de_puntuar_y_no_repite_la_misma_fuente():
    fuente = "Encabezado\nProducto A: stock 10.\nProducto B: stock 20."
    cs = [candidato(t, str(i), inicio=fuente.index(t)) for i, t in enumerate(fuente.splitlines())]
    r = RecuperadorConContextos(Recuperador(cs), {c.chunk.chunk_id: c.chunk for c in cs},
        {"reglamento": SimpleNamespace(version="1", texto_completo=fuente)})

    class Reranker:
        def puntuar(self, pregunta, pasajes):
            self.pasajes = pasajes
            return [3, 2, 1]

    reranker = Reranker()
    m = motor(candidatos=cs, reranker=reranker, opciones={"lote_reranker": 32})
    m.retriever = r
    resultado = m.consultar("stock", "s")
    assert reranker.pasajes == fuente.splitlines()
    assert [e.chunk_id for e in resultado.evidencias] == ["0", "2"]
    for e in resultado.evidencias:
        assert fuente[e.offset_inicio:e.offset_fin] == e.texto
    assert "Producto A: stock 10." in resultado.evidencias[0].texto
    assert resultado.evidencias[0].score == 3
    assert any(not e["publicado"] for e in resultado.diagnostico["contextos_resultados"])


@pytest.mark.parametrize("clave", ["consejo", "council"])
def test_migracion_retira_consejo_y_preserva_los_presupuestos(clave):
    original = {"config_version": 6, "pipeline": "v2",
        "recuperacion": {"estrategia_chunking": "CH-F256", "coleccion_base": "demo"},
        "v2": {clave: {"modelos": ["no-descargar"]}, "recuperar_n": 80}}
    copia = deepcopy(original)
    cfg = validar_motor(original)
    assert original == copia
    assert cfg["config_version"] == 8 and clave not in cfg["v2"]
    assert cfg["v2"]["recuperar_n"] == 80 and cfg["v2"]["resultados_n"] == 3
    assert cfg["v2"]["destacar_fragmentos"] is False


def test_fabrica_medium_v2_no_carga_lector_ni_anuncia_modelos_no_ejecutados():
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.configuracion.carga import cargar_proyecto, cargar_dominio
    from ipsis.nucleo.registro import RegistroComponentes

    registro = RegistroComponentes()
    registro.registrar("retriever", "fuentes_test", lambda **_: Recuperador([candidato("Fuente")]))
    cfg = cargar_proyecto()
    cfg.update(pipeline="v2")
    cfg["componentes"]["retriever"] = "fuentes_test"
    m = construir_motor(cfg, cfg_dominio={**cargar_dominio(), "perfil": "medium"}, registro=registro)
    assert m.lector is None and m.reranker is not None and not hasattr(m, "consejo")
    assert "lector" not in m.metadatos_auditoria["modelos"]
    assert m.top_k == 3
    assert m.reranker.lote == 2 and m.reranker.spec.max_tokens == 256
    assert m.metadatos_auditoria["modelos"]["reranker"]["lote"] == 2


def test_fabrica_legacy_carga_contexto_del_markdown_sin_reindexar(tmp_path, monkeypatch):
    from ipsis.aplicacion.consulta import construir_motor
    from ipsis.cli import main
    from ipsis.configuracion.carga import cargar_proyecto, cargar_dominio
    from ipsis.ingesta.catalogo import agregar_documentos_al_catalogo
    from ipsis.ingesta.ingesta import parsear_corpus
    from ipsis.nucleo.registro import RegistroComponentes

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    archivo = tmp_path / "manual.md"
    archivo.write_text("# Productos\n\nFicha A.\n\nStock: 10 unidades.\n", encoding="utf-8")
    agregar_documentos_al_catalogo([str(archivo)])
    doc = parsear_corpus("documents", preparacion="legacy")[0]
    ficha = next(b for b in doc.bloques if b.texto == "Ficha A.")
    c = candidato(ficha.texto, "ficha", inicio=ficha.offset_inicio, seccion=ficha.seccion_path)
    c.chunk.doc_id, c.chunk.doc_titulo = doc.doc_id, doc.doc_titulo
    r = Recuperador([c])
    r.coleccion = SimpleNamespace(nombre="legacy")
    monkeypatch.setattr("ipsis.indice.manifiesto.cargar_manifiesto", lambda *_: SimpleNamespace(
        preparacion=None, hash_corpus=None))
    registro = RegistroComponentes()
    registro.registrar("retriever", "legacy_test", lambda **_: r)
    cfg = cargar_proyecto()
    cfg["pipeline"] = "v2"
    cfg["componentes"]["retriever"] = "legacy_test"
    m = construir_motor(cfg, cfg_dominio=cargar_dominio(), registro=registro)
    resultado = m.consultar("ficha", "s")
    e = resultado.evidencias[0]
    assert "Stock: 10 unidades." in e.texto
    assert doc.texto_completo[e.offset_inicio:e.offset_fin] == e.texto
    assert resultado.diagnostico["contextos_resultados"][0]["source_hash"] == doc.hash_documento
    assert respuesta_publica(resultado.contrato_http)["fragments"][0]["source_name"] == "manual.md"
