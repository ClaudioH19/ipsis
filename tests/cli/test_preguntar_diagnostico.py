"""``ipsis ask --diagnostics`` con un motor falso: sin servicio, modelos ni índice."""
from __future__ import annotations

import pytest

from ipsis.cli import main
from ipsis.nucleo.esquemas import AssistantResult, AssistantState

DIAGNOSTICO = {
    "perfil": "medium",
    "regla": "ok_lector",
    "etapas": {"filtros_ms": 3, "recuperacion_ms": 12, "lectura_ms": 40, "politica_ms": 0},
    "senales_politica": {"s_ret": 0.81, "s_oov": 0.0, "s_foco": 0.5, "s_cov": 0.75, "s_rr": 2.3, "s_qa": 0.93},
    "senales_lexicas": {"terminos_foco": ["filtro", "sedimentos"], "foco_encontrados": ["filtro"],
                        "foco_ausentes": ["sedimentos"], "ausentes_del_corpus": ["xilofon"]},
    "oracion_foco": "El filtro se cambia cada 6 meses.",
    "evidencias": [{"doc_id": "manual", "chunk_id": "manual__c0000", "texto": "El filtro se cambia cada 6 meses.",
                    "offset_inicio": 14, "offset_fin": 47}],
    "advertencias": [],
    "tono": "cordial",
    "plantillas": ["cordial.opening.2"],
    "contrato_http": {"estado": "ok", "respuesta": "El filtro se cambia cada 6 meses.",
                      "respuesta_exacta": {"chunk_id": "manual__c0000", "texto": "6 meses",
                                           "offset_inicio": 39, "offset_fin": 46}},
}


class MotorFalso:
    def __init__(self, diagnostico=DIAGNOSTICO):
        self.diagnostico, self.llamadas = diagnostico, []

    def calentar(self):
        self.llamadas.append("calentar")

    def consultar(self, pregunta, id_sesion):
        self.llamadas.append(("consultar", pregunta))
        return AssistantResult(estado=AssistantState.RESPUESTA_DIRECTA, motivo="lector",
                               mensaje_usuario=self.diagnostico["contrato_http"]["respuesta"],
                               diagnostico=self.diagnostico)

    def cerrar(self):
        self.llamadas.append("cerrar")


def test_el_caso_de_uso_lee_el_diagnostico_del_motor():
    from ipsis.aplicacion.consulta import diagnosticar_pregunta

    motor = MotorFalso()
    d = diagnosticar_pregunta("¿Cada cuánto se cambia el filtro?", motor=motor)
    assert (d.estado, d.regla, d.motivo, d.perfil) == ("ok", "ok_lector", "lector", "medium")
    assert d.etapas == [("filters", 3), ("retrieval", 12), ("reading", 40), ("policy", 0)]
    assert d.total_ms == 55
    assert d.senales["s_qa"] == 0.93
    assert (d.foco_encontrados, d.foco_ausentes) == (["filtro"], ["sedimentos"])
    assert d.tramo["texto"] == "6 meses" and d.tramo["offset_inicio"] == 39
    assert motor.llamadas == [("consultar", "¿Cada cuánto se cambia el filtro?")]  # un motor ajeno no se cierra


def test_cli_muestra_etapas_senales_foco_regla_y_tramo(monkeypatch, capsys):
    motor = MotorFalso()
    monkeypatch.setattr("ipsis.aplicacion.consulta.construir_motor_del_proyecto", lambda: motor)
    monkeypatch.setattr("httpx.post", lambda *a, **k: pytest.fail("--diagnostics no usa el servicio"))
    assert main(["ask", "--diagnostics", "¿Cada cuánto se cambia el filtro?"]) == 0
    salida = capsys.readouterr().out
    assert "[OK]" in salida and "Regla: ok_lector (motivo: lector; perfil: medium)" in salida
    for linea in ("  filters               3", "  reading              40", "  total                55"):
        assert linea in salida
    assert "s_qa=0.930" in salida and "s_foco=0.500" in salida
    assert "Términos foco: encontrados: filtro; ausentes: sedimentos" in salida
    assert "Términos que no están en el corpus: xilofon" in salida
    assert "Tramo exacto: «6 meses» (manual__c0000, offsets 39-46)" in salida
    assert "Evidencia: manual offsets 14-47" in salida
    assert "Tono: cordial; plantillas: cordial.opening.2" in salida
    assert motor.llamadas[0] == "calentar" and motor.llamadas[-1] == "cerrar"  # latencias sin carga de modelos


def test_cli_sin_tramo_ni_foco_muestra_guiones(monkeypatch, capsys):
    diagnostico = {**DIAGNOSTICO, "senales_lexicas": None,
                   "contrato_http": {"estado": "relacionado", "respuesta": "No encontré…"}}
    monkeypatch.setattr("ipsis.aplicacion.consulta.construir_motor_del_proyecto", lambda: MotorFalso(diagnostico))
    assert main(["ask", "--diagnostics", "x"]) == 0
    salida = capsys.readouterr().out
    assert "Tramo exacto: -" in salida and "encontrados: -; ausentes: -" in salida


def test_cli_motor_que_no_se_puede_construir_pide_rag_doctor(monkeypatch, capsys):
    def roto():
        raise FileNotFoundError("el modelo intfloat/multilingual-e5-small no está en la caché")

    monkeypatch.setattr("ipsis.aplicacion.consulta.construir_motor_del_proyecto", roto)
    assert main(["ask", "--diagnostics", "x"]) == 1
    salida = capsys.readouterr().out
    assert "no está en la caché" in salida and "Acción: ipsis doctor" in salida and "Traceback" not in salida
