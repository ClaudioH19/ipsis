"""Alternativas ante una abstención: lo más parecido que sí está (ADR 0008).

Con la postura ``proactiva``, cuando la política se abstiene por ``premisa`` o
``sin_respuesta``, se ofrecen hasta ``max_alternativas`` párrafos del corpus
parecidos a lo pedido. Nunca se genera texto: cada alternativa es un párrafo
literal de un fragmento indexado, con sus offsets y su cita.

La afinidad sale de los metadatos que la ingesta ya guardó en cada fragmento
y de la recuperación, sin modelos nuevos:

- ``familia``: el párrafo tiene una entidad de la misma familia que la
  entidad ausente de la pregunta (mismo tipo y forma: «TP-500» → «TP-400»),
  si ese tipo lo declara el proyecto en ``domain.yaml``;
- ``medida``: lo mismo para una medida del núcleo («60 días» → «90 días»,
  «20 %»), solo si el párrafo además comparte una palabra de la pregunta: esas
  medidas aparecen en documentos sin relación;
- ``terminos``: parte de los términos de la pregunta que el párrafo contiene;
- ``seccion``: parte de esos términos en el título del documento o la ruta
  de sección;
- ``keywords``: parte de esos términos en las palabras clave del fragmento;
- ``categoria``: el fragmento es de la categoría de la pregunta (solo si la
  taxonomía del proyecto distingue categorías);
- ``similitud``: coseno denso entre la pregunta y el párrafo, desde el piso
  del modelo.

Un párrafo solo es candidato si comparte algo con la pregunta (``familia`` o
``terminos``); se ofrece si su afinidad (media ponderada de las señales con
los pesos del perfil) alcanza el umbral del perfil. Pesos y umbral se
calibran con el banco ``tests/datos/banco_alternativas`` para una precisión
de al menos 0,9.
"""
from __future__ import annotations

import functools
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from ipsis.nucleo.esquemas import ChunkRecord, EvidenceSpan, FiltroEntidad

SENALES = ("familia", "medida", "terminos", "seccion", "keywords", "categoria", "similitud")
MOTIVOS_CON_ALTERNATIVAS = frozenset({"premisa", "generico"})
# Párrafos que se puntúan como mucho por abstención: acota el costo del coseno.
MAX_PARRAFOS = 16
# Vecinos de familia que se buscan por entidad ausente (los de número más cercano).
MAX_VECINOS_FAMILIA = 4

_DIGITOS = re.compile(r"\d+")
_LINEA = re.compile(r"[^\n]+")


@dataclass(frozen=True)
class SenalesAlternativa:
    familia: float = 0.0
    medida: float = 0.0
    terminos: float = 0.0
    seccion: float = 0.0
    keywords: float = 0.0
    categoria: float = 0.0
    similitud: float = 0.0


def afinidad(senales: SenalesAlternativa | dict, pesos: dict[str, float]) -> float:
    """Media ponderada de las señales; 0 si ningún peso es positivo."""
    valores = senales if isinstance(senales, dict) else asdict(senales)
    total = sum(max(0.0, float(pesos.get(s, 0.0))) for s in SENALES)
    if total <= 0:
        return 0.0
    return sum(max(0.0, float(pesos.get(s, 0.0))) * float(valores.get(s, 0.0)) for s in SENALES) / total


def elegible(senales: SenalesAlternativa | dict) -> bool:
    """Un párrafo que no comparte nada con la pregunta nunca es alternativa."""
    valores = senales if isinstance(senales, dict) else asdict(senales)
    return any(valores.get(s, 0.0) > 0 for s in ("familia", "medida", "terminos"))


@dataclass
class Alternativa:
    evidencia: EvidenceSpan
    chunk: ChunkRecord
    senales: SenalesAlternativa
    afinidad: float
    origen: str  # «candidato» (de la recuperación) o «familia» (por la entidad ausente)

    def diagnostico(self) -> dict[str, Any]:
        return {"chunk_id": self.chunk.chunk_id, "texto": self.evidencia.texto, "origen": self.origen,
                "afinidad": round(self.afinidad, 4), "senales": {k: round(v, 4) for k, v in asdict(self.senales).items()}}


@dataclass
class ResultadoAlternativas:
    ofrecidas: list[Alternativa] = field(default_factory=list)
    descartadas: list[Alternativa] = field(default_factory=list)

    def diagnostico(self) -> dict[str, Any]:
        return {"ofrecidas": [a.diagnostico() for a in self.ofrecidas],
                "descartadas": [a.diagnostico() for a in self.descartadas]}


# --- familia de una entidad ----------------------------------------------------------------------
def esqueleto(valor_norm: str) -> str | None:
    """La forma de un valor sin sus números («codigo_tp-#»), o ``None`` si no
    tiene letras: dos cifras sueltas («30.000» y «45.000») no son familia."""
    forma = _DIGITOS.sub("#", valor_norm)
    return forma if "#" in forma and any(c.isalpha() for c in forma) else None


def _numero(valor_norm: str) -> float | None:
    cifras = _DIGITOS.findall(valor_norm)
    return float(cifras[-1]) if cifras else None


def vecinos_de_familia(valor_norm: str, inventario: set[str], limite: int = MAX_VECINOS_FAMILIA) -> list[str]:
    """Valores del inventario con el mismo esqueleto, del número más cercano al más lejano."""
    forma = esqueleto(valor_norm)
    if forma is None:
        return []
    numero = _numero(valor_norm)
    vecinos = [v for v in inventario if v != valor_norm and esqueleto(v) == forma]
    vecinos.sort(key=lambda v: (abs((_numero(v) or 0.0) - (numero or 0.0)), v))
    return vecinos[:limite]


# --- párrafos ------------------------------------------------------------------------------------
def _stems(texto: str, paquete) -> frozenset[str]:
    """Términos de un texto del corpus: los mismos párrafos vuelven en muchas consultas."""
    return _stems_con(texto, getattr(paquete, "stemmer", None))


@functools.lru_cache(maxsize=8192)
def _stems_con(texto: str, stemmer: str | None) -> frozenset[str]:
    from types import SimpleNamespace

    from ipsis.lenguaje.texto import terminos

    return frozenset(terminos(texto, SimpleNamespace(stemmer=stemmer)))


def parrafos(texto: str, limite_caracteres: int | None = None,
             titulos: tuple[str, ...] = ()) -> list[tuple[int, int]]:
    """Offsets (relativos a ``texto``) de sus párrafos: cada línea no vacía.

    El parser deja un párrafo por línea y los títulos de sección como líneas
    sueltas: una línea igual a uno de ``titulos`` (el documento o una sección)
    o que empieza con ``#`` no es un párrafo. Uno más largo que
    ``limite_caracteres`` se parte en oraciones: una alternativa muestra un
    producto o una regla, no una sección entera.
    """
    from ipsis.lenguaje.texto import dividir_oraciones

    normalizados = {" ".join(t.split()).lower() for t in titulos if t}
    salida = []
    for m in _LINEA.finditer(texto):
        inicio, fin = m.start(), m.end()
        bloque = texto[inicio:fin]
        inicio += len(bloque) - len(bloque.lstrip())
        fin -= len(bloque) - len(bloque.rstrip())
        linea = texto[inicio:fin]
        if fin <= inicio or linea.startswith("#") or " ".join(linea.split()).lower() in normalizados:
            continue
        if limite_caracteres and fin - inicio > limite_caracteres:
            salida.extend((inicio + a, inicio + b) for a, b in dividir_oraciones(linea))
        else:
            salida.append((inicio, fin))
    return salida


def _ruta(chunk: ChunkRecord, inicio: int) -> list[str]:
    """Ruta de sección del párrafo que empieza en ``inicio`` (relativo al chunk).

    Un chunk que cruza secciones las trae en ``metadata["secciones"]``, con
    offsets del documento; la cita usa la del párrafo mostrado."""
    absoluto = chunk.offset_inicio + inicio
    for seccion in (chunk.metadata or {}).get("secciones") or []:
        if seccion["inicio"] <= absoluto < seccion["fin"]:
            return list(seccion["ruta"])
    return list(chunk.seccion_path)


def _evidencia(chunk: ChunkRecord, inicio: int, fin: int, ruta: list[str], score: float) -> EvidenceSpan:
    """Evidencia con offsets del documento, como la del resto de la cascada."""
    return EvidenceSpan(doc_id=chunk.doc_id, chunk_id=chunk.chunk_id, texto=chunk.texto_fuente[inicio:fin],
                        offset_inicio=chunk.offset_inicio + inicio, offset_fin=chunk.offset_inicio + fin,
                        seccion_path=ruta, score=score)


# --- búsqueda ------------------------------------------------------------------------------------
@dataclass
class ConfigAlternativas:
    modo: str = "proactiva"  # o «estricta»: sin alternativas
    max_alternativas: int = 3
    umbral: float = 0.5
    pesos: dict[str, float] = field(default_factory=dict)

    @property
    def activa(self) -> bool:
        return self.modo == "proactiva" and self.max_alternativas > 0


def _terminos_pregunta(motor, ctx) -> tuple[set[str], int]:
    """Términos de contenido de la pregunta que están en el corpus (stems) y
    cuántos términos de contenido tiene la pregunta en total.

    Las fracciones se toman sobre el total: en «¿Tienen guantes de trabajo?»
    solo «trabajo» está en el corpus, pero lo pedido son los guantes; un
    párrafo con «trabajo» cubre la mitad de la pregunta, no toda.

    Las palabras de una entidad de la pregunta («cuatro días», «TP-500») no
    cuentan: de lo parecido a una entidad se encarga la familia."""
    from ipsis.lenguaje.consultas import terminos_genericos
    from ipsis.lenguaje.entidades import extraer_entidades

    obtener = getattr(motor.retriever, "estadisticas_lexico", None)
    est = obtener() if callable(obtener) else None
    genericos = terminos_genericos(motor.idioma)
    de_entidades = _stems(" ".join(e["texto"] for e in extraer_entidades(ctx.pregunta_usuario or ctx.pregunta)),
                          motor.idioma)
    propios = [t for t in ctx.terminos_pregunta if t not in de_entidades]
    todos = set(t for t in propios if t not in genericos) or set(propios)
    en_corpus = {t for t in todos if est.df.get(t, 0) > 0} if est is not None and hasattr(est, "df") else todos
    return en_corpus, len(todos)


def _categoria_pregunta(motor, pregunta: str) -> str | None:
    """Categoría de la pregunta con la taxonomía del proyecto, si distingue alguna."""
    taxonomia = getattr(motor, "taxonomia", None)
    if not taxonomia:
        return None
    propias = [c for c in taxonomia.get("categorias", []) if c.get("id") != "otro"]
    if len(propias) < 2:
        return None  # una sola categoría (la plantilla: «contenido») no distingue nada
    paquete = motor.idioma
    preguntas = _terminos_categoria(pregunta, paquete, _palabras_vacias(motor, paquete))
    mejor, puntaje = None, 0.0
    for cat, descripcion, gatillo in _terminos_taxonomia(motor, paquete):
        # Misma puntuación que ``clasificar_categoria`` de la ingesta.
        valor = min(1.0, (2 * len(preguntas & gatillo) + len(preguntas & descripcion)) / 6.0)
        if valor > puntaje:
            mejor, puntaje = cat, valor
    return mejor


def _palabras_vacias(motor, paquete) -> frozenset[str]:
    guardado = getattr(motor, "_palabras_vacias", None)
    if guardado is not None and guardado[0] is paquete:
        return guardado[1]
    vacias = _stems(" ".join(getattr(paquete, "stopwords", None) or []), paquete)
    motor._palabras_vacias = (paquete, vacias)
    return vacias


def _terminos_categoria(texto: str, paquete, vacias: frozenset[str]) -> frozenset[str]:
    """Los términos con que la ingesta clasifica un fragmento
    (``ipsis.ingesta.metadata._terminos``): sin palabras vacías, cifras ni
    palabras de menos de tres letras."""
    from ipsis.lenguaje.texto import terminos, tokenizar

    pares = zip(terminos(texto, paquete), tokenizar(texto, normalizado=False))
    return frozenset(t for t, f in pares if t not in vacias and len(f) >= 3 and f.isalpha())


def _terminos_taxonomia(motor, paquete) -> list[tuple[str, frozenset[str], frozenset[str]]]:
    guardado = getattr(motor, "_terminos_taxonomia", None)
    if guardado is not None and guardado[0] is motor.taxonomia:
        return guardado[1]
    vacias = _palabras_vacias(motor, paquete)
    terminos_cat = [(c["id"], _terminos_categoria(c.get("descripcion", ""), paquete, vacias),
                     _terminos_categoria(" ".join(c.get("palabras_gatillo", [])), paquete, vacias))
                    for c in motor.taxonomia.get("categorias", []) if c.get("id") != "otro"]
    motor._terminos_taxonomia = (motor.taxonomia, terminos_cat)
    return terminos_cat


def _fraccion(tq: set[str], presentes: set[str], total: int) -> float:
    return len(tq & presentes) / total if total else 0.0


def buscar_alternativas(motor, ctx, *, entidades_ausentes: list[dict] | None = None,
                        config: ConfigAlternativas | None = None,
                        guardar_todas: bool = False) -> ResultadoAlternativas:
    """Alternativas para la pregunta de ``ctx``, de mayor a menor afinidad.

    ``guardar_todas`` deja en ``descartadas`` todos los párrafos elegibles
    con sus señales (la calibración re-decide con ellas sin volver a correr
    el motor).
    """
    config = config or getattr(motor, "alternativas", None) or ConfigAlternativas()
    paquete = motor.idioma
    tq, total = _terminos_pregunta(motor, ctx)

    # 1. Fragmentos: los de la recuperación y, por cada entidad ausente, los
    #    que tienen una entidad de su familia.
    fragmentos: dict[str, tuple[ChunkRecord, str]] = {}
    for candidato in ctx.candidatos:
        fragmentos.setdefault(candidato.chunk.chunk_id, (candidato.chunk, "candidato"))
    # La familia de un tipo que declara el proyecto (sus códigos de producto)
    # es la señal «familia». La de una medida del núcleo («90 días», «20 %»)
    # es «medida»: aparece en documentos sin relación, y solo se busca si pesa
    # (o para calibrar).
    from ipsis.lenguaje.entidades import perfil_activo

    perfil = perfil_activo()
    declarados = perfil.tipos_aportados() if perfil is not None else set()
    con_medidas = config.pesos.get("medida", 0.0) > 0 or guardar_todas
    familia: set[str] = set()
    medidas: set[str] = set()
    inventario = motor.retriever.inventario_entidades()
    for entidad in entidades_ausentes or []:
        propia = entidad.get("tipo") in declarados
        if not propia and not con_medidas:
            continue
        for valor in vecinos_de_familia(entidad["valor_norm"], inventario):
            (familia if propia else medidas).add(valor)
            for candidato in motor.retriever.recuperar(ctx.consulta, 1, filtro=FiltroEntidad(valor_norm=valor)):
                fragmentos.setdefault(candidato.chunk.chunk_id, (candidato.chunk, "familia"))

    # 2. Párrafos elegibles con sus señales léxicas y de metadatos.
    categoria = _categoria_pregunta(motor, ctx.pregunta_usuario or ctx.pregunta)
    limite = (getattr(motor, "configuracion_redaccion", None) or {}).get("longitud_maxima_fragmento_chars")
    unidades: list[tuple[ChunkRecord, int, int, list[str], dict[str, float], str]] = []
    for chunk, origen in fragmentos.values():
        meta = chunk.metadata or {}
        titulos = (chunk.doc_titulo, *chunk.seccion_path,
                   *(t for seccion in meta.get("secciones") or [] for t in seccion["ruta"]))
        en_keywords = _stems(" ".join(meta.get("keywords") or []), paquete)
        misma_categoria = 1.0 if categoria is not None and meta.get("categoria") == categoria else 0.0
        valores_familia = {e["valor_norm"] for e in chunk.entidades} & (familia | medidas)
        for inicio, fin in parrafos(chunk.texto_fuente, limite, titulos):
            texto = chunk.texto_fuente[inicio:fin]
            ruta = _ruta(chunk, inicio)
            en_parrafo = {e["valor_norm"] for e in chunk.entidades
                          if e["valor_norm"] in valores_familia and inicio <= e.get("offset", -1) < fin}
            terminos_parrafo = _fraccion(tq, _stems(texto, paquete), total)
            senales = {
                "familia": 1.0 if en_parrafo & familia else 0.0,
                "medida": 1.0 if en_parrafo & medidas and terminos_parrafo > 0 else 0.0,
                "terminos": terminos_parrafo,
                "seccion": _fraccion(tq, _stems(" ".join([chunk.doc_titulo, *ruta]), paquete), total),
                "keywords": _fraccion(tq, en_keywords, total),
                "categoria": misma_categoria,
            }
            if elegible(senales):
                unidades.append((chunk, inicio, fin, ruta, senales, origen))
    unidades.sort(key=lambda u: (-u[4]["familia"], -u[4]["medida"], -u[4]["terminos"], -u[4]["seccion"]))
    unidades = unidades[:MAX_PARRAFOS]
    # Si la entidad ausente tiene vecinos («TP-400» para «TP-500»), lo parecido
    # son ellos: un párrafo que solo comparte el tema no se ofrece a su lado.
    hay_familia = any(u[4]["familia"] > 0 for u in unidades)

    # 3. Similitud densa de cada párrafo con la pregunta: solo si pesa (o para calibrar).
    if config.pesos.get("similitud", 0.0) > 0 or guardar_todas:
        _similitudes(motor, ctx, unidades)
    else:
        for unidad in unidades:
            unidad[4]["similitud"] = 0.0

    alternativas = []
    for chunk, inicio, fin, ruta, senales, origen in unidades:
        valor = afinidad(senales, config.pesos)
        alternativas.append(Alternativa(_evidencia(chunk, inicio, fin, ruta, round(valor, 4)), chunk,
                                        SenalesAlternativa(**senales), valor, origen))
    alternativas.sort(key=lambda a: -a.afinidad)

    resultado = ResultadoAlternativas()
    vistos: set[str] = set()
    for alternativa in alternativas:
        clave = " ".join(alternativa.evidencia.texto.split())
        repetida = clave in vistos
        vistos.add(clave)
        if (not repetida and alternativa.afinidad >= config.umbral
                and (alternativa.senales.familia > 0 or not hay_familia)
                and len(resultado.ofrecidas) < config.max_alternativas):
            resultado.ofrecidas.append(alternativa)
        elif guardar_todas or not repetida:
            resultado.descartadas.append(alternativa)
    return resultado


def _similitudes(motor, ctx, unidades) -> None:
    """Agrega ``similitud`` a cada unidad: coseno denso normalizado desde el piso."""
    codificador = getattr(motor.retriever, "codificador", None)
    vector = getattr(motor.retriever, "vector_consulta", None)
    if not unidades or codificador is None or not callable(vector):
        for unidad in unidades:
            unidad[4]["similitud"] = 0.0
        return
    import numpy as np

    from ipsis.consulta.etapas.politica import normalizar_coseno

    piso = getattr(motor.politica_abstencion, "piso_coseno", 0.0) or 0.0
    q = np.asarray(vector(ctx.consulta.pregunta_original), dtype=float)
    textos = [chunk.texto_fuente[inicio:fin] for chunk, inicio, fin, *_ in unidades]
    matriz = np.asarray(codificador.codificar_documentos(textos), dtype=float)
    normas = np.linalg.norm(matriz, axis=1) * (np.linalg.norm(q) or 1.0)
    cosenos = matriz @ q / np.where(normas == 0, 1.0, normas)
    for unidad, coseno in zip(unidades, cosenos):
        unidad[4]["similitud"] = normalizar_coseno(float(coseno), piso)


__all__ = [
    "Alternativa", "ConfigAlternativas", "MOTIVOS_CON_ALTERNATIVAS", "ResultadoAlternativas", "SENALES",
    "SenalesAlternativa", "afinidad", "buscar_alternativas", "elegible", "esqueleto", "parrafos",
    "vecinos_de_familia",
]
