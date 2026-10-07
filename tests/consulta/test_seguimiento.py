"""Memoria de la conversación y preguntas de seguimiento (ipsis.consulta.seguimiento)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ipsis.consulta.seguimiento import MemoriaConversacion
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
    resolutor = MemoriaConversacion()
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


def test_genericas_de_memoria_no_quitan_contenido_de_la_respuesta(es):
    from ipsis.lenguaje.consultas import terminos_de_contenido

    est = _estadisticas(es, "Las muestras de sangre se guardan a cuatro grados.", "El tiempo de espera es dos días.")
    memoria = MemoriaConversacion()
    inicio = memoria.resolver("¿A qué temperatura guardan las muestras de sangre?", "s", es, est)
    memoria.recordar_evidencia("s", set(terminos("Las muestras de sangre se guardan a cuatro grados.", es)), turno=inicio.turno)
    seguimiento = memoria.resolver("¿por cuánto tiempo?", "s", es, est)
    assert seguimiento.seguimiento and "sangre" in seguimiento.heredado
    # 'tiempo' existe en otro tema del corpus: no abre un tema distinto,
    # pero la pregunta que se responde conserva ese término de contenido.
    assert terminos("tiempo", es)[0] in terminos_de_contenido("¿por cuánto tiempo?", es, est)


def test_cada_sesion_recuerda_lo_suyo(es):
    est = _estadisticas(es, *CORPUS)
    resolutor = MemoriaConversacion()
    resolutor.resolver("¿Qué pasa si el proveedor rechaza la orden?", "a", es, est)
    assert not resolutor.resolver("¿y con 90?", "b", es, est).seguimiento
    assert resolutor.resolver("¿y con 90?", "a", es, est).seguimiento


def test_la_memoria_tiene_tope(es):
    est = _estadisticas(es, *CORPUS)
    resolutor = MemoriaConversacion(max_sesiones=2)
    for sesion in ("a", "b", "c"):
        resolutor.resolver("¿Qué pasa si el proveedor rechaza la orden?", sesion, es, est)
    assert not resolutor.resolver("¿y con 90?", "a", es, est).seguimiento  # «a» ya salió


def test_una_pregunta_fuera_de_dominio_no_hereda(es):
    _, r = _conversar(es, ("¿Qué pasa si el proveedor rechaza la orden?", CORPUS[0]),
                      ("¿Cuál es la capital de Mongolia?", ""))
    assert not r.seguimiento


# Los mismos turnos en inglés y portugués: cada paquete trae sus marcadores («and», «e»).
OTROS = {
    "en": (("The supplier has two business days to accept the Purchase Order. If the supplier rejects the "
            "Purchase Order, the Supervisor cancels the order.",
            "The library opens Monday to Friday.",
            "The coffee maker warranty lasts 24 months."),
           ("What happens if the supplier rejects the order?", "and with 90?", "and if they accept it?",
            "How long does the coffee maker warranty last?", "What are the library opening hours?")),
    "pt": (("O fornecedor tem dois dias úteis para aceitar a Ordem de Compra. Se o fornecedor recusar a "
            "Ordem de Compra, o Supervisor cancela a ordem.",
            "A biblioteca abre de segunda a sexta.",
            "A garantia da cafeteira dura 24 meses."),
           ("O que acontece se o fornecedor recusar a ordem?", "e com 90?", "e se ele aceitar?",
            "Quanto dura a garantia da cafeteira?", "Qual é o horário da biblioteca?")),
}


@pytest.mark.parametrize("idioma", ["en", "pt"])
def test_seguimiento_en_otros_idiomas(idioma):
    paquete = cargar_paquete(idioma)
    corpus, (pregunta, con_90, acepta, garantia, biblioteca) = OTROS[idioma]
    est = _estadisticas(paquete, *corpus)

    def turno(resolutor, texto, evidencia):
        r = resolutor.resolver(texto, "s", paquete, est)
        resolutor.recordar_evidencia("s", set(terminos(evidencia, paquete)))
        return r

    resolutor = MemoriaConversacion()
    turno(resolutor, pregunta, corpus[0])
    r = turno(resolutor, con_90, "")
    assert r.seguimiento and r.pregunta.startswith(con_90)

    resolutor = MemoriaConversacion()
    turno(resolutor, pregunta, corpus[0])
    assert turno(resolutor, acepta, "").seguimiento

    resolutor = MemoriaConversacion()
    turno(resolutor, garantia, corpus[2])
    assert not turno(resolutor, biblioteca, "").seguimiento


# --- memoria de toda la conversación (plan V4, F4) -----------------------------------------------------

CORPUS_LARGO = (
    "El viático diario es de 45.000 pesos dentro del país y de 150 dólares en el extranjero. "
    "El funcionario solicita el viático al menos siete días antes del viaje.",
    "La Mesa de Ayuda atiende de lunes a viernes de 8:00 a 18:00 horas. "
    "La Mesa de Ayuda entrega el equipo nuevo dentro de diez días hábiles.",
    "El teletrabajo puede abarcar hasta tres días por semana. "
    "Se otorga una asignación mensual de 20.000 pesos para gastos de conexión.",
)


class Reloj:
    def __init__(self) -> None:
        self.ahora = 0.0

    def __call__(self) -> float:
        return self.ahora


def _turnos(es, memoria, *turnos, sesion="s"):
    est = _estadisticas(es, *CORPUS_LARGO)
    salida = []
    for pregunta, evidencia in turnos:
        salida.append(memoria.resolver(pregunta, sesion, es, est))
        memoria.recordar_evidencia(sesion, set(terminos(evidencia, es)))
    return salida


def test_la_conversacion_vence_por_inactividad_y_no_antes(es):
    reloj = Reloj()
    memoria = MemoriaConversacion(vencimiento_s=60, reloj=reloj)
    _turnos(es, memoria, ("¿Cuál es el viático diario dentro del país?", CORPUS_LARGO[0]))
    reloj.ahora = 59
    assert _turnos(es, memoria, ("¿y en el extranjero?", ""))[0].seguimiento
    reloj.ahora = 59 + 61  # el último uso fue a los 59
    assert not _turnos(es, memoria, ("¿y en el extranjero?", ""))[0].seguimiento
    assert len(memoria) == 1  # la vencida se olvidó; queda la que acaba de empezar


def test_la_conversacion_vence_exactamente_en_el_limite(es):
    reloj = Reloj()
    memoria = MemoriaConversacion(vencimiento_s=60, reloj=reloj)
    _turnos(es, memoria, ("¿Cuál es el viático diario?", CORPUS_LARGO[0]))
    reloj.ahora = 60
    assert len(memoria) == 0


def test_olvidar_borra_la_conversacion(es):
    memoria = MemoriaConversacion()
    _turnos(es, memoria, ("¿Cuál es el viático diario dentro del país?", CORPUS_LARGO[0]))
    memoria.olvidar("s")
    assert not _turnos(es, memoria, ("¿y en el extranjero?", ""))[0].seguimiento


def test_un_cambio_de_tema_deliberado_no_hereda_aunque_empiece_con_y(es):
    memoria = MemoriaConversacion()
    _, r = _turnos(es, memoria, ("¿Cuánto tarda la Mesa de Ayuda en entregar un equipo nuevo?", CORPUS_LARGO[1]),
                   ("¿y cuánto es el viático en el extranjero?", CORPUS_LARGO[0]))
    assert not r.seguimiento and r.accion == "tema_nuevo"


def test_retoma_un_tema_de_dos_turnos_atras(es):
    memoria = MemoriaConversacion()
    _, _, r = _turnos(es, memoria, ("¿Cuál es el viático diario dentro del país?", CORPUS_LARGO[0]),
                      ("¿Qué horario tiene la Mesa de Ayuda?", CORPUS_LARGO[1]),
                      ("volviendo al viático, ¿y en el extranjero?", ""))
    assert r.accion == "retoma" and "diario" in r.heredado


def test_una_pregunta_fuera_de_dominio_no_cambia_el_tema(es):
    memoria = MemoriaConversacion()
    _, fuera, r = _turnos(es, memoria, ("¿Cuál es el viático diario dentro del país?", CORPUS_LARGO[0]),
                          ("¿Cuál es la capital de Mongolia?", ""),
                          ("¿y en el extranjero?", ""))
    assert not fuera.seguimiento and fuera.accion == "sin_cambio"
    assert r.seguimiento and "viatico" in r.heredado


def test_el_nucleo_del_tema_sobrevive_a_la_compactacion(es):
    """Cuatro turnos: lo del primer seguimiento se pliega, el núcleo («teletrabajo») sigue."""
    memoria = MemoriaConversacion()
    *_, r = _turnos(es, memoria, ("¿Cuántos días por semana abarca el teletrabajo?", CORPUS_LARGO[2]),
                    ("¿y la asignación?", CORPUS_LARGO[2]),
                    ("¿y para qué gastos?", CORPUS_LARGO[2]),
                    ("¿y de cuánto es?", ""))
    assert r.seguimiento and "teletrabajo" in r.heredado and "asignacion" not in r.heredado


def test_la_memoria_es_segura_entre_hilos(es):
    import threading

    memoria = MemoriaConversacion(max_sesiones=50)
    est = _estadisticas(es, *CORPUS_LARGO)

    def conversar(n):
        for _ in range(20):
            memoria.resolver("¿Cuál es el viático diario dentro del país?", f"s{n}", es, est)
            memoria.recordar_evidencia(f"s{n}", {"viatic"})

    hilos = [threading.Thread(target=conversar, args=(n,)) for n in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert len(memoria) == 8


def test_la_compactacion_no_conserva_formas_de_turnos_antiguos(es):
    memoria = MemoriaConversacion()
    _turnos(es, memoria, ("¿Cuántos días por semana abarca el teletrabajo?", CORPUS_LARGO[2]),
            ("¿y la asignación?", CORPUS_LARGO[2]), ("¿y para qué gastos?", CORPUS_LARGO[2]))
    tema = memoria._sesiones["s"].tema
    assert set(tema.formas) <= set(tema.nucleo + tema.ultimo)
    assert "asignacion" not in tema.formas.values()


def test_evidencia_tardia_no_contamina_otro_tema_ni_una_sesion_recreada(es):
    memoria = MemoriaConversacion()
    est = _estadisticas(es, *CORPUS_LARGO)
    viejo = memoria.resolver("¿Cuál es el viático diario?", "s", es, est)
    memoria.resolver("¿Qué horario tiene la Mesa de Ayuda?", "s", es, est)
    memoria.recordar_evidencia("s", {"extranj"}, turno=viejo.turno)
    assert not memoria._sesiones["s"].tema.respuestas
    memoria.olvidar("s")
    memoria.resolver("¿Cuánto abarca el teletrabajo?", "s", es, est)
    memoria.recordar_evidencia("s", {"extranj"}, turno=viejo.turno)
    assert not memoria._sesiones["s"].tema.respuestas


def test_evidencias_vencidas_o_vacias_no_desplazan_pasajes_utiles(es):
    reloj = Reloj()
    memoria = MemoriaConversacion(vencimiento_s=60, reloj=reloj)
    _turnos(es, memoria, ("¿Cuál es el viático diario?", CORPUS_LARGO[0]))
    memoria.recordar_evidencia("s", set())
    assert len(memoria._sesiones["s"].tema.respuestas) == 1
    reloj.ahora = 61
    memoria.recordar_evidencia("s", {"extranj"})
    assert len(memoria) == 0


def test_vocabulario_guarda_solo_los_ultimos_tres_pasajes(es):
    memoria = MemoriaConversacion()
    _turnos(es, memoria, ("¿Cuál es el viático diario?", ""))
    for n in range(5):
        memoria.recordar_evidencia("s", {f"palabra{n}"})
    tema = memoria._sesiones["s"].tema
    assert tema.respuestas == [frozenset({f"palabra{n}"}) for n in (2, 3, 4)]
