"""``ipsis calibrate`` con un motor falso: orquestación, mensajes, persistencia y
códigos de salida. La matemática de la calibración la prueba
``tests/evaluacion/test_calibracion.py``."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from apoyo import CORPUS

from ipsis.cli import main
from apoyo import leer_proyecto

LITERALES = [
    "24 meses desde la fecha de compra",
    "10 días hábiles",
    "entre 1,5 y 4,0 bar",
    "Los sábados solo se atienden emergencias por filtraciones",
    "conserva la boleta y el número de serie",
]


def _escribir_golden(ruta: Path, respondibles: int, trampas: int) -> None:
    filas = [{"id": f"r{i:03d}", "pregunta": f"¿Pregunta respondible {i}?", "tipo": "respondible",
              "respuesta_literal": LITERALES[i % len(LITERALES)]} for i in range(respondibles)]
    filas += [{"id": f"t{i:03d}", "pregunta": f"¿Trampa {i}?", "tipo": "sin_respuesta",
               "subtipo": "trampa_mismo_tema", "par": "r000"} for i in range(trampas)]
    filas += [{"id": "c001", "pregunta": "hola", "tipo": "conversacional"}]
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=["id", "pregunta", "tipo", "respuesta_literal", "subtipo", "par"])
        escritor.writeheader()
        escritor.writerows({k: f.get(k, "") for k in escritor.fieldnames} for f in filas)


def _indice_falso(hash_corpus: str = "sha256:indice-del-proyecto") -> str:
    """Manifiesto del índice que abriría el proyecto (sin Qdrant ni modelos)."""
    from ipsis.configuracion.carga import cargar_proyecto, config_recuperacion
    from ipsis.indice.manifiesto import ManifiestoIndice, guardar_manifiesto
    from ipsis.indice.qdrant import nombre_coleccion_versionada

    cfg_rec = config_recuperacion(cargar_proyecto())
    nombre = nombre_coleccion_versionada(cfg_rec["coleccion_base"], cfg_rec["modelo"], cfg_rec["version_coleccion"])
    guardar_manifiesto(ManifiestoIndice(coleccion=nombre, modelo_denso=cfg_rec["modelo"], dimension=384,
                                        hash_corpus=hash_corpus, n_chunks=2))
    return hash_corpus


def _motor_falso(qa_respondibles: float, qa_trampas: float):
    """Sustituye la evaluación real: observaciones con señales controladas."""
    from ipsis.evaluacion.banco import cargar_banco
    from ipsis.evaluacion.metricas import ArtefactoEvaluacion, ObservacionEvaluacion, SenalesObservadas

    def evaluar(ruta_manifiesto: str) -> ArtefactoEvaluacion:
        banco = cargar_banco(ruta_manifiesto)
        observaciones = []
        for caso in banco.casos:
            if caso.categoria.value == "conversacional":
                observaciones.append(ObservacionEvaluacion(caso_id=caso.id, backend="falso", estado="conversacional"))
                continue
            qa = qa_respondibles if caso.respondible else qa_trampas
            senales = SenalesObservadas(s_ret=0.9, s_oov=0.0, s_foco=1.0, s_cov=1.0, s_qa=qa, dominio=0.9)
            observaciones.append(ObservacionEvaluacion(
                caso_id=caso.id, backend="falso", estado="relacionado", regla="relacionado", senales=senales,
                respuesta=f"Esto dice el documento: {caso.respuesta_literal or 'otra cosa'}."))
        return ArtefactoEvaluacion.model_construct(observaciones=observaciones)

    return evaluar


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    assert main(["load", str(CORPUS)]) == 0

    def preparar(respondibles: int, trampas: int, qa_respondibles: float, qa_trampas: float) -> str:
        (tmp_path / "golden").mkdir(exist_ok=True)
        _escribir_golden(tmp_path / "golden" / "golden.csv", respondibles, trampas)
        assert main(["golden", "import", "golden/golden.csv"]) == 0
        monkeypatch.setattr("ipsis.aplicacion.evaluacion.evaluar_backend_activo",
                            _motor_falso(qa_respondibles, qa_trampas))
        return _indice_falso()

    return preparar


CALIBRACION = Path("config") / "calibration.yaml"


def test_calibrado_sin_aplicar_no_escribe_nada(proyecto, capsys):
    proyecto(140, 20, qa_respondibles=0.9, qa_trampas=0.5)
    assert main(["calibrate"]) == 0
    salida = capsys.readouterr().out
    assert "CALIBRADO" in salida and "(cambia)" in salida and "ipsis calibrate --apply" in salida
    assert "Test (solo verifica)" in salida
    assert not CALIBRACION.exists()


def test_calibrado_con_aplicar_guarda_procedencia_del_indice_y_se_habilita(proyecto, capsys):
    from ipsis.configuracion.perfiles import cargar_perfil_instalacion, perfil_efectivo
    from ipsis.evaluacion.banco import cargar_banco, hash_banco

    hash_indice = proyecto(140, 20, qa_respondibles=0.9, qa_trampas=0.5)
    assert main(["calibrate", "--apply"]) == 0
    assert "guardada y habilitada" in capsys.readouterr().out
    datos = leer_proyecto(CALIBRACION)
    procedencia = datos["procedencia"]
    assert datos["estado"] == "calibrado" and datos["alfa"] == 0.05
    assert procedencia["hash_corpus"] == hash_indice  # del manifiesto del índice activo
    assert procedencia["perfil"] == "light"
    assert procedencia["modelos"] == cargar_perfil_instalacion("light").modelos.model_dump()
    assert procedencia["hash_banco"] == hash_banco(cargar_banco("golden/bank/manifest.json"))
    # El motor la aplica con ese índice; con otro corpus, no.
    assert perfil_efectivo("light", hash_corpus=hash_indice).origen_umbrales == "calibracion"
    assert perfil_efectivo("light", hash_corpus="sha256:otro").origen_umbrales == "perfil"


def test_muestra_insuficiente_no_es_fallo_y_no_se_aplica(proyecto, capsys):
    from ipsis.configuracion.perfiles import perfil_efectivo

    hash_indice = proyecto(40, 10, qa_respondibles=0.9, qa_trampas=0.5)
    assert main(["calibrate", "--apply"]) == 0
    salida = capsys.readouterr().out
    assert "MUESTRA_INSUFICIENTE" in salida and "faltan al menos" in salida
    assert "inseguro" in salida and "no significa" in salida
    assert "guardado para auditoría" in salida and "habilitada" not in salida
    assert leer_proyecto(CALIBRACION)["estado"] == "muestra_insuficiente"
    assert perfil_efectivo("light", hash_corpus=hash_indice).origen_umbrales == "perfil"


def test_sin_umbral_seguro_sale_con_error_y_no_se_aplica(proyecto, capsys):
    from ipsis.configuracion.perfiles import perfil_efectivo

    hash_indice = proyecto(140, 20, qa_respondibles=0.9, qa_trampas=0.99)
    assert main(["calibrate", "--apply"]) == 1
    salida = capsys.readouterr().out
    assert "SIN_UMBRAL_SEGURO" in salida and "Siguen vigentes los umbrales del perfil" in salida
    datos = leer_proyecto(CALIBRACION)
    assert datos["estado"] == "sin_umbral_seguro" and datos["umbrales"]["ok"] != 1.01
    assert perfil_efectivo("light", hash_corpus=hash_indice).origen_umbrales == "perfil"


# --- errores operacionales ---------------------------------------------------------
@pytest.mark.parametrize("alfa", ["0", "1", "-0.1"])
def test_alfa_invalido(proyecto, capsys, alfa):
    proyecto(40, 10, 0.9, 0.5)
    assert main(["calibrate", "--alpha", alfa]) == 1
    assert "--alpha" in capsys.readouterr().out


def test_sin_golden_o_sin_indice(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "light"]) == 0
    assert main(["load", str(CORPUS)]) == 0
    assert main(["calibrate"]) == 1
    assert "ipsis index" in capsys.readouterr().out  # sin índice, antes que nada
    _indice_falso()
    assert main(["calibrate"]) == 1
    assert "ipsis golden import" in capsys.readouterr().out


def test_corpus_cambiado_o_banco_de_regresion(proyecto, capsys, tmp_path):
    proyecto(40, 10, 0.9, 0.5)
    manifiesto = tmp_path / "golden" / "bank" / "manifest.json"
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    manifiesto.write_text(json.dumps({**datos, "uso": "regresion"}), encoding="utf-8")
    assert main(["calibrate"]) == 1
    assert "no para calibrar" in capsys.readouterr().out

    manifiesto.write_text(json.dumps(datos), encoding="utf-8")
    documento = tmp_path / "documents" / "manual_purificador.md"
    documento.write_text(documento.read_text(encoding="utf-8") + "\nNueva línea.\n", encoding="utf-8")
    assert main(["calibrate"]) == 1
    salida = capsys.readouterr().out
    assert "corpus cambió" in salida and "ipsis golden validate" in salida


# --- integración real (lenta): medium sobre el banco sintético v1.1.0 ------------------
MEDIUM = ("intfloat/multilingual-e5-small", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
          "dewdev/mdeberta-v3-base-squad2-onnx")


@pytest.mark.slow
@pytest.mark.modelos(*MEDIUM)
def test_calibrar_medium_con_el_banco_v1_1_0(tmp_path, monkeypatch, capsys):
    """medium → evaluación real → observaciones → calibración. El banco es
    chico: lo correcto es «muestra_insuficiente», no forzar «calibrado»."""
    from apoyo import BANCO_SINTETICO

    from ipsis.configuracion.carga import cargar_proyecto, config_recuperacion
    from ipsis.evaluacion.banco import cargar_banco
    from ipsis.evaluacion.golden import COLUMNAS_EXPORTADAS, escribir_csv, exportar_filas_csv
    from ipsis.indice.manifiesto import cargar_manifiesto
    from ipsis.indice.qdrant import nombre_coleccion_versionada

    banco_v11 = cargar_banco(BANCO_SINTETICO)
    assert banco_v11.manifiesto.dataset_version == "1.1.0" and banco_v11.manifiesto.uso == "evaluacion"
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--profile", "medium"]) == 0
    assert main(["load", str(CORPUS)]) == 0
    assert main(["index"]) == 0
    escribir_csv(exportar_filas_csv(banco_v11), tmp_path / "golden" / "golden.csv", COLUMNAS_EXPORTADAS)
    assert main(["golden", "import", "golden/golden.csv"]) == 0
    capsys.readouterr()

    assert main(["calibrate", "--apply"]) == 0
    salida = capsys.readouterr().out
    datos = leer_proyecto(CALIBRACION)
    assert datos["estado"] == "muestra_insuficiente", salida
    assert "MUESTRA_INSUFICIENTE" in salida and "faltan al menos" in salida
    # La procedencia sale del índice realmente abierto y del perfil efectivo.
    cfg_rec = config_recuperacion(cargar_proyecto())
    nombre = nombre_coleccion_versionada(cfg_rec["coleccion_base"], cfg_rec["modelo"], cfg_rec["version_coleccion"])
    assert datos["procedencia"]["hash_corpus"] == cargar_manifiesto(nombre).hash_corpus
    assert datos["procedencia"]["perfil"] == "medium"
    assert datos["procedencia"]["modelos"]["lector"] == MEDIUM[2]
    # Las métricas vienen de señales reales: hubo respuestas directas en dev.
    assert datos["resultado"]["dev"]["riesgo"]["n"] > 0
