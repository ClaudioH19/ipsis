"""``ipsis ask --diagnostics`` con un motor falso: sin servicio, modelos ni índice."""
from __future__ import annotations

import pytest

from ipsis.cli import main
from ipsis.nucleo.esquemas import AssistantResult, AssistantState

DIAGNOSTICO = {
    "regla": "recuperado",
    "etapas": {"preparacion_ms": 1, "recuperacion_ms": 12, "reranking_ms": 40, "lectura_ms": 2},
    "ortografia": {"sedimentso": "sedimentos"},
    "candidatos": [
        {"chunk_id": "manual__c0000", "inicio": "El filtro se cambia cada 6 meses.",
         "signals": {"dense_rank": 2, "sparse_rank": 1, "fusion_rank": 1}},
        {"chunk_id": "manual__c0001", "inicio": "La garantía dura dos años.",
         "signals": {"fusion_rank": 2}},
    ],
    "rerank": [{"chunk_id": "manual__c0001", "score": 1.5}, {"chunk_id": "manual__c0000", "score": 3.25}],
    "lecturas": [{"chunk_id": "manual__c0000", "prob_respuesta": 0.93, "texto": "6 meses"}],
    "evidencias": [{"doc_id": "manual", "chunk_id": "manual__c0000", "texto": "El filtro se cambia cada 6 meses.",
                    "offset_inicio": 14, "offset_fin": 47}],
    "advertencias": ["contexto truncado"],
    "contrato_http": {"estado": "related", "respuesta": "2 resultados relacionados para revisar."},
}


class MotorFalso:
    def __init__(self, diagnostico=DIAGNOSTICO):
        self.diagnostico, self.llamadas = diagnostico, []

    def calentar(self):
        self.llamadas.append("calentar")

    def consultar(self, pregunta, id_sesion):
        self.llamadas.append(("consultar", pregunta))
        return AssistantResult(estado=AssistantState.RELACIONADO, motivo="recuperado",
                               mensaje_usuario=self.diagnostico["contrato_http"]["respuesta"],
                               diagnostico=self.diagnostico)

    def cerrar(self):
        self.llamadas.append("cerrar")


def test_el_caso_de_uso_lee_el_diagnostico_del_motor():
    from ipsis.aplicacion.consulta import diagnosticar_pregunta

    motor = MotorFalso()
    d = diagnosticar_pregunta("¿Cada cuánto se cambia el filtro?", motor=motor)
    assert (d.estado, d.regla, d.motivo) == ("related", "recuperado", "recuperado")
    assert d.etapas == [("preparation", 1), ("retrieval", 12), ("reranking", 40), ("reading", 2)]
    assert d.total_ms == 55
    assert d.ortografia == {"sedimentso": "sedimentos"} and d.advertencias == ["contexto truncado"]
    assert [e["chunk_id"] for e in d.evidencias] == ["manual__c0000"]
    assert motor.llamadas == [("consultar", "¿Cada cuánto se cambia el filtro?")]  # un motor ajeno no se cierra


def test_los_candidatos_traen_su_lugar_en_cada_ranking():
    from ipsis.aplicacion.consulta import diagnosticar_pregunta

    d = diagnosticar_pregunta("x", motor=MotorFalso())
    primero, segundo = d.candidatos
    assert (primero["denso"], primero["bm25"], primero["fusion"]) == (2, 1, 1)
    assert (primero["rerank"], primero["rerank_score"], primero["qa"]) == (2, 3.25, 0.93)
    assert (segundo["rerank"], segundo["rerank_score"], segundo["qa"]) == (1, 1.5, None)


def test_cli_muestra_etapas_regla_candidatos_y_evidencia(monkeypatch, capsys):
    motor = MotorFalso()
    monkeypatch.setattr("ipsis.aplicacion.consulta.construir_motor_del_proyecto", lambda: motor)
    monkeypatch.setattr("httpx.post", lambda *a, **k: pytest.fail("--diagnostics no usa el servicio"))
    assert main(["ask", "--diagnostics", "¿Cada cuánto se cambia el filtro?"]) == 0
    salida = capsys.readouterr().out
    assert "[RELACIONADO" in salida and "Regla: recuperado (motivo: recuperado)" in salida
    for linea in ("  retrieval            12", "  reranking            40", "  total                55"):
        assert linea in salida
    assert "Erratas corregidas con el corpus: sedimentso → sedimentos" in salida
    assert "Evidencia: manual offsets 14-47" in salida
    assert "manual__c0000: denso 2, bm25 1, fusión 1, reranker 2 (+3.25), QA 0.93" in salida
    assert "Advertencia: contexto truncado" in salida
    assert motor.llamadas[0] == "calentar" and motor.llamadas[-1] == "cerrar"  # latencias sin carga de modelos


def test_cli_sin_candidatos_ni_evidencia_no_imprime_esas_secciones(monkeypatch, capsys):
    diagnostico = {"etapas": {"recuperacion_ms": 1}, "contrato_http": {"estado": "no_answer", "respuesta": "No hay."}}
    monkeypatch.setattr("ipsis.aplicacion.consulta.construir_motor_del_proyecto", lambda: MotorFalso(diagnostico))
    assert main(["ask", "--diagnostics", "x"]) == 0
    salida = capsys.readouterr().out
    assert "Candidatos" not in salida and "Evidencia:" not in salida and "Regla: - " in salida


def test_cli_motor_que_no_se_puede_construir_pide_rag_doctor(monkeypatch, capsys):
    def roto():
        raise FileNotFoundError("el modelo intfloat/multilingual-e5-small no está en la caché")

    monkeypatch.setattr("ipsis.aplicacion.consulta.construir_motor_del_proyecto", roto)
    assert main(["ask", "--diagnostics", "x"]) == 1
    salida = capsys.readouterr().out
    assert "no está en la caché" in salida and "Acción: ipsis doctor" in salida and "Traceback" not in salida
