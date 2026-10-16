"""Diagnóstico de longitud en tokens: la aritmética de cortes, con un tokenizador falso (una palabra = un token)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

RUTA = Path(__file__).resolve().parents[2] / "herramientas/evaluacion/tokens_fragmentos.py"


@pytest.fixture(scope="module")
def tf():
    spec = importlib.util.spec_from_file_location("tokens_fragmentos", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class TokenizadorFalso:
    """Palabras como tokens, más 3 especiales (como un par [CLS] a [SEP] b [SEP])."""

    def encode(self, texto, par=None):
        ids = texto.split() + ((par or "").split() if par is not None else [])
        return SimpleNamespace(ids=list(range(len(ids) + (3 if par is not None else 0))))


def _caso(pregunta, doc, ini, fin):
    return SimpleNamespace(pregunta=pregunta, evidencias=[SimpleNamespace(doc_id=doc, offset_inicio=ini, offset_fin=fin)])


def test_percentil_sin_valores_y_con_valores(tf):
    assert tf.percentil([], 0.5) == 0
    assert tf.percentil([1, 2, 3, 4, 5], 0.5) == 3
    assert tf.percentil([1, 2, 3, 4, 5], 0.95) == 5


def test_evidencia_cortada_cuando_cae_despues_del_limite(tf):
    texto = " ".join(f"p{i}" for i in range(100))
    ini = len(" ".join(f"p{i}" for i in range(80))) + 1
    pasajes = [{"doc_id": "d", "inicio": 0, "fin": len(texto), "texto": texto, "prefijo": 0}]
    casos = [_caso("una pregunta corta", "d", ini, len(texto))]
    spec = SimpleNamespace(max_tokens=512)
    r = tf.medir_estrategia("X", pasajes, [texto], casos, TokenizadorFalso(), spec, TokenizadorFalso(), spec, [64, 256])
    # pregunta de 3 palabras + 80 palabras antes de la evidencia + 3 especiales = 86 > 64
    assert r["evidencia"]["64"]["evidencia_fuera_pct"] == 100.0
    assert r["evidencia"]["64"]["evidencia_cortada_pct"] == 100.0
    assert r["evidencia"]["64"]["pasaje_truncado_pct"] == 100.0
    assert r["evidencia"]["256"] == {"pasaje_truncado_pct": 0.0, "evidencia_cortada_pct": 0.0, "evidencia_fuera_pct": 0.0}
    assert r["evidencia"]["casos"] == 1
    assert r["denso"]["truncados_pct"] == 0.0


def test_prefijo_de_seccion_cuenta_antes_de_la_evidencia(tf):
    fuente = " ".join(f"f{i}" for i in range(10))
    texto = "Seccion A\n" + fuente          # la unidad estructural antepone la sección
    pasajes = [{"doc_id": "d", "inicio": 100, "fin": 100 + len(fuente), "texto": texto, "prefijo": len("Seccion A\n")}]
    casos = [_caso("q", "d", 100, 100 + len(fuente))]
    spec = SimpleNamespace(max_tokens=512)
    r = tf.medir_estrategia("E", pasajes, [texto], casos, TokenizadorFalso(), spec, TokenizadorFalso(), spec, [8])
    # q (1) + "Seccion A" (2) + 10 palabras + 3 especiales = 16 > 8
    assert r["evidencia"]["8"]["evidencia_cortada_pct"] == 100.0


def test_markdown_resume_todas_las_ventanas(tf):
    informe = {"modelo_denso": "d", "ventana_denso": 512, "modelo_reranker": "r", "limite_motor": 256, "casos": 1,
               "limites": [256, 512], "estrategias": {"X": {
                   "fragmentos": 2, "palabras_p50": 100, "denso": {"p95": 90, "truncados_pct": 0.0},
                   "reranker_pasaje": {"p50": 120, "p95": 150},
                   "evidencia": {"256": {"evidencia_cortada_pct": 5.0, "pasaje_truncado_pct": 10.0},
                                 "512": {"evidencia_cortada_pct": 0.0, "pasaje_truncado_pct": 0.0}}}}}
    md = tf.a_markdown(informe)
    assert "evidencia cortada @256" in md and "evidencia cortada @512" in md and "5.0 %" in md
