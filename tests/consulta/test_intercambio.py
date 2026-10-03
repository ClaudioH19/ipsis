"""Matriz de contratos e intercambio de componentes de la Fase A."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from rag.consulta.etapas.politica import DecisionAbstencion, LayeredV1
from rag.nucleo.esquemas import (
    AssistantState,
    ChunkRecord,
    EvidenceSpan,
    FiltroEntidad,
    QueryAnalysis,
    QueryDiagnostic,
    RetrievalCandidate,
    RetrievalSignals,
    SenalesRecuperacion,
)
from rag.aplicacion.registro_base import LiteralOffsetsVerifier, SentenceSelectorExtractor
from rag.consulta.motor import Motor


def _candidato(
    chunk_id: str = "c1",
    texto: str = "El equipo incluye un filtro lavable.",
    score: float = 0.9,
    *,
    entidades: list[dict] | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=ChunkRecord(
            chunk_id=chunk_id,
            doc_id="manual",
            doc_titulo="Manual",
            version="1",
            texto_fuente=texto,
            texto_embedding=texto,
            offset_inicio=0,
            offset_fin=len(texto),
            entidades=entidades or [],
        ),
        signals=RetrievalSignals(fusion_score=score, fusion_rank=1),
    )


class RetrieverMemoria:
    def __init__(self) -> None:
        self.general = [_candidato()]
        self.dirigido = _candidato(
            "c9",
            "El artículo 9 establece el procedimiento.",
            0.8,
            entidades=[{"tipo": "articulo", "valor_norm": "articulo:9", "texto": "artículo 9"}],
        )
        self.filtros: list[str | None] = []

    def estimar_confianza(self, _consulta, _limite):
        return SenalesRecuperacion(confianza_top1=0.9, margen_top1_top2=0.2)

    def recuperar(self, _consulta, limite, filtro=None):
        self.filtros.append(filtro.valor_norm if filtro else None)
        candidatos = [self.dirigido] if filtro else self.general
        return [candidato.model_copy(deep=True) for candidato in candidatos[:limite]]

    def inventario_entidades(self):
        return {"articulo:9"}

    def estadisticas_lexico(self):
        from rag.indice.estadisticas import EstadisticasLexicas

        return EstadisticasLexicas.construir(["El equipo incluye un filtro."])

    def n_chunks(self):
        return 2

    def calentar(self):
        return None


class AnalizadorMemoria:
    def analizar(self, pregunta, contexto=None):
        return QueryAnalysis(
            pregunta_original=pregunta,
            pregunta_normalizada=" ".join(pregunta.lower().split()),
            contexto=contexto or {},
        )


class ExtractorLiteral:
    def extraer(self, _consulta, candidatos):
        return [
            EvidenceSpan(
                doc_id=candidato.chunk.doc_id,
                chunk_id=candidato.chunk.chunk_id,
                texto=candidato.chunk.texto_fuente,
                offset_inicio=candidato.chunk.offset_inicio,
                offset_fin=candidato.chunk.offset_fin,
                seccion_path=candidato.chunk.seccion_path,
                score=candidato.score,
            )
            for candidato in candidatos
        ]


class PoliticaForzada:
    def __init__(self, resultado: str):
        self.resultado = resultado

    def decidir_dominio(self, _consulta, _senales):
        if self.resultado == "fuera_dominio":
            return DecisionAbstencion(
                resultado="abstiene",
                motivo="fuera_dominio",
                capa_decisora="fuera_dominio",
            )
        return None

    def decidir(self, _consulta, _senales, _candidatos):
        if self.resultado == "premisa":
            return DecisionAbstencion(
                resultado="abstiene",
                motivo="premisa",
                entidad_texto="artículo 99",
                capa_decisora="premisa",
            )
        if self.resultado == "relacionado":
            return DecisionAbstencion(
                resultado="relacionado",
                motivo="zona_gris",
                capa_decisora="zona_gris",
            )
        return DecisionAbstencion(
            resultado="responde",
            motivo="confianza_alta",
            capa_decisora="confianza_alta",
        )


_PLANTILLAS = {
    "conversacional": {
        "categorias": ["saludo"],
        "patrones": {"saludo": [r"^hola$"]},
        "respuestas": {"saludo": "Hola desde memoria."},
    },
    "conectores": {
        "apertura": [],
        "complemento": ["Además:"],
        "condicion": ["Como condición:"],
        "excepcion": ["Como excepción:"],
    },
    "abstencion": {
        "generico": "No encontré información suficiente.",
        "premisa_no_encontrada": "No encontré {entidad}.",
        "zona_gris_intro": "Encontré información relacionada:",
    },
}

_REDACCION = {
    "max_fragmentos_en_respuesta": 2,
    "score_relativo_minimo": 0.0,
    "cita_en_texto": "breve",
    "incluir_apertura": False,
}


def _crear_motor(resultado: str = "responde") -> Motor:
    return Motor(
        retriever=RetrieverMemoria(),
        analizador=AnalizadorMemoria(),
        politica_abstencion=PoliticaForzada(resultado),
        extractor=ExtractorLiteral(),
        verificador=LiteralOffsetsVerifier(),
        backend="memoria",
        plantillas=_PLANTILLAS,
        configuracion_redaccion=_REDACCION,
    )


def _validar_diagnostico(resultado) -> QueryDiagnostic:
    diagnostico = dict(resultado.diagnostico)
    diagnostico.pop("contrato_http")
    return QueryDiagnostic.model_validate(diagnostico)


def test_contrato_retriever_orden_filtro_senales_e_inventarios():
    retriever = RetrieverMemoria()
    consulta = AnalizadorMemoria().analizar("pregunta")

    primera = retriever.recuperar(consulta, 3)
    segunda = retriever.recuperar(consulta, 3)
    dirigida = retriever.recuperar(
        consulta,
        1,
        filtro=FiltroEntidad(valor_norm="articulo:9"),
    )

    assert primera == segunda
    assert [c.chunk.chunk_id for c in primera] == ["c1"]
    assert dirigida[0].chunk.chunk_id == "c9"
    assert dirigida[0].score == pytest.approx(0.8)
    assert retriever.filtros == [None, None, "articulo:9"]
    assert retriever.inventario_entidades() == {"articulo:9"}
    assert retriever.estadisticas_lexico().df["equipo"] == 1


def test_contrato_politica_es_determinista_para_la_misma_entrada():
    politica = LayeredV1(
        configuracion={
            "capa_a_fuera_dominio": {
                "umbral": 0.4,
                "grounding_lexico": {"oov_max": 0.5},
            },
            "confianza_alta": {"umbral": 0.8},
            "zona_gris": {"modo": "relacionado"},
        },
    )
    consulta = AnalizadorMemoria().analizar("pregunta general")
    senales = SenalesRecuperacion(confianza_top1=0.9, margen_top1_top2=0.1)
    candidatos = [_candidato()]

    assert politica.decidir(consulta, senales, candidatos) == politica.decidir(
        consulta, senales, candidatos
    )


def test_contrato_selector_produce_texto_literal_y_offsets_exactos():
    candidato = _candidato(texto="Primera oración. El filtro es lavable.")
    consulta = AnalizadorMemoria().analizar("¿El filtro es lavable?")

    evidencias = SentenceSelectorExtractor(limite_caracteres=80).extraer(
        consulta, [candidato]
    )

    assert evidencias
    for evidencia in evidencias:
        inicio = evidencia.offset_inicio - candidato.chunk.offset_inicio
        fin = evidencia.offset_fin - candidato.chunk.offset_inicio
        assert candidato.chunk.texto_fuente[inicio:fin] == evidencia.texto


def test_contrato_verificador_rechaza_evidencia_ajena_al_fragmento():
    candidato = _candidato(texto="Texto fuente literal.")
    evidencia = EvidenceSpan(
        doc_id="manual",
        chunk_id="c1",
        texto="Texto fuente mutado..",
        offset_inicio=0,
        offset_fin=len("Texto fuente mutado.."),
    )

    valida, errores = LiteralOffsetsVerifier().verificar([evidencia], [candidato])

    assert valida is False
    assert errores


@pytest.mark.parametrize(
    ("decision", "estado"),
    [
        ("responde", AssistantState.RESPUESTA_DIRECTA),
        ("relacionado", AssistantState.RELACIONADO),
        ("premisa", AssistantState.SIN_RESPUESTA),
        ("fuera_dominio", AssistantState.SIN_RESPUESTA),
    ],
)
def test_motor_intercambia_politicas_y_conserva_resultado_estable(decision, estado):
    motor = _crear_motor(decision)

    primero = motor.consultar("¿Qué incluye el equipo?", "s1")
    segundo = motor.consultar("¿Qué incluye el equipo?", "s1")

    assert primero.estado == estado
    assert primero.mensaje_usuario == segundo.mensaje_usuario
    diagnostico = _validar_diagnostico(primero)
    assert diagnostico.backend == "memoria"
    assert set(diagnostico.etapas) >= {"analisis_ms", "confianza_ms"}
    if decision in {"responde", "relacionado", "premisa"}:
        assert diagnostico.decision is not None


def test_motor_conversacional_en_memoria_no_exige_componentes():
    motor = Motor(plantillas=_PLANTILLAS)

    resultado = motor.consultar("hola", "s1")

    assert resultado.estado == AssistantState.CONVERSACIONAL
    assert resultado.mensaje_usuario == "Hola desde memoria."
    assert _validar_diagnostico(resultado).backend == "sin_configurar"


def test_motor_no_emite_ok_si_piden_precio_sin_importe_en_evidencia():
    resultado = _crear_motor("responde").consultar(
        "¿Cuánto cuesta el equipo?",
        "s-precio",
    )

    assert resultado.estado == AssistantState.SIN_RESPUESTA
    diagnostico = _validar_diagnostico(resultado)
    assert any("importe monetario" in aviso for aviso in diagnostico.advertencias)


def test_corte_en_memoria_no_importa_dependencias_pesadas():
    raiz = Path(__file__).resolve().parents[2]
    script = """
import runpy
import sys

for nombre in ('qdrant_client', 'torch', 'transformers', 'sentence_transformers'):
    sys.modules[nombre] = None
ns = runpy.run_path('tests/consulta/test_intercambio.py')
resultado = ns['_crear_motor']('responde').consultar('¿Qué incluye el equipo?', 'aislado')
assert resultado.estado.value == 'respuesta_directa'
"""
    proceso = subprocess.run(
        [sys.executable, "-c", script],
        cwd=raiz,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proceso.returncode == 0, proceso.stdout + proceso.stderr


# ---------------------------------------------------------------------------
# Etapas desde el perfil y salida temprana léxica
# ---------------------------------------------------------------------------
class _EtapaConModelo:
    nombre = "modelo_falso"
    requiere_admision = True
    usa_modelos = True

    def __init__(self):
        self.llamadas = 0

    def ejecutar(self, ctx):
        self.llamadas += 1


def _motor_con_etapa_de_modelo():
    from rag.lenguaje.paquete import cargar_paquete

    from rag.indice.estadisticas import EstadisticasLexicas

    es = cargar_paquete("es")
    motor = _crear_motor()
    motor.idioma = es
    estadisticas = EstadisticasLexicas.construir(["El equipo incluye un filtro.", "Garantía de dos años."], es)
    motor.retriever.estadisticas_lexico = lambda: estadisticas
    falsa = _EtapaConModelo()
    posicion = [e.nombre for e in motor.etapas].index("recuperacion") + 1
    motor.etapas.insert(posicion, falsa)
    return motor, falsa


def test_salida_temprana_salta_las_etapas_con_modelos_sin_terminos_foco():
    motor, falsa = _motor_con_etapa_de_modelo()
    # El foco «filtro» aparece en el candidato: se ejecutan los modelos.
    motor.consultar("¿Qué filtro incluye?", "s1")
    assert falsa.llamadas == 1
    # Ningún candidato menciona «filtro»: salida temprana, los modelos no corren.
    motor.retriever.general = [_candidato(texto="Garantía de dos años.")]
    motor.consultar("¿Qué filtro incluye?", "s2")
    assert falsa.llamadas == 1


def test_perfil_con_etapa_desconocida_falla_al_construir(monkeypatch):
    from copy import deepcopy

    from rag.aplicacion.consulta import construir_motor
    from rag.configuracion.carga import cargar_dominio, cargar_proyecto

    cfg = deepcopy(cargar_proyecto())
    cfg["ajustes_perfil"] = {"etapas": ["conversacional", "no_existe"]}
    with pytest.raises(ValueError, match="no_existe"):
        construir_motor(cfg, cfg_dominio=cargar_dominio())


def test_diagnostico_v2_incluye_perfil_senales_lexicas_y_regla():
    motor, _ = _motor_con_etapa_de_modelo()
    resultado = motor.consultar("¿Qué filtro incluye?", "s1")
    diagnostico = _validar_diagnostico(resultado)
    assert diagnostico.schema_version == 2
    assert diagnostico.senales_lexicas["terminos_foco"]
    assert diagnostico.regla
    assert diagnostico.salto_modelos is False
    assert "modelo_falso_ms" in diagnostico.etapas
