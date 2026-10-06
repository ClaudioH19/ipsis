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
    ("¿Cuánto dura la garantía?", None),  # sin intención: todo sigue como antes
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
