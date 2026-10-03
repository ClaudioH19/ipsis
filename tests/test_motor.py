from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from rag.nucleo.registro import RegistroComponentes
from rag.configuracion.carga import cargar_dominio, cargar_proyecto
from rag.nucleo.esquemas import AssistantResult, AssistantState, QueryAnalysis, QueryDiagnostic
from rag.abstencion import DecisionAbstencion
from rag.nucleo.esquemas import (
    ChunkRecord,
    RetrievalCandidate,
    RetrievalSignals,
    SenalesRecuperacion,
)
from rag.aplicacion.registro_base import LiteralOffsetsVerifier, RulesIntentClassifier, SentenceSelectorExtractor
from rag.lenguaje.entidades import extraer_entidades
from rag.servicio.motor import Motor


def test_endpoint_consultar_delega_en_motor():
    from rag.servicio import api
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
        "/consultar",
        json={"pregunta": "¿dato?", "id_sesion": "sesión"},
    )

    assert llamadas == [("¿dato?", "sesión")]
    assert respuesta.status_code == 200
    assert respuesta.json() == contrato


def test_crear_app_aisla_estado_y_lifespan_calienta_y_cierra_motor():
    from fastapi.testclient import TestClient
    from rag.servicio.api import crear_app

    eventos: list[str] = []

    class _Control:
        class config:
            concurrencia_maxima = 2

    class _MotorFalso:
        politica_abstencion = object()
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
        assert respuesta.json() == {
            "estado": "listo",
            "backend": "memoria",
            "coleccion": "memoria",
            "n_chunks": 4,
            "n_entidades_inventario": 1,
            "abstencion_calibrada": True,
            "concurrencia_maxima": 2,
        }

    assert eventos == ["calentar", "cerrar"]


def test_health_sigue_vivo_y_ready_diagnostica_un_arranque_fallido():
    from fastapi.testclient import TestClient
    from rag.servicio.api import crear_app

    class _MotorQueFalla:
        politica_abstencion = None

        def calentar(self):
            raise RuntimeError("índice ausente para la prueba")

        def cerrar(self):
            pass

    aplicacion = crear_app(_MotorQueFalla())

    with TestClient(aplicacion) as cliente:
        health = cliente.get("/health")
        ready = cliente.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"estado": "vivo"}
    assert ready.status_code == 503
    assert "RuntimeError: índice ausente para la prueba" in ready.json()["detail"]


def test_motor_orquesta_recuperacion_dirigida_y_etapas_tipadas():
    pregunta = "¿Qué establece el artículo 9?"
    valor_entidad = extraer_entidades(pregunta)[0]["valor_norm"]

    def candidato(chunk_id: str, texto: str, score: float) -> RetrievalCandidate:
        return RetrievalCandidate(
            chunk=ChunkRecord(
                chunk_id=chunk_id,
                doc_id="reglamento",
                doc_titulo="Reglamento",
                texto_fuente=texto,
                texto_embedding=texto,
                offset_inicio=0,
                offset_fin=len(texto),
            ),
            signals=RetrievalSignals(fusion_score=score),
        )

    inicial = candidato("c8", "El artículo 8 regula la instalación.", 0.9)
    dirigido = candidato("c9", "El artículo 9 fija un plazo de 10 días.", 0.8)

    class _Retriever:
        def __init__(self):
            self.filtros: list[str | None] = []

        def estimar_confianza(self, _consulta, _limite):
            return SenalesRecuperacion(confianza_top1=0.95, margen_top1_top2=0.1)

        def recuperar(self, _consulta, _limite, filtro=None):
            self.filtros.append(filtro.valor_norm if filtro else None)
            return [dirigido] if filtro else [inicial]

        def inventario_entidades(self):
            return {valor_entidad}

        def estadisticas_lexico(self):
            return {}

        def n_chunks(self):
            return 2

        def calentar(self):
            return None

    class _Politica:
        def decidir_dominio(self, _consulta, _senales):
            return None

        def decidir(self, _consulta, _senales, _candidatos):
            return DecisionAbstencion(
                resultado="responde",
                motivo="confianza_alta",
                capa_decisora="confianza_alta",
            )

    retriever = _Retriever()
    motor = Motor(
        retriever=retriever,
        analizador=RulesIntentClassifier(),
        politica_abstencion=_Politica(),
        extractor=SentenceSelectorExtractor(limite_caracteres=500),
        verificador=LiteralOffsetsVerifier(),
        top_k=3,
        max_fragmentos_adicionales=2,
    )

    resultado = motor.consultar(pregunta, "sesión")

    assert resultado.estado == AssistantState.RESPUESTA_DIRECTA
    assert retriever.filtros == [None, valor_entidad]
    assert [e.chunk_id for e in resultado.evidencias] == ["c9", "c8"]
    assert resultado.diagnostico["decision"]["motivo"] == "confianza_alta"
    assert set(resultado.diagnostico["etapas"]) >= {
        "analisis_ms", "confianza_ms", "recuperacion_ms", "evidencia_ms",
    }
    diagnostico = dict(resultado.diagnostico)
    diagnostico.pop("contrato_http")
    validado = QueryDiagnostic.model_validate(diagnostico)
    assert validado.backend == "_Retriever"
    assert [c.chunk_id for c in validado.candidatos] == ["c8", "c9"]
    assert [e.chunk_id for e in validado.evidencias] == ["c9", "c8"]
    assert validado.advertencias == []


def test_motor_emite_diagnostico_completo_en_respuesta_conversacional():
    resultado = Motor().consultar("hola", "sesión")
    diagnostico = dict(resultado.diagnostico)
    diagnostico.pop("contrato_http")

    validado = QueryDiagnostic.model_validate(diagnostico)

    assert resultado.estado == AssistantState.CONVERSACIONAL
    assert validado.backend == "sin_configurar"
    assert validado.etapas.keys() == {"conversacional_ms"}
    assert validado.candidatos == []
    assert validado.senales == {}
    assert validado.decision is None
    assert validado.evidencias == []


def test_motor_desde_configuracion_resuelve_runtime_y_usa_clasificador(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    cfg = deepcopy(cargar_proyecto())
    cfg["componentes"].update({
        "retriever": "fake",
        "intent_classifier": "fake",
        "abstention_policy": "fake",
        "answer_extractor": "fake",
        "evidence_verifier": "fake",
        "response_renderer": "fake",
    })
    registro = RegistroComponentes()
    capturado: dict[str, Any] = {}

    class _Retriever:
        codificador = object()

        def inventario_entidades(self):
            return {"articulo:9"}

        def estadisticas_lexico(self):
            return {"documento": 0.2}

        def calentar(self):
            capturado["calentado"] = True

        def n_chunks(self):
            return 7

    class _Analizador:
        def analizar(self, pregunta, contexto=None):
            capturado["analisis"] = (pregunta, contexto)
            return QueryAnalysis(
                pregunta_original=pregunta,
                pregunta_normalizada=pregunta.lower(),
                contexto=contexto or {},
            )

    retriever = _Retriever()
    registro.registrar("retriever", "fake", lambda **_: retriever)
    registro.registrar("intent_classifier", "fake", _Analizador)
    registro.registrar("abstention_policy", "fake", lambda **kwargs: kwargs)
    registro.registrar(
        "answer_extractor",
        "fake",
        lambda **kwargs: capturado.setdefault("extractor", kwargs) or object(),
    )
    registro.registrar("evidence_verifier", "fake", object)
    registro.registrar("response_renderer", "fake", object)

    motor = Motor.desde_configuracion(
        cfg,
        cfg_dominio=cargar_dominio(),
        registro=registro,
    )
    analisis = motor._analizar("  DATO  ", "s-1")
    motor.calentar()
    monkeypatch.chdir(tmp_path)
    conversacional = motor.consultar("hola", "s-2")

    assert motor.retriever is retriever
    assert motor.n_chunks() == 7
    assert analisis.pregunta_normalizada == "  dato  "
    assert capturado["analisis"] == ("  DATO  ", {"id_sesion": "s-1"})
    assert capturado["extractor"]["modelo_st"] is retriever.codificador
    assert capturado["calentado"] is True
    assert motor.perfil is not None
    assert motor.plantillas is not None
    assert conversacional.estado == AssistantState.CONVERSACIONAL


def test_motor_desde_configuracion_rechaza_nombre_desconocido_antes_de_construir():
    cfg = deepcopy(cargar_proyecto())
    cfg["componentes"]["response_renderer"] = "inexistente"

    with pytest.raises(KeyError, match="response_renderer/inexistente"):
        Motor.desde_configuracion(cfg, cfg_dominio=cargar_dominio())
