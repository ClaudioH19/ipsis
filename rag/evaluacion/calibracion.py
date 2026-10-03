"""Calibración de umbrales sobre el split ``dev`` de un banco de evaluación."""
from __future__ import annotations

from dataclasses import dataclass, field


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
