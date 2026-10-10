"""Calibración de umbrales con control de riesgo sobre el golden del cliente.

No entrena nada: elige umbrales escalares entre valores observados. Trabaja
solo con observaciones ya producidas (señales guardadas por caso) y re-decide
cada caso con ``regla_cascada``, la misma función que usa la política en
producción, sin volver a correr modelos.

Criterio (docs/methodology/calibration.md): maximizar la cobertura directa
sujeta a que la cota superior de Clopper-Pearson del riesgo de las respuestas
aceptadas sea ≤ α. Los umbrales se eligen en ``dev``; ``test`` solo verifica.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ipsis.configuracion.calibracion import (
    ArchivoCalibracion,
    EstadoCalibracion,
    ProcedenciaCalibracion,
    normalizar_umbrales,
)
from ipsis.consulta.etapas.politica import (
    RESULTADO_DE_REGLA,
    SenalesPolitica,
    foco_exigido,
    lector_seguro,
    regla_cascada,
)
from ipsis.evaluacion.banco import BancoEvaluacion, CasoEvaluacion, exigir_calibrable
from ipsis.recursos.mensajes import t
from ipsis.evaluacion.metricas import (
    ObservacionEvaluacion,
    RiesgoAceptadas,
    cota_superior_clopper_pearson,
    es_no_respondible,
    muestra_respuesta_literal,
    n_minimo,
    reporte_cobertura,
)

# Los umbrales que deciden si se responde directo. Los de dominio y
# relacionado (oov_dominio, dominio, relacionado) y cov quedan en el valor del
# perfil: no cambian el riesgo de una respuesta aceptada.
CALIBRABLES = ("ok", "oov_ok", "foco")
NUNCA = 1.01  # umbral que ninguna señal en [0, 1] alcanza
ESTADO_DE_RESULTADO = {"responde": "respuesta_directa", "relacionado": "relacionado", "abstiene": "sin_respuesta"}

Par = tuple[CasoEvaluacion, ObservacionEvaluacion]


# ---------------------------------------------------------------------------
# Re-decidir con otros umbrales
# ---------------------------------------------------------------------------
def _senales(obs: ObservacionEvaluacion) -> SenalesPolitica | None:
    s = obs.senales
    if s is None or None in (s.s_ret, s.s_oov, s.s_foco, s.s_cov):
        return None
    return SenalesPolitica(s_ret=s.s_ret, s_oov=s.s_oov, s_foco=s.s_foco, s_cov=s.s_cov, s_rr=s.s_rr, s_qa=s.s_qa,
                           coloquial=bool(s.coloquial))


def redecidir(obs: ObservacionEvaluacion, umbrales: dict[str, float]) -> ObservacionEvaluacion:
    """La observación con el estado que la política habría dado con ``umbrales``.

    - Sin señales (la política no decidió: conversacional, sin fragmentos…) el
      caso queda igual.
    - Una premisa que falló sigue fallando: no depende de umbrales.
    - «concordancia» (si ajustes_perfil la activa) baja un ok a relacionado, como en producción.
    - Las evidencias son las mismas: la etapa de evidencia corre antes de la
      política. Si la política se abstuvo, no se guardaron evidencias y un ok
      simulado sin la respuesta literal cuenta como error (conservador).
    """
    senales = _senales(obs)
    if senales is None:
        return obs
    regla = regla_cascada(senales, umbrales, premisa_falla=obs.regla == "premisa")
    if obs.regla == "concordancia" and regla.startswith("ok_"):
        regla = "concordancia"
    return obs.model_copy(update={"estado": ESTADO_DE_RESULTADO[RESULTADO_DE_REGLA[regla]], "regla": regla})


def redecidir_pares(pares: list[Par], umbrales: dict[str, float]) -> list[Par]:
    return [(caso, redecidir(obs, umbrales)) for caso, obs in pares]


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------
class MetricasSplit(BaseModel):
    n_casos: int
    cobertura_directa: float | None
    cobertura_exacta: float | None
    cobertura_parafrasis: float | None
    falsos_ok: int
    falsos_ok_trampas: int
    recall_fuera_de_dominio: float | None
    recall_premisa_falsa: float | None
    riesgo: RiesgoAceptadas


class ResultadoCalibracion(BaseModel):
    estado: EstadoCalibracion
    alfa: float
    confianza: float
    umbrales_perfil: dict[str, float]
    # Calibrado: los elegidos. Si no: los del perfil (no se aplica nada).
    umbrales: dict[str, float]
    calibrables: list[str]
    combinaciones_evaluadas: int
    n_minimo_sin_errores: int
    # Respuestas aceptadas en dev con la combinación más permisiva (la que más responde)…
    aceptadas_max_dev: int
    # …y el máximo de aceptadas sin ningún error, que es lo que cuenta para certificar.
    aceptadas_sin_error_max_dev: int
    faltan_aceptadas: int | None = None
    dev: MetricasSplit
    test: MetricasSplit | None = None
    # «cumple», «excede» o «muestra_insuficiente»: test se reporta aparte, nunca elige.
    verificacion_test: str | None = None
    mensaje: str
    candidatos: dict[str, list[float]] = Field(default_factory=dict)


def metricas_split(pares: list[Par], confianza: float) -> MetricasSplit:
    r = reporte_cobertura(pares, confianza)
    g = r.por_grupo
    return MetricasSplit(
        n_casos=r.total.n,
        cobertura_directa=r.total.cobertura_directa,
        cobertura_exacta=g["exacta"].cobertura_directa if "exacta" in g else None,
        cobertura_parafrasis=g["parafrasis"].cobertura_directa if "parafrasis" in g else None,
        falsos_ok=r.total.falsos_ok,
        falsos_ok_trampas=g["trampa_mismo_tema"].falsos_ok if "trampa_mismo_tema" in g else 0,
        recall_fuera_de_dominio=g["fuera_de_dominio"].recall_sin_respuesta if "fuera_de_dominio" in g else None,
        recall_premisa_falsa=g["premisa_falsa"].recall_sin_respuesta if "premisa_falsa" in g else None,
        riesgo=r.riesgo_aceptadas,
    )


# ---------------------------------------------------------------------------
# Búsqueda de umbrales (solo dev)
# ---------------------------------------------------------------------------
def _candidatos(pares: list[Par], base: dict[str, float]) -> dict[str, list[float]]:
    """Valores observados de cada señal (deterministas), más el del perfil.

    ``ok`` y ``foco`` se comparan con «≥»: el candidato es el valor. ``oov_ok``
    se compara con «<»: para admitir un ``s_oov`` observado ``v`` el umbral
    es apenas mayor que ``v``.
    """
    senales = [s for s in (_senales(o) for _c, o in pares) if s is not None]
    puntajes = {s.s_qa if s.s_qa is not None else s.s_ret for s in senales}
    return {
        "ok": sorted(puntajes | {base["ok"], NUNCA}),
        "foco": sorted({s.s_foco for s in senales} | {base["foco"]}),
        "oov_ok": sorted({round(s.s_oov + 1e-9, 12) for s in senales} | {base["oov_ok"]}),
    }


def _puntaje(s: SenalesPolitica, umbrales: dict[str, float]) -> float | None:
    """Señal que se compara con τ_ok para responder directo; ``None`` si el
    caso no puede dar ok por otra condición (cobertura léxica)."""
    if s.s_qa is not None:
        return s.s_qa
    return s.s_ret if s.s_cov >= umbrales["cov"] else None


def _barrer_ok(pares: list[Par], umbrales: dict[str, float],
               candidatos_ok: list[float]) -> list[tuple[float, int, int, int]]:
    """Para ``foco`` y ``oov_ok`` fijos, todos los ``ok`` candidatos de una vez.

    Devuelve ``(ok, n_aceptadas, errores, respondibles_directas)`` por
    candidato. Un caso responde directo si pasa las reglas previas (premisa,
    fuera de dominio, foco, oov_ok) y su puntaje ≥ ok: ordenar por puntaje y
    acumular da todos los cortes en O(n log n).
    """
    elegibles = []  # (puntaje, es_error, es_respondible)
    for caso, obs in pares:
        if caso.categoria.value == "conversacional":
            continue
        s = _senales(obs)
        if s is None or obs.regla in ("premisa", "concordancia"):
            continue
        if s.s_oov >= umbrales["oov_dominio"] and s.dominio < umbrales["dominio"]:
            continue
        seguro = lector_seguro(s, umbrales)
        if not seguro and not (s.s_foco >= foco_exigido(s, umbrales) and s.s_oov < umbrales["oov_ok"]):
            continue
        # El tramo fuerte (``lector_seguro``) no depende de ``ok``: entra con cualquier corte.
        puntaje = float("inf") if seguro else _puntaje(s, umbrales)
        if puntaje is None:
            continue
        error = es_no_respondible(caso) or (caso.respondible and not muestra_respuesta_literal(caso, obs))
        elegibles.append((puntaje, error, caso.respondible))
    elegibles.sort(key=lambda e: -e[0])
    salida, i, n, x, r = [], 0, 0, 0, 0
    for ok in sorted(candidatos_ok, reverse=True):  # de más estricto a más permisivo
        while i < len(elegibles) and elegibles[i][0] >= ok:
            n, x, r = n + 1, x + elegibles[i][1], r + elegibles[i][2]
            i += 1
        salida.append((ok, n, x, r))
    return salida


def _conservadora(umbrales: dict[str, float]) -> tuple:
    """Último desempate determinista: la más estricta."""
    return (umbrales["ok"], -umbrales["oov_ok"], umbrales["foco"])


def _preferencia(r: int, x: int, umbrales: dict[str, float], base: dict[str, float]) -> tuple:
    """Orden entre combinaciones que ya cumplen la cota (mayor es mejor).

    Primero más respuestas directas correctas en dev y menos errores. Ante
    empate, la más cercana al perfil: si dev no distingue dos valores, no hay
    evidencia para mover el umbral (antes se iba al extremo más estricto, p. ej.
    ``oov_ok`` a ~0 con todos los ``s_oov`` en 0). Recién después, la más estricta.
    """
    movidos = [abs(umbrales[k] - base[k]) for k in CALIBRABLES]
    return (r, -x, -sum(d > 1e-12 for d in movidos), -sum(movidos), _conservadora(umbrales))


def calibrar(
    banco: BancoEvaluacion,
    observaciones: list[ObservacionEvaluacion],
    umbrales_perfil: dict[str, float],
    alfa: float = 0.05,
    confianza: float = 0.95,
    *,
    separar_oov: bool = True,
) -> ResultadoCalibracion:
    """Elige ``ok``, ``oov_ok`` y ``foco`` en dev; verifica en test.

    Solo con un banco calibrable (el golden del cliente): el universal se
    rechaza. ``separar_oov=False`` reproduce la configuración anterior (un
    único ``oov`` para dominio y para ok), para comparar.
    """
    exigir_calibrable(banco)
    por_id = {o.caso_id: o for o in observaciones}
    return _calibrar_pares([(c, por_id[c.id]) for c in banco.casos], umbrales_perfil, alfa, confianza,
                           separar_oov=separar_oov)


def _calibrar_pares(pares: list[Par], umbrales_perfil: dict[str, float], alfa: float, confianza: float, *,
                    separar_oov: bool) -> ResultadoCalibracion:
    if not 0.0 < alfa < 1.0:
        raise ValueError("alfa debe estar en (0, 1)")
    base = normalizar_umbrales(umbrales_perfil)
    dev = [(c, o) for c, o in pares if c.split == "dev"]
    test = [(c, o) for c, o in pares if c.split == "test"]
    candidatos = _candidatos(dev, base)
    respondibles_dev = sum(c.respondible for c, _o in dev)

    mejor, combinaciones, aceptadas_max, sin_error_max = None, 0, 0, 0
    for foco in candidatos["foco"]:
        for oov_ok in candidatos["oov_ok"]:
            umbrales = {**base, "foco": foco, "oov_ok": oov_ok}
            if not separar_oov:
                umbrales["oov_dominio"] = oov_ok
            for ok, n, x, r in _barrer_ok(dev, umbrales, candidatos["ok"]):
                combinaciones += 1
                aceptadas_max = max(aceptadas_max, n)
                if x == 0:
                    sin_error_max = max(sin_error_max, n)
                if n == 0 or cota_superior_clopper_pearson(x, n, confianza) > alfa:
                    continue
                elegido = {**umbrales, "ok": ok}
                clave = _preferencia(r, x, elegido, base)
                if mejor is None or clave > mejor[0]:
                    mejor = (clave, elegido)

    necesarias = n_minimo(0, alfa, confianza)
    if mejor is not None:
        estado, umbrales_finales = EstadoCalibracion.CALIBRADO, mejor[1]
    elif aceptadas_max < necesarias:
        estado, umbrales_finales = EstadoCalibracion.MUESTRA_INSUFICIENTE, base
    else:
        estado, umbrales_finales = EstadoCalibracion.SIN_UMBRAL_SEGURO, base

    # La combinación final se verifica con la política completa, no con el barrido.
    metricas_dev = metricas_split(redecidir_pares(dev, umbrales_finales), confianza)
    resultado = ResultadoCalibracion(
        estado=estado, alfa=alfa, confianza=confianza, umbrales_perfil=base, umbrales=umbrales_finales,
        calibrables=list(CALIBRABLES), combinaciones_evaluadas=combinaciones, n_minimo_sin_errores=necesarias,
        aceptadas_max_dev=aceptadas_max, aceptadas_sin_error_max_dev=sin_error_max, dev=metricas_dev, mensaje="", candidatos=candidatos,
    )
    if estado == EstadoCalibracion.CALIBRADO:
        riesgo = metricas_dev.riesgo
        if riesgo.cota_superior is None or riesgo.cota_superior > alfa:
            raise AssertionError("la verificación completa en dev no reproduce el barrido")  # nunca debería
        resultado.mensaje = t("evaluation.calibrated", n=riesgo.n, x=riesgo.x, bound=f"{riesgo.cota_superior:.4f}",
                              alpha=alfa,
                              coverage=f"{metricas_dev.cobertura_directa if respondibles_dev else 0:.3f}")
    elif estado == EstadoCalibracion.MUESTRA_INSUFICIENTE:
        resultado.faltan_aceptadas = necesarias - sin_error_max
        resultado.mensaje = t("evaluation.insufficient_sample", without_errors=sin_error_max, alpha=alfa,
                              confidence=f"{confianza:.0%}", needed=necesarias,
                              missing=necesarias - sin_error_max)
    else:
        resultado.mensaje = t("evaluation.no_safe_threshold", accepted=aceptadas_max, alpha=alfa)

    if test:
        metricas_test = metricas_split(redecidir_pares(test, umbrales_finales), confianza)
        resultado.test = metricas_test
        riesgo = metricas_test.riesgo
        if riesgo.cota_superior is not None and riesgo.cota_superior <= alfa:
            resultado.verificacion_test = "cumple"
        elif riesgo.n < necesarias:  # ni sin errores alcanzaría para certificar α
            resultado.verificacion_test = "muestra_insuficiente"
        else:
            resultado.verificacion_test = "excede"
    return resultado


def explorar_umbrales(pares: list[Par], umbrales_perfil: dict[str, float], alfa: float = 0.05,
                      confianza: float = 0.95, *, separar_oov: bool = True) -> ResultadoCalibracion:
    """Análisis sobre cualquier banco (incluido el universal): mismo cálculo que
    ``calibrar`` pero sin escribir nada ni exigir un banco calibrable. Sus
    umbrales nunca se aplican a un cliente."""
    return _calibrar_pares(pares, umbrales_perfil, alfa, confianza, separar_oov=separar_oov)


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------
def escribir_calibracion(resultado: ResultadoCalibracion, procedencia: ProcedenciaCalibracion,
                         ruta: str | Path) -> Path:
    """``config/calibration.yaml`` (escritura atómica). Se escribe en
    cualquier estado, para auditoría; solo ``calibrado`` se aplica."""
    from ipsis.evaluacion.golden import escribir_atomico

    archivo = ArchivoCalibracion(
        estado=resultado.estado, alfa=resultado.alfa, confianza=resultado.confianza, procedencia=procedencia,
        umbrales=resultado.umbrales,
        resultado={"mensaje": resultado.mensaje, "dev": resultado.dev.model_dump(mode="json"),
                   "test": resultado.test.model_dump(mode="json") if resultado.test else None,
                   "verificacion_test": resultado.verificacion_test},
    )
    ruta = Path(ruta)
    from ipsis.configuracion.archivos import volcar

    escribir_atomico(ruta, volcar(archivo.model_dump(mode="json"), "calibracion"))
    return ruta


def cargar_calibracion(ruta: str | Path, *, perfil: str, modelos: dict, hash_corpus: str | None,
                       hash_lexico: str | None = None):
    """``(archivo, motivo)``: el archivo leído y por qué no se aplicaría
    (``None`` si se aplica). ``(None, None)`` si no hay calibración."""
    from ipsis.configuracion.calibracion import leer_calibracion, motivo_no_aplicable

    archivo = leer_calibracion(ruta)
    if archivo is None:
        return None, None
    return archivo, motivo_no_aplicable(archivo, perfil=perfil, modelos=modelos, hash_corpus=hash_corpus,
                                       hash_lexico=hash_lexico)


__all__ = [
    "CALIBRABLES", "MetricasSplit", "ResultadoCalibracion", "calibrar", "cargar_calibracion",
    "escribir_calibracion", "explorar_umbrales", "metricas_split", "redecidir", "redecidir_pares",
]
