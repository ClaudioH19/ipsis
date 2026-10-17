"""Las cuentas de ``carril_multimedia.py`` (M2.2) sobre filas inventadas: sin modelos ni índice."""
from __future__ import annotations

import importlib.util
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / "herramientas" / "evaluacion" / "carril_multimedia.py"
_spec = importlib.util.spec_from_file_location("carril_multimedia", RUTA)
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)


def fila(tipo, score, top="a", esperada="a", capitulo=None, inicio=None, particion="dev", informal=False):
    return {"tipo": tipo, "score_top": score, "media_id_top": top if score is not None else None, "media_id": esperada,
            "capitulo_segundos": capitulo, "inicio_top": inicio, "particion": particion, "informal": informal}


def test_wilson_superior_crece_con_pocos_datos_y_acota_a_uno():
    assert cm.wilson_superior(0, 0) == 1.0
    assert 0.09 < cm.wilson_superior(0, 36) < 0.10          # cero errores en 36 no certifica el 5 %
    assert cm.wilson_superior(0, 400) < 0.01
    assert cm.wilson_superior(5, 5) <= 1.0


def test_evaluar_cuenta_falsas_cobertura_equivocadas_y_capitulos():
    filas = [fila("mismo_tema", 0.90), fila("fuera", 0.70), fila("mismo_tema", 0.60),
             fila("ficha", 0.95, capitulo=60, inicio=60), fila("ficha", 0.93, capitulo=90, inicio=30),
             fila("ficha", 0.92, top="b"), fila("ficha", 0.50)]
    p = cm.evaluar(filas, 0.85)
    assert (p["falsas"], p["negativas"], p["falsas_mismo_tema"], p["falsas_fuera"]) == (1, 3, 1, 0)
    assert (p["correctas"], p["positivas"], p["equivocadas"]) == (2, 4, 1)
    assert p["capitulo_correcto"] == "1/2" and p["cobertura"] == 0.5
    assert cm.evaluar(filas, 0.0)["falsas"] == 3 and cm.evaluar(filas, 2.0)["correctas"] == 0


def test_una_ficha_sin_candidato_nunca_se_muestra():
    p = cm.evaluar([fila("fuera", None), fila("ficha", None)], -1.0)
    assert p["falsas"] == 0 and p["correctas"] == 0 and p["equivocadas"] == 0


def test_recomendar_es_el_menor_umbral_que_cumple_y_sin_falsas_redondea_hacia_arriba():
    dev = [fila("mismo_tema", 0.8571), fila("fuera", 0.80), fila("ficha", 0.90), fila("ficha", 0.8801)]
    assert cm.recomendar(dev, 0.0) == 0.8801                      # justo por encima de la falsa más alta
    assert cm.recomendar(dev, 0.5) <= 0.8801                      # con tolerancia puede ser menor
    assert cm.sin_falsas(dev) == 0.881                             # 3 decimales, hacia arriba
    assert cm.recomendar([fila("mismo_tema", 0.9, top="a")], 0.0) is None  # el único candidato es la falsa
    assert cm.sin_falsas([]) is None


def test_analizar_elige_con_dev_e_informa_test_sin_volver_a_elegir():
    filas = [fila("mismo_tema", 0.80), fila("ficha", 0.90),
             fila("mismo_tema", 0.95, particion="test"), fila("ficha", 0.91, particion="test")]
    informe = cm.analizar(filas, 0.05)
    elegido = informe["sin_falsas_en_dev"]
    assert elegido["tau"] == 0.9 and elegido["dev"]["falsas"] == 0
    assert elegido["test"]["falsas"] == 1                         # en test falla, y se informa tal cual
    assert "Recomendado: `min_score` 0.9" in cm.a_markdown(informe)  # y un subconjunto vacío no rompe la tabla


def test_sin_ningun_umbral_posible_el_informe_lo_dice():
    informe = cm.analizar([fila("fuera", 0.9, top="a"), fila("ficha", None)], 0.05)
    assert informe["sin_falsas_en_dev"] is None
    assert "sin `min_score`" in cm.a_markdown(informe)
