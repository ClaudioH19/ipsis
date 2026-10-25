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
