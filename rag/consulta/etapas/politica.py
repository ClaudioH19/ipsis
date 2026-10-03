"""Políticas de abstención independientes del transporte y del backend.

La política decide con señales normalizadas y candidatos tipados. No recupera
datos ni conoce Qdrant: la orquestación puede pedir evidencia adicional y
volver a evaluarla con el conjunto ampliado.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from rag.consulta.etapas.base import _Etapa
from rag.nucleo.esquemas import (
    DecisionAbstencion,
    QueryAnalysis,
    Resultado,
    RetrievalCandidate,
    SenalesRecuperacion,
)
from rag.lenguaje.entidades import extraer_entidades


@dataclass(frozen=True)
class ResultadoPremisa:
    premisa_valida: bool
    entidades_ausentes: list[dict]


def verificar_premisa_textos(pregunta: str, textos: Sequence[str]) -> ResultadoPremisa:
    """Comprueba que las entidades cerradas de la pregunta estén respaldadas."""
    entidades_pregunta = extraer_entidades(pregunta)
    if not entidades_pregunta:
        return ResultadoPremisa(premisa_valida=True, entidades_ausentes=[])
    entidades_fragmentos = {
        entidad["valor_norm"]
        for entidad in extraer_entidades(" ".join(textos))
    }
    ausentes = [
        entidad for entidad in entidades_pregunta
        if entidad["valor_norm"] not in entidades_fragmentos
    ]
    return ResultadoPremisa(
        premisa_valida=not ausentes,
        entidades_ausentes=ausentes,
    )


def verificar_premisa_candidatos(
    consulta: QueryAnalysis,
    candidatos: Sequence[RetrievalCandidate],
) -> ResultadoPremisa:
    return verificar_premisa_textos(
        consulta.pregunta_original,
        [candidato.chunk.texto_fuente for candidato in candidatos],
    )


def separar_entidades_ausentes(
    entidades_ausentes: list[dict],
    inventario_corpus: set[str],
) -> tuple[list[dict], list[dict]]:
    en_corpus = [
        entidad for entidad in entidades_ausentes
        if entidad["valor_norm"] in inventario_corpus
    ]
    genuinamente_ausentes = [
        entidad for entidad in entidades_ausentes
        if entidad["valor_norm"] not in inventario_corpus
    ]
    return en_corpus, genuinamente_ausentes


def tiene_grounding_lexico(pregunta: str, estadisticas, oov_max: float = 0.5, paquete=None) -> bool:
    """La pregunta usa vocabulario del corpus: ``s_oov`` bajo ``oov_max``.

    ``s_oov`` es la masa IDF de los términos de la pregunta que no existen en
    el corpus; no necesita listas de palabras generales por idioma.
    """
    from rag.lenguaje.lexico import s_oov, terminos_pregunta

    if estadisticas is None:
        return False
    tq = terminos_pregunta(pregunta, paquete)
    return bool(tq) and s_oov(tq, estadisticas) < oov_max


def tiene_grounding_dominio(
    pregunta: str,
    inventario_entidades: set[str],
    estadisticas,
    oov_max: float = 0.5,
    paquete=None,
) -> bool:
    """Una entidad de la pregunta existe en el corpus, o su vocabulario sí."""
    if any(e["valor_norm"] in inventario_entidades for e in extraer_entidades(pregunta)):
        return True
    return tiene_grounding_lexico(pregunta, estadisticas, oov_max, paquete)


def decidir_capas(
    senales: SenalesRecuperacion,
    umbral_fuera_dominio: float,
    umbral_confianza_alta: float,
    resultado_premisa: ResultadoPremisa,
    *,
    zona_gris_modo: str = "relacionado",
    grounding_dominio: bool = False,
    candidato_id: str | None = None,
) -> DecisionAbstencion:
    """Decisión heredada, pura y sin dependencias de infraestructura."""
    if resultado_premisa.entidades_ausentes:
        return DecisionAbstencion(
            resultado="abstiene",
            motivo="premisa",
            entidad_texto=resultado_premisa.entidades_ausentes[0]["texto"],
            capa_decisora="premisa",
            confianza_utilizada=senales.confianza_top1,
            candidato_id=candidato_id,
        )
    if senales.confianza_top1 < umbral_fuera_dominio and not grounding_dominio:
        return DecisionAbstencion(
            resultado="abstiene",
            motivo="fuera_dominio",
            capa_decisora="fuera_dominio",
            confianza_utilizada=senales.confianza_top1,
            candidato_id=candidato_id,
        )
    if senales.confianza_top1 < umbral_confianza_alta:
        return DecisionAbstencion(
            resultado=("relacionado" if zona_gris_modo == "relacionado" else "abstiene"),
            motivo="zona_gris",
            capa_decisora="zona_gris",
            confianza_utilizada=senales.confianza_top1,
            candidato_id=candidato_id,
        )
    return DecisionAbstencion(
        resultado="responde",
        motivo="confianza_alta",
        capa_decisora="confianza_alta",
        confianza_utilizada=senales.confianza_top1,
        candidato_id=candidato_id,
    )


class LayeredV1:
    """Implementación tipada de la decisión heredada por capas."""

    def __init__(
        self,
        configuracion: dict,
        inventario_entidades: set[str] | None = None,
        estadisticas_lexico=None,
        paquete=None,
        **_ignoradas,
    ) -> None:
        try:
            capa_a = configuracion["capa_a_fuera_dominio"]
            confianza_alta = configuracion["confianza_alta"]
            self.umbral_fuera_dominio = float(capa_a["umbral"])
            self.umbral_confianza_alta = float(confianza_alta["umbral"])
            self.oov_max = float(capa_a.get("grounding_lexico", {}).get("oov_max", 0.5))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("configuración inválida para abstention_policy/layered_v1") from exc
        if self.umbral_confianza_alta < self.umbral_fuera_dominio:
            raise ValueError(
                "confianza_alta.umbral debe ser mayor o igual que "
                "capa_a_fuera_dominio.umbral"
            )
        self.zona_gris_modo = configuracion.get("zona_gris", {}).get(
            "modo", "relacionado"
        )
        if self.zona_gris_modo not in {"relacionado", "abstenerse"}:
            raise ValueError("abstencion.zona_gris.modo debe ser relacionado o abstenerse")
        self.inventario_entidades = set(inventario_entidades or ())
        self.estadisticas_lexico = estadisticas_lexico
        self.paquete = paquete

    def _grounding(self, consulta: QueryAnalysis) -> bool:
        return tiene_grounding_dominio(
            consulta.pregunta_original,
            self.inventario_entidades,
            self.estadisticas_lexico,
            self.oov_max,
            self.paquete,
        )

    def decidir_dominio(
        self,
        consulta: QueryAnalysis,
        senales: SenalesRecuperacion,
    ) -> DecisionAbstencion | None:
        """Devuelve una abstención temprana o ``None`` para continuar.

        Si la pregunta menciona entidades concretas (un artículo, un plazo),
        decide la capa de premisa: su mensaje dice exactamente qué no existe.
        """
        if extraer_entidades(consulta.pregunta_original):
            return None
        if (
            senales.confianza_top1 < self.umbral_fuera_dominio
            and not self._grounding(consulta)
        ):
            return DecisionAbstencion(
                resultado="abstiene",
                motivo="fuera_dominio",
                capa_decisora="fuera_dominio",
                confianza_utilizada=senales.confianza_top1,
            )
        return None

    def decidir(
        self,
        consulta: QueryAnalysis,
        senales: SenalesRecuperacion,
        candidatos: Sequence[RetrievalCandidate],
    ) -> DecisionAbstencion:
        return decidir_capas(
            senales,
            self.umbral_fuera_dominio,
            self.umbral_confianza_alta,
            verificar_premisa_candidatos(consulta, candidatos),
            zona_gris_modo=self.zona_gris_modo,
            grounding_dominio=self._grounding(consulta),
            candidato_id=candidatos[0].chunk.chunk_id if candidatos else None,
        )


UMBRALES_CASCADA = ("oov", "dominio", "relacionado", "foco", "ok", "cov")


@dataclass(frozen=True)
class SenalesPolitica:
    """Señales que lee ``cascada_v1``; ``None`` si la etapa que las produce no corrió."""

    s_ret: float
    s_oov: float
    s_foco: float
    s_cov: float
    acuerdo: float | None
    s_rr: float | None
    s_qa: float | None

    @property
    def dominio(self) -> float:
        """Señal de dominio: el reranker si existe; si no, la recuperación."""
        return self.s_rr if self.s_rr is not None else self.s_ret


def senales_de_contexto(ctx) -> SenalesPolitica:
    from rag.consulta.etapas.reranking import sigmoide

    lex = ctx.lexicas
    return SenalesPolitica(
        s_ret=float(ctx.senales.confianza_top1) if ctx.senales is not None else 0.0,
        s_oov=lex.s_oov if lex is not None else 0.0,
        # Sin términos de foco no hay nada que exigir: s_foco neutro.
        s_foco=lex.s_foco if lex is not None and lex.s_foco is not None else 1.0,
        s_cov=lex.s_cov if lex is not None and lex.s_cov is not None else 0.0,
        acuerdo=lex.acuerdo if lex is not None else None,
        s_rr=sigmoide(ctx.puntajes_rerank[0]) if ctx.puntajes_rerank else None,
        s_qa=max((lec.s_qa for lec in ctx.lecturas), default=0.0) if ctx.lecturas is not None else None,
    )


def forma_en_pregunta(pregunta: str, termino: str, paquete=None) -> str:
    """Palabra de la pregunta cuyo término (stem) es ``termino``; para el mensaje."""
    from rag.lenguaje.texto import terminos, tokenizar

    for palabra in tokenizar(pregunta, normalizado=False):
        if terminos(palabra, paquete) == [termino]:
            return palabra
    return termino


class CascadaV1:
    """Decide con todas las señales de la cascada (arquitectura.md §2.1).

    Reglas en orden; la primera que se cumple decide:

    1. La premisa falla (pide una entidad que no está) → sin_respuesta.
    2. ``s_oov ≥ τ_oov`` y dominio < ``τ_dominio`` → fuera_dominio.
    3. ``s_foco ≥ τ_foco`` y (con lector: ``s_qa ≥ τ_ok``; sin lector:
       ``s_ret ≥ τ_ok``, ``s_cov ≥ τ_cov`` y ``acuerdo ≥ 0,5``) → ok.
    4. dominio ≥ ``τ_relacionado`` → relacionado (con el término ausente si
       falló el foco).
    5. Si no → sin_respuesta.

    Los umbrales vienen del perfil (y de la calibración, si coincide).
    """

    def __init__(self, configuracion: dict | None = None, *, umbrales: dict[str, float] | None = None,
                 paquete=None, **_ignoradas) -> None:
        faltantes = [u for u in UMBRALES_CASCADA if u not in (umbrales or {})]
        if faltantes:
            raise ValueError(f"abstention_policy/cascada_v1 requiere los umbrales {faltantes}")
        self.umbrales = {k: float(v) for k, v in umbrales.items()}
        self.paquete = paquete

    def decidir_dominio(self, consulta: QueryAnalysis, senales: SenalesRecuperacion) -> None:
        """Sin salida temprana: el filtro de dominio usa señales posteriores."""
        return None

    def decidir(self, consulta, senales, candidatos) -> DecisionAbstencion:
        raise NotImplementedError("cascada_v1 decide con el contexto completo (decidir_contexto)")

    def decidir_contexto(self, ctx) -> DecisionAbstencion:
        u = self.umbrales
        s = senales_de_contexto(ctx)
        ctx.diagnostico["senales_politica"] = {k: v for k, v in s.__dict__.items()} | {"dominio": s.dominio}
        candidato = ctx.candidatos[0].chunk.chunk_id if ctx.candidatos else None

        def decision(resultado: Resultado, motivo: str, regla: str, entidad: str | None = None) -> DecisionAbstencion:
            return DecisionAbstencion(resultado=resultado, motivo=motivo, entidad_texto=entidad,
                                      capa_decisora=regla, confianza_utilizada=s.dominio, candidato_id=candidato)

        premisa = verificar_premisa_candidatos(ctx.consulta, ctx.candidatos)
        if premisa.entidades_ausentes:
            return decision("abstiene", "premisa", "premisa", premisa.entidades_ausentes[0]["texto"])
        if s.s_oov >= u["oov"] and s.dominio < u["dominio"]:
            return decision("abstiene", "fuera_dominio", "fuera_dominio")
        foco_ok = s.s_foco >= u["foco"]
        if foco_ok and s.s_qa is not None and s.s_qa >= u["ok"]:
            return decision("responde", "lector", "ok_lector")
        if (foco_ok and s.s_qa is None and s.s_ret >= u["ok"] and s.s_cov >= u["cov"]
                and (s.acuerdo is None or s.acuerdo >= 0.5)):
            return decision("responde", "lexico", "ok_lexico")
        if s.dominio >= u["relacionado"]:
            if not foco_ok and ctx.terminos_foco:
                termino = forma_en_pregunta(ctx.pregunta, ctx.terminos_foco[0], self.paquete)
                return decision("relacionado", "foco_ausente", "relacionado", termino)
            return decision("relacionado", "relacionado", "relacionado")
        return decision("abstiene", "generico", "sin_respuesta")


class EtapaPolitica(_Etapa):
    """Decisión de la política: responder, relacionado o abstenerse."""

    nombre = "politica"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        politica = m.politica_abstencion
        if hasattr(politica, "decidir_contexto"):
            decision = politica.decidir_contexto(ctx)
        else:
            decision = politica.decidir(ctx.consulta, ctx.senales, ctx.candidatos)
        if ctx.discordancia and decision.resultado == "responde":
            from dataclasses import replace

            decision = replace(decision, resultado="relacionado", motivo="discordancia", capa_decisora="concordancia")
        ctx.decision = decision
        ctx.diagnostico["decision"] = decision.__dict__
        ctx.diagnostico["regla"] = decision.capa_decisora or decision.motivo
        if decision.abstiene:
            motivo = decision.motivo if decision.motivo in {"premisa", "fuera_dominio"} else "generico"
            ctx.resultado = m._abstener(
                motivo, ctx.confianza, ctx.latencia_ms(),
                entidad_texto=decision.entidad_texto, diagnostico=ctx.diagnostico,
            )


__all__ = [
    "CascadaV1",
    "DecisionAbstencion",
    "EtapaPolitica",
    "decidir_capas",
    "LayeredV1",
    "ResultadoPremisa",
    "SenalesPolitica",
    "forma_en_pregunta",
    "senales_de_contexto",
    "separar_entidades_ausentes",
    "tiene_grounding_dominio",
    "tiene_grounding_lexico",
    "verificar_premisa_candidatos",
    "verificar_premisa_textos",
]
