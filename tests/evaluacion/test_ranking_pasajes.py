"""Script de ranking por etapa: núcleo probado con un motor falso, sin modelos."""
from __future__ import annotations

import importlib.util
import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from ipsis.evaluacion.banco import EvidenciaEsperada

RUTA = Path(__file__).resolve().parents[2] / "herramientas/evaluacion/ranking_pasajes.py"


@pytest.fixture(scope="module")
def rp():
    spec = importlib.util.spec_from_file_location("ranking_pasajes", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _chunk(chunk_id, ini, fin, doc="d"):
    return SimpleNamespace(chunk=SimpleNamespace(chunk_id=chunk_id, doc_id=doc, offset_inicio=ini, offset_fin=fin))


class RetrieverFalso:
    def __init__(self, candidatos):
        self.candidatos = candidatos
        self.pedido = None

    def recuperar(self, consulta, k):
        self.pedido = k
        return self.candidatos[:k]


class MotorFalso:
    """Híbrido: a, b, c. El «reranker» publica b, c, a (con texto ampliado a vecinos)."""

    def __init__(self):
        self.opciones = {"recuperar_n": 60}
        self.retriever = RetrieverFalso([_chunk("a", 0, 100), _chunk("b", 100, 200), _chunk("c", 200, 300)])

    def consultar(self, pregunta, sesion):
        ev = lambda cid, ini, fin: SimpleNamespace(chunk_id=cid, doc_id="d", offset_inicio=ini, offset_fin=fin)
        # b publicado con offsets de todo el documento (vecinos): no debe contar como solape con a ni c.
        return SimpleNamespace(evidencias=[ev("b", 0, 300), ev("c", 0, 300), ev("a", 0, 300)],
                               diagnostico={"etapas": {"recuperacion_ms": 4, "reranking_ms": 30}})


def _caso(inicio, fin, split="dev", cid="x"):
    return SimpleNamespace(id=cid, split=split, pregunta="¿algo?", respondible=True,
                           evidencias=[EvidenciaEsperada(doc_id="d", offset_inicio=inicio, offset_fin=fin,
                                                         texto="t" * (fin - inicio))])


def test_rango_correcto_usa_solape_y_el_documento(rp):
    ev = _caso(150, 160).evidencias
    assert rp.rango_correcto([("d", 0, 100), ("d", 100, 200)], ev) == 2
    assert rp.rango_correcto([("otro", 100, 200)], ev) is None
    assert rp.rango_correcto([("d", 0, 150), ("d", 160, 200)], ev) is None  # tocar el borde no es solapar


def test_observa_ambos_rangos_con_los_offsets_del_fragmento_recuperado(rp):
    obs = rp.observar_caso(MotorFalso(), _caso(210, 220))
    assert obs["rango_hibrido"] == 3          # c es el tercero en el orden híbrido
    assert obs["rango_final"] == 2            # y el segundo tras el reranker
    assert obs["etapas_ms"] == {"recuperacion": 4, "reranking": 30}


def test_usa_recuperar_n_del_motor_como_k(rp):
    motor = MotorFalso()
    rp.observar_caso(motor, _caso(0, 10))
    assert motor.retriever.pedido == 60


def test_metricas_cuentan_none_como_fallo(rp):
    m = rp.metricas_de_rangos([1, 2, 5, None])
    assert m == {"n": 4, "hit@1": 0.25, "hit@3": 0.5, "hit@5": 0.75, "mrr": round((1 + 0.5 + 0.2) / 4, 4)}
    assert rp.metricas_de_rangos([])["n"] == 0


def test_resumen_lista_los_casos_que_no_son_primeros(rp):
    obs = [dict(id="a", rango_hibrido=2, rango_final=1, latencia_ms=10.0, etapas_ms={"reranking": 5}),
           dict(id="b", rango_hibrido=1, rango_final=3, latencia_ms=30.0, etapas_ms={"reranking": 7})]
    r = rp.resumir(obs)
    assert r["final"]["hit@1"] == 0.5 and r["hibrido"]["hit@1"] == 0.5
    assert r["casos_no_primeros"] == [{"id": "b", "rango_hibrido": 1, "rango_final": 3}]
    assert r["latencia_ms"]["p95"] > r["latencia_ms"]["p50"]
    assert r["etapas_ms"]["reranking"]["p50"] == 6.0


def test_comparar_lista_ganados_y_perdidos(rp):
    def informe(rangos):
        return {"perfiles": {"medium": {"observaciones": [dict(id=i, rango_final=r) for i, r in rangos.items()]}}}

    c = rp.comparar(informe({"a": 2, "b": 1, "c": 1}), informe({"a": 1, "b": 3, "c": 1}))
    assert c["medium"]["ganados"] == [{"id": "a", "antes": 2, "ahora": 1}]
    assert c["medium"]["perdidos"] == [{"id": "b", "antes": 1, "ahora": 3}]


def test_aplicar_configuracion_cambia_solo_lo_pedido(rp):
    cfg = {"recuperacion": {"estrategia_chunking": "CH-F256", "con_header": False}, "v2": {}}
    args = rp.construir_parser().parse_args(["b.json", "--salida", "s", "--con-cabecera", "--reranker-max-tokens", "512"])
    resumen = rp.aplicar_configuracion(cfg, args)
    assert cfg["recuperacion"] == {"estrategia_chunking": "CH-F256", "con_header": True}
    assert cfg["v2"] == {"max_tokens_reranker": 512, "resultados_n": 5}
    assert resumen["con_cabecera"] is True and resumen["estrategia"] == "CH-F256"


def test_markdown_incluye_etapas_y_comparacion(rp):
    obs = [dict(id="a", rango_hibrido=2, rango_final=2, latencia_ms=10.0, etapas_ms={})]
    informe = {"banco": "b", "particion": "dev", "configuracion": {}, "perfiles": {
        "light": {"resumen": rp.resumir(obs), "observaciones": obs}}}
    texto = rp.a_markdown(informe, {"light": {"ganados": [], "perdidos": [{"id": "a", "antes": 1, "ahora": 2}]}})
    assert "| híbrido |" in texto and "| final |" in texto and "perdido `a`" in texto


class MotorConFuentes(MotorFalso):
    """Como ``MotorFalso`` pero con el contrato HTTP que publica el motor real (puntaje, tipo, alcance, texto)."""

    def consultar(self, pregunta, sesion):
        ev = lambda cid, ini, fin, sec: SimpleNamespace(chunk_id=cid, doc_id="d", offset_inicio=ini, offset_fin=fin,
                                                         seccion_path=sec, score=1.0)
        evidencias = [ev("b", 0, 300, ["Reglamento", "Plazos"]), ev("c", 0, 300, ["Reglamento", "Plazos"]),
                      ev("a", 0, 300, ["Anexo"])]
        fragmentos = [
            {"chunk_id": "b", "score": 3.5, "tipo_puntaje": "logit_reranker", "alcance": "Práctica I",
             "rasgos": ["planta"], "texto": "TEXTO SECRETO B"},
            {"chunk_id": "c", "score": 1.25, "tipo_puntaje": "logit_reranker", "alcance": "Práctica II",
             "rasgos": None, "texto": "TEXTO SECRETO C"},
            {"chunk_id": "a", "score": -2.0, "tipo_puntaje": "logit_reranker", "alcance": None, "rasgos": None,
             "texto": "TEXTO SECRETO A"}]
        return SimpleNamespace(evidencias=evidencias, diagnostico={"etapas": {}, "contrato_http": {"fragmentos": fragmentos}})


def test_grabador_publicados_registra_orden_puntaje_y_si_es_correcto(rp, tmp_path, monkeypatch):
    grabador = rp.GrabadorPublicados(tmp_path / "p.jsonl", "medium")
    monkeypatch.setattr(rp, "PUBLICADOS", grabador)
    rp.observar_caso(MotorConFuentes(), _caso(210, 220, cid="caso-7"))
    fila, = grabador.filas
    assert (fila["id"], fila["split"], fila["perfil"], fila["rango_final"]) == ("caso-7", "dev", "medium", 2)
    assert [p["chunk_id"] for p in fila["publicadas"]] == ["b", "c", "a"]
    assert [p["rango"] for p in fila["publicadas"]] == [1, 2, 3]
    # c es la única que toca la evidencia: se usan los offsets del fragmento recuperado, no los de la ventana ampliada
    assert [p["correcto"] for p in fila["publicadas"]] == [False, True, False]
    b = fila["publicadas"][0]
    assert b["score"] == 3.5 and b["tipo_puntaje"] == "logit_reranker" and b["alcance"] == "Práctica I"
    assert b["rasgos"] == ["planta"] and b["seccion_path"] == ["Reglamento", "Plazos"] and b["doc_id"] == "d"


def test_grabador_publicados_no_escribe_ni_el_texto_ni_la_pregunta(rp, tmp_path, monkeypatch):
    grabador = rp.GrabadorPublicados(tmp_path / "salida" / "p.jsonl", "light")
    monkeypatch.setattr(rp, "PUBLICADOS", grabador)
    rp.observar_caso(MotorConFuentes(), _caso(0, 10))
    grabador.guardar()
    contenido = (tmp_path / "salida" / "p.jsonl").read_text(encoding="utf-8")
    assert "TEXTO SECRETO" not in contenido and "¿algo?" not in contenido
    filas = [json.loads(linea) for linea in contenido.splitlines()]
    assert len(filas) == 1 and "pregunta" not in filas[0] and "texto" not in filas[0]["publicadas"][0]


def test_grabador_publicados_tolera_un_resultado_sin_contrato(rp, tmp_path, monkeypatch):
    grabador = rp.GrabadorPublicados(tmp_path / "p.jsonl", "light")
    monkeypatch.setattr(rp, "PUBLICADOS", grabador)
    rp.observar_caso(MotorFalso(), _caso(210, 220))
    publicada = grabador.filas[0]["publicadas"][0]
    assert publicada["score"] is None and publicada["tipo_puntaje"] is None and publicada["seccion_path"] == []


def test_sin_grabador_observar_caso_no_registra_nada(rp):
    assert rp.PUBLICADOS is None
    assert rp.observar_caso(MotorConFuentes(), _caso(210, 220))["rango_final"] == 2


def test_cada_perfil_escribe_su_propio_archivo_de_publicados(rp, tmp_path):
    assert rp.ruta_publicados(tmp_path / "publicados.jsonl", "medium").name == "publicados-medium.jsonl"
    assert rp.ruta_publicados(tmp_path / "x" / "p.json", "light") == tmp_path / "x" / "p-light.json"
    args = rp.construir_parser().parse_args(["b.json", "--salida", "s", "--volcar-publicados", "p.jsonl"])
    assert args.volcar_publicados == "p.jsonl"

