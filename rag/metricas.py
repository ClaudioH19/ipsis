"""Métricas compartidas por las evaluaciones E1–E6 (sección 5 y 11).

Incluye:
  - el evaluador factual determinista (comparación por ``valor_norm``,
    nunca similitud semántica) usado para validar P1–P7 y, más adelante,
    en E6 sobre respuestas reales del sistema.
  - recall@k, MRR, nDCG@k, cobertura de evidencia y de hechos (para E2/E3).
  - bootstrap de percentiles para IC 95% (sección 5, E2).
"""
from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field

from rag.reglas_extraccion import extraer_entidades

MARCADORES_EXCEPCION_CONDICION = [
    "salvo", "excepto", "a menos que", "sin perjuicio de", "no aplica", "con todo",
    "excepcionalmente", "siempre que", "en caso de", "cuando", "en tanto",
    "sin embargo", "no obstante", "pero", "a excepcion de", "excluye", "exceptuando",
]

_RE_NEGACION = re.compile(r"\bno\s+\w+|\btampoco\b", re.IGNORECASE)

# Defecto 3 (E6/P5): se agregó "pero" (la conectiva usada por el golden set v2
# para redactar excepciones) y otras
# formas equivalentes ("a excepcion de", "excluye", "exceptuando") encontradas
# leyendo las respuestas del golden set real. "pero" faltaba y por eso P5 daba
# 55.6% en vez de rechazar el 100% de esas perturbaciones (ver ESTADO.md).

# Defecto 1 (E6/precisión de hechos): además de las entidades del vocabulario
# cerrado del dominio (nota/porcentaje/plazo/fecha/articulo/saber/semana/
# organismo, ver rag/reglas_extraccion.py), se detectan dos patrones GENÉRICOS
# adicionales -solo para el chequeo de precisión, nunca para hechos_clave ni
# para la ingesta/metadata- que permiten marcar como "inventada" una cifra
# monetaria o un organismo ajenos por completo al dominio (p.ej. "45 UF" o
# "Contraloría General de la República"), que el vocabulario cerrado no
# reconocería en absoluto y por eso pasarían desapercibidos.
_RE_CIFRA_GENERICA = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(UF|USD|CLP|\$|pesos)\b", re.IGNORECASE)

_PALABRAS_INSTITUCIONALES = [
    "ministerio", "contraloria", "servicio", "direccion", "consejo", "comision",
    "tribunal", "corte", "republica", "gobierno", "superintendencia", "subsecretaria",
    "intendencia", "municipalidad", "fiscalia",
]
_RE_ORGANISMO_GENERICO = re.compile(
    r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*(?:\s+(?:de|del|la|las|los|y)?\s*[A-ZÁÉÍÓÚÑ][\wáéíóúñ]*)+\b"
)

# Bug corregido de E6/precisión de hechos:
# _RE_ORGANISMO_GENERICO captura el artículo determinante inicial ("La",
# "El", "Los", "Las") cuando queda en mayúscula por ir al comienzo de una
# oración ("La Dirección de Escuela resuelve..."), pero no cuando el mismo
# organismo aparece a mitad de frase ("...lo resuelve la Dirección de
# Escuela"), porque ahí el artículo va en minúscula y el regex exige mayúscula
# inicial. Las dos capturas producían `valor_norm` distintos para la MISMA
# entidad ("la_direccion_de_escuela" vs. "direccion_de_escuela"), así que una
# paráfrasis fiel que solo reordenara la oración podía marcarse como "posible
# información inventada" (caso mínimo reproducible: PERT-0181, de Q-0100).
# Reparación: se quita un artículo determinante inicial del texto capturado
# ANTES de normalizar, para que ambas formas colapsen al mismo valor_norm.
_ARTICULOS_DETERMINANTES_INICIALES = {"el", "la", "los", "las"}


def _quitar_articulo_inicial(texto_organismo: str) -> str:
    """Quita un artículo determinante inicial (mayúscula o minúscula) del
    texto capturado por ``_RE_ORGANISMO_GENERICO``, para que "La Dirección de
    Escuela" y "la Dirección de Escuela" normalicen al mismo ``valor_norm``."""
    partes = texto_organismo.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() in _ARTICULOS_DETERMINANTES_INICIALES:
        return partes[1]
    return texto_organismo


def _normalizar_laxo(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower()
    return re.sub(r"[^a-z0-9]+", "_", texto).strip("_")


def _valores_norm(texto: str) -> set[str]:
    return {e["valor_norm"] for e in extraer_entidades(texto)}


def _valores_precision_amplios(texto: str) -> set[str]:
    """Superconjunto de ``_valores_norm`` usado SOLO por el chequeo de
    precisión de hechos (Defecto 1): agrega cifras monetarias y organismos
    genéricos (lista cerrada de palabras institucionales, no NER abierto) que
    el vocabulario cerrado del dominio no cubre. No se usa para hechos_clave,
    hechos_prohibidos ni para la cobertura de entidades de la referencia,
    para no alterar ningún comportamiento ya validado por P1-P7."""
    valores = set(_valores_norm(texto))
    for m in _RE_CIFRA_GENERICA.finditer(texto):
        num = m.group(1).replace(",", ".")
        unidad = m.group(2).lower().replace("$", "clp")
        valores.add(f"cifra_{num}_{unidad}")
    for m in _RE_ORGANISMO_GENERICO.finditer(texto):
        candidato = _normalizar_laxo(_quitar_articulo_inicial(m.group(0)))
        if any(p in candidato for p in _PALABRAS_INSTITUCIONALES):
            valores.add(f"organismo_generico_{candidato}")
    return valores


def _contar_negaciones(texto: str) -> int:
    return len(_RE_NEGACION.findall(texto))


def _marcadores_presentes(texto: str) -> set[str]:
    low = texto.lower()
    return {m for m in MARCADORES_EXCEPCION_CONDICION if m in low}


# Defecto 2 (E6/negación): la paridad global de negaciones se cancela con dos
# negaciones agregadas en cláusulas distintas (p.ej. "debe" -> "no debe" Y
# "puede" -> "no puede" en la misma respuesta: 2 negaciones más, paridad
# global sin cambios). Se reemplaza por una comparación por CLÁUSULA: se
# separa el texto en cláusulas (puntuación fuerte y conectores adversativos
# "pero"/"sin embargo"/"no obstante") y se compara, cláusula a cláusula, la
# paridad de negaciones. Invertir el sentido en una cláusula cambia SU
# paridad aunque el total global no cambie. Además, si la candidata tiene
# menos cláusulas que la referencia se marca como posible truncamiento/
# omisión (una respuesta cortada a la mitad pierde cláusulas completas).
_RE_CLAUSULA_SEP = re.compile(r"[.;]+|\bpero\b|\bsin embargo\b|\bno obstante\b", re.IGNORECASE)


def _clausulas(texto: str) -> list[str]:
    return [p.strip() for p in _RE_CLAUSULA_SEP.split(texto) if p.strip()]


def _paridades_por_clausula(texto: str) -> list[int]:
    return [_contar_negaciones(c) % 2 for c in _clausulas(texto)]


def _palabra_presente(palabra: str, tokens: set[str]) -> bool:
    """Presencia de ``palabra`` en el conjunto de tokens de la candidata, con
    una tolerancia mínima de conjugación (stemming de prefijo) para hechos
    ``proposicion`` (Defecto 4). ``hechos_clave`` se redacta a partir de la
    EVIDENCIA literal (el formato del golden set lo exige
    así), pero ``respuesta_referencia`` a veces conjuga el mismo verbo
    distinto (p.ej. evidencia "tratar como" -> referencia "los trata como").
    Exigir el token exacto rompería ese caso legítimo; ignorar la palabra
    por completo perdonaría verdaderos hechos ausentes. Para palabras
    funcionales muy cortas (<=3 letras: "no", "se", "al"...) NO se aplica
    stemming -- son justamente las que marcan negación/sentido, y una
    coincidencia de prefijo ahí sería casi cualquier palabra."""
    if palabra in tokens:
        return True
    if len(palabra) <= 3:
        return False
    raiz = palabra[: max(3, len(palabra) - 2)]
    return any(len(tok) > 3 and tok.startswith(raiz) for tok in tokens)


@dataclass
class ResultadoFactual:
    correcta: bool
    motivos: list[str] = field(default_factory=list)


def evaluar_exactitud_factual(respuesta_candidata: str, respuesta_referencia: str,
                               hechos_clave: list[dict], hechos_prohibidos: list[dict],
                               fragmentos: list[str] | None = None) -> ResultadoFactual:
    """Evaluador factual determinista (sección 4.4 / E6).

    ``fragmentos`` es OPCIONAL y nuevo (Defecto 1): los fragmentos fuente
    reales usados para construir la respuesta candidata (los chunks
    recuperados). Si no se entregan, la precisión de hechos se valida contra
    ``respuesta_referencia`` (comportamiento de respaldo, compatible con
    quien llamaba a esta función antes de este cambio, p.ej.
    pruebas adversariales sobre perturbaciones sin fragmentos).

    Regla de decisión — TODAS deben cumplirse para que la respuesta se
    marque ``correcta``:
      1. Toda entidad determinista presente en la respuesta de referencia
         (nota, porcentaje, plazo, fecha, artículo, saber, semana, organismo)
         debe seguir presente en la respuesta candidata (detecta P1 cifra,
         P2 unidad, P4 entidad por AUSENCIA).
      1b. **Precisión de hechos** (Defecto 1): toda entidad determinista (y,
          de forma más amplia solo para este chequeo, cifra monetaria u
          organismo genérico) presente en la respuesta CANDIDATA debe estar
          respaldada por los fragmentos fuente (o, sin fragmentos, por la
          referencia) — detecta información AGREGADA que no viene de la
          fuente (cifra/organismo/plazo inventado), que el punto 1 nunca
          detecta porque solo mira ausencias.
      2. Todo ``hecho_clave`` del ítem debe estar presente en la respuesta
         candidata. Los hechos de tipo ``proposicion`` (Defecto 4: hechos que
         son oraciones comprimidas, no valores/entidades, p.ej.
         "no_se_agregan_entradas") se verifican por cobertura de palabras
         (todas las palabras de su ``valor_norm`` deben aparecer como token
         en la candidata, en cualquier orden) en vez de por substring literal
         contiguo, porque una paráfrasis fiel puede reordenar o intercalar
         palabras sin cambiar el sentido. El resto (cifras, plazos,
         entidades, conceptos cortos) se sigue verificando por entidad o por
         forma laxa normalizada, sin cambios.
      3. Ningún ``hecho_prohibido`` debe aparecer en la respuesta candidata
         (detecta P6 versión/valor equivocado).
      4. La paridad de negaciones POR CLÁUSULA (Defecto 2) debe conservarse
         cláusula a cláusula entre referencia y candidata, y la candidata no
         debe tener menos cláusulas que la referencia (detecta P3 negación,
         doble negación que invierte el sentido, y respuestas truncadas u
         omisiones parciales — la paridad GLOBAL antigua se cancelaba con dos
         negaciones agregadas en cláusulas distintas).
      5. Todo marcador de excepción/condición presente en la referencia debe
         seguir presente en la candidata (detecta P5 condición eliminada).
    """
    motivos: list[str] = []

    ref_valores = _valores_norm(respuesta_referencia)
    cand_valores = _valores_norm(respuesta_candidata)
    cand_laxo = _normalizar_laxo(respuesta_candidata)
    cand_tokens = set(cand_laxo.split("_"))

    faltantes = ref_valores - cand_valores
    if faltantes:
        motivos.append(f"entidades de la referencia ausentes en la candidata: {faltantes}")

    # --- Defecto 1: precisión de hechos (información agregada/inventada) ---
    if respuesta_candidata.strip():
        cand_valores_amplios = _valores_precision_amplios(respuesta_candidata)
        if fragmentos:
            fuente_valores = set()
            for frag in fragmentos:
                fuente_valores |= _valores_precision_amplios(frag)
        else:
            fuente_valores = _valores_precision_amplios(respuesta_referencia)
        inventados = cand_valores_amplios - fuente_valores
        if inventados:
            motivos.append(f"entidades en la candidata no respaldadas por la fuente (posible información inventada): {inventados}")

    for hc in hechos_clave:
        vn = hc["valor_norm"]
        if hc.get("tipo") == "proposicion":
            palabras = [w for w in vn.split("_") if w]
            if not all(_palabra_presente(w, cand_tokens) for w in palabras):
                motivos.append(f"hecho_clave (proposición) ausente: {vn}")
        elif vn not in cand_valores and _normalizar_laxo(vn) not in cand_laxo:
            motivos.append(f"hecho_clave ausente: {vn}")

    for hp in hechos_prohibidos:
        vn = hp["valor_norm"]
        if vn in cand_valores or _normalizar_laxo(vn) in cand_laxo:
            motivos.append(f"hecho_prohibido presente: {vn}")

    # --- Defecto 2: paridad de negación por cláusula, no global ---
    par_ref = _paridades_por_clausula(respuesta_referencia)
    par_cand = _paridades_por_clausula(respuesta_candidata)
    if len(par_cand) < len(par_ref):
        motivos.append(
            f"la candidata tiene menos cláusulas que la referencia "
            f"({len(par_cand)} vs {len(par_ref)}): posible truncamiento u omisión"
        )
    else:
        for i, p_ref in enumerate(par_ref):
            if par_cand[i] != p_ref:
                motivos.append(
                    f"paridad de negación distinta en la cláusula {i + 1} "
                    f"(ref={p_ref}, cand={par_cand[i]}): posible inversión de sentido"
                )

    marcadores_ref = _marcadores_presentes(respuesta_referencia)
    marcadores_cand = _marcadores_presentes(respuesta_candidata)
    marcadores_perdidos = marcadores_ref - marcadores_cand
    if marcadores_perdidos:
        motivos.append(f"marcadores de excepción/condición perdidos: {marcadores_perdidos}")

    return ResultadoFactual(correcta=(len(motivos) == 0), motivos=motivos)


# ---------------------------------------------------------------------------
# Métricas de recuperación (E2/E3)
# ---------------------------------------------------------------------------

def acierto_chunk(chunk_offset_ini: int, chunk_offset_fin: int, ev_ini: int, ev_fin: int,
                   umbral: float = 0.5) -> bool:
    """Criterio de acierto de la sección 5: el chunk contiene >= 50% de los
    caracteres de la evidencia."""
    inter_ini = max(chunk_offset_ini, ev_ini)
    inter_fin = min(chunk_offset_fin, ev_fin)
    inter = max(0, inter_fin - inter_ini)
    largo_evidencia = ev_fin - ev_ini
    if largo_evidencia <= 0:
        return False
    return (inter / largo_evidencia) >= umbral


def recall_at_k(resultados_por_pregunta: list[list[bool]], k: int) -> float:
    """``resultados_por_pregunta[i]`` es la lista de aciertos (bool) de los
    chunks recuperados para la pregunta i, en orden de score. Recall@k = 1 si
    hay al menos un acierto en los primeros k."""
    if not resultados_por_pregunta:
        return 0.0
    aciertos = [any(r[:k]) for r in resultados_por_pregunta]
    return sum(aciertos) / len(aciertos)


def mrr(resultados_por_pregunta: list[list[bool]]) -> float:
    total = 0.0
    for r in resultados_por_pregunta:
        for i, acierto in enumerate(r, 1):
            if acierto:
                total += 1.0 / i
                break
    return total / len(resultados_por_pregunta) if resultados_por_pregunta else 0.0


def ndcg_at_k(resultados_por_pregunta: list[list[bool]], k: int) -> float:
    import math
    total = 0.0
    for r in resultados_por_pregunta:
        dcg = sum((1.0 / math.log2(i + 1)) for i, acierto in enumerate(r[:k], 1) if acierto)
        idcg = 1.0  # como máximo hay un acierto relevante contado por pregunta (criterio binario)
        total += dcg / idcg if idcg else 0.0
    return total / len(resultados_por_pregunta) if resultados_por_pregunta else 0.0


def cobertura_evidencia(chunks_top_k: list[tuple[int, int]], evidencias: list[tuple[int, int]]) -> float:
    """% de caracteres de las evidencias cubiertos por la unión de los chunks top-k."""
    total_evidencia = sum(fin - ini for ini, fin in evidencias)
    if total_evidencia == 0:
        return 0.0
    cubiertos = 0
    for ev_ini, ev_fin in evidencias:
        for c_ini, c_fin in chunks_top_k:
            inter_ini = max(ev_ini, c_ini)
            inter_fin = min(ev_fin, c_fin)
            cubiertos += max(0, inter_fin - inter_ini)
    return min(1.0, cubiertos / total_evidencia)


def hecho_presente_en_texto(hecho: dict, texto: str) -> bool:
    """Verifica si un ``hecho_clave``/``hecho_prohibido`` está presente en
    ``texto``, con el MISMO criterio que ya usan ``cobertura_hechos`` y
    ``evaluar_exactitud_factual`` (no se reimplementa la lógica): por entidad determinista
    (``rag/reglas_extraccion.py``), por subcadena laxa normalizada, o -- para
    ``tipo: "proposicion"`` (Defecto 4, hechos que son oraciones comprimidas)
    -- por cobertura de palabras con tolerancia de prefijo.

    Expuesta como función pública (las de arriba usan un helper privado
    equivalente) para que otros módulos puedan reutilizarla
    sin duplicar la normalización.
    """
    vn = hecho["valor_norm"]
    if hecho.get("tipo") == "proposicion":
        tokens = set(_normalizar_laxo(texto).split("_"))
        palabras = [w for w in vn.split("_") if w]
        return all(_palabra_presente(w, tokens) for w in palabras)
    valores = _valores_norm(texto)
    laxo = _normalizar_laxo(texto)
    return vn in valores or _normalizar_laxo(vn) in laxo


def cobertura_hechos(hechos_clave: list[dict], textos_top_k: list[str]) -> float:
    if not hechos_clave:
        return 1.0
    texto_concat = " ".join(textos_top_k)
    valores_presentes = _valores_norm(texto_concat)
    laxo = _normalizar_laxo(texto_concat)
    presentes = 0
    for hc in hechos_clave:
        vn = hc["valor_norm"]
        if vn in valores_presentes or _normalizar_laxo(vn) in laxo:
            presentes += 1
    return presentes / len(hechos_clave)


# ---------------------------------------------------------------------------
# Bootstrap (sección 5, E2): IC 95% por remuestreo con reposición.
# ---------------------------------------------------------------------------

def bootstrap_ic(valores: list[float], n_remuestreos: int = 1000, nivel: float = 0.95,
                  semilla: int = 42) -> tuple[float, float, float]:
    """Devuelve (media, límite_inferior, límite_superior) del IC bootstrap."""
    rng = random.Random(semilla)
    n = len(valores)
    if n == 0:
        return 0.0, 0.0, 0.0
    medias = []
    for _ in range(n_remuestreos):
        muestra = [valores[rng.randrange(n)] for _ in range(n)]
        medias.append(sum(muestra) / n)
    medias.sort()
    alpha = 1 - nivel
    lo_idx = int((alpha / 2) * n_remuestreos)
    hi_idx = int((1 - alpha / 2) * n_remuestreos) - 1
    media_obs = sum(valores) / n
    return media_obs, medias[max(0, lo_idx)], medias[min(n_remuestreos - 1, hi_idx)]
