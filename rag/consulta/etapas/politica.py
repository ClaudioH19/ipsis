"""Política de abstención: decide ok, relacionado o sin respuesta.

Decide con las señales que dejaron las etapas anteriores (``ContextoConsulta``).
No recupera datos ni conoce Qdrant.
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
        """Señal de dominio: la recuperación, o el reranker si da más.

        Los logits de un cross-encoder ordenan bien dentro de una consulta pero
        no son una escala absoluta (mmarco da 0,08 a un pasaje correcto): el
        reranker puede confirmar el dominio, no negarlo."""
        return self.s_ret if self.s_rr is None else max(self.s_ret, self.s_rr)


def normalizar_coseno(coseno: float, piso: float = 0.0) -> float:
    """Coseno del modelo denso llevado a [0, 1] desde su piso."""
    return min(1.0, max(0.0, (coseno - piso) / (1.0 - piso)))


def senales_de_contexto(ctx, piso_coseno: float = 0.0) -> SenalesPolitica:
    from rag.consulta.etapas.reranking import sigmoide

    lex = ctx.lexicas
    return SenalesPolitica(
        s_ret=normalizar_coseno(float(ctx.senales.confianza_top1), piso_coseno) if ctx.senales is not None else 0.0,
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
    2. ``s_oov ≥ τ_oov`` y dominio < ``τ_dominio`` → fuera_dominio
       (dominio = max(s_ret, s_rr); ver ``SenalesPolitica.dominio``).
    3. ``s_foco ≥ τ_foco``, ``s_oov < τ_oov`` y (con lector: ``s_qa ≥ τ_ok``;
       sin lector: ``s_ret ≥ τ_ok``, ``s_cov ≥ τ_cov`` y ``acuerdo ≥ 0,5``) → ok.
       ``s_oov < τ_oov``: si casi todo el vocabulario de la pregunta falta en el
       corpus, el corpus no puede respaldar una afirmación literal. El lector da
       el mismo tramo a «¿Cuándo vence la garantía?» y a «¿Qué incluye la
       garantía?»; solo distingue el tipo de respuesta esperado, y eso exigiría
       reglas por idioma.
    4. dominio ≥ ``τ_relacionado`` → relacionado (con el término ausente si
       falló el foco).
    5. Si no → sin_respuesta.

    Los umbrales vienen del perfil (y de la calibración, si coincide).
    """

    def __init__(self, *, umbrales: dict[str, float], paquete=None, piso_coseno: float = 0.0) -> None:
        faltantes = [u for u in UMBRALES_CASCADA if u not in (umbrales or {})]
        if faltantes:
            raise ValueError(f"abstention_policy/cascada_v1 requiere los umbrales {faltantes}")
        self.umbrales = {k: float(v) for k, v in umbrales.items()}
        self.paquete = paquete
        self.piso_coseno = piso_coseno

    def decidir_contexto(self, ctx) -> DecisionAbstencion:
        u = self.umbrales
        s = senales_de_contexto(ctx, self.piso_coseno)
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
        respaldo = foco_ok and s.s_oov < u["oov"]
        if respaldo and s.s_qa is not None and s.s_qa >= u["ok"]:
            return decision("responde", "lector", "ok_lector")
        if (respaldo and s.s_qa is None and s.s_ret >= u["ok"] and s.s_cov >= u["cov"]
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
        decision = m.politica_abstencion.decidir_contexto(ctx)
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
    "ResultadoPremisa",
    "SenalesPolitica",
    "forma_en_pregunta",
    "normalizar_coseno",
    "senales_de_contexto",
    "separar_entidades_ausentes",
    "verificar_premisa_candidatos",
    "verificar_premisa_textos",
]
