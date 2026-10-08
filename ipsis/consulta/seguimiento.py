"""Memoria de la conversación: preguntas de seguimiento en toda la conversación.

Cada pregunta se procesa sola, y una de seguimiento casi no trae tema: «¿y si
la acepta?» no dice qué se acepta. Este módulo recuerda, por sesión, la
conversación como una sucesión de **temas**. Si la pregunta nueva es de
seguimiento, se le suman las palabras del tema en curso: «¿y si la acepta?
proveedor rechaza orden». Es la *pregunta interpretada*: con ella se busca, se
selecciona y decide la política; la respuesta sigue siendo texto literal del
documento.

Un tema guarda:

- su **núcleo**: los términos de la pregunta que lo abrió («viático diario»),
  que se heredan mientras el tema dure;
- los términos del **último seguimiento** («extranjero»), que se heredan en
  el turno siguiente y luego se pliegan (la compactación: lo de varios turnos
  atrás no se arrastra, el núcleo sí);
- el **vocabulario** de los pasajes que lo respondieron (los últimos tres),
  para reconocer «¿y si la acepta?» como parte de él.

Una pregunta es de seguimiento si la conversación tiene un tema y sus
términos de tema (los que existen en el corpus, sin las palabras genéricas
como «días» o «tiempo») cumplen:

- ninguno, y empieza con un marcador del idioma («¿y con 90?», «¿y cuántos
  días a la semana?») o tiene una sola palabra de contenido («¿por cuánto
  tiempo?»); una pregunta fuera de dominio («¿Cuál es la capital de
  Mongolia?») no hereda;
- con un marcador al comienzo, hasta tres, y a lo sumo uno fuera del
  vocabulario del tema («¿y la asignación?», «and how often is the agreement
  reviewed?»);
- sin marcador, uno o dos, todos en el vocabulario del tema, y la pregunta es
  corta.

Los marcadores son los ``seguimiento`` del paquete («y», «entonces», «and»,
«e»). Sin marcador no se relaja nada: «¿Qué es el teletrabajo?» después de
hablar de viáticos abre un tema nuevo.

Una pregunta con tema propio que no es del tema en curso:

- **retoma** un tema anterior si todos sus términos están en el vocabulario de
  ese tema («volviendo al viático, ¿y en el extranjero?» dos turnos después
  de hablar de la Mesa de Ayuda);
- si no, **abre un tema nuevo** y no hereda nada: un cambio de tema deliberado
  nunca arrastra el anterior, aunque empiece con «y».

Una pregunta sin tema en el corpus que no es de seguimiento («¿Cuál es la
capital de Mongolia?») no cambia el tema: el turno siguiente puede seguir
con el de antes.

Lo heredado ayuda a buscar; la política exige los términos propios del
usuario (ver ``EtapaFiltros``), así que «¿y si la acepta?» no se responde con
la oración del rechazo.

La memoria vive en el proceso: con varios workers, cada uno recuerda lo
suyo. Guarda términos de preguntas y de los pasajes que respondieron, nunca
respuestas. Una conversación sin uso por ``vencimiento_s`` se olvida, y hay
un tope de ``max_sesiones``. El widget usa un ``session_id`` nuevo en cada
carga de página: salir de la página empieza una conversación nueva.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace

VENCIMIENTO_S = 30 * 60
MAX_SESIONES = 1024
MAX_TEMAS_ANTERIORES = 4
RESPUESTAS_POR_TEMA = 3
MAX_NUCLEO = 3


@dataclass(frozen=True)
class Resolucion:
    pregunta: str  # la que se procesa (la interpretada, si es de seguimiento)
    seguimiento: bool = False
    heredado: str = ""  # las palabras que se sumaron
    # Qué hizo el turno con la conversación: «hereda» (sigue el tema), «retoma» (vuelve a
    # uno anterior), «tema_nuevo» o «sin_cambio» (sin tema en el corpus, o sin conversación).
    accion: str = "sin_cambio"
    tema: str = ""  # el núcleo del tema en curso, como lo escribió el usuario
    turno: int = 0  # permite asociar evidencia al turno que la produjo


@dataclass
class _Tema:
    nucleo: list[str]  # raíces de la pregunta que lo abrió
    ultimo: list[str] = field(default_factory=list)  # raíces propias del último seguimiento
    formas: dict[str, str] = field(default_factory=dict)  # raíz -> palabra como la escribió el usuario
    respuestas: list[frozenset[str]] = field(default_factory=list)  # vocabulario de los últimos pasajes

    def vocabulario(self) -> set[str]:
        return set(self.nucleo) | set(self.ultimo) | set().union(*self.respuestas)


@dataclass
class _Conversacion:
    tema: _Tema | None = None
    anteriores: list[_Tema] = field(default_factory=list)  # el más reciente primero
    ultimo_uso: float = 0.0
    turno: int = 0


class MemoriaConversacion:
    def __init__(self, max_sesiones: int = MAX_SESIONES, vencimiento_s: float = VENCIMIENTO_S, reloj=time.monotonic) -> None:
        self.max_sesiones = max_sesiones
        self.vencimiento_s = vencimiento_s
        self._reloj = reloj
        self._sesiones: OrderedDict[str, _Conversacion] = OrderedDict()  # la menos usada primero
        self._candado = threading.Lock()
        self._turno = 0

    # --- ciclo de vida -------------------------------------------------------------------
    def _purgar(self, ahora: float) -> None:
        while self._sesiones:
            primera = next(iter(self._sesiones.values()))
            if ahora - primera.ultimo_uso < self.vencimiento_s and len(self._sesiones) <= self.max_sesiones:
                return
            self._sesiones.popitem(last=False)

    def _conversacion(self, id_sesion: str) -> _Conversacion:
        ahora = self._reloj()
        self._purgar(ahora)
        conversacion = self._sesiones.pop(id_sesion, None) or _Conversacion()
        conversacion.ultimo_uso = ahora
        self._sesiones[id_sesion] = conversacion
        self._purgar(ahora)
        return conversacion

    def olvidar(self, id_sesion: str) -> None:
        with self._candado:
            self._sesiones.pop(id_sesion, None)

    def __len__(self) -> int:
        with self._candado:
            self._purgar(self._reloj())
            return len(self._sesiones)

    # --- turnos --------------------------------------------------------------------------
    def recordar_evidencia(self, id_sesion: str, raices: set[str], *, turno: int | None = None) -> None:
        """El vocabulario del pasaje que respondió este turno: lo suma al tema en curso."""
        with self._candado:
            self._purgar(self._reloj())
            conversacion = self._sesiones.get(id_sesion)
            if conversacion is None or conversacion.tema is None:
                return
            if not raices or (turno is not None and turno != conversacion.turno):
                return  # una respuesta tardía no contamina otro turno o una sesión recreada
            respuestas = conversacion.tema.respuestas
            respuestas.append(frozenset(raices))
            del respuestas[:-RESPUESTAS_POR_TEMA]

    def resolver(self, pregunta: str, id_sesion: str, paquete, estadisticas) -> Resolucion:
        """La pregunta a procesar y, si es de seguimiento, lo que heredó. Actualiza
        el tema de la conversación para el turno siguiente."""
        with self._candado:
            conversacion = self._conversacion(id_sesion)
            self._turno += 1
            conversacion.turno = self._turno
            if paquete is None or estadisticas is None:
                return Resolucion(pregunta, turno=conversacion.turno)
            return replace(_resolver(pregunta, conversacion, paquete, estadisticas), turno=conversacion.turno)


def _resolver(pregunta: str, conversacion: _Conversacion, paquete, estadisticas) -> Resolucion:
    from ipsis.lenguaje.consultas import plano, terminos_de_contenido, terminos_genericos
    from ipsis.lenguaje.texto import terminos

    df = getattr(estadisticas, "df", {})
    solo_memoria = set(terminos(" ".join(getattr(paquete, "genericas_memoria", None) or []), paquete))
    propios = [t for t in terminos_de_contenido(pregunta, paquete, estadisticas) if t not in solo_memoria]
    genericos = terminos_genericos(paquete) | solo_memoria
    con_tema = [t for t in propios if df.get(t, 0) > 0 and t not in genericos]
    texto = plano(pregunta)
    marcadores = [plano(m) for m in getattr(paquete, "seguimiento", None) or []]
    empieza_con_marcador = any(texto == m or texto.startswith(m + " ") for m in marcadores)
    tema = conversacion.tema

    if tema is not None:
        if not con_tema:
            # Sin tema del corpus: «¿y con 90?» sigue el tema; «¿Cuál es la capital de
            # Mongolia?» no, y tampoco lo cambia.
            if (empieza_con_marcador and len(propios) <= 3) or len(propios) <= 1:
                return _heredar(pregunta, tema, propios, paquete)
            return Resolucion(pregunta, tema=_texto_nucleo(tema))
        vocabulario = tema.vocabulario()
        en_tema = sum(t in vocabulario for t in con_tema)
        corta = len(propios) <= 2
        if ((empieza_con_marcador and len(con_tema) <= 3 and en_tema >= len(con_tema) - 1)
                or (len(con_tema) <= 2 and en_tema == len(con_tema) and corta)):
            return _heredar(pregunta, tema, propios, paquete)
        for i, anterior in enumerate(conversacion.anteriores):
            if len(con_tema) <= 3 and all(t in anterior.vocabulario() for t in con_tema):
                # Retoma un tema anterior: vuelve a ser el tema en curso.
                conversacion.anteriores.pop(i)
                conversacion.anteriores.insert(0, tema)
                conversacion.tema = anterior
                return _heredar(pregunta, anterior, propios, paquete, retoma=True)
    if con_tema:
        # Tema nuevo: el anterior queda para poder retomarlo.
        if tema is not None:
            conversacion.anteriores.insert(0, tema)
            del conversacion.anteriores[MAX_TEMAS_ANTERIORES:]
        conversacion.tema = _abrir(pregunta, con_tema, paquete, estadisticas)
        return Resolucion(pregunta, accion="tema_nuevo", tema=_texto_nucleo(conversacion.tema))
    return Resolucion(pregunta)


def _texto_nucleo(tema: _Tema) -> str:
    return " ".join(tema.formas[t] for t in tema.nucleo if t in tema.formas)


def _formas(pregunta: str, raices: list[str], paquete) -> dict[str, str]:
    from ipsis.lenguaje.consultas import plano
    from ipsis.lenguaje.texto import terminos

    formas: dict[str, str] = {}
    for palabra in plano(pregunta).split():
        r = terminos(palabra, paquete)
        if r and r[0] in raices and r[0] not in formas:
            formas[r[0]] = palabra
    return formas


def _abrir(pregunta: str, con_tema: list[str], paquete, estadisticas) -> _Tema:
    # El núcleo son los términos más específicos (mayor IDF) de la pregunta que lo abre.
    idf = getattr(estadisticas, "idf", None)
    nucleo = sorted(dict.fromkeys(con_tema), key=lambda t: -(idf(t) if callable(idf) else 0))[:MAX_NUCLEO]
    # Los términos fuera del núcleo sobreviven al primer seguimiento, igual
    # que los de cualquier otro turno. Compactar no debe perder contenido
    # de la pregunta inicial antes de que se use una sola vez.
    ultimo = [t for t in dict.fromkeys(con_tema) if t not in nucleo]
    return _Tema(nucleo=nucleo, ultimo=ultimo, formas=_formas(pregunta, nucleo + ultimo, paquete))


def _heredar(pregunta: str, tema: _Tema, propios: list[str], paquete, retoma: bool = False) -> Resolucion:
    # El IDF decide qué guardar, no el orden lingüístico de la pregunta.
    vigentes = set(tema.nucleo + tema.ultimo)
    heredado = [t for t in tema.formas if t in vigentes and t not in propios]
    # Compactación: lo propio de este turno pasa a ser «el último»; lo del anterior se pliega.
    nuevos = [t for t in propios if t not in tema.nucleo]
    tema.ultimo = nuevos
    tema.formas.update(_formas(pregunta, nuevos, paquete))
    texto = " ".join(tema.formas[t] for t in heredado)
    vigentes = set(tema.nucleo + tema.ultimo)
    tema.formas = {t: f for t, f in tema.formas.items() if t in vigentes}
    accion = "retoma" if retoma else "hereda"
    if not heredado:
        return Resolucion(pregunta, accion=accion, tema=_texto_nucleo(tema))
    return Resolucion(f"{pregunta.rstrip()} {texto}", seguimiento=True, heredado=texto, accion=accion,
                      tema=_texto_nucleo(tema))


__all__ = ["MAX_SESIONES", "MemoriaConversacion", "Resolucion", "VENCIMIENTO_S"]
