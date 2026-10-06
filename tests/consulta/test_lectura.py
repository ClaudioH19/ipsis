"""Etapa de lectura con un lector falso."""
from __future__ import annotations

from ipsis.aplicacion.registro_base import LiteralOffsetsVerifier
from ipsis.consulta.contexto import ContextoConsulta
from ipsis.consulta.etapas.lectura import EtapaLectura, oracion_que_contiene
from ipsis.nucleo.esquemas import ChunkRecord, LecturaQA, RetrievalCandidate, RetrievalSignals

TEXTO = "Instalación sencilla. El filtro se cambia cada 6 meses. Garantía de 2 años."


def _candidato():
    return RetrievalCandidate(
        chunk=ChunkRecord(chunk_id="c1", doc_id="d", doc_titulo="D", version="1", texto_fuente=TEXTO,
                          texto_embedding=TEXTO, offset_inicio=100, offset_fin=100 + len(TEXTO)),
        signals=RetrievalSignals(fusion_score=0.5, fusion_rank=1),
    )


class _LectorFalso:
    def __init__(self, texto, s_qa=0.9):
        self.texto, self.p = texto, (1 + s_qa) / 2

    def leer(self, _pregunta, pasajes):
        ini = pasajes[0].find(self.texto) if self.texto else 0
        fin = ini + len(self.texto)
        return [LecturaQA(indice_pasaje=0, inicio=ini, fin=fin, texto=self.texto,
                          prob_respuesta=self.p, prob_sin_respuesta=1 - self.p)]


class _Motor:
    perfil_instalacion = None

    def __init__(self, lector):
        self.lector = lector


def test_evidencia_es_la_oracion_que_contiene_el_tramo_con_offsets_globales():
    ctx = ContextoConsulta(pregunta="¿Cada cuánto?", id_sesion="s")
    ctx.candidatos = [_candidato()]
    EtapaLectura(_Motor(_LectorFalso("6 meses"))).ejecutar(ctx)
    assert ctx.evidencia_lector.texto == "El filtro se cambia cada 6 meses."
    assert ctx.respuesta_exacta["texto"] == "6 meses"
    assert ctx.respuesta_exacta["offset_inicio"] == 100 + TEXTO.index("6 meses")
    validas, errores = LiteralOffsetsVerifier().verificar([ctx.evidencia_lector], ctx.candidatos)
    assert validas, errores


def test_sin_respuesta_del_lector_no_hay_evidencia():
    ctx = ContextoConsulta(pregunta="¿Precio?", id_sesion="s")
    ctx.candidatos = [_candidato()]
    EtapaLectura(_Motor(_LectorFalso("", s_qa=0.0))).ejecutar(ctx)
    assert ctx.evidencia_lector is None and ctx.respuesta_exacta is None
    assert ctx.diagnostico["lecturas"][0]["s_qa"] == 0.0


def test_oracion_que_contiene_un_tramo_que_cruza_oraciones():
    ini = TEXTO.index("6 meses")
    fin = TEXTO.index("2 años") + len("2 años")
    a, b = oracion_que_contiene(TEXTO, ini, fin)
    assert TEXTO[a:b] == "El filtro se cambia cada 6 meses. Garantía de 2 años."


def test_tramo_del_lector_lejos_del_foco_da_s_foco_cero():
    """«6 meses» sale de la oración del filtro: no responde «¿Cuánto dura la garantía?»."""
    from ipsis.consulta.etapas.seleccion import EtapaEvidencia
    from ipsis.indice.estadisticas import EstadisticasLexicas
    from ipsis.lenguaje.lexico import terminos_foco, terminos_pregunta
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.nucleo.esquemas import SenalesLexicas

    es = cargar_paquete("es")
    est = EstadisticasLexicas.construir([TEXTO, "La garantía cubre 24 meses."], es)

    class _Retriever:
        def estadisticas_lexico(self):
            return est

    class _Verificador:
        def verificar(self, evidencias, candidatos):
            return LiteralOffsetsVerifier().verificar(evidencias, candidatos)

    motor = _Motor(_LectorFalso("6 meses"))
    motor.retriever, motor.idioma, motor.verificador = _Retriever(), es, _Verificador()
    ctx = ContextoConsulta(pregunta="¿Cuánto dura la garantía?", id_sesion="s")
    ctx.terminos_pregunta = terminos_pregunta(ctx.pregunta, es)
    ctx.terminos_foco = terminos_foco(ctx.terminos_pregunta, est)
    ctx.lexicas = SenalesLexicas(terminos_foco=ctx.terminos_foco)
    ctx.candidatos = [_candidato()]
    ctx.diagnostico["senales_lexicas"] = {}  # lo crea EtapaFiltros
    EtapaLectura(motor).ejecutar(ctx)
    EtapaEvidencia(motor).ejecutar(ctx)
    assert ctx.evidencias[0].texto == "El filtro se cambia cada 6 meses."
    assert ctx.lexicas.s_foco == 0.0
    lexicas = ctx.diagnostico["senales_lexicas"]  # ipsis ask --diagnostics los muestra
    assert lexicas["foco_encontrados"] == [] and lexicas["foco_ausentes"] == [est.superficie[t] for t in ctx.terminos_foco]
    assert lexicas["foco_ausentes"]


def test_concordancia_detecta_plazos_distintos_en_pasajes_distintos():
    from ipsis.consulta.etapas.lectura import hay_discordancia

    def lec(i, texto, p=0.95):
        return LecturaQA(indice_pasaje=i, inicio=0, fin=len(texto), texto=texto,
                         prob_respuesta=p, prob_sin_respuesta=1 - p)

    assert hay_discordancia([lec(0, "6 meses"), lec(1, "12 meses")])
    assert not hay_discordancia([lec(0, "6 meses"), lec(1, "6 meses")])
    assert not hay_discordancia([lec(0, "6 meses"), lec(0, "12 meses")])  # mismo pasaje
    assert not hay_discordancia([lec(0, "6 meses"), lec(1, "12 meses", p=0.6)])  # el segundo no es confiable


def test_el_lector_recibe_solo_la_ventana_pertinente_y_los_offsets_vuelven_al_pasaje():
    largo = "Texto de relleno sin relación. " * 40 + TEXTO

    class _LectorQueAnota(_LectorFalso):
        def leer(self, pregunta, pasajes):
            self.leidos = pasajes
            return super().leer(pregunta, pasajes)

    class _Perfil:
        class cascada:  # noqa: N801
            leer_m = 1
            concordancia = False
            max_caracteres_lectura = 120

    lector = _LectorQueAnota("6 meses")
    motor = _Motor(lector)
    motor.perfil_instalacion = _Perfil()
    candidato = _candidato()
    candidato.chunk.texto_fuente = largo
    candidato.chunk.offset_fin = candidato.chunk.offset_inicio + len(largo)
    ctx = ContextoConsulta(pregunta="¿Cada cuánto se cambia el filtro?", id_sesion="s")
    ctx.candidatos = [candidato]
    EtapaLectura(motor).ejecutar(ctx)
    assert len(lector.leidos[0]) <= 120
    assert largo[ctx.lecturas[0].inicio:ctx.lecturas[0].fin] == "6 meses"
