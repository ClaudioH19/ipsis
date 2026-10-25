"""Forma de una página de resultados (P1.1): función pura, configuración y su traducción al archivo del proyecto."""
from __future__ import annotations

import pytest

from ipsis.configuracion.archivos import interpretar
from ipsis.configuracion.esquemas import PipelineV2Config, PresentacionConfig
from ipsis.consulta.v2.forma import FORMAS, forma_de_pagina, margen, margen_claro_efectivo, relacion


def f(doc="d", seccion=("Reglamento", "Plazos"), score=3.0, tipo="logit_reranker", alcance=None):
    return {"doc_id": doc, "seccion_path": list(seccion), "score": score, "tipo_puntaje": tipo, "alcance": alcance}


# --- margen -------------------------------------------------------------------

def test_el_margen_es_la_diferencia_entre_las_dos_primeras():
    assert margen([f(score=5.0), f(score=1.5), f(score=-9.0)]) == pytest.approx(3.5)


@pytest.mark.parametrize("fuentes", [
    [], [f()], [f(score=None), f()], [f(), f(score=None)],
    [f(tipo="logit_reranker"), f(tipo="recuperacion")],  # escalas distintas: no se restan
])
def test_sin_margen_comparable_es_none(fuentes):
    assert margen(fuentes) is None


# --- relación -----------------------------------------------------------------

@pytest.mark.parametrize("a, b, esperada", [
    (f(doc="a"), f(doc="b"), "documentos"),
    (f(seccion=("Reglamento", "Planta")), f(seccion=("Reglamento", "Contrata")), "variantes"),         # hermanas
    (f(seccion=("R", "Art 1", "P1")), f(seccion=("R", "Art 1", "P2")), "variantes"),
    (f(alcance="Práctica I"), f(alcance="Práctica II"), "variantes"),                                  # por alcance
    (f(seccion=("A",), alcance="P1"), f(seccion=("B",), alcance="P2"), "variantes"),                   # alcance manda
    (f(seccion=("Plazos",)), f(seccion=("Montos",)), "otra"),    # secciones de primer nivel: sin padre común
    (f(seccion=("R", "Plazos")), f(seccion=("R", "Plazos")), "otra"),                                  # la misma sección
    (f(alcance="P1"), f(alcance="P1"), "otra"),                                                        # mismo alcance
    (f(seccion=("R", "A", "x")), f(seccion=("R", "B", "x")), "otra"),                                  # padres distintos
    (f(alcance="P1"), f(alcance=None, seccion=("Otro", "Distinto")), "otra"),                          # alcance solo en una
])
def test_relacion_entre_las_dos_primeras(a, b, esperada):
    assert relacion([a, b]) == esperada


def test_relacion_solo_mira_las_dos_primeras_y_necesita_dos():
    assert relacion([]) is None and relacion([f()]) is None
    assert relacion([f(doc="a"), f(doc="a", seccion=("R", "Otra")), f(doc="z")]) == "otra"


# --- forma --------------------------------------------------------------------

def test_apagada_o_con_una_fuente_es_siempre_neutral():
    dos = [f(doc="a", score=9), f(doc="b", score=0)]
    assert forma_de_pagina(dos) == "neutral"                                   # apagada por defecto
    assert forma_de_pagina(dos, activo=False, margen_claro=1.0) == "neutral"
    assert forma_de_pagina([f()], activo=True, margen_claro=1.0) == "neutral"
    assert forma_de_pagina([], activo=True, margen_claro=1.0) == "neutral"


def test_una_pagina_clara_gana_sobre_cualquier_otra_relacion():
    dos = [f(doc="a", score=9.0), f(doc="b", score=2.0)]
    assert forma_de_pagina(dos, activo=True, margen_claro=5.0) == "clara"
    assert forma_de_pagina(dos, activo=True, margen_claro=7.0) == "clara"            # el margen es 7: «al menos»
    assert forma_de_pagina(dos, activo=True, margen_claro=7.5) == "documentos"
    variantes = [f(seccion=("R", "A"), score=9.0), f(seccion=("R", "B"), score=2.0)]
    assert forma_de_pagina(variantes, activo=True, margen_claro=5.0) == "clara"


def test_sin_margen_claro_la_forma_clara_no_existe():
    dos = [f(doc="a", score=99.0), f(doc="b", score=-99.0)]
    assert forma_de_pagina(dos, activo=True, margen_claro=None) == "documentos"


def test_variantes_documentos_y_neutral():
    cerca = {"activo": True, "margen_claro": 5.0}
    assert forma_de_pagina([f(seccion=("R", "Planta"), score=3.0), f(seccion=("R", "Contrata"), score=2.5)], **cerca) == "variantes"
    assert forma_de_pagina([f(doc="a", score=3.0), f(doc="b", score=2.5)], **cerca) == "documentos"
    assert forma_de_pagina([f(seccion=("R", "Plazos"), score=3.0), f(seccion=("R", "Plazos"), score=2.5)], **cerca) == "neutral"


def test_con_puntajes_de_escalas_distintas_no_hay_forma_clara_pero_si_las_demas():
    mezcla = [f(doc="a", score=9.0, tipo="logit_reranker"), f(doc="b", score=0.1, tipo="recuperacion")]
    assert forma_de_pagina(mezcla, activo=True, margen_claro=0.0) == "documentos"


def test_la_forma_es_determinista_y_siempre_una_de_las_conocidas():
    paginas = [[f(doc="a"), f(doc="b")], [f(seccion=("R", "A")), f(seccion=("R", "B"))], [f(), f()], [f()]]
    for pagina in paginas:
        una = forma_de_pagina(pagina, activo=True, margen_claro=1.0)
        assert una == forma_de_pagina(pagina, activo=True, margen_claro=1.0) and una in FORMAS


def test_no_modifica_las_fuentes():
    pagina = [f(doc="a", score=9.0), f(doc="b", score=2.0)]
    antes = [dict(x) for x in pagina]
    forma_de_pagina(pagina, activo=True, margen_claro=1.0)
    assert pagina == antes


# --- configuración -----------------------------------------------------------

def test_la_presentacion_esta_encendida_por_defecto_y_sin_margen_claro():
    assert PresentacionConfig().model_dump() == {"activo": True, "margen_claro": None, "margen_claro_por_perfil": {},
                                                 "linea_clave": False, "margen_linea_clave": 0.01}
    assert PipelineV2Config().model_dump()["presentacion"]["activo"] is True
    assert PipelineV2Config.model_validate({"presentacion": {"activo": False}}).presentacion.activo is False


def test_se_lee_con_los_nombres_en_ingles_del_archivo():
    datos = interpretar("v2:\n  presentation:\n    enabled: true\n    clear_margin: 2.5\n"
                        "    clear_margin_by_profile:\n      medium: 4.0\n      light: 0.3\n", "motor")
    assert PipelineV2Config.model_validate(datos["v2"]).presentacion.model_dump() == {
        "activo": True, "margen_claro": 2.5, "margen_claro_por_perfil": {"medium": 4.0, "light": 0.3},
        "linea_clave": False, "margen_linea_clave": 0.01}


@pytest.mark.parametrize("datos", [{"margen_claro": -1}, {"margen_claro_por_perfil": {"medium": -0.1}}, {"rareza": 1}])
def test_rechaza_margenes_negativos_y_claves_desconocidas(datos):
    with pytest.raises(ValueError):
        PresentacionConfig.model_validate(datos)


def test_el_margen_de_un_perfil_manda_sobre_el_general():
    p = {"margen_claro": 2.0, "margen_claro_por_perfil": {"medium": 4.0}}
    assert margen_claro_efectivo(p, "medium") == 4.0
    assert margen_claro_efectivo(p, "light") == 2.0 and margen_claro_efectivo(p, None) == 2.0
    assert margen_claro_efectivo({"margen_claro": None, "margen_claro_por_perfil": {"medium": 4.0}}, "light") is None
