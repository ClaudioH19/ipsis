"""Pipeline extractivo del servicio en línea.

Este módulo reúne, en un solo archivo, las piezas que el molde define para
el servicio en línea: admisión mínima (sección 7), abstención calibrada
(E4) y el árbol de decisión con sus plantillas y su guardia de fidelidad
(sección 6). Antes eran puros esqueletos (``NotImplementedError``); esta
tanda los implementa de verdad, con el alcance recortado que documenta cada
sección más abajo.

Restricción que atraviesa todas estas etapas: ninguna cifra, fecha o entidad
de la respuesta puede ser producida por un modelo. Todo se copia literalmente
de los fragmentos recuperados, y la guardia lo verifica antes de responder.

La recuperación NO se declara aquí: existe una sola implementación, en
``rag/indice.py``, compartida con las evaluaciones.

**Alcance deliberado:**

1. **Admisión** — sin cola con espera ni niveles de degradación
   escalonados (normal/media/alta de la sección 7): solo un límite duro de
   peticiones concurrentes y 503 inmediato al superarlo. E7 (carga) no se
   corrió; el límite (`configuracion/motor.yaml::servicio.concurrencia_maxima`)
   es conservador, no medido.
2. **Abstención** — combina score denso, grounding léxico y verificación
   determinista de entidades. Los umbrales iniciales deben validarse con el
   corpus de cada usuario.
3. **Planificador** — no implementa el árbol completo de planes de la
   sección 6.1 (definicion/dato_puntual/requisito/procedimiento/excepcion/
   comparacion). Un único plan "extractivo": copia literal de los
   fragmentos recuperados, unidos con conectores fijos de
   ``configuracion/textos.yaml``. Clasificar la pregunta en un plan específico
   y extraer sus slots exigiría reglas o un clasificador nuevos, sin golden
   set etiquetado por plan para validarlos — se prefiere una única vía
   extractiva, siempre citada y siempre verificada por la guardia, antes
   que slots sin validar.
4. **Guardia** — verifica que toda entidad determinista de la respuesta
   esté respaldada por los fragmentos fuente (no contra una
   ``respuesta_referencia``, que no existe en tiempo de inferencia real).
"""
from __future__ import annotations

import functools
import re
import zlib
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

import yaml

from rag.reglas_extraccion import extraer_entidades
from rag.texto_util import palabras_contenido


# ==========================================================================
# CONVERSACIONAL (Etapa C, punto 4): saludos y charla trivial se detectan
# ANTES de tocar Qdrant y se responden con texto fijo -- nunca pasan por
# recuperación, abstención ni guardia (no hay nada del corpus que
# verificar en "hola"). Pensado para el widget de chat: sin esto, un
# saludo caía en "No encontré esa información...", que es un mal primer
# mensaje para cualquier persona que recién abre el chat.
# ==========================================================================
@functools.lru_cache(maxsize=1)
def _patrones_conversacionales_compilados() -> dict[str, list[re.Pattern]]:
    cfg = _cargar_plantillas().get("conversacional", {})
    patrones = cfg.get("patrones", {})
    return {cat: [re.compile(p, re.IGNORECASE) for p in lista] for cat, lista in patrones.items()}


def detectar_conversacional(pregunta: str) -> str | None:
    """Devuelve la categoría conversacional detectada (``"saludo"``,
    ``"agradecimiento"``, ``"despedida"``, ``"capacidad"``) según los
    patrones deterministas de ``configuracion/textos.yaml::conversacional``, o
    ``None`` si la pregunta no matchea ninguno -- en cuyo caso sigue el
    flujo normal (recuperación + abstención). Se evalúan las categorías en
    el orden declarado en config; la primera que matchea gana. Regex
    simples, sin NLP: exactamente el mismo criterio de determinismo que el
    resto del proyecto (nada de esto lo decide un modelo)."""
    categorias = _cargar_plantillas().get("conversacional", {}).get("categorias", [])
    patrones = _patrones_conversacionales_compilados()
    for categoria in categorias:
        for patron in patrones.get(categoria, []):
            if patron.search(pregunta):
                return categoria
    return None


def respuesta_conversacional(categoria: str, pregunta: str = "") -> str:
    """Texto FIJO de ``configuracion/textos.yaml::conversacional.respuestas``
    para la categoría detectada -- nunca generado.

    Consume: la categoría y, opcionalmente, la pregunta tal cual la escribió
    el usuario. Produce: una de las formulaciones declaradas para esa
    categoría.

    La categoría declara varias formulaciones para que el asistente no
    conteste siempre con la misma frase. La elección es DETERMINISTA (hash
    de la pregunta): la misma pregunta devuelve siempre el mismo texto, así
    que sigue siendo testeable, pero "hola" y "buenas" no contestan lo
    mismo. Acepta también un string suelto, por compatibilidad con un
    `plantillas.yaml` anterior a esta variedad."""
    opciones = _cargar_plantillas()["conversacional"]["respuestas"][categoria]
    if isinstance(opciones, str):
        return opciones
    return _elegir_variante(opciones, pregunta)


# ==========================================================================
# ADMISION (sección 7, alcance recortado — ver docstring del módulo)
# ==========================================================================
class NivelServicio(str, Enum):
    NORMAL = "normal"
    MEDIA = "media"     # FASE 5 completa — no implementado en esta etapa
    ALTA = "alta"        # FASE 5 completa — no implementado en esta etapa
    SATURADO = "saturado"


@dataclass
class ConfiguracionAdmision:
    concurrencia_maxima: int


class ControlAdmision:
    """Límite duro de peticiones concurrentes, sin cola de espera: una
    petición que no cabe se rechaza de inmediato (503), en vez de esperar y
    acumular latencia — coherente con el principio fijo de
    ``configuracion/motor.yaml``: "ante carga, el sistema degrada en escalones y
    rechaza con 503 antes que acumular latencia". No implementa niveles
    media/alta (sección 7 completa, E7): solo normal/saturado.

    Pensado para poder testearse sin concurrencia real: ``intentar_admitir``
    y ``liberar`` son las dos operaciones atómicas que el test puede invocar
    directamente para forzar el estado "saturado" de forma determinista.
    """

    def __init__(self, config: ConfiguracionAdmision):
        self.config = config
        self._lock = threading.Lock()
        self._en_curso = 0

    def intentar_admitir(self) -> bool:
        """True si se admite (reserva un cupo); False si está saturado."""
        with self._lock:
            if self._en_curso >= self.config.concurrencia_maxima:
                return False
            self._en_curso += 1
            return True

    def liberar(self) -> None:
        with self._lock:
            self._en_curso = max(0, self._en_curso - 1)

    def nivel_actual(self) -> NivelServicio:
        with self._lock:
            if self._en_curso >= self.config.concurrencia_maxima:
                return NivelServicio.SATURADO
            return NivelServicio.NORMAL

    @property
    def en_curso(self) -> int:
        with self._lock:
            return self._en_curso


# ==========================================================================
# ABSTENCION (Fase 3 — Etapa B: rediseño en dos capas)
# ==========================================================================
#
# Etapa A midió una sola señal (score fusionado híbrido) y encontró que no
# discriminaba (mecánicamente: un score RRF es de rango relativo dentro del
# pool de ESA consulta, no una medida absoluta) -- se cambió al score DENSO
# (coseno) del top-1, vía una consulta vectorial-solo aparte de la híbrida
# de producción. Esa señal única mezclaba dos problemas distintos (señalado
# por el coordinador, verificado con casos reales): "esto no es del dominio
# del corpus" y "esto es del dominio pero el corpus no lo cubre" --
# un único umbral de coseno no puede separarlos bien porque e5 comprime los
# scores dentro del propio dominio (preguntas EN dominio sin respuesta,
# p.ej. C13, pueden quedar con un coseno similar al de preguntas SÍ
# respondibles). Se separa en dos capas independientes:
#
#   (a) FUERA DE DOMINIO -- usa el score denso del top-1 y grounding
#       determinista. El umbral pertenece a la configuración del proyecto.
#   (b) PREMISA DE LA PREGUNTA -- verificar_premisa: determinista, sin
#       umbral. Si la pregunta menciona una entidad concreta y cerrada del
#       dominio (plazo, fecha, artículo, organismo, porcentaje, nota u otra
#       entidad aportada por un perfil -- `rag/reglas_extraccion.py`)
#       que NO aparece en NINGÚN LUGAR DEL CORPUS (Etapa C, punto 1: ya no
#       basta con que falte en los fragmentos recuperados -- ver
#       `separar_entidades_ausentes` y `rag/servicio/api.py`, que primero
#       intenta una recuperación DIRIGIDA a los chunks que sí la
#       contienen), la premisa no está respaldada: el sistema no debe
#       responder con el contenido de otra entidad parecida.
#
# Zona gris (ambas capas pasan, pero el score denso es "intermedio" -- ni
# claramente fuera de dominio ni con un match fuerte): estado propio
# "relacionado" (Etapa C, punto 2), ver `redactar_zona_gris` más abajo --
# ACTIVO por defecto; configurable a "abstenerse" para dominios de costo de
# error alto.
@dataclass
class SenalesAbstencion:
    """Score DENSO (coseno) del top-1 de una consulta vectorial-solo, MÁS
    margen top1-top2 (disponible para observación, no usado en la decisión). Capa (a)
    exclusivamente: distingue "esto no es del dominio" de todo lo demás. La
    capa (b), `verificar_premisa`, es la que distingue dentro del dominio."""

    score_top1: float
    margen_top1_top2: float


def decidir_abstencion(senales: SenalesAbstencion, umbral: float) -> bool:
    """Capa (a): True si el sistema debe abstenerse por estar FUERA DE
    DOMINIO -- el score denso del mejor fragmento no alcanza el umbral
    calibrado contra preguntas genuinamente ajenas al dominio (ver
    ``configuracion/motor.yaml::abstencion.capa_a_fuera_dominio.umbral`` y su
    reporte fechado)."""
    return senales.score_top1 < umbral


@dataclass
class ResultadoPremisa:
    premisa_valida: bool
    entidades_ausentes: list[dict]


def verificar_premisa(pregunta: str, fragmentos: list[dict]) -> ResultadoPremisa:
    """Capa (b): chequeo de premisa determinista, sin umbral. Extrae toda
    entidad cerrada del dominio presente en la PREGUNTA
    (``rag/reglas_extraccion.py::extraer_entidades`` -- nota, porcentaje,
    plazo, fecha, artículo, saber, semana relativa, organismo, práctica) y
    exige que cada una tenga respaldo LITERAL en el texto de los fragmentos
    recuperados. Si la pregunta no menciona ninguna entidad cerrada, la
    premisa se da por válida (esta capa no tiene nada que verificar -- no es
    lo mismo que "está bien respaldada", ver la zona gris más abajo)."""
    from rag.reglas_extraccion import extraer_entidades

    entidades_pregunta = extraer_entidades(pregunta)
    if not entidades_pregunta:
        return ResultadoPremisa(premisa_valida=True, entidades_ausentes=[])
    texto_fragmentos = " ".join(f["texto"] for f in fragmentos)
    entidades_fragmentos = {e["valor_norm"] for e in extraer_entidades(texto_fragmentos)}
    ausentes = [e for e in entidades_pregunta if e["valor_norm"] not in entidades_fragmentos]
    return ResultadoPremisa(premisa_valida=(len(ausentes) == 0), entidades_ausentes=ausentes)


def separar_entidades_ausentes(entidades_ausentes: list[dict], inventario_corpus: set[str]) -> tuple[list[dict], list[dict]]:
    """Etapa C, punto 1: separa las entidades que ``verificar_premisa``
    marcó como ausentes del top-k en dos grupos, usando el inventario del
    CORPUS COMPLETO (``rag/corpus.py::cargar_inventario_entidades``):

      - las que SÍ existen en algún lugar del corpus (el llamador debe
        intentar una recuperación dirigida a esos chunks antes de decidir
        abstenerse -- pueden pasar a estar respaldadas después de esa
        recuperación, ver ``rag/servicio/api.py``);
      - las genuinamente ausentes de TODO el corpus (no hay nada que
        buscar: la abstención citándolas es correcta, no un artefacto del
        top-k, p.ej. "artículo 99" o "20 semanas").

    Devuelve ``(en_corpus, genuinamente_ausentes)``."""
    en_corpus = [e for e in entidades_ausentes if e["valor_norm"] in inventario_corpus]
    genuinamente_ausentes = [e for e in entidades_ausentes if e["valor_norm"] not in inventario_corpus]
    return en_corpus, genuinamente_ausentes


def tiene_grounding_lexico(pregunta: str, estadisticas_lexico: dict[str, float],
                             df_fraccion_max: float = 0.8,
                             palabras_generales: frozenset[str] | None = None) -> bool:
    """Señal ADICIONAL de "esto es del dominio" (Etapa C, punto 1) --
    REDISEÑADA en la Etapa D, punto 1: el chequeo original ("¿alguna
    palabra de contenido está en el vocabulario BM25?") resultó demasiado
    permisivo, medido por el coordinador: "¿Cómo se prepara un asado?" y
    "¿Qué nota necesito para aprobar el curso de cálculo?" quedaban
    `relacionado` porque "prepara"/"necesito"/"nota" bastaban con solo
    aparecer una vez en el corpus (38 chunks -- una palabra genérica puede
    aparecer 1-2 veces por puro azar y no ser, por eso, evidencia de
    dominio).

    Ahora una palabra de contenido de la pregunta (sin stopwords,
    ``rag/texto_util.py::palabras_contenido``) cuenta como evidencia de
    dominio solo si, TODAS a la vez:
      1. No está en ``rag/texto_util.py::PALABRAS_GENERALES_ES`` (lista
         curada de verbos/sustantivos de alta frecuencia general del
         español y vocabulario frecuente que no identifica un dominio).
      2. Aparece en el vocabulario del corpus (sin acentos) con una
         fracción de chunks <= ``df_fraccion_max`` (excluye palabras
         omnipresentes DENTRO del corpus -- poco discriminantes, aunque no
         estén en la lista general -- configurable,
         ``configuracion/motor.yaml::abstencion.capa_a_fuera_dominio.grounding_lexico.df_fraccion_max``).

    No sustituye la capa (a): solo evita rechazar una pregunta que
    literalmente usa vocabulario REAL Y ESPECÍFICO del dominio (con o sin
    tildes) por un margen de score pequeño.

    ``palabras_generales`` (Etapa Plugin, Tarea C): si se entrega, se usa en
    vez del recurso "es" por defecto -- permite que el servicio cargue el
    recurso del IDIOMA configurado en ``configuracion/asistente.yaml`` en vez de
    asumir siempre español (``rag/texto_util.py::cargar_palabras_generales``).
    Si es ``None`` (compatibilidad hacia atrás, tests unitarios), cae al
    conjunto por defecto en español."""
    from rag.texto_util import PALABRAS_GENERALES_ES

    generales = palabras_generales if palabras_generales is not None else PALABRAS_GENERALES_ES
    for palabra in palabras_contenido(pregunta):
        if palabra in generales:
            continue
        fraccion = estadisticas_lexico.get(palabra)
        if fraccion is not None and fraccion <= df_fraccion_max:
            return True
    return False


def tiene_grounding_dominio(pregunta: str, inventario_entidades: set[str],
                              estadisticas_lexico: dict[str, float],
                              df_fraccion_max: float = 0.8,
                              palabras_generales: frozenset[str] | None = None) -> bool:
    """Combina las dos señales deterministas de "esto es del dominio"
    (Etapa C/D, punto 1): una entidad cerrada de la pregunta que existe en
    el corpus, o una palabra de contenido ESPECÍFICA del corpus (ver
    ``tiene_grounding_lexico`` para el rediseño de la Etapa D). Usado por
    ``rag/servicio/api.py`` para NO rechazar en la capa (a) una pregunta con
    esta evidencia, aunque su score denso quede por debajo del umbral --
    casos reales medidos: "¿Qué pasa si saco un 3,9?" (entidad "3.9" en el
    corpus) y "q pasa si me atraso con la bitacora" (palabra "bitácora" en
    el vocabulario, sin tilde en la pregunta, y NO en
    ``PALABRAS_GENERALES_ES``)."""
    entidades_pregunta = extraer_entidades(pregunta)
    if any(e["valor_norm"] in inventario_entidades for e in entidades_pregunta):
        return True
    return tiene_grounding_lexico(pregunta, estadisticas_lexico, df_fraccion_max, palabras_generales)


Resultado = Literal["responde", "relacionado", "abstiene"]


@dataclass
class DecisionAbstencion:
    resultado: Resultado
    # "fuera_dominio" | "premisa" | "zona_gris" | "confianza_alta"
    motivo: str
    entidad_texto: str | None = None

    @property
    def abstiene(self) -> bool:
        """Compatibilidad: ``True`` solo para el resultado "abstiene" real
        (nunca para "relacionado", que es su propio estado -- Etapa C,
        punto 2: "no se abstiene ni afirma")."""
        return self.resultado == "abstiene"


def decidir_capas_abstencion(senales: SenalesAbstencion, umbral_fuera_dominio: float,
                               umbral_confianza_alta: float, resultado_premisa: ResultadoPremisa,
                               zona_gris_modo: str = "relacionado",
                               grounding_dominio: bool = False) -> DecisionAbstencion:
    """Combina las tres capas en la decisión final (llamada DESPUÉS de tener
    ``resultado_premisa``, o sea después de la recuperación real -- capa (a)
    sola, sin fragmentos, ya se resolvió antes si el score no alcanzaba
    ``umbral_fuera_dominio``, ver ``rag/servicio/api.py``).

    Tres resultados posibles (Etapa C, punto 2: "relacionado" es un ESTADO
    propio, ni abstención ni afirmación):
      - ``"responde"``: confianza alta, sin problema de premisa -- plan
        "extractivo" normal.
      - ``"relacionado"``: zona gris (score entre las dos capas) con
        ``zona_gris_modo="relacionado"`` (el default) -- muestra los
        fragmentos más pertinentes enmarcados con un conector fijo que dice
        explícitamente "no es una respuesta directa" (nunca afirma un
        hecho como si fuera la respuesta).
      - ``"abstiene"``: fuera de dominio, premisa no respaldada (ni
        siquiera con la recuperación dirigida de la capa (b) extendida,
        ver ``rag/servicio/api.py``), o zona gris con ``zona_gris_modo="abstenerse"``.

    Orden de evaluación (la premisa manda siempre, es determinista y no
    depende de dónde caiga el score continuo): capa (b) primero -- si hay
    una entidad de la pregunta sin respaldo (tras la recuperación dirigida),
    se abstiene citándola, pase lo que pase con el score."""
    if resultado_premisa.entidades_ausentes:
        entidad = resultado_premisa.entidades_ausentes[0]["texto"]
        return DecisionAbstencion(resultado="abstiene", motivo="premisa", entidad_texto=entidad)
    if senales.score_top1 < umbral_fuera_dominio and not grounding_dominio:
        return DecisionAbstencion(resultado="abstiene", motivo="fuera_dominio")
    if senales.score_top1 < umbral_confianza_alta:
        # Nota: si `grounding_dominio` rescató a la pregunta de la capa (a)
        # pese a un score bajo el umbral, cae aquí (zona gris) en vez de
        # "confianza alta" -- es la franja correcta para un match débil con
        # evidencia de dominio determinista, no una respuesta confiada.
        if zona_gris_modo == "relacionado":
            return DecisionAbstencion(resultado="relacionado", motivo="zona_gris")
        return DecisionAbstencion(resultado="abstiene", motivo="zona_gris")
    return DecisionAbstencion(resultado="responde", motivo="confianza_alta")


@dataclass
class ResultadoCalibracion:
    umbral: float
    falsa_respuesta: float
    falsa_abstencion: float
    fpr_objetivo: float
    n_respondibles: int
    n_no_respondibles: int
    curva: list[dict] = field(default_factory=list)


def calibrar_umbral(scores_respondibles: list[float], scores_no_respondibles: list[float],
                     fpr_objetivo: float) -> ResultadoCalibracion:
    """Curva de calibración sobre el split ``dev`` del golden set (E4).

    ``scores_respondibles``/``scores_no_respondibles`` son los
    ``score_top1`` (ver ``SenalesAbstencion``) medidos con retrieval REAL
    contra el índice de producción, uno por ítem del split dev — respondible
    contra no respondible (C13/C14/C17 y análogas). El split ``test`` nunca
    se toca aquí (regla dura del encargo).

    Recorre los thresholds observados (todo score único de la muestra,
    ordenado) y, para cada uno, calcula:
      - falsa_respuesta: fracción de NO respondibles con score >= umbral
        (el sistema respondería a una pregunta que debía rechazar).
      - falsa_abstencion: fracción de respondibles con score < umbral
        (el sistema se abstendría de una pregunta que sí podía responder).

    Elige el umbral MÁS BAJO que cumple ``falsa_respuesta <= fpr_objetivo``
    (fijado antes de medir, ``configuracion/motor.yaml::criterios_aceptacion.E4_umbral_abstencion``,
    coherente con ``costo_error_informacion: ALTO``): el más bajo que cumple
    el objetivo es el que menos abstención innecesaria produce entre los que
    ya cumplen la cota de falsa respuesta. Si ningún umbral cumple el
    objetivo, se toma el que minimiza la falsa respuesta (documentado en el
    reporte como "no alcanza el objetivo", nunca se afloja el objetivo
    después de medir."""
    todos = sorted(set(scores_respondibles) | set(scores_no_respondibles))
    # candidatos: un poco por debajo del mínimo (abstiene siempre) hasta un
    # poco por encima del máximo (nunca abstiene), más cada score observado.
    candidatos = [todos[0] - 1e-6] + todos + [todos[-1] + 1e-6] if todos else [0.0]

    n_resp = len(scores_respondibles)
    n_noresp = len(scores_no_respondibles)
    curva = []
    mejor = None
    for u in candidatos:
        fr = (sum(1 for s in scores_no_respondibles if s >= u) / n_noresp) if n_noresp else 0.0
        fa = (sum(1 for s in scores_respondibles if s < u) / n_resp) if n_resp else 0.0
        curva.append({"umbral": u, "falsa_respuesta": fr, "falsa_abstencion": fa})
        if fr <= fpr_objetivo:
            if mejor is None or u < mejor["umbral"]:
                mejor = {"umbral": u, "falsa_respuesta": fr, "falsa_abstencion": fa}

    if mejor is None:
        # ningún umbral alcanza el objetivo: se reporta el que MINIMIZA
        # falsa_respuesta (el extremo "abstiene siempre"), marcado como
        # incumplimiento explícito -- nunca se relaja fpr_objetivo.
        mejor = min(curva, key=lambda c: (c["falsa_respuesta"], c["falsa_abstencion"]))

    return ResultadoCalibracion(
        umbral=mejor["umbral"], falsa_respuesta=mejor["falsa_respuesta"],
        falsa_abstencion=mejor["falsa_abstencion"], fpr_objetivo=fpr_objetivo,
        n_respondibles=n_resp, n_no_respondibles=n_noresp, curva=curva,
    )


# ==========================================================================
# PLANIFICADOR (Fase 4, versión mínima — un único plan "extractivo")
# ==========================================================================
Plan = Literal["definicion", "dato_puntual", "requisito", "procedimiento",
                "excepcion", "comparacion", "extractivo", "sin_respuesta"]


@dataclass
class PlanDeRespuesta:
    plan: Plan
    slots: dict


def elegir_plan(pregunta: str, fragmentos: list[dict]) -> PlanDeRespuesta:
    """Versión mínima (recorte 3 del docstring del módulo): siempre
    "extractivo". No clasifica la pregunta en el árbol de planes de la
    sección 6.1 del molde."""
    return PlanDeRespuesta(plan="extractivo", slots={"fragmentos": fragmentos})


def extraer_slots(plan: Plan, fragmentos: list[dict]) -> dict:
    """No aplica en el plan único "extractivo": el fragmento completo ES la
    respuesta, no hay slots estructurados que extraer de él. Se mantiene la
    firma por compatibilidad con el contrato del molde."""
    return {"fragmentos": fragmentos}


# ==========================================================================
# REDACCION (sección 6.2 — plantillas y conectores fijos, nunca texto libre)
# ==========================================================================
@functools.lru_cache(maxsize=1)
def _cargar_plantillas(ruta: str = "configuracion/textos.yaml") -> dict:
    """Carga ``configuracion/textos.yaml`` y sustituye las variables de dominio
    (``{nombre_asistente}``/``{descripcion_dominio}``) en los textos
    conversacionales fijos, usando ``configuracion/asistente.yaml`` (Etapa Plugin,
    Tarea C) -- así el mismo YAML de plantillas sirve para cualquier
    dominio, sin nombrar ningún corpus en el texto fijo. Cacheado (mismo
    criterio que el resto del módulo): se lee una vez por proceso."""
    from rag.configuracion import cargar_dominio

    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    dominio = cargar_dominio()
    variables = {
        "nombre_asistente": dominio.get("nombre_asistente", "el asistente"),
        "descripcion_dominio": dominio.get("descripcion_dominio", "los documentos cargados"),
    }
    def sustituir(texto: str) -> str:
        """Sustituye las variables de dominio y arregla las contracciones.

        ``descripcion_dominio`` la escribe el usuario en
        ``configuracion/asistente.yaml`` y puede empezar con articulo ("el
        manual..."), asi que una plantilla que diga "de
        {descripcion_dominio}" puede producir "de el manual". Las dos
        contracciones obligatorias del castellano se aplican aqui, una vez,
        en vez de obligar a que cada plantilla esquive el problema."""
        salida = texto.format(**variables)
        return salida.replace(" de el ", " del ").replace(" a el ", " al ")

    respuestas = datos.get("conversacional", {}).get("respuestas", {})
    for categoria, valor in respuestas.items():
        # Cada categoria puede declarar un texto suelto o varias variantes.
        if isinstance(valor, str):
            respuestas[categoria] = sustituir(valor)
        else:
            respuestas[categoria] = [sustituir(t) for t in valor]
    return datos


def _elegir_variante(opciones: list[str], semilla: str, evitar: set[str] | None = None) -> str:
    """Elige una de varias formulaciones FIJAS de forma determinista.

    Consume: la lista declarada en ``configuracion/textos.yaml``, una cadena
    que sirve de semilla (el ``chunk_id`` del fragmento, o la pregunta) y,
    opcionalmente, las variantes ya usadas en esta misma respuesta. Produce:
    una de las opciones.

    El hash es de la semilla, no aleatorio: la misma pregunta sobre el mismo
    indice devuelve SIEMPRE el mismo texto. Sin eso, la respuesta cambiaria
    entre corridas y ningun test podria fijarla. ``evitar`` solo desplaza la
    eleccion al siguiente candidato, para que una respuesta con tres
    fragmentos no repita la misma frase tres veces."""
    if not opciones:
        return ""
    evitar = evitar or set()
    inicio = zlib.crc32(semilla.encode("utf-8")) % len(opciones)
    for desplazamiento in range(len(opciones)):
        candidato = opciones[(inicio + desplazamiento) % len(opciones)]
        if candidato not in evitar:
            return candidato
    return opciones[inicio]


def _fragmentos_para_el_texto(fragmentos: list[dict], cfg: dict) -> list[dict]:
    """Decide QUE fragmentos entran en la prosa de la respuesta.

    Consume: los fragmentos recuperados (ya ordenados por pertinencia) y la
    seccion ``redaccion:`` de ``configuracion/motor.yaml``. Produce: el
    subconjunto que se concatena en el texto.

    Antes se concatenaban los ``top_k`` completos, siempre. Con top_k=3 eso
    producia respuestas de tres bloques donde el tercero solia ser de otra
    seccion del documento y no venia al caso -- mas texto, menos precision.
    Ahora un fragmento posterior al primero entra solo si su score alcanza
    una fraccion del score del primero, y con un tope duro de cuantos
    caben.

    IMPORTANTE: esto acorta la PROSA, no esconde evidencia. El campo
    ``fragmentos`` de la respuesta HTTP sigue trayendo todos los
    recuperados, con su texto literal y sus offsets, que es lo que el widget
    despliega como citas. Nada de lo recuperado deja de estar disponible.

    Ambos valores son decisiones de diseno NO MEDIDAS (no hay golden set en
    el repositorio con el que medirlas); por eso son configurables y estan
    documentadas como tales en ``configuracion/motor.yaml``."""
    if not fragmentos:
        return []
    tope = int(cfg.get("max_fragmentos_en_respuesta", 0) or 0)
    minimo_relativo = float(cfg.get("score_relativo_minimo", 0.0) or 0.0)
    primero = fragmentos[0]
    salida = [primero]
    referencia = float(primero.get("score") or 0.0)
    for frag in fragmentos[1:]:
        if tope and len(salida) >= tope:
            break
        if referencia > 0 and minimo_relativo > 0:
            if float(frag.get("score") or 0.0) < referencia * minimo_relativo:
                continue
        salida.append(frag)
    return salida


def _formatear_cita(frag: dict, estilo: str) -> str:
    """Cita que va DENTRO del texto de la respuesta.

    ``completa`` trae documento y ruta de seccion; ``breve``, solo el
    documento; ``ninguna`` no pone nada en el texto. En los tres casos la
    cita exacta -- documento, seccion y offsets -- sigue viajando en el
    campo estructurado ``fragmentos`` de la respuesta HTTP: esto decide
    cuanto se repite dentro de la prosa, no si se cita."""
    if estilo == "ninguna":
        return ""
    if estilo == "breve":
        return f"(Fuente: {frag['doc_titulo']})"
    seccion = " > ".join(frag.get("seccion_path") or []) or "(sin seccion)"
    return f"(Fuente: {frag['doc_titulo']}, seccion: {seccion})"


def _ensamblar_fragmentos_con_citas(fragmentos: list[dict], con_apertura: bool = True) -> str:
    """Concatena el texto LITERAL de cada fragmento (nunca lo reescribe) con
    su cita y, entre fragmentos, un conector FIJO de
    ``configuracion/textos.yaml`` -- la unica "redaccion" permitida.

    La CATEGORIA del conector la decide metadata determinista calculada en
    la ingesta (``tiene_excepcion``/``tiene_condicion``), nunca un modelo;
    la VARIANTE dentro de la categoria sale de ``_elegir_variante``. Los
    conectores cierran en dos puntos a proposito: el texto que sigue es una
    cita literal que empieza donde el documento empiece, y un conector
    subordinante ("Siempre que,") producia frases rotas.

    Compartida por ``redactar`` (estado ``ok``) y ``redactar_zona_gris``
    (estado ``relacionado``)."""
    from rag.configuracion import config_redaccion

    plantillas = _cargar_plantillas()
    conectores = plantillas["conectores"]
    cfg = config_redaccion()
    estilo_cita = str(cfg.get("cita_en_texto", "completa"))

    elegidos = _fragmentos_para_el_texto(fragmentos, cfg)
    usadas: set[str] = set()
    partes: list[str] = []

    if con_apertura and cfg.get("incluir_apertura", False) and conectores.get("apertura"):
        semilla = str(elegidos[0].get("chunk_id", "")) if elegidos else ""
        apertura = _elegir_variante(list(conectores["apertura"]), semilla)
        if apertura:
            partes.append(apertura)
            usadas.add(apertura)

    for i, frag in enumerate(elegidos):
        texto = frag["texto"].strip()
        cita = _formatear_cita(frag, estilo_cita)
        cuerpo = f"{texto} {cita}." if cita else texto
        if i == 0:
            partes.append(cuerpo)
            continue
        if frag.get("tiene_excepcion"):
            categoria = "excepcion"
        elif frag.get("tiene_condicion"):
            categoria = "condicion"
        else:
            categoria = "complemento"
        opciones = list(conectores.get(categoria) or [])
        conector = _elegir_variante(opciones, str(frag.get("chunk_id", i)), usadas)
        if conector:
            usadas.add(conector)
            partes.append(f"{conector} {cuerpo}")
        else:
            partes.append(cuerpo)
    return " ".join(partes)


def redactar(plan: PlanDeRespuesta, fragmentos: list[dict]) -> str:
    """Respuesta normal (estado ``ok``): fragmentos literales + citas +
    conectores fijos, sin ningún encabezado adicional."""
    return _ensamblar_fragmentos_con_citas(fragmentos)


def redactar_zona_gris(fragmentos: list[dict]) -> str:
    """Estado propio ``"relacionado"`` (Etapa C, punto 2 del encargo del
    coordinador -- ACTIVO por defecto desde esta etapa): cuando la pregunta
    pasa las dos capas de abstención pero el score denso es "intermedio"
    (ni claramente fuera de dominio ni un match fuerte), en vez de
    abstenerse se muestran los fragmentos más pertinentes enmarcados con un
    conector fijo que dice explícitamente que NO es una respuesta directa
    -- con citas literales y el encuadre explícito, mostrar texto
    relacionado no es una afirmación directa.
    Sigue siendo texto literal + cita; el único agregado es la frase de
    encabezado fija (``configuracion/textos.yaml::abstencion.zona_gris_intro``).
    Configurable: ``configuracion/motor.yaml::abstencion.zona_gris.modo`` en
    {"relacionado" (default), "abstenerse"} -- dominios de costo de error
    ALTO pueden volver a "abstenerse" por configuración, sin tocar código."""
    intro = _cargar_plantillas()["abstencion"]["zona_gris_intro"]
    # Sin apertura: este estado ya trae su propio encabezado fijo, y apilar
    # los dos producia "No encontre una respuesta directa. Esto es lo que
    # dicen los documentos sobre el tema: Encontre esto en el documento:".
    return f"{intro} {_ensamblar_fragmentos_con_citas(fragmentos, con_apertura=False)}"


def construir_mensaje_abstencion(motivo: str, entidad_texto: str | None = None) -> str:
    """Mensaje de abstención SIEMPRE listo para mostrar a un usuario final
    (nunca ``null`` en la respuesta HTTP: el servicio puede servir a un
    frontend externo -- plugin/widget de chat -- que necesita un string,
    no un estado vacío que interpretar). ``motivo`` en
    {"fuera_dominio", "premisa", "guardia", "sin_fragmentos"}; solo
    "premisa" usa ``entidad_texto`` (copiado LITERAL de la pregunta del
    usuario, nunca inventado)."""
    plantillas = _cargar_plantillas()["abstencion"]
    if motivo == "premisa" and entidad_texto:
        return plantillas["premisa_no_encontrada"].format(entidad=entidad_texto)
    return plantillas["generico"]


# ==========================================================================
# GUARDIA (sección 6.3 — verificación de fidelidad en línea)
# ==========================================================================
@dataclass
class ResultadoFidelidad:
    fiel: bool
    motivos: list[str] = field(default_factory=list)


def verificar_fidelidad(respuesta_generada: str, fragmentos: list[dict]) -> ResultadoFidelidad:
    """Guardia real (no un stub): toda entidad determinista (nota,
    porcentaje, plazo, fecha, artículo, saber, semana, organismo —
    ``rag/reglas_extraccion.py``) presente en ``respuesta_generada`` debe
    estar también, literalmente, en el texto fuente (los fragmentos
    recuperados, más su cita determinista: título del documento y ruta de
    sección, que también se copian del corpus vía ``documentos/catalogo.yaml`` /
    el parser — nunca las produce un modelo). Si alguna entidad de la
    respuesta no tiene respaldo literal, la guardia falla y ``api.py`` debe
    abstenerse en vez de responder.

    A propósito NO usa ``rag.metricas.evaluar_exactitud_factual``: esa
    función compara contra una ``respuesta_referencia`` y ``hechos_clave``
    del golden set — información de EVALUACIÓN que no existe en tiempo de
    inferencia real (no hay "respuesta correcta" con la que comparar una
    pregunta real de un usuario). Aquí la única fuente de verdad son los
    fragmentos que el propio sistema recuperó."""
    entidades_respuesta = {e["valor_norm"] for e in extraer_entidades(respuesta_generada)}
    texto_fuente = " ".join(
        f"{f['texto']} {f['doc_titulo']} {' '.join(f.get('seccion_path') or [])}"
        for f in fragmentos
    )
    entidades_fuente = {e["valor_norm"] for e in extraer_entidades(texto_fuente)}
    faltantes = entidades_respuesta - entidades_fuente
    if faltantes:
        return ResultadoFidelidad(
            fiel=False,
            motivos=[f"entidad en la respuesta sin respaldo literal en los fragmentos: {sorted(faltantes)}"],
        )
    return ResultadoFidelidad(fiel=True)
