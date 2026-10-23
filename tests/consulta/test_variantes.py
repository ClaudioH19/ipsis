"""Elección de variantes del tono por sesión y su trazabilidad (P12.2)."""
from __future__ import annotations

import pytest

from ipsis.consulta.variantes import SelectorVariantes, elegir, en_consulta, usadas

OPCIONES = ["a", "b", "c", "d", "e"]


def _secuencia(selector, sesion, n, situacion="no_answer"):
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
    assert elegir("no_answer", OPCIONES, "x") == elegir("no_answer", OPCIONES, "x")
    assert elegir("no_answer", OPCIONES, "x", evitar={elegir("no_answer", OPCIONES, "x")}) != \
        elegir("no_answer", OPCIONES, "x")
    assert usadas() == (None, [])


def test_registra_el_plantilla_id_y_respeta_variedad_fija():
    selector = SelectorVariantes(tono="formal")
    with en_consulta(selector, "s"):
        texto = elegir("farewell", OPCIONES)
        tono, ids = usadas()
    assert tono == "formal" and ids == [f"formal.farewell.{OPCIONES.index(texto) + 1}"]
    fija = SelectorVariantes(fija=True)
    assert _secuencia(fija, "s", 3) == ["a", "a", "a"]


def test_la_memoria_de_sesiones_es_acotada():
    selector = SelectorVariantes(max_sesiones=3)
    for i in range(10):
        selector.nuevo_turno(f"s{i}")
    assert list(selector._sesiones) == ["s7", "s8", "s9"]


