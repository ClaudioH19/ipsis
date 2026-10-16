"""La forma de la página en el motor v2 y en la API pública (P1.2): se describe, no se cambia lo publicado."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier
from ipsis.consulta.v2 import MotorV2
from ipsis.nucleo.esquemas import ChunkRecord, RetrievalCandidate, RetrievalSignals
from ipsis.servicio.api import RespuestaConsulta, respuesta_publica

PREGUNTA = "¿Cuántas horas dura la práctica?"


def _candidato(cid, doc_id, ruta, alcance=None, rango=1):
    texto = f"Texto del fragmento {cid} sobre la práctica."
    metadata = {"alcance": alcance} if alcance else {}
    return RetrievalCandidate(chunk=ChunkRecord(chunk_id=cid, doc_id=doc_id, doc_titulo=doc_id.title(), version="1",
        texto_fuente=texto, texto_embedding=texto, offset_inicio=100 * rango, offset_fin=100 * rango + len(texto),
        seccion_path=ruta, tipo_contenido="parrafo", metadata=metadata),
        signals=RetrievalSignals(fusion_rank=rango, fusion_score=.04))


class Recuperador:
    def __init__(self, candidatos):
        self.candidatos = candidatos

    def recuperar(self, consulta, limite, filtro=None):
        return [c.model_copy(deep=True) for c in self.candidatos[:limite]]

    def calentar(self):
        pass

    def n_chunks(self):
        return len(self.candidatos)

    def inventario_entidades(self):
        return set()

    def estadisticas_lexico(self):
        return SimpleNamespace()


def _motor(candidatos, presentacion=None, **kwargs):
    opciones = {"presentacion": presentacion} if presentacion is not None else {}
    return MotorV2(retriever=Recuperador(candidatos), verificador=LiteralOffsetsVerifier(), opciones=opciones,
                   plantillas={"abstencion": {"generico": ["No hay evidencia."], "zona_gris_intro": ["Pasajes:"]}}, **kwargs)


HERMANAS = [_candidato("c1", "reglamento", ["Prácticas", "Duración"], rango=1),
            _candidato("c2", "reglamento", ["Prácticas", "Horario"], rango=2)]
DOS_DOCUMENTOS = [_candidato("c1", "reglamento", ["Prácticas"], rango=1),
                  _candidato("c2", "rubrica", ["Evaluación"], rango=2)]
OTRA_SECCION = [_candidato("c1", "reglamento", ["Prácticas"], rango=1),
                _candidato("c2", "reglamento", ["Titulación"], rango=2)]
ALCANCES = [_candidato("c1", "reglamento", ["Tabla"], alcance="Ingeniería", rango=1),
            _candidato("c2", "reglamento", ["Tabla"], alcance="Diseño", rango=2)]


def _forma(candidatos, **kwargs):
    resultado = _motor(candidatos, presentacion={"activo": True}, **kwargs).consultar(PREGUNTA, "s")
    return resultado.contrato_http.get("forma_resultados")


@pytest.mark.parametrize("candidatos, esperada", [
    (HERMANAS, "variantes"), (ALCANCES, "variantes"), (DOS_DOCUMENTOS, "documentos"), (OTRA_SECCION, "neutral")])
def test_la_forma_sale_de_lo_publicado(candidatos, esperada):
    assert _forma(candidatos) == esperada


def test_una_sola_fuente_es_neutral():
    assert _forma(HERMANAS[:1]) == "neutral"


def test_apagada_no_deja_ninguna_clave():
    resultado = _motor(HERMANAS).consultar(PREGUNTA, "s")
    assert "forma_resultados" not in resultado.contrato_http and "forma_resultados" not in resultado.diagnostico
    assert "result_shape" not in respuesta_publica(resultado.contrato_http)


@pytest.mark.parametrize("candidatos", [HERMANAS, DOS_DOCUMENTOS, OTRA_SECCION, ALCANCES])
def test_encenderla_no_cambia_ni_el_contenido_ni_el_orden(candidatos):
    def publicado(resultado):
        return ([e.model_dump(mode="json") for e in resultado.evidencias],
                [{k: v for k, v in f.items()} for f in resultado.contrato_http["fragmentos"]],
                resultado.contrato_http.get("bloques"))

    apagado = _motor(candidatos).consultar(PREGUNTA, "s")
    encendido = _motor(candidatos, presentacion={"activo": True}).consultar(PREGUNTA, "s")
    assert publicado(encendido) == publicado(apagado)


def test_el_diagnostico_guarda_la_forma_el_margen_y_la_relacion():
    resultado = _motor(DOS_DOCUMENTOS, presentacion={"activo": True}).consultar(PREGUNTA, "s")
    diag = resultado.diagnostico["forma_resultados"]
    assert diag["forma"] == "documentos" and diag["relacion"] == "documentos"
    assert diag["margen"] is None or isinstance(diag["margen"], float)


def test_sin_resultados_no_hay_forma():
    resultado = _motor([], presentacion={"activo": True}).consultar(PREGUNTA, "s")
    assert not resultado.evidencias and "forma_resultados" not in resultado.contrato_http


def test_clara_solo_con_un_margen_explicito():
    # sin margen configurado jamás sale «clara»; con uno inalcanzable tampoco
    assert _forma(DOS_DOCUMENTOS) == "documentos"
    inalcanzable = _motor(DOS_DOCUMENTOS, presentacion={"activo": True, "margen_claro": 1e9}).consultar(PREGUNTA, "s")
    assert inalcanzable.contrato_http["forma_resultados"] == "documentos"
    # los dobles dan a las dos fuentes el mismo puntaje (margen 0): con margen 0 se alcanza
    alcanzable = _motor(DOS_DOCUMENTOS, presentacion={"activo": True, "margen_claro": 0.0}).consultar(PREGUNTA, "s")
    assert alcanzable.contrato_http["forma_resultados"] == "clara"
    assert alcanzable.diagnostico["forma_resultados"]["margen"] == 0.0


def test_el_margen_por_perfil_gana_al_general():
    perfil = SimpleNamespace(perfil="medium")
    presentacion = {"activo": True, "margen_claro": 1e9, "margen_claro_por_perfil": {"medium": 0.0}}
    resultado = _motor(DOS_DOCUMENTOS, presentacion=presentacion, perfil=perfil).consultar(PREGUNTA, "s")
    assert resultado.contrato_http["forma_resultados"] == "clara"
    otro = _motor(DOS_DOCUMENTOS, presentacion=presentacion, perfil=SimpleNamespace(perfil="light")).consultar(PREGUNTA, "s")
    assert otro.contrato_http["forma_resultados"] == "documentos"


def test_pedir_mas_resultados_no_trae_forma():
    candidatos = [_candidato(f"c{i}", "reglamento" if i % 2 else "rubrica", ["S", str(i)], rango=i + 1) for i in range(6)]
    motor = _motor(candidatos, presentacion={"activo": True})
    primera = motor.consultar(PREGUNTA, "s")
    cursor = primera.contrato_http["continuation"]
    assert "forma_resultados" in primera.contrato_http and cursor
    segunda = motor.continuar(PREGUNTA, "s", cursor)
    assert "forma_resultados" not in segunda.contrato_http
    assert "result_shape" not in respuesta_publica(segunda.contrato_http)


@pytest.mark.parametrize("candidatos, publica", [
    (HERMANAS, "variants"), (DOS_DOCUMENTOS, "documents"), (OTRA_SECCION, "neutral")])
def test_la_api_publica_result_shape(candidatos, publica):
    contrato = _motor(candidatos, presentacion={"activo": True}).consultar(PREGUNTA, "s").contrato_http
    salida = respuesta_publica(contrato)
    assert salida["result_shape"] == publica
    assert RespuestaConsulta.model_validate(salida).result_shape == publica


def test_la_api_traduce_las_cuatro_formas():
    base = _motor(HERMANAS).consultar(PREGUNTA, "s").contrato_http
    for interna, publica in {"clara": "clear", "variantes": "variants", "documentos": "documents",
                             "neutral": "neutral"}.items():
        assert respuesta_publica({**base, "forma_resultados": interna})["result_shape"] == publica
