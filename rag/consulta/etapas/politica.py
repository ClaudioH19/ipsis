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


class EtapaPolitica(_Etapa):
    """Decisión de la política: responder, relacionado o abstenerse."""

    nombre = "politica"

    def ejecutar(self, ctx) -> None:
        m = self.motor
        decision = m.politica_abstencion.decidir(ctx.consulta, ctx.senales, ctx.candidatos)
        ctx.decision = decision
        ctx.diagnostico["decision"] = decision.__dict__
        ctx.diagnostico["regla"] = decision.capa_decisora or decision.motivo
        if decision.abstiene:
            motivo = "premisa" if decision.motivo == "premisa" else "generico"
            ctx.resultado = m._abstener(
                motivo, ctx.confianza, ctx.latencia_ms(),
                entidad_texto=decision.entidad_texto, diagnostico=ctx.diagnostico,
            )


__all__ = [
    "DecisionAbstencion",
    "EtapaPolitica",
    "decidir_capas",
    "LayeredV1",
    "ResultadoPremisa",
    "separar_entidades_ausentes",
    "tiene_grounding_dominio",
    "tiene_grounding_lexico",
    "verificar_premisa_candidatos",
    "verificar_premisa_textos",
]
