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


def test_seguimiento_lee_relacion_actual_y_aisla_el_actor_con_offsets_exactos():
    from ipsis.indice.estadisticas import EstadisticasLexicas
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.nucleo.esquemas import QueryAnalysis
    from types import SimpleNamespace

    paquete = cargar_paquete("es")
    texto = "El Director firma la resolución. La Secretaría redacta la resolución y la envía al Director para su firma."
    est = EstadisticasLexicas.construir([texto], paquete)

    class Lector(_LectorFalso):
        def leer(self, pregunta, pasajes):
            self.pregunta, self.pasajes = pregunta, pasajes
            return super().leer(pregunta, pasajes)

    lector = Lector("La Secretaría")
    motor = _Motor(lector)
    motor.idioma = paquete
    motor.retriever = SimpleNamespace(estadisticas_lexico=lambda: est)
    candidato = _candidato()
    candidato.chunk.texto_fuente = texto
    candidato.chunk.offset_fin = 100 + len(texto)
    actual = "¿Y quién la redacta?"
    ctx = ContextoConsulta(actual + " firma resolución", "s", pregunta_usuario=actual,
                           consulta=QueryAnalysis(pregunta_original=actual + " firma resolución", pregunta_normalizada=actual,
                                                  intencion="responsable", contexto={"pregunta_usuario": actual}))
    ctx.candidatos = [candidato]
    EtapaLectura(motor).ejecutar(ctx)
    assert lector.pregunta == actual
    assert lector.pasajes == ["La Secretaría redacta la resolución y la envía al Director para su firma."]
    assert ctx.respuesta_exacta["texto"] == "La Secretaría redacta la resolución"
    a, b = ctx.respuesta_exacta["offset_inicio"] - 100, ctx.respuesta_exacta["offset_fin"] - 100
    assert texto[a:b] == ctx.respuesta_exacta["texto"]
    assert ctx.diagnostico["tramo_completado"]["original"] == "La Secretaría"


def test_un_calificativo_eliptico_conserva_la_pregunta_interpretada_del_lector():
    from ipsis.lenguaje.paquete import cargar_paquete
    from types import SimpleNamespace
    from ipsis.nucleo.esquemas import QueryAnalysis

    class Lector(_LectorFalso):
        def leer(self, pregunta, pasajes):
            self.pregunta = pregunta
            return super().leer(pregunta, pasajes)

    texto = "En invierno se cambia el filtro cada 6 meses."
    lector = Lector("6 meses")
    motor = _Motor(lector)
    motor.idioma = cargar_paquete("es")
    actual = "¿Y en invierno?"
    interpretada = actual + " cambia filtro"
    candidato = _candidato()
    candidato.chunk.texto_fuente = texto
    candidato.chunk.offset_fin = 100 + len(texto)
    ctx = ContextoConsulta(interpretada, "s", pregunta_usuario=actual,
                           consulta=QueryAnalysis(pregunta_original=interpretada, pregunta_normalizada=interpretada,
                                                  contexto={"pregunta_usuario": actual}))
    ctx.candidatos = [candidato]
    EtapaLectura(motor).ejecutar(ctx)
    assert lector.pregunta == interpretada
    assert ctx.respuesta_exacta["texto"] == "6 meses"


def test_la_evidencia_nombra_la_subseccion_de_su_oracion():
    """Un chunk de FAQ cruza varias preguntas; la evidencia nombra la de su oración."""
    from ipsis.consulta.etapas.lectura import seccion_de

    texto = "¿Cómo cambio la clave?\nEn el portal.\n¿Qué horario tiene la Mesa?\nAtiende de 8 a 18."
    inicio = texto.index("¿Qué horario")
    chunk = ChunkRecord(chunk_id="c", doc_id="d", doc_titulo="FAQ", version="1", texto_fuente=texto,
                        texto_embedding=texto, offset_inicio=10, offset_fin=10 + len(texto),
                        seccion_path=["FAQ"],
                        metadata={"secciones": [
                            {"inicio": 10, "fin": 10 + inicio, "ruta": ["FAQ", "¿Cómo cambio la clave?"]},
                            {"inicio": 10 + inicio, "fin": 10 + len(texto), "ruta": ["FAQ", "¿Qué horario tiene la Mesa?"]},
                        ]})
    assert seccion_de(chunk, 10 + texto.index("Atiende")) == ["FAQ", "¿Qué horario tiene la Mesa?"]
    assert seccion_de(chunk, 10 + texto.index("En el portal")) == ["FAQ", "¿Cómo cambio la clave?"]
    assert seccion_de(chunk, 0) == ["FAQ"]  # fuera de toda sección: la del chunk


def _s_foco(texto: str, pregunta: str, tramo: str) -> float:
    from ipsis.consulta.etapas.seleccion import EtapaEvidencia
    from ipsis.indice.estadisticas import EstadisticasLexicas
    from ipsis.lenguaje.lexico import terminos_foco, terminos_pregunta
    from ipsis.lenguaje.paquete import cargar_paquete
    from ipsis.nucleo.esquemas import SenalesLexicas

    es = cargar_paquete("es")
    est = EstadisticasLexicas.construir([texto, "La garantía cubre 24 meses."], es)

    class _Retriever:
        def estadisticas_lexico(self):
            return est

    class _Verificador:
        def verificar(self, evidencias, candidatos):
            return LiteralOffsetsVerifier().verificar(evidencias, candidatos)

    motor = _Motor(_LectorFalso(tramo))
    motor.retriever, motor.idioma, motor.verificador = _Retriever(), es, _Verificador()
    ctx = ContextoConsulta(pregunta=pregunta, id_sesion="s")
    ctx.terminos_pregunta = terminos_pregunta(pregunta, es)
    ctx.terminos_foco = terminos_foco(ctx.terminos_pregunta, est)
    ctx.lexicas = SenalesLexicas(terminos_foco=ctx.terminos_foco)
    ctx.candidatos = [RetrievalCandidate(
        chunk=ChunkRecord(chunk_id="c1", doc_id="d", doc_titulo="D", version="1", texto_fuente=texto,
                          texto_embedding=texto, offset_inicio=0, offset_fin=len(texto)),
        signals=RetrievalSignals(fusion_score=0.5, fusion_rank=1))]
    ctx.diagnostico["senales_lexicas"] = {}
    EtapaLectura(motor).ejecutar(ctx)
    EtapaEvidencia(motor).ejecutar(ctx)
    return ctx.lexicas.s_foco


def test_la_oracion_previa_del_parrafo_enmarca_el_foco():
    """«Si no rinde a tiempo…» habla de los gastos que nombra la oración anterior."""
    texto = "Al regresar, el funcionario rinde los gastos en cinco días. Si no rinde a tiempo, el monto se descuenta."
    assert _s_foco(texto, "¿Qué pasa si no rindo los gastos a tiempo?", "el monto se descuenta") == 1.0


def test_la_oracion_previa_no_cruza_un_salto_de_linea():
    """Otro ítem o un título no es el contexto de la oración."""
    texto = "Al regresar, el funcionario rinde los gastos en cinco días.\nSi no rinde a tiempo, el monto se descuenta."
    assert _s_foco(texto, "¿Qué pasa si no rindo los gastos a tiempo?", "el monto se descuenta") < 1.0


def test_lectura_semantica_lee_la_oracion_que_ordena_la_fusion_y_no_los_titulos():
    """El cross-encoder y el coseno ordenan; los títulos del FAQ nunca se leen."""
    from ipsis.consulta.etapas.lectura import ventanas_semanticas

    texto = ("¿Cómo cambio mi clave?\nIngrese al portal de autoservicio y elija cambiar.\n"
             "¿Cada cuánto vence?\nLa contraseña vence cada 90 días sin aviso.")
    t1, t2 = texto.index("¿Cada cuánto"), texto.index("La contraseña")
    chunk = ChunkRecord(chunk_id="c", doc_id="d", doc_titulo="FAQ", version="1", texto_fuente=texto,
                        texto_embedding=texto, offset_inicio=0, offset_fin=len(texto),
                        metadata={"secciones": [
                            {"inicio": texto.index("Ingrese"), "fin": t1, "ruta": ["FAQ", "¿Cómo cambio mi clave?"]},
                            {"inicio": t2, "fin": len(texto), "ruta": ["FAQ", "¿Cada cuánto vence?"]}]})
    candidato = RetrievalCandidate(chunk=chunk, signals=RetrievalSignals(fusion_score=0.5, fusion_rank=1))

    class _Reranker:  # puntúa alto la oración del portal, como el cross-encoder real
        def puntuar(self, _q, textos):
            return [5.0 if "portal" in x else (9.0 if "¿" in x.split(". ", 1)[-1] else 0.0) for x in textos]

    class _Codificador:
        def codificar_documentos(self, textos):
            return [[1.0, 0.0] if "portal" in x else [0.0, 1.0] for x in textos]

    class _Retriever:
        codificador = _Codificador()

        def vector_consulta(self, _q):
            return [1.0, 0.0]

        def estadisticas_lexico(self):
            return None

    motor = _Motor(None)
    motor.reranker, motor.retriever, motor.idioma = _Reranker(), _Retriever(), None
    ventanas = ventanas_semanticas(motor, "olvidé la clave, cómo la cambio?", [candidato], n=1)
    assert [texto[a:b] for _, a, b in ventanas] == ["Ingrese al portal de autoservicio y elija cambiar."]
    motor.reranker = None  # sin reranker: se usa la ventana léxica
    assert ventanas_semanticas(motor, "x", [candidato]) == []


def test_lectura_semantica_no_lee_la_presentacion_de_un_documento_con_secciones():
    """«Establece las condiciones de la beca… para funcionarios» repite el tema y no responde."""
    from ipsis.consulta.etapas.lectura import ventanas_semanticas

    texto = ("Establece las condiciones de la beca de perfeccionamiento para funcionarios.\n"
             "Pueden postular los funcionarios con contrato indefinido.")
    t = texto.index("Pueden")
    chunk = ChunkRecord(chunk_id="c", doc_id="d", doc_titulo="Beca", version="1", texto_fuente=texto,
                        texto_embedding=texto, offset_inicio=0, offset_fin=len(texto),
                        metadata={"secciones": [
                            {"inicio": 0, "fin": t, "ruta": ["Beca"]},
                            {"inicio": t, "fin": len(texto), "ruta": ["Beca", "Requisitos"]}]})
    candidato = RetrievalCandidate(chunk=chunk, signals=RetrievalSignals(fusion_score=0.5, fusion_rank=1))

    class _Reranker:  # prefiere la presentación, como el cross-encoder real
        def puntuar(self, _q, textos):
            return [9.0 if "Establece" in x else 1.0 for x in textos]

    class _Codificador:
        def codificar_documentos(self, textos):
            return [[1.0, 0.0] if "Establece" in x else [0.0, 1.0] for x in textos]

    class _Retriever:
        codificador = _Codificador()

        def vector_consulta(self, _q):
            return [1.0, 0.0]

        def estadisticas_lexico(self):
            return None

    motor = _Motor(None)
    motor.reranker, motor.retriever, motor.idioma = _Reranker(), _Retriever(), None
    ventanas = ventanas_semanticas(motor, "¿Quiénes pueden postular a la beca?", [candidato], n=3)
    assert [texto[a:b] for _, a, b in ventanas] == ["Pueden postular los funcionarios con contrato indefinido."]
