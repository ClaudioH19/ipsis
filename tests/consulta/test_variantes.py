"""Elección de variantes del tono por sesión y su trazabilidad (P12.2)."""
from __future__ import annotations

import pytest

from rag.consulta.variantes import SelectorVariantes, elegir, en_consulta, usadas

OPCIONES = ["a", "b", "c", "d", "e"]


def _secuencia(selector, sesion, n, situacion="sin_respuesta"):
    salida = []
    for _ in range(n):
        with en_consulta(selector, sesion):
            salida.append(elegir(situacion, OPCIONES, "misma pregunta"))
    return salida


def test_no_repite_en_turnos_seguidos_de_una_sesion():
    secuencia = _secuencia(SelectorVariantes(), "s1", 6)
    assert all(a != b for a, b in zip(secuencia, secuencia[1:]))
    assert len(set(secuencia)) > 1


def test_misma_sesion_y_turno_dan_el_mismo_texto():
    assert _secuencia(SelectorVariantes(), "s1", 6) == _secuencia(SelectorVariantes(), "s1", 6)
    assert _secuencia(SelectorVariantes(), "s1", 6) != _secuencia(SelectorVariantes(), "otra", 6)


def test_fuera_de_una_consulta_depende_solo_de_la_semilla():
    assert elegir("sin_respuesta", OPCIONES, "x") == elegir("sin_respuesta", OPCIONES, "x")
    assert elegir("sin_respuesta", OPCIONES, "x", evitar={elegir("sin_respuesta", OPCIONES, "x")}) != \
        elegir("sin_respuesta", OPCIONES, "x")
    assert usadas() == (None, [])


def test_registra_el_plantilla_id_y_respeta_variedad_fija():
    selector = SelectorVariantes(tono="formal")
    with en_consulta(selector, "s"):
        texto = elegir("despedida", OPCIONES)
        tono, ids = usadas()
    assert tono == "formal" and ids == [f"formal.despedida.{OPCIONES.index(texto) + 1}"]
    fija = SelectorVariantes(fija=True)
    assert _secuencia(fija, "s", 3) == ["a", "a", "a"]


def test_la_memoria_de_sesiones_es_acotada():
    selector = SelectorVariantes(max_sesiones=3)
    for i in range(10):
        selector.nuevo_turno(f"s{i}")
    assert list(selector._sesiones) == ["s7", "s8", "s9"]


# --- en el motor --------------------------------------------------------------------------------
@pytest.fixture
def motor():
    from rag.consulta.etapas.redaccion import cargar_plantillas
    from rag.consulta.motor import Motor
    from rag.lenguaje.paquete import cargar_paquete

    plantillas = cargar_plantillas(cargar_paquete("es"), {"nombre_asistente": "Ana",
                                                          "descripcion_dominio": "el manual"})
    return Motor(plantillas=plantillas)


def test_el_motor_varia_el_saludo_y_lo_deja_trazado(motor):
    resultados = [motor.consultar("hola", "sesion-1") for _ in range(6)]
    textos = [r.mensaje_usuario for r in resultados]
    assert all(a != b for a, b in zip(textos, textos[1:]))
    d = resultados[0].diagnostico
    assert d["tono"] == "cordial" and d["plantillas"][0].startswith("cordial.saludo.")
    assert d["contrato_http"]["categoria_conversacional"] == "saludo"


def test_categoria_conversacional_por_cada_categoria(motor):
    for pregunta, categoria in [("hola", "saludo"), ("gracias", "agradecimiento"), ("chao", "despedida"),
                                ("¿qué puedes hacer?", "capacidad")]:
        contrato = motor.consultar(pregunta, "s").diagnostico["contrato_http"]
        assert contrato["categoria_conversacional"] == categoria


def test_la_respuesta_http_publica_la_categoria_solo_si_es_conversacional(motor):
    from fastapi.testclient import TestClient

    from rag.servicio.api import crear_app

    cliente = TestClient(crear_app(motor))
    datos = cliente.post("/consultar", json={"pregunta": "hola", "id_sesion": "s"}).json()
    assert datos["estado"] == "conversacional" and datos["categoria_conversacional"] == "saludo"


def test_la_abstencion_varia_por_turno_y_queda_trazada():
    from rag.consulta.etapas.redaccion import construir_mensaje_abstencion

    selector = SelectorVariantes()
    textos, ids = [], []
    for _ in range(5):
        with en_consulta(selector, "s"):
            textos.append(construir_mensaje_abstencion("generico"))
            ids += usadas()[1]
    assert all(a != b for a, b in zip(textos, textos[1:]))
    assert all(i.startswith("cordial.sin_respuesta.") for i in ids)
    with en_consulta(selector, "s"):
        premisa = construir_mensaje_abstencion("premisa", "X900")
    assert "X900" in premisa


def test_todas_las_variantes_de_conectores_pasan_la_fidelidad():
    """El tono enmarca: con cualquier apertura o conector, la respuesta sigue siendo literal."""
    from rag.consulta.etapas.redaccion import redactar
    from rag.consulta.etapas.verificacion import verificar_fidelidad
    from rag.lenguaje.tonos import cargar_tono, tonos_disponibles

    fragmentos = [
        {"chunk_id": "c1", "texto": "El filtro se cambia cada 6 meses.", "doc_titulo": "Manual", "score": 0.9,
         "seccion_path": ["Filtro"]},
        {"chunk_id": "c2", "texto": "La garantía dura 2 años.", "doc_titulo": "Manual", "score": 0.85,
         "seccion_path": ["Garantía"], "tiene_condicion": True},
    ]
    for tono in tonos_disponibles("es"):
        paquete = cargar_tono("es", tono)
        for apertura in paquete.variantes("apertura"):
            for condicion in paquete.variantes("condicion"):
                plantillas = {"conectores": {"apertura": [apertura], "condicion": [condicion]}}
                texto = redactar(fragmentos, plantillas=plantillas, cfg_redaccion={"incluir_apertura": True})
                assert texto.startswith(apertura) and condicion in texto
                assert verificar_fidelidad(texto, fragmentos).fiel, texto
