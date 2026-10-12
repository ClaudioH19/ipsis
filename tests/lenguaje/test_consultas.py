"""Comprensión determinista de la consulta (ipsis.lenguaje.consultas)."""
from __future__ import annotations

import pytest

from ipsis.lenguaje.consultas import comprender, peso_pista, plano, terminos_de_contenido
from ipsis.lenguaje.paquete import cargar_paquete


@pytest.fixture(scope="module")
def es():
    return cargar_paquete("es")


@pytest.mark.parametrize(("pregunta", "intencion"), [
    ("cuando empieza la compra?", "inicio"),
    ("¿Cuándo parte la compra?", "inicio"),
    ("¿Desde cuándo se hace la compra?", "inicio"),
    ("¿En qué momento se realiza la compra?", "inicio"),
    ("¿Cuándo vence la garantía?", "fin"),
    ("¿Qué pasa si el proveedor rechaza la orden?", "consecuencia"),
    ("¿Quién firma la Resolución?", "responsable"),
    ("¿Qué documentos se necesitan?", "requisito"),
    ("¿Cómo se pide un reembolso?", "procedimiento"),
    ("¿Desde qué monto se necesita una Resolución?", "umbral"),
    ("¿Cuánto dura la garantía?", "duracion"),
    ("¿Cuál es el horario de la biblioteca?", None),  # sin intención: todo sigue como antes
])
def test_reconoce_la_relacion_que_se_pregunta(es, pregunta, intencion):
    assert comprender(pregunta, es).intencion == intencion


def test_las_palabras_de_la_relacion_no_son_tema(es):
    """«empieza» no está en la oración que responde: no debe contar como término ausente."""
    assert terminos_de_contenido("cuando empieza la compra?", es) == ["compr"]
    assert "garanti" in terminos_de_contenido("¿Cuánto dura la garantía?", es)
    # Si la pregunta fuera solo la relación, se dejan sus términos.
    assert terminos_de_contenido("¿cuándo empieza?", es)


def test_la_pista_pesa_mas_al_comienzo_de_la_oracion(es):
    inicio = comprender("cuando empieza la compra?", es)
    assert peso_pista("Una vez aprobado el formulario, se realizará la compra.", inicio) == 1.0
    assert peso_pista("La compra requiere una resolución antes de emitir la orden.", inicio) == 0.5
    assert peso_pista("El supervisor envía la orden al proveedor.", inicio) == 0.0
    # Como palabra completa: «tras» no calza dentro de «contrasta».
    assert peso_pista("El informe contrasta los precios.", inicio) == 0.0


def test_un_idioma_sin_intenciones_no_cambia_nada():
    sin = cargar_paquete("en").model_copy(update={"intenciones": {}})
    assert comprender("when does the purchase start?", sin).intencion is None


def test_plano_quita_tildes_y_signos():
    assert plano("¿Cuándo EMPIEZA   la compra?") == "cuando empieza la compra"


def test_la_seleccion_elige_la_oracion_que_dice_cuando(es):
    """El caso que motivó la capa: «compra» está en todas; la que responde empieza con «Una vez»."""
    from ipsis.consulta.etapas.seleccion import seleccionar_texto_pertinente
    from ipsis.lenguaje.entidades import usar_idioma

    texto = ("El Supervisor de Compras envía la Orden de Compra al proveedor. "
             "Si el proveedor rechaza la Orden de Compra, se inicia una nueva compra con otro proveedor. "
             "Una vez aprobado el Formulario de Requerimiento, se realizará la compra del producto.")
    with usar_idioma(es):
        r = seleccionar_texto_pertinente("cuando empieza la compra?", texto, 0, 90)
    assert r.texto.startswith("Una vez aprobado el Formulario de Requerimiento")


def test_la_evidencia_del_lector_no_arrastra_titulos_ni_queda_en_uno():
    from ipsis.consulta.etapas.lectura import oracion_que_contiene

    texto = "El formulario se envía.\n6.3 Procedimiento de Compra\nUna vez aprobado, se realizará la compra. Luego sigue."
    i = texto.index("Una vez")
    a, b = oracion_que_contiene(texto, i, i + 8)
    assert texto[a:b] == "Una vez aprobado, se realizará la compra."  # sin el título de arriba
    i = texto.index("Procedimiento")
    a, b = oracion_que_contiene(texto, i, i + 13)  # el lector marcó el título
    assert texto[a:b] == "6.3 Procedimiento de Compra\nUna vez aprobado, se realizará la compra."


def test_el_lector_lee_el_candidato_con_la_pista_aunque_el_reranker_lo_baje(es):
    from types import SimpleNamespace

    from ipsis.consulta.etapas.lectura import _candidato_por_pista
    from ipsis.lenguaje.entidades import usar_idioma

    def candidato(cid, texto):
        return SimpleNamespace(chunk=SimpleNamespace(chunk_id=cid, texto_fuente=texto))

    motor = SimpleNamespace(idioma=es, retriever=None)
    leidos = [candidato("horarios", "La biblioteca abre de lunes a viernes. Las compras se registran en el portal.")]
    resto = [candidato("orden", "El Supervisor de Compras envía la Orden de Compra al proveedor."),
             candidato("inicio", "Una vez aprobado el formulario, se realizará la compra.")]
    with usar_idioma(es):
        assert _candidato_por_pista(motor, "cuando empieza la compra?", leidos, resto).chunk.chunk_id == "inicio"
        # Sin intención reconocida, el lector lee lo de siempre.
        assert _candidato_por_pista(motor, "¿Qué es la compra?", leidos, resto) is None


def test_una_palabra_de_la_relacion_que_esta_en_el_corpus_se_queda():
    """«até» está en la respuesta («…o reembolso até 30 dias…»): suma cobertura."""
    from types import SimpleNamespace

    pt = cargar_paquete("pt")
    con_ate = SimpleNamespace(df={"ate": 3, "reembols": 2, "ped": 2})
    assert "ate" in terminos_de_contenido("Até quando posso pedir o reembolso?", pt, con_ate)
    assert "ate" not in terminos_de_contenido("Até quando posso pedir o reembolso?", pt, SimpleNamespace(df={}))


def test_un_sinonimo_reemplaza_solo_la_palabra_que_falta_en_el_corpus(es):
    """«necesita» no está y «requieren» sí: se busca y se mide con «requieren»."""
    from types import SimpleNamespace

    from ipsis.lenguaje.consultas import sinonimos_presentes
    from ipsis.lenguaje.texto import terminos

    df = {t: 1 for t in terminos("Las compras superiores a 100 UTM requieren una Resolución.", es)}
    est = SimpleNamespace(df=df)
    pregunta = "¿Desde qué monto se necesita una Resolución?"
    assert list(sinonimos_presentes(pregunta, es, est)) == ["necesita"]
    assert "requieren" in sinonimos_presentes(pregunta, es, est)["necesita"]
    # La relación no se expande: «empieza» no trae «inicia».
    df.update({t: 1 for t in terminos("se inicia una nueva compra", es)})
    assert sinonimos_presentes("cuando empieza la compra?", es, est) == {}
    tq = terminos_de_contenido(pregunta, es, est)
    assert set(terminos("requieren", es)) <= set(tq) and not set(terminos("necesita", es)) & set(tq)
    # Si la palabra ya está en el corpus, no se toca.
    df.update({t: 1 for t in terminos("necesita", es)})
    assert sinonimos_presentes(pregunta, es, est) == {}


def test_las_palabras_genericas_no_son_tema_pero_cuentan_para_la_cobertura(es):
    """«hace» no es de qué se habla en «¿Desde cuándo se hace la compra?»."""
    from ipsis.lenguaje.consultas import terminos_genericos
    from ipsis.lenguaje.texto import terminos

    hac = terminos("hace", es)[0]
    assert hac in terminos_genericos(es)
    assert hac not in terminos_de_contenido("¿Desde cuándo se hace la compra?", es)
    assert hac in terminos_de_contenido("¿Desde cuándo se hace la compra?", es, sin_genericas=False)
    # Si no hubiera otra cosa, se dejan.
    assert terminos_de_contenido("¿Qué hace?", es)


def test_un_sustantivo_derivado_o_un_sinonimo_cuentan_para_el_foco():
    """«Who signs…?» se responde con «…for signature»; «need» con «require»."""
    from ipsis.lenguaje.consultas import equivalentes
    from ipsis.lenguaje.texto import terminos

    en = cargar_paquete("en")
    oracion = terminos("Purchases above 100 UTM require a Resolution sent for signature.", en)
    assert {terminos("signs", en)[0], terminos("need", en)[0]} <= set(equivalentes(oracion, en))
    pt = cargar_paquete("pt")
    assert terminos("assina", pt)[0] in equivalentes(terminos("para assinatura", pt), pt)


def test_la_oracion_con_el_verbo_de_la_pregunta_no_gana_a_la_que_dice_cuando():
    """«…starts a new purchase» tiene «start», pero la que responde es «Once…»."""
    from ipsis.consulta.etapas.seleccion import seleccionar_texto_pertinente
    from ipsis.indice.estadisticas import EstadisticasLexicas
    from ipsis.lenguaje.entidades import usar_idioma

    en = cargar_paquete("en")
    once = "Once the form has been approved by the Head of Purchasing, the product will be purchased."
    rechazo = ("If the supplier rejects the Purchase Order, the Purchasing Officer starts a new purchase "
               "with another supplier.")
    texto = f"{once} {rechazo}"
    with usar_idioma(en):
        est = EstadisticasLexicas.construir([once, rechazo], en)
        r = seleccionar_texto_pertinente("when does the purchase start?", texto, 0, 100, estadisticas=est)
    assert r.texto.startswith("Once the form")


@pytest.mark.parametrize(("idioma", "pregunta", "cuantificador"), [
    ("pt", "Quantos dias o fornecedor tem para aceitar a Ordem de Compra?", "quantos"),
    ("en", "How often is the remote work agreement reviewed?", "often"),
    ("en", "how long can i keep a book", "long"),
])
def test_los_cuantificadores_de_la_pregunta_no_son_tema(idioma, pregunta, cuantificador):
    """«quantos» u «often» son la forma de la pregunta: exigirlos en la oración rechazaba
    «O fornecedor tem dois dias úteis…». Siguen contando para s_oov y s_cov: sin lector,
    light no tiene otra señal de que «how often» pide un período."""
    from ipsis.lenguaje.consultas import terminos_genericos
    from ipsis.lenguaje.texto import terminos

    paquete = cargar_paquete(idioma)
    raiz = terminos(cuantificador, paquete)[0]
    assert raiz in terminos_genericos(paquete)
    assert raiz not in terminos_de_contenido(pregunta, paquete)


@pytest.mark.parametrize(("idioma", "pregunta", "abreviatura"), [
    ("es", "a q hora se riega el invernadero", "q"),
    ("pt", "q horas vc abre pra gente", "pra"),
    ("en", "What happens if I don't report my expenses on time?", "t"),
    ("en", "can u tell me ur hours pls", "ur"),
])
def test_abreviaturas_y_contracciones_no_cuentan_como_palabras_ausentes(idioma, pregunta, abreviatura):
    """«q», «pra» o el «t» de «don't» son palabras funcionales, no contenido ausente del corpus."""
    paquete = cargar_paquete(idioma)
    assert abreviatura not in terminos_de_contenido(pregunta, paquete, sin_genericas=False)


@pytest.mark.parametrize(("idioma", "unidad"), [("es", "tiempo"), ("pt", "tempo"), ("en", "time")])
def test_el_tiempo_es_generico_como_las_demas_unidades(idioma, unidad):
    """«A cada quanto tempo…» no habla del tiempo; «a tiempo» sí cuenta para la cobertura."""
    from ipsis.lenguaje.consultas import terminos_genericos
    from ipsis.lenguaje.texto import terminos

    paquete = cargar_paquete(idioma)
    assert terminos(unidad, paquete)[0] in terminos_genericos(paquete)


@pytest.mark.parametrize(("idioma", "pregunta", "procedimiento", "periodo"), [
    ("es", "cada cuanto hay q cambiar la contrasena",
     "Ingrese al portal y seleccione «Cambiar contraseña».", "La contraseña vence cada 90 días."),
    ("en", "How often should I change my password?",
     'Go to the portal and select "Change password".', "The password expires every 90 days."),
    ("pt", "A cada quanto tempo troco a senha?",
     "Acesse o portal e selecione «Trocar senha».", "A senha expira a cada 90 dias."),
])
def test_una_pregunta_de_frecuencia_exige_un_periodo_en_la_respuesta(idioma, pregunta, procedimiento, periodo):
    """«¿Cada cuánto…?» se responde con un período. Light respondía con el procedimiento
    para cambiar la contraseña: todas las palabras de la pregunta estaban ahí."""
    from ipsis.consulta.etapas.seleccion import forma_ausente

    paquete = cargar_paquete(idioma)
    assert comprender(pregunta, paquete).intencion == "frecuencia"
    assert forma_ausente(paquete, pregunta, procedimiento)
    assert not forma_ausente(paquete, pregunta, periodo)
    # Una intención sin exige_pista no impone forma.
    assert not forma_ausente(paquete, "¿Quién firma la Resolución?" if idioma == "es" else "x", procedimiento)


@pytest.mark.parametrize(("idioma", "pregunta", "oracion", "esperado"), [
    ("es", "¿Qué asignación se da para gastos de electricidad?",
     "Se otorga una asignación de 20.000 pesos para gastos de conexión.", "electricidad≠conexion"),
    ("pt", "Qual auxílio é concedido para despesas de energia?",
     "É concedido um auxílio de 20.000 pesos para despesas de conexão.", "energia≠conexao"),
    ("en", "What allowance is paid for electricity costs?",
     "An allowance of 20,000 pesos is paid for connection costs.", "electricity≠connection"),
    ("en", "Who buys the bus tickets?", "Air tickets are bought by the Travel Unit.", "bus≠air"),
    # La vecindad sin preposición no basta: «carro elétrico» es un sinónimo, no otra cosa.
    ("pt", "Onde carrego o carro elétrico?", "Os veículos elétricos carregam nos pontos de recarga.", None),
    # Sin conflicto: un número es el dato, «many» es genérica y un verbo distinto no es modificador.
    ("en", "How many days does the supplier have?", "The supplier has two business days.", None),
    ("es", "¿Cuántos caracteres debe tener la clave?", "La clave debe tener 12 caracteres.", None),
    ("es", "¿Cuándo me depositan el viático?", "Finanzas transfiere el viático dos días antes.", None),
])
def test_mismo_nucleo_con_otro_modificador_es_otra_cosa(idioma, pregunta, oracion, esperado):
    """«gastos de electricidad» no se responde con «gastos de conexión»."""
    from ipsis.consulta.etapas.seleccion import modificador_distinto
    from ipsis.indice.estadisticas import EstadisticasLexicas

    paquete = cargar_paquete(idioma)
    est = EstadisticasLexicas.construir([oracion, "Texto de relleno sin relación."], paquete)
    assert modificador_distinto(paquete, pregunta, oracion, est) == esperado


def test_el_modificador_distinto_se_busca_tambien_en_los_titulos_de_la_seccion():
    """«beca de idiomas» frente al título «Beca de Perfeccionamiento»."""
    from ipsis.consulta.etapas.seleccion import modificador_distinto
    from ipsis.indice.estadisticas import EstadisticasLexicas

    paquete = cargar_paquete("es")
    oracion = "Las postulaciones se reciben entre el 1 y el 30 de junio."
    titulos = ["Bases de la Beca de Perfeccionamiento", "Postulación"]
    est = EstadisticasLexicas.construir([oracion, *titulos], paquete)
    pregunta = "¿Hasta cuándo puedo postular a la beca de idiomas?"
    assert modificador_distinto(paquete, pregunta, oracion, est) is None
    assert modificador_distinto(paquete, pregunta, oracion, est, titulos) == "idiomas≠perfeccionamiento"


@pytest.mark.parametrize(("idioma", "pregunta", "sin_monto", "con_monto"), [
    ("es", "¿Cuánto cuesta cambiar el filtro?", "El filtro se cambia cada 45 días.", "El cambio cuesta $ 15.000."),
    ("es", "¿Cuánto vale el viático?", "El viático se pide siete días antes.", "El viático es de 45.000 pesos."),
    ("en", "How much does it cost to change the filter?", "Change the filter every 45 days.", "It costs USD 40."),
    ("en", "How much does return shipping cost?", "Returns are accepted for 30 days.", "Return shipping is free."),
    ("pt", "Quanto custa trocar o filtro?", "Troque o filtro a cada 45 dias.", "Custa R$ 50."),
])
def test_una_pregunta_de_costo_exige_un_monto(idioma, pregunta, sin_monto, con_monto):
    """«¿Cuánto cuesta…?» no se responde con «cada 45 días» aunque hable del filtro."""
    from ipsis.consulta.etapas.seleccion import forma_ausente

    paquete = cargar_paquete(idioma)
    assert comprender(pregunta, paquete).intencion == "costo"
    assert forma_ausente(paquete, pregunta, sin_monto)
    assert not forma_ausente(paquete, pregunta, con_monto)


@pytest.mark.parametrize(("idioma", "indefinido"), [("es", "alguien"), ("pt", "alguém"), ("en", "someone"),
                                                    ("en", "anyone")])
def test_los_pronombres_indefinidos_son_genericos(idioma, indefinido):
    """«What happens if someone parks without a permit?» se responde con «Anyone who parks…»."""
    from ipsis.lenguaje.consultas import terminos_genericos
    from ipsis.lenguaje.texto import terminos

    paquete = cargar_paquete(idioma)
    assert terminos(indefinido, paquete)[0] in terminos_genericos(paquete)


@pytest.mark.parametrize(("idioma", "pregunta", "funcional"), [
    ("pt", "quantos dias eu tenho de ferias", "eu"),
    ("pt", "posso levar minha bicicleta", "minha"),
    ("pt", "o que faço se tiver problema numa sala", "numa"),
    ("es", "usted me puede decir el horario", "usted"),
    ("en", "can i install it myself", "myself"),
])
def test_los_pronombres_personales_no_cuentan_como_palabras_ausentes(idioma, pregunta, funcional):
    """«eu», «minha», «usted» o «myself» son palabras funcionales, no contenido ausente del corpus."""
    paquete = cargar_paquete(idioma)
    assert funcional not in terminos_de_contenido(pregunta, paquete, sin_genericas=False)


@pytest.mark.parametrize(("idioma", "forma"), [("pt", "vou"), ("pt", "tiver"), ("pt", "der"), ("es", "viene")])
def test_las_formas_de_ir_tener_y_dar_son_genericas(idioma, forma):
    """«se der problema», «se eu tiver»: el verbo no es el tema de la pregunta."""
    from ipsis.lenguaje.consultas import terminos_genericos
    from ipsis.lenguaje.texto import terminos

    paquete = cargar_paquete(idioma)
    assert terminos(forma, paquete)[0] in terminos_genericos(paquete)


@pytest.mark.parametrize(("idioma", "pregunta", "apoyo"), [
    ("es", "¿Qué requisitos debo cumplir para inscribir la práctica?", "cumplir"),
    ("es", "Quisiera saber cuándo se inscribe la práctica", "saber"),
    ("en", "What requirements do I have to meet to enrol in the internship?", "meet"),
    ("en", "I would like to know when the internship opens", "know"),
    ("pt", "Que requisitos devo cumprir para me inscrever no estágio?", "cumprir"),
    ("pt", "Gostaria de saber quando abre a inscrição", "gostaria"),
])
def test_los_verbos_de_apoyo_no_son_tema(idioma, pregunta, apoyo):
    """«¿Qué requisitos debo cumplir…?» habla de la inscripción, no de cumplir: si «cumplir»
    fuera tema, la oración que responde (sin ese verbo) fallaría el foco."""
    from ipsis.lenguaje.consultas import terminos_genericos
    from ipsis.lenguaje.texto import terminos

    paquete = cargar_paquete(idioma)
    assert terminos(apoyo, paquete)[0] in terminos_genericos(paquete)


@pytest.mark.parametrize(("idioma", "pregunta", "definicion", "plazo"), [
    ("es", "cuanto dura la primera practica",
     "La práctica es una actividad formativa en una empresa.", "La práctica dura cuatro semanas."),
    ("en", "How long is the internship?",
     "The internship is a training activity in a company.", "The internship lasts four weeks."),
    ("pt", "quanto dura o estagio",
     "O estágio é uma atividade formativa numa empresa.", "O estágio dura quatro semanas."),
])
def test_una_pregunta_de_duracion_exige_un_plazo_en_la_respuesta(idioma, pregunta, definicion, plazo):
    """«¿Cuánto dura…?» se responde con un plazo, no con la oración que define el término."""
    from ipsis.consulta.etapas.seleccion import forma_ausente

    paquete = cargar_paquete(idioma)
    assert comprender(pregunta, paquete).intencion == "duracion"
    assert forma_ausente(paquete, pregunta, definicion)
    assert not forma_ausente(paquete, pregunta, plazo)
