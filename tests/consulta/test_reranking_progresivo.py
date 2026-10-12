"""Presupuestos con reloj controlado y navegación sin pérdida de candidatos."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from ipsis.consulta.v2.reranking import preparar_vistas, puntuar_progresivo
from ipsis.servicio.api import crear_app
from tests.consulta.test_motor_v2 import candidato, motor
from tests.consulta.test_paginacion_v2 import fuentes


def test_presupuesto_detiene_lotes_y_no_compara_logits_con_scores_hibridos():
    reloj = [0.0]
    llamadas = []

    class Reranker:
        def puntuar(self, pregunta, textos):
            llamadas.append(textos)
            reloj[0] += .4
            return [-2, -1]

    cs = fuentes(6)
    ordenados, diag = puntuar_progresivo(cs, "stock", Reranker(),
        {"rerank_candidatos": 6, "lote_reranker": 2}, limite=.9, reloj=lambda: reloj[0])
    assert len(llamadas) == 1
    assert [c.chunk.chunk_id for c in ordenados] == ["1", "0", "2", "3", "4", "5"]
    assert diag["presupuesto_agotado"] and diag["pendientes"] == 4
    assert all(c.signals.reranker_score is None for c in cs)  # Entrada inmutable.


def test_limite_de_candidatos_solo_limita_trabajo_y_conserva_la_cola():
    class Reranker:
        def puntuar(self, pregunta, textos):
            return [1] * len(textos)

    cs, diag = puntuar_progresivo(fuentes(8), "stock", Reranker(),
        {"rerank_candidatos": 2, "lote_reranker": 2}, limite=100, reloj=lambda: 0)
    assert len(cs) == 8 and diag["puntuados_esta_pagina"] == 2
    assert diag["pendientes"] == 6


def test_presupuesto_ya_agotado_no_inicia_inferencia():
    class Prohibido:
        def puntuar(self, *args):
            raise AssertionError("No hay tiempo para un lote")

    cs, diag = puntuar_progresivo(fuentes(8), "stock", Prohibido(),
        {"rerank_candidatos": 8, "lote_reranker": 2}, limite=0, reloj=lambda: 1)
    assert len(cs) == 8 and diag["puntuados_esta_pagina"] == 0


@pytest.mark.parametrize("scores", [[1], [float("nan"), 1], [float("inf"), 1]])
def test_lotes_invalidos_no_se_publican(scores):
    class Reranker:
        def puntuar(self, *args):
            return scores

    with pytest.raises(ValueError):
        puntuar_progresivo(fuentes(3), "stock", Reranker(),
            {"rerank_candidatos": 3, "lote_reranker": 2}, limite=10, reloj=lambda: 0)


def test_vista_usa_mejor_hijo_sin_recortar_la_fuente_para_el_usuario():
    padre = candidato("Inicio\nFicha A: precio 20.\nFicha B: precio 40.\nFinal", "padre")
    a = candidato("Ficha A: precio 20.", "a")
    b = candidato("Ficha B: precio 40.", "b")
    b.chunk.metadata["structure_hash"] = "s"
    b.chunk.texto_embedding = "Productos\nNombre: B\nPrecio: 40"
    padre.chunk.metadata["hijos_recuperados"] = ["b", "a"]
    preparado = preparar_vistas([b, a], [padre])[0]
    assert preparado.chunk.metadata["vista_reranking"]["texto"] == b.chunk.texto_embedding
    assert preparado.chunk.texto_fuente == padre.chunk.texto_fuente
    assert "vista_reranking" not in padre.chunk.metadata


def test_vista_rechaza_hijo_de_otra_version():
    padre = candidato("Fuente", "padre")
    hijo = candidato("Fuente", "hijo")
    padre.chunk.metadata["hijos_recuperados"] = ["hijo"]
    hijo.chunk.version = "otra"
    with pytest.raises(ValueError, match="versión"):
        preparar_vistas([hijo], [padre])


def test_presupuesto_de_trabajo_pequeno_no_depende_del_legacy_rerank_k():
    m = motor(candidatos=fuentes(8), opciones={"rerank_candidatos": 2})
    r = m.consultar("stock", "s")
    assert len(r.evidencias) == 3 and r.contrato_http["has_more"]


def test_continuacion_puntua_solo_pendientes_y_reintento_conserva_la_pagina(monkeypatch):
    reloj = [0.0]
    monkeypatch.setattr("ipsis.consulta.v2.motor.time.perf_counter", lambda: reloj[0])

    class Reranker:
        entradas = []

        def puntuar(self, pregunta, textos):
            self.entradas.extend(textos)
            reloj[0] += .4
            return [100 - int(p.split()[1].rstrip(":")) for p in textos]

    r = Reranker()
    m = motor(candidatos=fuentes(12), reranker=r, opciones={"presupuesto_consulta_ms": 800})
    primera = m.consultar("stock", "s")
    assert primera.diagnostico["reranking_progresivo"]["puntuados_esta_pagina"] == 2
    assert [f["tipo_puntaje"] for f in primera.contrato_http["fragmentos"]] == [
        "logit_reranker", "logit_reranker", "recuperacion"]
    cursor = primera.contrato_http["continuation"]
    segunda = m.continuar("stock", "s", cursor)
    assert segunda.diagnostico["reranking_progresivo"]["puntuados_esta_pagina"] == 2
    entradas = list(r.entradas)
    repetida = m.continuar("stock", "s", cursor)
    assert r.entradas == entradas
    assert repetida.contrato_http["fragmentos"] == segunda.contrato_http["fragmentos"]
    assert repetida.diagnostico["paginacion"]["pagina_reutilizada"]
    assert repetida.diagnostico["reranking_progresivo"]["puntuados_esta_pagina"] == 0
    assert repetida.diagnostico["reranking_progresivo"]["lotes"] == []
    ids = [e.chunk_id for e in primera.evidencias + segunda.evidencias]
    siguiente = segunda.contrato_http["continuation"]
    while siguiente:
        p = m.continuar("stock", "s", siguiente)
        ids.extend(e.chunk_id for e in p.evidencias)
        siguiente = p.contrato_http["continuation"]
    assert ids == [str(i) for i in range(12)]
    assert len(set(r.entradas)) == len(r.entradas)
    assert len(m.retriever.consultas) == 1
    assert m.continuar("stock", "s", cursor).contrato_http["fragmentos"] == segunda.contrato_http["fragmentos"]


def test_dos_peticiones_del_mismo_cursor_comparten_la_inferencia():
    empezo, liberar = Event(), Event()

    class Reranker:
        llamadas = 0

        def puntuar(self, pregunta, textos):
            self.llamadas += 1
            if self.llamadas == 3:
                empezo.set()
                assert liberar.wait(5)
            return [100 - int(p.split()[1].rstrip(":")) for p in textos]

    r = Reranker()
    m = motor(candidatos=fuentes(12), reranker=r,
              opciones={"rerank_candidatos": 4, "rerank_k": 4, "leer_m": 4})
    cursor = m.consultar("stock", "s").contrato_http["continuation"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        uno = executor.submit(m.continuar, "stock", "s", cursor)
        assert empezo.wait(5)
        dos = executor.submit(m.continuar, "stock", "s", cursor)
        liberar.set()
        a, b = uno.result(timeout=10), dos.result(timeout=10)
    assert a.contrato_http["fragmentos"] == b.contrato_http["fragmentos"]
    assert r.llamadas == 4


def test_api_aplica_deadline_sin_descartar_fuentes_y_lo_valida():
    class Reranker:
        llamadas = 0

        def puntuar(self, pregunta, textos):
            self.llamadas += 1
            return [1] * len(textos)

        def calentar(self):
            pass

    r = Reranker()
    m = motor(candidatos=fuentes(8), reranker=r)
    with TestClient(crear_app(m)) as client:
        req = {"question": "stock", "session_id": "s", "deadline_ms": 1}
        primera = client.post("/ask", json=req)
        assert primera.status_code == 200 and primera.json()["has_more"]
        assert {f["score_kind"] for f in primera.json()["fragments"]} == {"retrieval_score"}
        assert r.llamadas == 0
        req.update(continuation=primera.json()["continuation"], deadline_ms=2500)
        segunda = client.post("/ask", json=req)
        assert segunda.status_code == 200 and r.llamadas > 0
        assert {f["score_kind"] for f in segunda.json()["fragments"]} == {"reranker_logit"}
        assert len(m.retriever.consultas) == 1
        assert client.post("/ask", json={**req, "deadline_ms": 0}).status_code == 422
    assert m._limite(0, 30000) == m._limite(0)  # El cliente no amplía el máximo del servidor.
