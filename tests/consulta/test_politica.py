from __future__ import annotations

import pytest

from rag.consulta.etapas.politica import LayeredV1
from rag.nucleo.contratos import AbstentionPolicy
from rag.nucleo.registro import RegistroComponentes
from rag.nucleo.esquemas import (
    ChunkRecord,
    QueryAnalysis,
    RetrievalCandidate,
    SenalesRecuperacion,
)
from rag.aplicacion.registro_base import registrar_componentes_base


def _configuracion(*, zona_gris: str = "relacionado") -> dict:
    return {
        "capa_a_fuera_dominio": {
            "umbral": 0.80,
            "grounding_lexico": {"oov_max": 0.5},
        },
        "confianza_alta": {"umbral": 0.85},
        "zona_gris": {"modo": zona_gris},
    }


def _consulta(texto: str) -> QueryAnalysis:
    return QueryAnalysis(
        pregunta_original=texto,
        pregunta_normalizada=texto,
    )


def _senales(confianza: float) -> SenalesRecuperacion:
    return SenalesRecuperacion(
        confianza_top1=confianza,
        margen_top1_top2=0.05,
    )


def _candidato(texto: str, chunk_id: str = "c1") -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=ChunkRecord(
            chunk_id=chunk_id,
            doc_id="doc",
            texto_fuente=texto,
            texto_embedding=texto,
            offset_inicio=0,
            offset_fin=len(texto),
        )
    )


def test_layered_v1_cumple_el_protocolo_y_se_registra():
    registro = registrar_componentes_base(RegistroComponentes())
    politica = registro.crear(
        "abstention_policy",
        "layered_v1",
        configuracion=_configuracion(),
    )

    assert isinstance(politica, AbstentionPolicy)
    assert registro.disponibles("abstention_policy") == ["layered_v1"]


def test_fuera_de_dominio_usa_comparacion_estricta_en_el_limite():
    politica = LayeredV1(_configuracion())
    consulta = _consulta("una pregunta ajena")

    debajo = politica.decidir_dominio(consulta, _senales(0.79999))
    en_limite = politica.decidir_dominio(consulta, _senales(0.80))

    assert debajo is not None
    assert debajo.resultado == "abstiene"
    assert debajo.motivo == "fuera_dominio"
    assert debajo.capa_decisora == "fuera_dominio"
    assert debajo.confianza_utilizada == pytest.approx(0.79999)
    assert en_limite is None


def test_premisa_invalida_manda_aunque_la_confianza_sea_alta():
    politica = LayeredV1(_configuracion())
    decision = politica.decidir(
        _consulta("¿Qué establece el artículo 9?"),
        _senales(0.99),
        [_candidato("El artículo 8 establece las condiciones.")],
    )

    assert decision.resultado == "abstiene"
    assert decision.motivo == "premisa"
    assert decision.entidad_texto == "artículo 9"
    assert decision.capa_decisora == "premisa"
    assert decision.candidato_id == "c1"


def test_limites_de_zona_gris_y_confianza_alta():
    politica = LayeredV1(_configuracion())
    consulta = _consulta("¿Cómo funciona?")
    candidatos = [_candidato("El proceso funciona de esta manera.")]

    zona_gris = politica.decidir(consulta, _senales(0.84999), candidatos)
    confianza_alta = politica.decidir(consulta, _senales(0.85), candidatos)

    assert (zona_gris.resultado, zona_gris.motivo) == ("relacionado", "zona_gris")
    assert (confianza_alta.resultado, confianza_alta.motivo) == (
        "responde",
        "confianza_alta",
    )


def test_grounding_rescata_score_bajo_pero_lo_deja_en_zona_gris():
    from rag.indice.estadisticas import EstadisticasLexicas
    from rag.lenguaje.paquete import cargar_paquete

    es = cargar_paquete("es")
    politica = LayeredV1(
        _configuracion(),
        estadisticas_lexico=EstadisticasLexicas.construir(["La garantía cubre el equipo.", "Otro tema."], es),
        paquete=es,
    )
    consulta = _consulta("garantía")
    senales = _senales(0.70)

    assert politica.decidir_dominio(consulta, senales) is None
    decision = politica.decidir(
        consulta,
        senales,
        [_candidato("La garantía cubre el equipo.")],
    )
    assert (decision.resultado, decision.motivo) == ("relacionado", "zona_gris")


def test_zona_gris_puede_configurarse_para_abstenerse():
    politica = LayeredV1(_configuracion(zona_gris="abstenerse"))
    decision = politica.decidir(
        _consulta("¿Cómo funciona?"),
        _senales(0.82),
        [_candidato("El proceso funciona de esta manera.")],
    )
    assert decision.resultado == "abstiene"
    assert decision.motivo == "zona_gris"


@pytest.mark.parametrize(
    "configuracion",
    [
        {},
        {
            "capa_a_fuera_dominio": {
                "umbral": 0.9,
                "grounding_lexico": {"oov_max": 0.5},
            },
            "confianza_alta": {"umbral": 0.8},
        },
        {
            **_configuracion(),
            "zona_gris": {"modo": "inventado"},
        },
    ],
)
def test_configuracion_invalida_falla_al_construir(configuracion: dict):
    with pytest.raises(ValueError):
        LayeredV1(configuracion)
