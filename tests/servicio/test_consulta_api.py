"""El servicio HTTP delega en el motor y traduce su contrato: ciclo de vida, /ask y bloques de respuesta."""
from __future__ import annotations

from copy import deepcopy

import pytest

from ipsis.aplicacion.consulta import construir_motor
from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto
from ipsis.nucleo.esquemas import AssistantResult, AssistantState


def test_endpoint_consultar_delega_en_motor():
    from ipsis.servicio import api
    from fastapi.testclient import TestClient

    contrato = {
        "estado": "sin_respuesta",
        "nivel_servicio": "normal",
        "respuesta": "No encontré información.",
        "plan": "sin_respuesta",
        "fragmentos": [],
        "confianza": {"top1": 0.2, "margen": 0.01, "acuerdo_bm25": None},
        "latencia_ms": 3,
    }
    llamadas: list[tuple[str, str]] = []

    class _MotorFalso:
        def consultar(self, pregunta: str, id_sesion: str) -> AssistantResult:
            llamadas.append((pregunta, id_sesion))
            return AssistantResult(
                estado=AssistantState.SIN_RESPUESTA,
                motivo="prueba",
                mensaje_usuario=contrato["respuesta"],
                diagnostico={"contrato_http": contrato},
            )

    cliente = TestClient(api.crear_app(_MotorFalso()))
    respuesta = cliente.post(
        "/ask",
        json={"question": "¿dato?", "session_id": "sesión"},
    )

    assert llamadas == [("¿dato?", "sesión")]
    assert respuesta.status_code == 200
    from ipsis.servicio.api import respuesta_publica

    assert respuesta.json() == respuesta_publica(contrato)
    assert respuesta.json()["status"] == "no_answer" and respuesta.json()["plan"] == "no_answer"


def test_crear_app_aisla_estado_y_lifespan_calienta_y_cierra_motor(monkeypatch):
    from fastapi.testclient import TestClient
    from ipsis.servicio.api import crear_app

    # La disponibilidad de los modelos del proyecto no es lo que se prueba aquí (depende de la caché de quien corre).
    monkeypatch.setattr("ipsis.servicio.api._calcular_diagnostico", lambda: None)

    eventos: list[str] = []

    class _Control:
        class config:
            concurrencia_maxima = 2

    class _MotorFalso:
        backend = "memoria"
        retriever = object()
        control_admision = _Control()

        def calentar(self):
            eventos.append("calentar")

        def cerrar(self):
            eventos.append("cerrar")

        def n_chunks(self):
            return 4

        def inventario_entidades(self):
            return {"articulo:9"}

    app_1 = crear_app(_MotorFalso())
    app_2 = crear_app(_MotorFalso())
    assert app_1.state.servicio is not app_2.state.servicio

    with TestClient(app_1) as cliente:
        respuesta = cliente.get("/ready")
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        proyecto = cuerpo.pop("project")
        assert proyecto is None or proyecto["ready"]  # el diagnóstico del proyecto (P12.11)
        assert cuerpo == {
            "status": "ready",
            "ready": True,
            "mode": "production",
            "backend": "memoria",
            "pipeline": "v2",
            "collection": "memoria",
            "n_chunks": 4,
            "n_inventory_entities": 1,
            "calibrated_abstention": False,
            "max_concurrency": 2,
        }

    assert eventos == ["calentar", "cerrar"]


def test_health_sigue_vivo_y_ready_diagnostica_un_arranque_fallido():
    from fastapi.testclient import TestClient
    from ipsis.servicio.api import crear_app

    class _MotorQueFalla:
        def calentar(self):
            raise RuntimeError("índice ausente para la prueba")

        def cerrar(self):
            pass

    aplicacion = crear_app(_MotorQueFalla())

    with TestClient(aplicacion) as cliente:
        health = cliente.get("/health")
        ready = cliente.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "alive", "mode": "production"}
    assert ready.status_code == 503
    assert "RuntimeError: índice ausente para la prueba" in ready.json()["detail"]


def test_motor_desde_configuracion_rechaza_nombre_desconocido_antes_de_construir():
    cfg = deepcopy(cargar_proyecto())
    cfg["componentes"]["evidence_verifier"] = "inexistente"

    with pytest.raises(KeyError, match="evidence_verifier/inexistente"):
        construir_motor(cfg, cfg_dominio=cargar_dominio())


def test_answer_blocks_traduce_los_bloques_y_cubre_contratos_sin_ellos():
    from ipsis.servicio.api import respuesta_publica

    base = {"estado": "ok", "nivel_servicio": "normal", "plan": "extractivo", "fragmentos": [],
            "confianza": {}, "latencia_ms": 1, "respuesta": "Dice:\n\nEl plazo. (Fuente: M)."}
    con = respuesta_publica({**base, "bloques": [
        {"tipo": "encabezado", "texto": "Dice:"},
        {"tipo": "pasaje", "texto": "El plazo.", "conector": None, "cita": "(Fuente: M)", "chunk_id": "c1"}]})
    assert con["answer_blocks"] == [
        {"type": "lead", "text": "Dice:", "connector": None, "citation": None, "chunk_id": None},
        {"type": "passage", "text": "El plazo.", "connector": None, "citation": "(Fuente: M)", "chunk_id": "c1"}]
    # Un contrato anterior (o un estado sin redacción) trae el texto como un solo mensaje.
    assert respuesta_publica(base)["answer_blocks"] == [
        {"type": "message", "text": base["respuesta"], "connector": None, "citation": None, "chunk_id": None}]


def test_la_aclaracion_es_no_answer_con_plan_clarification():
    """Compatible con los clientes que validan ``status``: el plan dice que se pide el tema."""
    from ipsis.servicio.api import RespuestaConsulta, respuesta_publica

    contrato = {"estado": "sin_respuesta", "nivel_servicio": "normal", "plan": "aclaracion", "fragmentos": [],
                "confianza": {"top1": 0.4, "margen": 0.1}, "latencia_ms": 1,
                "respuesta": "¿Sobre qué tema me preguntas?"}
    publica = respuesta_publica(contrato)
    assert publica["status"] == "no_answer" and publica["plan"] == "clarification"
    RespuestaConsulta.model_validate(publica)


def test_el_nivel_de_confianza_llega_a_la_api():
    from ipsis.servicio.api import RespuestaConsulta, respuesta_publica

    base = {"estado": "ok", "nivel_servicio": "normal", "plan": "extractivo", "fragmentos": [],
            "confianza": {"top1": 0.8, "margen": 0.1}, "latencia_ms": 1, "respuesta": "x"}
    assert respuesta_publica({**base, "nivel_confianza": "media"})["confidence_level"] == "medium"
    assert "confidence_level" not in respuesta_publica(base)  # sin respuesta que medir
    RespuestaConsulta.model_validate(respuesta_publica({**base, "nivel_confianza": "alta"}))
