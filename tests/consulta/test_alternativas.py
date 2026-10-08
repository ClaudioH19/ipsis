"""Postura proactiva: alternativas ante una abstención (ADR 0008)."""
from __future__ import annotations

import re

import pytest

from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier, RulesIntentClassifier, SentenceSelectorExtractor
from ipsis.consulta.alternativas import (
    ConfigAlternativas,
    afinidad,
    elegible,
    esqueleto,
    parrafos,
    vecinos_de_familia,
)
from ipsis.consulta.etapas.politica import DecisionAbstencion
from ipsis.consulta.etapas.redaccion import cargar_plantillas
from ipsis.consulta.motor import Motor
from ipsis.consulta.seguimiento import MemoriaConversacion
from ipsis.lenguaje.dominio import PerfilDominio, ReglaEntidad
from ipsis.lenguaje.entidades import extraer_entidades, usar_perfil
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.nucleo.esquemas import AssistantState, ChunkRecord, RetrievalCandidate, RetrievalSignals, SenalesRecuperacion

PERFIL = PerfilDominio(nombre="ferreteria", reglas=[ReglaEntidad(
    "codigo", re.compile(r"\b(?P<pre>[A-Z]{2})-(?P<num>\d{1,3})\b", re.IGNORECASE), "codigo_{pre}-{num}",
    {"pre": "minusculas"})])

CATALOGO = ("Catálogo de herramientas\nTaladros\n"
            "El taladro percutor TP-400 tiene un motor de 600 W. Su precio es de 39.990 pesos.\n"
            "El taladro percutor TP-600 tiene un motor de 800 W. Su precio es de 54.990 pesos.\n"
            "Escaleras\nLa escalera tijera ET-5 tiene cinco peldaños.")


# --- familia y párrafos --------------------------------------------------------------------------
def test_la_familia_de_un_codigo_comparte_su_forma_y_va_del_numero_mas_cercano():
    inventario = {"codigo_tp-400", "codigo_tp-600", "codigo_tp-900", "codigo_ti-18", "30.000", "4_dia"}
    assert esqueleto("codigo_tp-500") == "codigo_tp-#"
    assert vecinos_de_familia("codigo_tp-500", inventario) == ["codigo_tp-400", "codigo_tp-600", "codigo_tp-900"]
    assert vecinos_de_familia("codigo_tp-500", inventario, limite=1) == ["codigo_tp-400"]


def test_dos_cifras_sueltas_no_son_familia():
    assert esqueleto("30.000") is None
    assert vecinos_de_familia("45.000", {"30.000", "20.000"}) == []
    assert vecinos_de_familia("60_dia", {"90_dia", "30.000"}) == ["90_dia"]


def test_los_parrafos_son_lineas_sin_los_titulos():
    tramos = parrafos(CATALOGO, None, ("Catálogo de herramientas", "Taladros", "Escaleras"))
    textos = [CATALOGO[a:b] for a, b in tramos]
    assert textos == [
        "El taladro percutor TP-400 tiene un motor de 600 W. Su precio es de 39.990 pesos.",
        "El taladro percutor TP-600 tiene un motor de 800 W. Su precio es de 54.990 pesos.",
        "La escalera tijera ET-5 tiene cinco peldaños.",
    ]


def test_un_parrafo_largo_se_parte_en_oraciones():
    texto = "Primera oración bastante larga del párrafo. Segunda oración también larga."
    tramos = parrafos(texto, 50)
    assert len(tramos) == 2 and all(texto[a:b].strip() == texto[a:b] for a, b in tramos)


def test_afinidad_es_la_media_ponderada_y_sin_nada_en_comun_no_es_elegible():
    senales = {"familia": 1.0, "terminos": 0.5, "seccion": 0.0, "keywords": 0.0, "categoria": 1.0, "similitud": 0.5}
    assert afinidad(senales, {"familia": 2.0, "terminos": 2.0}) == pytest.approx(0.75)
    assert afinidad(senales, {}) == 0.0
    assert elegible(senales)
    assert not elegible({**senales, "familia": 0.0, "terminos": 0.0})


# --- motor ---------------------------------------------------------------------------------------
def _chunk(chunk_id: str, texto: str, inicio: int = 100) -> ChunkRecord:
    with usar_perfil(PERFIL):
        entidades = extraer_entidades(texto)
    return ChunkRecord(chunk_id=chunk_id, doc_id="catalogo", doc_titulo="Catálogo de herramientas",
                       texto_fuente=texto, texto_embedding=texto, offset_inicio=inicio,
                       offset_fin=inicio + len(texto), entidades=entidades)


class _Retriever:
    """Recupera el chunk de escaleras para la pregunta y el catálogo por la familia del código."""

    def __init__(self):
        self.catalogo = _chunk("c-taladros", CATALOGO)
        self.escaleras = _chunk("c-otro", "Las escaleras se guardan en la Bodega Norte.", 900)
        self.filtros: list[str] = []

    def estimar_confianza(self, _consulta, _limite):
        return SenalesRecuperacion(confianza_top1=0.4, margen_top1_top2=0.1)

    def recuperar(self, _consulta, _limite, filtro=None):
        if filtro is not None:
            self.filtros.append(filtro.valor_norm)
            return [RetrievalCandidate(chunk=self.catalogo, signals=RetrievalSignals())]
        return [RetrievalCandidate(chunk=self.escaleras, signals=RetrievalSignals(fusion_score=0.5))]

    def inventario_entidades(self):
        return {"codigo_tp-400", "codigo_tp-600", "codigo_et-5"}

    def estadisticas_lexico(self):
        return None

    def n_chunks(self):
        return 2

    def calentar(self):
        return None


class _Politica:
    def __init__(self, motivo: str, entidad: str | None = None):
        self.motivo, self.entidad = motivo, entidad

    def decidir_contexto(self, _ctx):
        return DecisionAbstencion(resultado="abstiene", motivo=self.motivo, entidad_texto=self.entidad,
                                  capa_decisora=self.motivo)


class _Memoria(MemoriaConversacion):
    def __init__(self):
        super().__init__()
        self.recordadas: list[set[str]] = []

    def recordar_evidencia(self, id_sesion, raices, *, turno=None):
        self.recordadas.append(raices)
        super().recordar_evidencia(id_sesion, raices, turno=turno)


def _motor(motivo: str = "premisa", modo: str = "proactiva") -> Motor:
    idioma = cargar_paquete("es")
    motor = Motor(retriever=_Retriever(), analizador=RulesIntentClassifier(),
                  politica_abstencion=_Politica(motivo, "TP-500" if motivo == "premisa" else None),
                  extractor=SentenceSelectorExtractor(limite_caracteres=500), verificador=LiteralOffsetsVerifier(),
                  perfil=PERFIL, idioma=idioma, plantillas=cargar_plantillas(idioma),
                  configuracion_redaccion={"cita_en_texto": "breve"})
    motor.alternativas = ConfigAlternativas(modo=modo, max_alternativas=2, umbral=0.5,
                                            pesos={"familia": 1.0, "terminos": 1.0})
    motor.seguimiento = _Memoria()
    return motor


def test_una_premisa_falsa_ofrece_la_familia_del_codigo_sin_cambiar_el_estado():
    motor = _motor()
    resultado = motor.consultar("¿Tienen el taladro TP-500?", "sesión")

    assert resultado.estado == AssistantState.SIN_RESPUESTA
    assert motor.retriever.filtros == ["codigo_tp-400", "codigo_tp-600"]
    contrato = resultado.diagnostico["contrato_http"]
    assert contrato["fragmentos"] == []
    textos = [a["texto"] for a in contrato["alternativas"]]
    assert all("TP-" in t for t in textos) and len(textos) == 2
    # Mensaje de abstención, encabezado fijo del tono y cada alternativa literal con su cita.
    tipos = [b["tipo"] for b in contrato["bloques"]]
    assert tipos == ["mensaje", "encabezado", "pasaje", "pasaje"]
    assert "TP-500" in contrato["bloques"][0]["texto"]
    intro = cargar_plantillas(cargar_paquete("es"))["abstencion"]["alternativas_intro"]
    assert contrato["bloques"][1]["texto"] in intro
    for alternativa in contrato["alternativas"]:
        inicio = alternativa["offset_inicio"] - 100
        assert CATALOGO[inicio:inicio + len(alternativa["texto"])] == alternativa["texto"]
    assert resultado.mensaje_usuario.startswith(contrato["bloques"][0]["texto"])
    diagnostico = resultado.diagnostico["alternativas"]
    assert [a["origen"] for a in diagnostico["ofrecidas"]] == ["familia", "familia"]


def test_las_alternativas_no_alimentan_la_memoria_de_la_conversacion():
    motor = _motor()
    motor.consultar("¿Tienen el taladro TP-500?", "sesión")
    assert motor.seguimiento.recordadas == []


def test_la_postura_estricta_no_ofrece_nada():
    resultado = _motor(modo="estricta").consultar("¿Tienen el taladro TP-500?", "sesión")
    contrato = resultado.diagnostico["contrato_http"]
    assert resultado.estado == AssistantState.SIN_RESPUESTA
    assert "alternativas" not in contrato and [b["tipo"] for b in contrato["bloques"]] == ["mensaje"]


def test_fuera_de_dominio_nunca_ofrece_alternativas():
    resultado = _motor(motivo="fuera_dominio").consultar("¿Tienen el taladro TP-500?", "sesión")
    assert "alternativas" not in resultado.diagnostico["contrato_http"]
    assert resultado.diagnostico.get("alternativas") is None


def test_bajo_el_umbral_no_se_ofrece_nada():
    motor = _motor()
    motor.alternativas.umbral = 1.01
    resultado = motor.consultar("¿Tienen el taladro TP-500?", "sesión")
    assert "alternativas" not in resultado.diagnostico["contrato_http"]
    assert resultado.diagnostico["alternativas"]["ofrecidas"] == []
    assert resultado.diagnostico["alternativas"]["descartadas"]


def test_la_respuesta_publica_trae_las_alternativas():
    from ipsis.servicio.api import RespuestaConsulta, respuesta_publica

    resultado = _motor().consultar("¿Tienen el taladro TP-500?", "sesión")
    publica = respuesta_publica(resultado.diagnostico["contrato_http"])
    RespuestaConsulta.model_validate(publica)
    assert publica["status"] == "no_answer"
    assert [a["text"] for a in publica["alternatives"]] == [
        a["texto"] for a in resultado.diagnostico["contrato_http"]["alternativas"]]
    assert [b["type"] for b in publica["answer_blocks"]] == ["message", "lead", "passage", "passage"]


@pytest.mark.parametrize("motivo", ["premisa", "generico", "fuera_dominio"])
def test_la_postura_nunca_cambia_el_estado_ni_el_motivo(motivo):
    proactiva = _motor(motivo).consultar("¿Tienen el taladro TP-500?", "a")
    estricta = _motor(motivo, modo="estricta").consultar("¿Tienen el taladro TP-500?", "b")
    assert (proactiva.estado, proactiva.motivo) == (estricta.estado, estricta.motivo)
    assert proactiva.evidencias == estricta.evidencias == []


def test_una_medida_del_nucleo_no_tiene_familia():
    """«60 días» se parece a todo «N días» del corpus, de documentos sin
    relación: solo los tipos que declara el proyecto (sus códigos) tienen
    familia. Ni exigir una palabra de la pregunta alcanzó 0,9 (ADR 0008)."""
    from types import SimpleNamespace

    from ipsis.consulta.alternativas import buscar_alternativas
    from ipsis.lenguaje.entidades import usar_idioma
    from ipsis.lenguaje.texto import terminos

    idioma = cargar_paquete("es")
    texto = "La contraseña vence cada 90 días.\nEl préstamo de libros dura 14 días."
    with usar_idioma(idioma):
        chunk = ChunkRecord(chunk_id="c", doc_id="d", doc_titulo="Preguntas", texto_fuente=texto,
                            texto_embedding=texto, offset_inicio=0, offset_fin=len(texto),
                            entidades=extraer_entidades(texto))
        pregunta = "¿La contraseña vence cada 60 días?"
        ausente = [e for e in extraer_entidades(pregunta) if e["valor_norm"] == "60_dia"]
        retriever = SimpleNamespace(
            inventario_entidades=lambda: {"90_dia", "14_dia"},
            recuperar=lambda *_a, **_k: [RetrievalCandidate(chunk=chunk)])
        motor = SimpleNamespace(retriever=retriever, idioma=idioma, taxonomia=None, configuracion_redaccion={},
                                politica_abstencion=None)
        ctx = SimpleNamespace(pregunta=pregunta, pregunta_usuario="", candidatos=[],
                              consulta=SimpleNamespace(pregunta_original=pregunta),
                              terminos_pregunta=[t for t in terminos(pregunta, idioma) if t in {"contraseñ", "venc"}])
        resultado = buscar_alternativas(motor, ctx, entidades_ausentes=ausente, config=ConfigAlternativas(
            umbral=0.4, pesos={"familia": 1.0, "terminos": 1.0}))
    assert resultado.ofrecidas == [] and resultado.descartadas == []
