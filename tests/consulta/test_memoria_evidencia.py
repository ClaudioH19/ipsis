"""La memoria solo recibe vocabulario después de verificar la salida."""
from types import SimpleNamespace

import pytest

from ipsis.consulta.contexto import ContextoConsulta
from ipsis.consulta.etapas.verificacion import EtapaVerificacion, ResultadoFidelidad
from ipsis.consulta.seguimiento import MemoriaConversacion
from ipsis.indice.estadisticas import EstadisticasLexicas
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.texto import terminos
from ipsis.nucleo.esquemas import AssistantState, EvidenceSpan


def _preparar(estado=AssistantState.RESPUESTA_DIRECTA):
    paquete = cargar_paquete("es")
    texto = "El viático diario cubre el viaje. La solicitud se presenta antes de viajar."
    est = EstadisticasLexicas.construir([texto, "La biblioteca abre."], paquete)
    memoria = MemoriaConversacion()
    r = memoria.resolver("¿Cuál es el viático diario?", "s", paquete, est)
    evidencia = EvidenceSpan(doc_id="d", chunk_id="c", texto="El viático diario cubre el viaje.",
                             offset_inicio=0, offset_fin=len("El viático diario cubre el viaje."))
    ctx = ContextoConsulta("¿Cuál es el viático diario?", "s", turno_memoria=r.turno)
    ctx.estado = estado
    ctx.texto = evidencia.texto
    ctx.decision = SimpleNamespace(motivo="lexico")
    ctx.evidencias = [evidencia]
    ctx.payloads = [{"texto": texto, "doc_titulo": "Viajes", "seccion_path": []}]
    ctx.candidatos = [SimpleNamespace(chunk=SimpleNamespace(chunk_id="c", texto_fuente=texto)),
                      SimpleNamespace(chunk=SimpleNamespace(chunk_id="otro", texto_fuente="La biblioteca abre."))]
    ctx.diagnostico = {"conversacion": {"accion": r.accion}, "advertencias": []}
    motor = SimpleNamespace(idioma=paquete, seguimiento=memoria, _resultado=lambda **kwargs: kwargs,
                            _fragmentos_http=lambda *args: [], _abstener=lambda *args, **kwargs: {"guardia": True})
    return paquete, est, memoria, ctx, motor, texto


@pytest.mark.parametrize("estado", [AssistantState.RESPUESTA_DIRECTA, AssistantState.RELACIONADO])
def test_recuerda_fuente_de_primera_cita_y_excluye_candidatos_ajenos(estado):
    paquete, est, memoria, ctx, motor, texto = _preparar(estado)
    EtapaVerificacion(motor).ejecutar(ctx)
    assert memoria._sesiones["s"].tema.respuestas == [frozenset(terminos(texto, paquete))]
    assert not set(terminos("biblioteca", paquete)) & memoria._sesiones["s"].tema.vocabulario()


def test_guardia_fallida_no_incorpora_vocabulario(monkeypatch):
    _, _, memoria, ctx, motor, _ = _preparar()
    monkeypatch.setattr("ipsis.consulta.etapas.verificacion.verificar_fidelidad",
                        lambda *a: ResultadoFidelidad(False, ["sin respaldo"]))
    EtapaVerificacion(motor).ejecutar(ctx)
    assert ctx.resultado == {"guardia": True}
    assert not memoria._sesiones["s"].tema.respuestas


def test_pregunta_sin_cambio_no_contamina_el_tema_aunque_muestre_relacionados():
    _, _, memoria, ctx, motor, _ = _preparar(AssistantState.RELACIONADO)
    ctx.diagnostico["conversacion"]["accion"] = "sin_cambio"
    EtapaVerificacion(motor).ejecutar(ctx)
    assert not memoria._sesiones["s"].tema.respuestas
