"""Continuación estable, con evidencia nueva y sin repetir inferencias."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ipsis.consulta.v2.paginacion import ContinuacionInvalida, RankingsTemporales
from ipsis.indice.contextos import RecuperadorConContextos
from ipsis.servicio.api import crear_app, respuesta_publica
from tests.consulta.test_motor_v2 import candidato, motor, Recuperador


def fuentes(n):
    return [candidato(f"Producto {i}: stock {i + 10}.", str(i), inicio=100 * i) for i in range(n)]


def test_recorrer_ranking_completo_sin_repetir_recuperacion_modelos_o_paginas():
    class Reranker:
        llamadas = 0

        def puntuar(self, pregunta, pasajes):
            self.llamadas += 1
            return [100 - int(p.split()[1].rstrip(":")) for p in pasajes]

    reranker = Reranker()
    m = motor(candidatos=fuentes(12), reranker=reranker)
    primera = m.consultar("stock", "s")
    pagina = primera
    ids, rangos = [], []
    while True:
        publica = respuesta_publica(pagina.contrato_http)
        assert len(publica["fragments"]) == 3
        ids.extend(f["chunk_id"] for f in publica["fragments"])
        rangos.extend(f["rank"] for f in publica["fragments"])
        if not publica["has_more"]:
            assert publica["continuation"] is None
            break
        pagina = m.continuar("stock", "s", publica["continuation"])
        assert pagina.diagnostico["paginacion"]["ranking_reutilizado"] is True
        assert set(pagina.diagnostico["etapas"]) == {"evidencia_ms", "redaccion_ms"}
    assert ids == [str(i) for i in range(12)]  # Incluye posiciones posteriores al antiguo top-8.
    assert rangos == list(range(1, 13))
    assert reranker.llamadas == 6 and len(m.retriever.consultas) == 1
    cursor = primera.contrato_http["continuation"]
    assert [f["chunk_id"] for f in m.continuar("stock", "s", cursor).contrato_http["fragmentos"]] == ["3", "4", "5"]
    assert reranker.llamadas == 6


def test_deduplicacion_del_contexto_tambien_entre_paginas():
    fuente = "Cabecera\nProducto A: stock 10.\nProducto B: stock 20.\nProducto C: stock 30."
    cs = [candidato(t, str(i), inicio=fuente.index(t)) for i, t in enumerate(fuente.splitlines())]
    r = RecuperadorConContextos(Recuperador(cs), {c.chunk.chunk_id: c.chunk for c in cs},
        {"reglamento": SimpleNamespace(version="1", texto_completo=fuente)})
    m = motor(candidatos=cs, top_k=1)
    m.retriever = r
    p1 = m.consultar("stock", "s")
    p2 = m.continuar("stock", "s", p1.contrato_http["continuation"])
    assert p1.evidencias[0].chunk_id == "0"
    assert p2.evidencias[0].chunk_id == "2"  # La coincidencia 1 ya estaba en la ventana 0.
    assert p2.contrato_http["has_more"] is False
    for p in (p1, p2):
        e = p.evidencias[0]
        assert fuente[e.offset_inicio:e.offset_fin] == e.texto


@pytest.mark.parametrize("pregunta,sesion", [("otro producto", "s"), ("stock", "otra")])
def test_cursor_esta_ligado_a_pregunta_y_sesion(pregunta, sesion):
    m = motor(candidatos=fuentes(7))
    cursor = m.consultar("stock", "s").contrato_http["continuation"]
    with pytest.raises(ContinuacionInvalida):
        m.continuar(pregunta, sesion, cursor)
    assert len(m.retriever.consultas) == 1


def test_ttl_absoluto_y_desalojo_de_rankings():
    reloj = [0]
    m = motor(candidatos=fuentes(7))
    m._rankings = RankingsTemporales(ttl=10, capacidad=1, reloj=lambda: reloj[0])
    c1 = m.consultar("stock", "s").contrato_http["continuation"]
    c2 = m.consultar("precio", "s").contrato_http["continuation"]
    with pytest.raises(ContinuacionInvalida):
        m.continuar("stock", "s", c1)
    reloj[0] = 9
    m.continuar("precio", "s", c2)
    reloj[0] = 10
    with pytest.raises(ContinuacionInvalida):
        m.continuar("precio", "s", c2)
    assert not m._rankings._cursores and not m._rankings._busquedas


def test_no_hay_continuacion_si_solo_existen_tres_fuentes_y_nueva_consulta_es_independiente():
    m = motor(candidatos=fuentes(3))
    r = m.consultar("stock", "s")
    assert r.contrato_http["has_more"] is False
    assert r.contrato_http["continuation"] is None
    m.consultar("precio", "s")
    assert len(m.retriever.consultas) == 2


def test_api_continuacion_y_cursor_invalido():
    m = motor(candidatos=fuentes(7))
    with TestClient(crear_app(m)) as client:
        primera = client.post("/ask", json={"question": "stock", "session_id": "s"})
        assert primera.status_code == 200
        cursor = primera.json()["continuation"]
        p2 = client.post("/ask", json={"question": "stock", "session_id": "s", "continuation": cursor})
        assert p2.status_code == 200
        assert [f["rank"] for f in p2.json()["fragments"]] == [4, 5, 6]
        error = client.post("/ask", json={"question": "stock", "session_id": "otra", "continuation": cursor})
        assert error.status_code == 409
        assert len(m.retriever.consultas) == 1
        cfg = client.get("/config").json()
        assert cfg["interface"]["placeholder"] == cfg["interface"]["search_placeholder"]
        assert cfg["greeting"] == cfg["microcopy"]["welcome"][0]


def test_cerrar_motor_invalida_cursores():
    m = motor(candidatos=fuentes(7))
    cursor = m.consultar("stock", "s").contrato_http["continuation"]
    m.cerrar()
    with pytest.raises(ContinuacionInvalida):
        m.continuar("stock", "s", cursor)


def test_presupuesto_de_contexto_desaloja_busqueda_anterior():
    m = motor(candidatos=fuentes(7))
    c1 = m.consultar("stock", "s").contrato_http["continuation"]
    presupuesto = m._rankings._caracteres
    m._rankings.max_caracteres = presupuesto
    c2 = m.consultar("precio", "s").contrato_http["continuation"]
    assert c2 and m._rankings._caracteres <= presupuesto
    with pytest.raises(ContinuacionInvalida):
        m.continuar("stock", "s", c1)
    assert m.continuar("precio", "s", c2).evidencias


def test_api_v1_rechaza_cursor_sin_ejecutar_busqueda():
    class V1:
        pipeline = "v1"
        control_admision = None

        def calentar(self):
            pass

        def cerrar(self):
            pass

        def consultar(self, *args):
            raise AssertionError("No debe ejecutar una nueva consulta con un cursor no soportado")

    with TestClient(crear_app(V1())) as client:
        r = client.post("/ask", json={"question": "stock", "session_id": "s", "continuation": "cursor"})
        assert r.status_code == 400


def test_qa_optativo_no_vuelve_a_ejecutarse_al_continuar():
    from tests.consulta.test_motor_v2 import Lector

    lector = Lector("stock")
    m = motor(candidatos=fuentes(7), lector=lector)
    r = m.consultar("stock", "s")
    pagina = m.continuar("stock", "s", r.contrato_http["continuation"])
    assert len(lector.entradas) == 1
    assert [e.chunk_id for e in pagina.evidencias] == ["3", "4", "5"]
