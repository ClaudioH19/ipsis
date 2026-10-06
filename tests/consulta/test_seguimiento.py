"""Preguntas de seguimiento (ipsis.consulta.seguimiento)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipsis.consulta.seguimiento import ResolutorSeguimiento
from ipsis.lenguaje.paquete import cargar_paquete
from ipsis.lenguaje.texto import terminos


@pytest.fixture(scope="module")
def es():
    return cargar_paquete("es")


def _estadisticas(es, *textos):
    df: dict[str, int] = {}
    for texto in textos:
        for t in set(terminos(texto, es)):
            df[t] = df.get(t, 0) + 1
    return SimpleNamespace(df=df)


CORPUS = ("El proveedor tiene dos días hábiles para aceptar la Orden de Compra. Si el proveedor rechaza "
          "la Orden de Compra, el Supervisor anula la orden.",
          "La biblioteca abre de lunes a viernes.",
          "La garantía de la cafetera dura 24 meses.")


def _conversar(es, *turnos):
    est = _estadisticas(es, *CORPUS)
    resolutor = ResolutorSeguimiento()
    salida = []
    for pregunta, evidencia in turnos:
        r = resolutor.resolver(pregunta, "s", es, est)
        resolutor.recordar_evidencia("s", set(terminos(evidencia, es)))
        salida.append(r)
    return salida


def test_hereda_el_tema_si_la_pregunta_no_trae_el_suyo(es):
    _, r = _conversar(es, ("¿Qué pasa si el proveedor rechaza la orden?", CORPUS[0]), ("¿y con 90?", ""))
    assert r.seguimiento and "proveedor" in r.heredado and r.pregunta.startswith("¿y con 90?")


def test_hereda_si_lo_propio_esta_en_lo_que_respondio_el_turno_anterior(es):
    _, r = _conversar(es, ("¿Qué pasa si el proveedor rechaza la orden?", CORPUS[0]), ("¿y si la acepta?", ""))
    assert r.seguimiento


def test_una_pregunta_con_tema_nuevo_no_hereda(es):
    _, r = _conversar(es, ("¿Cuánto dura la garantía de la cafetera?", CORPUS[2]),
                      ("¿Qué horario tiene la biblioteca?", ""))
    assert not r.seguimiento and r.pregunta == "¿Qué horario tiene la biblioteca?"


def test_sin_turno_anterior_no_hay_seguimiento(es):
    (r,) = _conversar(es, ("¿y con 90?", ""))
    assert not r.seguimiento


def test_cada_sesion_recuerda_lo_suyo(es):
    est = _estadisticas(es, *CORPUS)
    resolutor = ResolutorSeguimiento()
    resolutor.resolver("¿Qué pasa si el proveedor rechaza la orden?", "a", es, est)
    assert not resolutor.resolver("¿y con 90?", "b", es, est).seguimiento
    assert resolutor.resolver("¿y con 90?", "a", es, est).seguimiento


def test_la_memoria_tiene_tope(es):
    est = _estadisticas(es, *CORPUS)
    resolutor = ResolutorSeguimiento(max_sesiones=2)
    for sesion in ("a", "b", "c"):
        resolutor.resolver("¿Qué pasa si el proveedor rechaza la orden?", sesion, es, est)
    assert not resolutor.resolver("¿y con 90?", "a", es, est).seguimiento  # «a» ya salió


def test_una_pregunta_fuera_de_dominio_no_hereda(es):
    _, r = _conversar(es, ("¿Qué pasa si el proveedor rechaza la orden?", CORPUS[0]),
                      ("¿Cuál es la capital de Mongolia?", ""))
    assert not r.seguimiento
