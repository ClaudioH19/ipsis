"""Análisis de la forma de los resultados (P0.2): núcleo con filas inventadas, sin modelos ni banco."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[2] / "herramientas/evaluacion/forma_resultados.py"


@pytest.fixture(scope="module")
def fr():
    spec = importlib.util.spec_from_file_location("forma_resultados", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def fila(id_, split, rango_final, margen=None, perfil="medium", doc2="d", seccion=("R", "A"), seccion2=("R", "B"),
         alcance=None, alcance2=None, tipo="logit_reranker", una_fuente=False):
    """Una pregunta con dos fuentes publicadas cuyo margen es ``margen`` (la segunda vale 0)."""
    publicadas = [{"rango": 1, "chunk_id": f"{id_}-1", "doc_id": "d", "seccion_path": list(seccion), "score": margen,
                   "tipo_puntaje": tipo, "alcance": alcance, "rasgos": None, "correcto": rango_final == 1}]
    if not una_fuente:
        publicadas.append({"rango": 2, "chunk_id": f"{id_}-2", "doc_id": doc2, "seccion_path": list(seccion2),
                           "score": 0.0, "tipo_puntaje": tipo, "alcance": alcance2, "rasgos": None,
                           "correcto": rango_final == 2})
    return {"id": id_, "split": split, "perfil": perfil, "rango_final": rango_final, "publicadas": publicadas}


def escenario(split="dev"):
    """20 preguntas: margen 5 → 10 aciertos de 10; margen 1 → 3 de 6; margen 0,2 → 1 de 4."""
    filas = [fila(f"a{i}", split, 1, margen=5.0) for i in range(10)]
    filas += [fila(f"b{i}", split, 1 if i < 3 else 2, margen=1.0) for i in range(6)]
    filas += [fila(f"c{i}", split, 1 if i < 1 else 3, margen=0.2) for i in range(4)]
    return filas


# --- estadística -------------------------------------------------------------

def test_wilson_inferior_penaliza_las_muestras_chicas(fr):
    assert fr.wilson_inferior(0, 0) == 0.0
    assert fr.wilson_inferior(10, 10) == pytest.approx(0.7225, abs=1e-3)       # 10 de 10 no es «100 %»
    assert fr.wilson_inferior(100, 100) > 0.96                                  # con 100 de 100, sí casi
    assert fr.wilson_inferior(50, 100) < 0.5 < fr.wilson_inferior(50, 100) + 0.2


# --- relación y curva --------------------------------------------------------

def test_hit_por_relacion(fr):
    filas = [fila("m1", "dev", 1, margen=1.0, doc2="otro"), fila("m2", "dev", 2, margen=1.0, doc2="otro"),
             fila("v1", "dev", 1, margen=1.0, seccion=("R", "A"), seccion2=("R", "B")),
             fila("o1", "dev", 3, margen=1.0, seccion=("R", "A"), seccion2=("R", "A")),
             fila("u1", "dev", 1, una_fuente=True, margen=2.0)]
    r = fr.por_relacion(filas)
    assert r["documentos"] == {"n": 2, "hit@1": 0.5, "hit@3": 1.0}
    assert r["variantes"] == {"n": 1, "hit@1": 1.0, "hit@3": 1.0}
    assert r["otra"] == {"n": 1, "hit@1": 0.0, "hit@3": 1.0}
    assert r["una_fuente"]["n"] == 1


def test_curva_cobertura_y_precision_por_umbral(fr):
    puntos = {p["tau"]: p for p in fr.curva(escenario(), [0.2, 1.0, 5.0, 9.0])}
    assert (puntos[0.2]["n"], puntos[0.2]["cobertura"], puntos[0.2]["precision"]) == (20, 1.0, 0.7)
    assert (puntos[1.0]["n"], puntos[1.0]["cobertura"], puntos[1.0]["precision"]) == (16, 0.8, 0.8125)
    assert (puntos[5.0]["n"], puntos[5.0]["cobertura"], puntos[5.0]["precision"]) == (10, 0.5, 1.0)
    assert puntos[9.0]["n"] == 0 and puntos[9.0]["precision"] is None and puntos[9.0]["cobertura"] == 0.0
    assert puntos[5.0]["precision_wilson_inferior"] < 1.0                        # 10 de 10 con intervalo


def test_las_preguntas_sin_margen_comparable_no_cuentan_en_la_curva(fr):
    filas = escenario() + [fila("u", "dev", 1, una_fuente=True, margen=9.0), fila("x", "dev", 1, margen=9.0, tipo="logit_reranker")]
    filas[-1]["publicadas"][1]["tipo_puntaje"] = "recuperacion"                  # escalas mezcladas
    assert fr.curva(filas, [0.0])[0]["n"] == 20


# --- recomendación -----------------------------------------------------------

def test_recomienda_el_menor_umbral_que_cumple_precision_y_cobertura(fr):
    r = fr.recomendar(escenario(), precision_objetivo=0.98, cobertura_minima=0.30)
    assert r["tau"] == 5.0 and r["dev"]["precision"] == 1.0
    # con una precisión objetivo más baja alcanza un umbral menor (más cobertura)
    assert fr.recomendar(escenario(), 0.80, 0.30)["tau"] == 1.0
    assert fr.recomendar(escenario(), 0.65, 0.30)["tau"] == 0.2


def test_si_nada_cumple_la_forma_clara_se_desactiva(fr):
    assert fr.recomendar(escenario(), 0.98, 0.80)["tau"] is None          # solo el 50 % llega a la precisión pedida
    assert fr.recomendar([fila(f"c{i}", "dev", 2, margen=3.0) for i in range(5)], 0.5, 0.1)["tau"] is None
    assert fr.recomendar([], 0.9, 0.1) == {"tau": None, "dev": None}


def test_el_umbral_se_elige_en_dev_y_se_informa_en_test(fr):
    filas = escenario("dev") + [fila(f"t{i}", "test", 1 if i < 4 else 2, margen=5.0) for i in range(5)]
    informe = fr.analizar_perfil(filas, 0.98, 0.30)
    r = informe["recomendacion"]
    assert r["tau"] == 5.0 and r["dev"]["precision"] == 1.0                        # elegido solo con dev
    assert r["test"]["n"] == 5 and r["test"]["precision"] == 0.8                   # y en test no llega: se ve
    assert informe["preguntas"] == {"dev": 20, "test": 5, "total": 25}


def test_las_formas_resultantes_usan_la_funcion_del_motor(fr):
    from ipsis.consulta.v2.forma import forma_de_pagina

    informe = fr.analizar_perfil(escenario(), 0.98, 0.30)
    esperadas = {"clara": 10, "variantes": 10, "documentos": 0, "neutral": 0}      # margen ≥ 5 → clara; el resto, hermanas
    assert informe["formas"]["dev"] == esperadas
    assert forma_de_pagina(escenario()[0]["publicadas"], activo=True, margen_claro=5.0) == "clara"
    sin_tau = fr.analizar_perfil(escenario(), 0.98, 0.99)                          # ningún τ: no hay «clara»
    assert sin_tau["recomendacion"]["tau"] is None and sin_tau["formas"]["dev"]["clara"] == 0


# --- entrada y salida --------------------------------------------------------

def test_lee_los_volcados_por_perfil(fr, tmp_path):
    for perfil in ("light", "medium"):
        (tmp_path / f"p-{perfil}.jsonl").write_text(
            "".join(json.dumps(fila(f"{perfil}{i}", "dev", 1, margen=1.0, perfil=perfil)) + "\n" for i in range(3)),
            encoding="utf-8")
    perfiles = fr.leer_filas([str(tmp_path / "p-light.jsonl"), str(tmp_path / "p-medium.jsonl")])
    assert sorted(perfiles) == ["light", "medium"] and all(len(v) == 3 for v in perfiles.values())


def test_la_cli_escribe_el_informe_y_no_pide_modelos(fr, tmp_path, capsys):
    (tmp_path / "pub.jsonl").write_text("".join(json.dumps(f) + "\n" for f in escenario() + escenario("test")), encoding="utf-8")
    assert fr.main([str(tmp_path / "pub.jsonl"), "--salida", str(tmp_path / "s"), "--precision-objetivo", "0.98"]) == 0
    informe = json.loads((tmp_path / "s" / "forma.json").read_text(encoding="utf-8"))
    assert informe["perfiles"]["medium"]["recomendacion"]["tau"] == 5.0
    texto = (tmp_path / "s" / "forma.md").read_text(encoding="utf-8")
    assert "## Perfil `medium`" in texto and "**τ = 5**" in texto and "Wilson" in texto
    assert "# Forma de los resultados" in capsys.readouterr().out


def test_el_informe_dice_cuando_la_forma_clara_queda_desactivada(fr, tmp_path):
    filas = [fila(f"c{i}", s, 2, margen=3.0) for i in range(6) for s in ("dev", "test")]
    (tmp_path / "pub.jsonl").write_text("".join(json.dumps(f) + "\n" for f in filas), encoding="utf-8")
    fr.main([str(tmp_path / "pub.jsonl"), "--salida", str(tmp_path / "s")])
    assert "la forma `clara` queda desactivada" in (tmp_path / "s" / "forma.md").read_text(encoding="utf-8")


def test_avisa_cuando_hay_muy_pocos_errores_para_sacar_una_conclusion(fr):
    perfecto = [fila(f"p{i}", "dev", 1, margen=1.0 + i) for i in range(30)]
    aviso = fr.analizar_perfil(perfecto, 0.98, 0.30)["advertencias"]
    assert len(aviso) == 1 and "0 errores de primer resultado en dev" in aviso[0]
    # el escenario inventado tiene 6 errores en dev (3 con margen 1,0 y 3 con 0,2): también avisa; con 10 ya no
    assert "6 errores" in fr.analizar_perfil(escenario(), 0.98, 0.30)["advertencias"][0]
    nueve = escenario() + [fila(f"e{i}", "dev", 2, margen=0.1) for i in range(3)]
    assert "9 errores" in fr.analizar_perfil(nueve, 0.98, 0.30)["advertencias"][0]
    diez = escenario() + [fila(f"e{i}", "dev", 2, margen=0.1) for i in range(4)]
    assert fr.analizar_perfil(diez, 0.98, 0.30)["advertencias"] == []


def test_el_markdown_muestra_la_advertencia(fr, tmp_path):
    perfecto = [fila(f"p{i}", s, 1, margen=1.0 + i) for i in range(10) for s in ("dev", "test")]
    (tmp_path / "pub.jsonl").write_text("".join(json.dumps(f) + "\n" for f in perfecto), encoding="utf-8")
    fr.main([str(tmp_path / "pub.jsonl"), "--salida", str(tmp_path / "s")])
    assert "> ⚠ Solo hay 0 errores de primer resultado en dev" in (tmp_path / "s" / "forma.md").read_text(encoding="utf-8")
