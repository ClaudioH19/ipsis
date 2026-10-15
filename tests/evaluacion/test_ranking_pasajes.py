"""Script de ranking por etapa: núcleo probado con un motor falso, sin modelos."""
from __future__ import annotations

import importlib.util
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
