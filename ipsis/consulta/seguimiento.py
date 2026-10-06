"""Preguntas de seguimiento: «¿y con 90?» después de «¿qué pasa sobre 100 UTM?».

Cada pregunta se procesa sola, y una de seguimiento casi no trae tema: «¿y si
la acepta?» no dice qué se acepta. Este resolvedor recuerda, por sesión, la
última pregunta efectiva y, si la nueva es de seguimiento, le suma las
palabras de tema de aquella: «¿y si la acepta? proveedor rechaza orden». Es
la *pregunta interpretada*: con ella se busca, se selecciona y decide la
política; la respuesta sigue siendo texto literal del documento.

Una pregunta es de seguimiento si hay un turno anterior en la sesión y:

- no trae ningún término de tema que exista en el corpus y empieza con un
  marcador del idioma («¿y con 90?») o tiene uno solo («¿cuánto cuesta?»); una
  pregunta fuera de dominio («¿Cuál es la capital de Mongolia?») no hereda; o
- trae uno o dos, todos están en el fragmento que respondió el turno anterior
  («acepta» en el pasaje de la orden de compra; «pagan» y «días» en el del
  reembolso), y la pregunta es corta o empieza con un marcador del idioma
  («y», «entonces», «and», «e se»: ``seguimiento`` en el paquete).

Una pregunta con tema propio fuera de lo anterior («¿Qué horario tiene la
biblioteca?» tras hablar de la garantía) nunca hereda. Lo heredado ayuda a
buscar; la política exige los términos propios del usuario (ver
``EtapaFiltros``), así que «¿y si la acepta?» no se responde con la oración del
rechazo.

La memoria vive en el proceso (como la de las variantes de tono): con varios
workers, cada uno recuerda lo suyo. Guarda texto de preguntas, nunca respuestas.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class Resolucion:
    pregunta: str  # la que se procesa (la interpretada, si es de seguimiento)
    seguimiento: bool = False
    heredado: str = ""  # las palabras que se sumaron


class ResolutorSeguimiento:
    def __init__(self, max_sesiones: int = 1024) -> None:
        self.max_sesiones = max_sesiones
        # id_sesion -> (pregunta efectiva, raíces de los fragmentos que la respondieron)
        self._ultimas: OrderedDict[str, tuple[str, frozenset[str]]] = OrderedDict()
        self._candado = threading.Lock()

    def _anterior(self, id_sesion: str) -> tuple[str, frozenset[str]] | None:
        with self._candado:
            return self._ultimas.get(id_sesion)

    def recordar(self, id_sesion: str, pregunta: str, vocabulario: frozenset[str] = frozenset()) -> None:
        with self._candado:
            self._ultimas.pop(id_sesion, None)
            self._ultimas[id_sesion] = (pregunta, vocabulario)
            while len(self._ultimas) > self.max_sesiones:
                self._ultimas.popitem(last=False)

    def recordar_evidencia(self, id_sesion: str, raices: set[str]) -> None:
        """Las raíces de los fragmentos que respondieron este turno (las usa el siguiente)."""
        with self._candado:
            if id_sesion in self._ultimas:
                pregunta, _ = self._ultimas[id_sesion]
                self._ultimas[id_sesion] = (pregunta, frozenset(raices))

    def resolver(self, pregunta: str, id_sesion: str, paquete, estadisticas) -> Resolucion:
        """La pregunta a procesar y, si es de seguimiento, lo que heredó. Recuerda
        la pregunta resultante para el turno siguiente."""
        resolucion = self._resolver(pregunta, self._anterior(id_sesion), paquete, estadisticas)
        self.recordar(id_sesion, resolucion.pregunta)
        return resolucion

    @staticmethod
    def _resolver(pregunta: str, previo: tuple[str, frozenset[str]] | None, paquete,
                  estadisticas) -> Resolucion:
        if not previo or paquete is None or estadisticas is None:
            return Resolucion(pregunta)
        anterior, vocabulario = previo
        from ipsis.lenguaje.consultas import plano, terminos_de_contenido
        from ipsis.lenguaje.texto import terminos

        df = getattr(estadisticas, "df", {})
        propios = terminos_de_contenido(pregunta, paquete, estadisticas)
        con_tema = [t for t in propios if df.get(t, 0) > 0]
        texto = plano(pregunta)
        marcadores = [plano(m) for m in getattr(paquete, "seguimiento", None) or []]
        empieza_con_marcador = any(texto == m or texto.startswith(m + " ") for m in marcadores)
        if not con_tema:
            # Sin tema del corpus puede ser «¿y con 90?» o una pregunta fuera de
            # dominio («¿Cuál es la capital de Mongolia?»): solo hereda si empieza
            # con un marcador o es mínima («¿cuánto cuesta?»).
            if not ((empieza_con_marcador and len(propios) <= 3) or len(propios) <= 1):
                return Resolucion(pregunta)
        elif (len(con_tema) > 2 or any(t not in vocabulario for t in con_tema)
              or (len(propios) > 2 and not empieza_con_marcador)):
            return Resolucion(pregunta)
        # Las palabras de tema del turno anterior que la pregunta no trae, en su forma escrita.
        temas_previos = set(terminos_de_contenido(anterior, paquete, estadisticas)) - set(propios)
        heredado = []
        for palabra in plano(anterior).split():
            raices = terminos(palabra, paquete)
            if raices and raices[0] in temas_previos and palabra not in heredado:
                heredado.append(palabra)
        if not heredado:
            return Resolucion(pregunta)
        texto_heredado = " ".join(heredado)
        return Resolucion(f"{pregunta.rstrip()} {texto_heredado}", seguimiento=True, heredado=texto_heredado)


__all__ = ["Resolucion", "ResolutorSeguimiento"]
