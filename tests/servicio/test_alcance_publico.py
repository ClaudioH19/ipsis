"""El alcance de la unidad llega al contrato público como ``scope``."""
from ipsis.servicio.api import Fragmento, respuesta_publica


def _contrato(**extra):
    fragmento = {"chunk_id": "c", "doc_titulo": "Reglamento", "seccion": "Art. 18", "version": "1",
                 "offset_inicio": 0, "offset_fin": 5, "texto": "hola", "score": 1.0, **extra}
    return {"estado": "relacionado", "nivel_servicio": "normal", "respuesta": "x", "fragmentos": [fragmento],
            "plan": "zona_gris", "confianza": {}, "latencia_ms": 1}


def test_el_alcance_se_publica_como_scope():
    publica = respuesta_publica(_contrato(alcance="Práctica Profesional II"))
    assert publica["fragments"][0]["scope"] == "Práctica Profesional II"
    Fragmento(**publica["fragments"][0])


def test_sin_alcance_el_scope_es_nulo():
    publica = respuesta_publica(_contrato())
    assert "scope" not in publica["fragments"][0] or publica["fragments"][0]["scope"] is None
