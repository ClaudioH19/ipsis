"""Auditoría de ejecuciones originales, sin modelos ni búsquedas adicionales."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from ipsis.nucleo.esquemas import ChunkRecord, QueryAnalysis, RetrievalCandidate
from ipsis.nucleo.traza import capturar_traza, recuperar_con_traza, traza_actual


def test_recuperacion_guarda_texto_filtro_y_copia_del_ranking_original():
    candidato = RetrievalCandidate(chunk=ChunkRecord(
        chunk_id="manual__1", doc_id="manual", texto_fuente="Original", texto_embedding="Original",
        offset_inicio=0, offset_fin=8))
    llamadas = []

    class Retriever:
        modo = "hibrida"

        def recuperar(self, consulta, limite, filtro=None):
            llamadas.append((consulta, limite, filtro))
            return [candidato]

    from ipsis.nucleo.esquemas import FiltroEntidad

    consulta = QueryAnalysis(pregunta_original="pregunta", pregunta_normalizada="pregunta",
                             contexto={"id_sesion": "secreto", "pregunta_recuperacion": "pregunta ampliada"})
    with capturar_traza() as traza:
        recuperar_con_traza(Retriever(), consulta, 1, filtro=FiltroEntidad(valor_norm="articulo_1"), origen="premisa")
    candidato.chunk.texto_fuente = "Modificado"
    assert len(llamadas) == 1
    evento = traza.eventos[0]
    assert evento["candidatos"][0]["chunk"]["texto_fuente"] == "Original"
    assert evento["filtro"]["valor_norm"] == "articulo_1"
    assert evento["pregunta_recuperacion"] == "pregunta ampliada"
    assert "secreto" not in str(traza.eventos)


def test_v2_traza_cada_etapa_y_la_salida_no_cambia_despues():
    from apoyo_v2 import RecuperadorMemoria
    from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier
    from ipsis.consulta.v2 import MotorV2

    motor = MotorV2(retriever=RecuperadorMemoria(), verificador=LiteralOffsetsVerifier())
    with capturar_traza() as traza:
        resultado = motor.consultar("filtro del purificador", "sesion-secreta")
    etapas = [e for e in traza.eventos if e["tipo"] == "etapa"]
    assert [e["nombre"] for e in etapas][:4] == ["cortesia", "preparacion", "recuperacion", "contexto"]
    assert {e["estado"] for e in etapas} == {"completada"}
    assert any(e["tipo"] == "recuperacion" and e["origen"] == "principal" for e in traza.eventos)
    resultado.diagnostico["regla"] = "modificada"
    assert etapas[-1]["salida"]["diagnostico"].get("regla") != "modificada"
    assert "sesion-secreta" not in str(traza.eventos)
    assert traza_actual() is None


def test_v2_una_etapa_fallida_conserva_la_traza_y_propaga_el_error():
    from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier
    from ipsis.consulta.v2 import MotorV2

    class Roto:
        def recuperar(self, consulta, limite, filtro=None):
            raise RuntimeError("error interno")

        def estadisticas_lexico(self):
            return None

    motor = MotorV2(retriever=Roto(), verificador=LiteralOffsetsVerifier())
    with capturar_traza() as traza, pytest.raises(RuntimeError):
        motor.consultar("dato", "secreto")
    fallida = [e for e in traza.eventos if e["tipo"] == "etapa" and e["estado"] == "error"]
    assert fallida and fallida[0]["error"] == "RuntimeError" and "salida" in fallida[0]
    assert traza_actual() is None


def test_peticiones_concurrentes_y_contextos_anidados_estan_aislados():
    barrera = Barrier(4)

    def consultar(numero):
        with capturar_traza() as traza:
            barrera.wait(timeout=5)
            traza_actual().agregar("dato", numero=numero)
            with capturar_traza(activo=False):
                assert traza_actual() is None
            assert traza_actual() is traza
        assert traza_actual() is None
        return traza

    with ThreadPoolExecutor(max_workers=4) as pool:
        trazas = list(pool.map(consultar, range(4)))
    assert len({t.consulta_id for t in trazas}) == 4
    assert [t.eventos[0]["numero"] for t in trazas] == list(range(4))


def test_modelo_registra_pasaje_exacto_y_no_repite_inferencia():
    from ipsis.nucleo.traza import ejecutar_modelo_con_traza

    llamadas = []

    def puntuar(pregunta, pasajes):
        llamadas.append((pregunta, pasajes))
        return [0.75]

    pasajes = ["ventana realmente leída"]
    with capturar_traza() as traza:
        assert ejecutar_modelo_con_traza("reranker", "pregunta", pasajes, puntuar) == [0.75]
    pasajes[0] = "otra ventana"
    assert len(llamadas) == 1
    assert traza.eventos[0]["pasajes"] == ["ventana realmente leída"]
    assert traza.eventos[0]["salida"] == [0.75]
