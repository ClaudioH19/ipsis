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


import yaml

from rag.lenguaje.entidades import extraer_entidades
from rag.lenguaje.texto import sin_acentos


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


def detectar_conversacional(pregunta: str, plantillas: dict | None = None) -> str | None:
    """Devuelve la categoría conversacional detectada (``"saludo"``,
    ``"agradecimiento"``, ``"despedida"``, ``"capacidad"``) según los
    patrones deterministas de ``configuracion/textos.yaml::conversacional``, o
    ``None`` si la pregunta no matchea ninguno -- en cuyo caso sigue el
    flujo normal (recuperación + abstención). Se evalúan las categorías en
    el orden declarado en config; la primera que matchea gana. Regex
    simples, sin NLP: exactamente el mismo criterio de determinismo que el
    resto del proyecto (nada de esto lo decide un modelo)."""
    datos = plantillas or _cargar_plantillas()
    categorias = datos.get("conversacional", {}).get("categorias", [])
    if plantillas is None:
        patrones = _patrones_conversacionales_compilados()
    else:
        patrones = {
            categoria: [re.compile(patron, re.IGNORECASE) for patron in lista]
            for categoria, lista in datos.get("conversacional", {}).get("patrones", {}).items()
        }
    for categoria in categorias:
        for patron in patrones.get(categoria, []):
            if patron.search(pregunta):
                return categoria
    return None


def respuesta_conversacional(
    categoria: str,
    pregunta: str = "",
    plantillas: dict | None = None,
) -> str:
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
    opciones = (plantillas or _cargar_plantillas())["conversacional"]["respuestas"][categoria]
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
# REDACCION (sección 6.2 — plantillas y conectores fijos, nunca texto libre)
# ==========================================================================
def cargar_plantillas(ruta: str | Path, dominio: dict | None = None) -> dict:
    """Carga ``configuracion/textos.yaml`` y sustituye las variables de dominio
    (``{nombre_asistente}``/``{descripcion_dominio}``) en los textos
    conversacionales fijos, usando ``configuracion/asistente.yaml`` (Etapa Plugin,
    Tarea C) -- así el mismo YAML de plantillas sirve para cualquier
    dominio, sin nombrar ningún corpus en el texto fijo. Cacheado (mismo
    criterio que el resto del módulo): se lee una vez por proceso."""
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    if dominio is None:
        from rag.configuracion.carga import cargar_dominio

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


@functools.lru_cache(maxsize=1)
def _cargar_plantillas(ruta: str = "configuracion/textos.yaml") -> dict:
    """Compatibilidad para llamadas fuera de ``Motor``."""
    return cargar_plantillas(ruta)


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


def _ensamblar_fragmentos_con_citas(
    fragmentos: list[dict],
    con_apertura: bool = True,
    *,
    plantillas: dict | None = None,
    cfg_redaccion: dict | None = None,
) -> str:
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
    from rag.configuracion.carga import config_redaccion

    plantillas = plantillas or _cargar_plantillas()
    conectores = plantillas["conectores"]
    cfg = cfg_redaccion or config_redaccion()
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


def redactar(
    fragmentos: list[dict],
    *,
    plantillas: dict | None = None,
    cfg_redaccion: dict | None = None,
) -> str:
    """Respuesta normal (estado ``ok``): fragmentos literales + citas +
    conectores fijos, sin ningún encabezado adicional."""
    return _ensamblar_fragmentos_con_citas(
        fragmentos,
        plantillas=plantillas,
        cfg_redaccion=cfg_redaccion,
    )


def redactar_zona_gris(
    fragmentos: list[dict],
    *,
    plantillas: dict | None = None,
    cfg_redaccion: dict | None = None,
) -> str:
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
    plantillas = plantillas or _cargar_plantillas()
    intro = plantillas["abstencion"]["zona_gris_intro"]
    # Sin apertura: este estado ya trae su propio encabezado fijo, y apilar
    # los dos producia "No encontre una respuesta directa. Esto es lo que
    # dicen los documentos sobre el tema: Encontre esto en el documento:".
    return f"{intro} {_ensamblar_fragmentos_con_citas(fragmentos, con_apertura=False, plantillas=plantillas, cfg_redaccion=cfg_redaccion)}"


def construir_mensaje_abstencion(
    motivo: str,
    entidad_texto: str | None = None,
    plantillas: dict | None = None,
) -> str:
    """Mensaje de abstención SIEMPRE listo para mostrar a un usuario final
    (nunca ``null`` en la respuesta HTTP: el servicio puede servir a un
    frontend externo -- plugin/widget de chat -- que necesita un string,
    no un estado vacío que interpretar). ``motivo`` en
    {"fuera_dominio", "premisa", "guardia", "sin_fragmentos"}; solo
    "premisa" usa ``entidad_texto`` (copiado LITERAL de la pregunta del
    usuario, nunca inventado)."""
    textos = (plantillas or _cargar_plantillas())["abstencion"]
    if motivo == "premisa" and entidad_texto:
        return textos["premisa_no_encontrada"].format(entidad=entidad_texto)
    return textos["generico"]


# ==========================================================================
# GUARDIA (sección 6.3 — verificación de fidelidad en línea)
# ==========================================================================
@dataclass
class ResultadoFidelidad:
    fiel: bool
    motivos: list[str] = field(default_factory=list)


_RE_SOLICITUD_PRECIO = re.compile(
    r"\b(?:precio|costo|coste|tarifa)\b|\bcuanto\s+(?:cuesta|cuestan|vale|valen)\b|\bvalor\s+(?:de|del)\b",
    re.IGNORECASE,
)
_RE_DINERO = re.compile(
    r"(?:[$€£]\s*\d)|(?:\b(?:clp|usd|eur|uf|utm)\s*\$?\s*\d)"
    r"|(?:\b\d[\d.,]*\s*(?:pesos?|dolares?|euros?|clp|usd|eur|uf|utm)\b)",
    re.IGNORECASE,
)
_RE_SOLICITUD_DURACION = re.compile(
    r"\bcada\s+cuanto\b|\bcuanto\s+dura\b|\bcuantos?\s+(?:dias?|semanas?|meses?|horas?|minutos?)\b",
    re.IGNORECASE,
)
_RE_SOLICITUD_CANTIDAD = re.compile(
    r"\bcuant(?:os|as)\s+([a-z]+)\b|\bcantidad\s+de\s+([a-z]+)\b",
    re.IGNORECASE,
)
_NUMEROS_CANTIDAD = {
    "un", "una", "uno", "dos", "tres", "cuatro", "cinco", "seis",
    "siete", "ocho", "nueve", "diez", "once", "doce", "trece",
    "catorce", "quince", "veinte", "treinta", "cien", "mil",
}


def _texto_fuente(fragmentos: list[dict]) -> str:
    return " ".join(
        f"{f['texto']} {f['doc_titulo']} {' '.join(f.get('seccion_path') or [])}"
        for f in fragmentos
    )


def _cantidad_cercana_a_objetivo(texto: str, objetivo: str) -> bool:
    tokens = re.findall(r"\d+(?:[.,]\d+)?|[a-z]+", sin_acentos(texto).lower())
    raiz = objetivo[:-2] if objetivo.endswith("es") else objetivo[:-1] if objetivo.endswith("s") else objetivo
    for indice, token in enumerate(tokens):
        if token != objetivo and not (len(raiz) >= 3 and token.startswith(raiz)):
            continue
        anteriores = tokens[max(0, indice - 4):indice]
        if any(re.fullmatch(r"\d+(?:[.,]\d+)?", valor) or valor in _NUMEROS_CANTIDAD for valor in anteriores):
            return True
    return False


def verificar_respaldo_dato_solicitado(
    pregunta: str,
    fragmentos: list[dict],
) -> ResultadoFidelidad:
    """Exige el tipo de dato pedido antes de permitir una respuesta directa.

    Es deliberadamente conservadora: solo bloquea intenciones cuantitativas
    reconocibles con alta precisión. No intenta juzgar relevancia semántica ni
    sustituye la evaluación de recuperación.
    """
    pregunta_norm = sin_acentos(pregunta).lower()
    fuente = _texto_fuente(fragmentos)
    fuente_norm = sin_acentos(fuente).lower()

    if _RE_SOLICITUD_PRECIO.search(pregunta_norm):
        if not _RE_DINERO.search(fuente_norm):
            return ResultadoFidelidad(
                fiel=False,
                motivos=["la pregunta solicita un precio, pero la evidencia no contiene un importe monetario"],
            )
        return ResultadoFidelidad(fiel=True)

    if _RE_SOLICITUD_DURACION.search(pregunta_norm):
        if not any(entidad["tipo"] == "plazo" for entidad in extraer_entidades(fuente)):
            return ResultadoFidelidad(
                fiel=False,
                motivos=["la pregunta solicita una duración, pero la evidencia no contiene un plazo"],
            )
        return ResultadoFidelidad(fiel=True)

    solicitud = _RE_SOLICITUD_CANTIDAD.search(pregunta_norm)
    if solicitud:
        objetivo = solicitud.group(1) or solicitud.group(2)
        if not _cantidad_cercana_a_objetivo(fuente_norm, objetivo):
            return ResultadoFidelidad(
                fiel=False,
                motivos=[
                    f"la pregunta solicita una cantidad de {objetivo}, pero la evidencia no contiene esa cantidad"
                ],
            )
    return ResultadoFidelidad(fiel=True)


def verificar_fidelidad(respuesta_generada: str, fragmentos: list[dict]) -> ResultadoFidelidad:
    """Guardia real (no un stub): toda entidad determinista (nota,
    porcentaje, plazo, fecha, artículo, saber, semana, organismo —
    ``rag/lenguaje/entidades.py``) presente en ``respuesta_generada`` debe
    estar también, literalmente, en el texto fuente (los fragmentos
    recuperados, más su cita determinista: título del documento y ruta de
    sección, que también se copian del corpus vía ``documentos/catalogo.yaml`` /
    el parser — nunca las produce un modelo). Si alguna entidad de la
    respuesta no tiene respaldo literal, la guardia falla y ``api.py`` debe
    abstenerse en vez de responder.

    No compara contra un golden set: en inferencia real no existe una
    "respuesta correcta". La única fuente de verdad son los fragmentos que el
    propio sistema recuperó."""
    entidades_respuesta = {e["valor_norm"] for e in extraer_entidades(respuesta_generada)}
    texto_fuente = _texto_fuente(fragmentos)
    entidades_fuente = {e["valor_norm"] for e in extraer_entidades(texto_fuente)}
    faltantes = entidades_respuesta - entidades_fuente
    if faltantes:
        return ResultadoFidelidad(
            fiel=False,
            motivos=[f"entidad en la respuesta sin respaldo literal en los fragmentos: {sorted(faltantes)}"],
        )
    return ResultadoFidelidad(fiel=True)
