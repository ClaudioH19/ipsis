"""``ipsis benchmark --profiles`` con perfiles falsos: mismo banco, latencia,
presupuesto, reportes, experimentos y código de salida. Sin modelos."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ipsis.cli import main
from ipsis.evaluacion.banco import cargar_banco
from ipsis.evaluacion.benchmark import ReporteBenchmark, codigo_salida, latencia_de, markdown, percentil
from ipsis.evaluacion.metricas import ArtefactoEvaluacion, ObservacionEvaluacion, SenalesObservadas, evaluar_observaciones
from ipsis.nucleo.esquemas import EvidenceSpan

UNIVERSAL_ES = Path(__file__).resolve().parents[1] / "datos" / "banco_universal" / "es" / "manifiesto.json"
SINTETICO = Path(__file__).resolve().parents[1] / "datos" / "banco" / "manifiesto.json"
# Latencia por consulta de cada perfil falso (ms); todos cumplen su presupuesto.
LATENCIA = {"bm25": 20, "light": 60, "medium": 700}


def _artefacto(banco, perfil: str, *, trampa_qa: float = 0.82) -> ArtefactoEvaluacion:
    """Respondibles bien contestadas; la primera trampa contesta ok con s_qa 0,82."""
    observaciones, primera = [], True
    for caso in banco.casos:
        etapas = {"recuperacion_ms": LATENCIA[perfil] // 2, "politica_ms": 1}
        if caso.categoria.value == "conversacional":
            observaciones.append(ObservacionEvaluacion(caso_id=caso.id, backend="falso", estado="conversacional",
                                                       latencia_ms=LATENCIA[perfil], etapas_ms=etapas))
            continue
        if caso.respondible:
            qa, estado, regla, texto = 0.9, "respuesta_directa", "ok_lector", caso.respuesta_literal
        elif primera:  # el primer caso no respondible: una trampa en el banco universal
            primera = False
            qa, estado, regla, texto = trampa_qa, "respuesta_directa", "ok_lector", "un pasaje tentador"
        else:
            qa, estado, regla, texto = 0.1, "relacionado", "relacionado", "pasaje"
        senales = SenalesObservadas(s_ret=0.9, s_oov=0.0, s_foco=1.0, s_cov=1.0, s_qa=qa, dominio=0.9)
        observaciones.append(ObservacionEvaluacion(
            caso_id=caso.id, backend="falso", estado=estado, regla=regla, senales=senales, respuesta=texto,
            evidencias=[EvidenceSpan(doc_id=e.doc_id, chunk_id=f"c-{caso.id}", texto=e.texto,
                                    offset_inicio=e.offset_inicio, offset_fin=e.offset_fin)
                        for e in caso.evidencias],
            latencia_ms=LATENCIA[perfil], etapas_ms=etapas, idioma=banco.manifiesto.idioma))
    reporte = evaluar_observaciones(banco, observaciones, {})
    return ArtefactoEvaluacion(backend="falso", dataset_id=banco.manifiesto.dataset_id,
                               dataset_version=banco.manifiesto.dataset_version, dataset_sha256="0" * 64,
                               configuracion_sha256="1" * 64, configuracion={}, indice={}, reporte=reporte,
                               observaciones=observaciones)


def _evaluar_falso(perfil, manifiesto, banco, experimentos):
    acuerdo = None
    if experimentos and perfil == "light":
        # acuerdo 0 en la trampa que da ok (las búsquedas no coinciden), 1 en el resto
        trampa = next(c.id for c in banco.casos if c.subtipo == "trampa_mismo_tema")
        acuerdo = ({c.id: 0.0 if c.id == trampa else 1.0 for c in banco.casos}, {c.id: 3.0 for c in banco.casos})
    return _artefacto(banco, perfil), 1.5, acuerdo


def _benchmark(tmp_path, perfiles, experimentos=False, bancos=(UNIVERSAL_ES,)):
    from ipsis.aplicacion.benchmark import ejecutar_benchmark_perfiles

    return ejecutar_benchmark_perfiles([str(b) for b in bancos], perfiles, main, tmp_path,
                                       experimentos=experimentos, evaluar_perfil=_evaluar_falso)


# --- funciones puras -----------------------------------------------------------------
def test_latencia_p50_p95_y_por_etapa():
    observaciones = [ObservacionEvaluacion(caso_id=str(i), backend="b", estado="x", latencia_ms=i,
                                           etapas_ms={"lectura_ms": 2 * i}) for i in range(1, 101)]
    latencia = latencia_de(observaciones)
    assert (latencia.p50, latencia.p95) == (pytest.approx(50.5), pytest.approx(95.05, abs=0.1))
    assert latencia.etapas["lectura"]["p95"] == pytest.approx(190.1, abs=0.1)
    con_extra = latencia_de(observaciones, extra_ms={str(i): 10 for i in range(1, 101)})
    assert con_extra.p95 == pytest.approx(105.05, abs=0.1)
    assert percentil([], 0.95) == 0.0


# --- orquestación ----------------------------------------------------------------------
def test_mismos_casos_orden_estable_y_presupuesto(tmp_path, monkeypatch):
    monkeypatch.setitem(LATENCIA, "medium", 1500)  # medium excede su presupuesto (1000)
    reporte = _benchmark(tmp_path, ["medium", "bm25", "light"])
    assert [p.nombre for p in reporte.perfiles] == ["medium", "bm25", "light"]  # el orden pedido
    ids = {p.nombre: {f.caso_id for f in p.cobertura.casos} for p in reporte.perfiles}
    assert len({frozenset(v) for v in ids.values()}) == 1  # todos midieron los mismos casos
    cumple = {p.nombre: p.cumple_presupuesto for p in reporte.perfiles}
    assert cumple == {"medium": False, "bm25": True, "light": True}
    assert codigo_salida(reporte) == 1  # medium excede


def test_un_perfil_que_omite_casos_falla(tmp_path):
    from ipsis.aplicacion.benchmark import ejecutar_benchmark_perfiles

    def incompleto(perfil, manifiesto, banco, experimentos):
        artefacto = _artefacto(banco, perfil)
        return artefacto.model_copy(update={"observaciones": artefacto.observaciones[:-1]}), 0.0, None

    with pytest.raises(RuntimeError, match="exactamente los casos"):
        ejecutar_benchmark_perfiles([str(UNIVERSAL_ES)], ["light"], main, tmp_path, evaluar_perfil=incompleto)


def test_perfil_desconocido(tmp_path):
    with pytest.raises(ValueError, match="perfiles desconocidos"):
        _benchmark(tmp_path, ["light", "turbo"])


def test_reportes_json_markdown_y_artefactos_para_comparar(tmp_path):
    from ipsis.aplicacion.benchmark import escribir_reporte_benchmark
    from ipsis.evaluacion.comparacion import cargar_artefacto, comparar_artefactos

    reporte = _benchmark(tmp_path, ["light", "medium"])
    ruta_json, ruta_md = escribir_reporte_benchmark(reporte, tmp_path)
    assert ReporteBenchmark.model_validate_json(ruta_json.read_text(encoding="utf-8")) == reporte
    texto = ruta_md.read_text(encoding="utf-8")
    assert "| light |" in texto and "Falsos ok por perfil" in texto and "no la memoria usada" in texto
    # Banco de regresión: compara, nunca certifica.
    assert "no certifican" in texto and "certificado" not in texto.lower()
    informe = comparar_artefactos([cargar_artefacto(r) for r in reporte.artefactos])
    assert len(informe.filas) == 2


def test_falsos_ok_solo_cortan_con_un_banco_de_evaluacion(tmp_path):
    regresion = _benchmark(tmp_path, ["light"])
    assert regresion.perfiles[0].cobertura.total.falsos_ok == 1
    assert codigo_salida(regresion) == 0  # banco universal: sin límite de falsos ok propio
    evaluacion = _benchmark(tmp_path, ["light"], bancos=(SINTETICO,))
    assert cargar_banco(SINTETICO).manifiesto.uso == "evaluacion"
    assert codigo_salida(evaluacion) == 1  # misma guardia que ipsis evaluate: 0 falsos ok


def test_experimentos_son_variantes_y_no_cortan(tmp_path):
    reporte = _benchmark(tmp_path, ["light", "medium"], experimentos=True)
    por_nombre = {p.nombre: p for p in reporte.perfiles}
    variante = por_nombre["medium+ok0.85"]
    assert variante.variante and variante.latencia == por_nombre["medium"].latencia
    assert por_nombre["medium"].cobertura.total.falsos_ok == 1
    assert variante.cobertura.total.falsos_ok == 0  # s_qa 0,82 < 0,85
    acuerdo = por_nombre["light+acuerdo"]
    assert acuerdo.cobertura.total.falsos_ok == 1  # la trampa usa el lector (ok_lector): acuerdo no aplica
    assert acuerdo.costo_extra["búsquedas extra p95 ms"] == 3.0
    assert acuerdo.latencia.p95 == pytest.approx(por_nombre["light"].latencia.p95 + 3.0)
    assert "Variantes experimentales" in markdown(reporte)


# --- bm25 de diagnóstico ---------------------------------------------------------------
def test_bm25_recupera_solo_con_bm25_y_no_se_instala(tmp_path, monkeypatch):
    from ipsis.configuracion.carga import config_recuperacion
    from ipsis.configuracion.perfiles import cargar_perfil_instalacion

    assert cargar_perfil_instalacion("bm25").recuperacion_modo == "dispersa"
    cfg = {"recuperacion": {"modelo": None, "modo": "hibrida", "coleccion_base": "x"}}
    assert config_recuperacion(cfg, perfil="bm25")["modo"] == "dispersa"
    assert config_recuperacion(cfg, perfil="light")["modo"] == "hibrida"
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main(["init", "--profile", "bm25"])


# --- CLI -------------------------------------------------------------------------------
def test_cli_escribe_reportes_y_sale_segun_presupuesto(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("ipsis.aplicacion.benchmark._evaluar_en_proyecto",
                        lambda p, m, b, main, e: _evaluar_falso(p, m, b, e))
    salida = tmp_path / "reportes"
    assert main(["benchmark", "--bank", str(UNIVERSAL_ES), "--profiles", "bm25,light,medium",
                 "--output", str(salida)]) == 0
    texto = capsys.readouterr().out
    assert "no certifican" in texto and "[cumple]" in texto
    assert (salida / "benchmark-profiles.json").is_file() and (salida / "benchmark-profiles.md").is_file()
    datos = json.loads((salida / "benchmark-profiles.json").read_text(encoding="utf-8"))
    assert [p["nombre"] for p in datos["perfiles"]] == ["bm25", "light", "medium"]
    monkeypatch.setitem(LATENCIA, "medium", 1500)
    assert main(["benchmark", "--bank", str(UNIVERSAL_ES), "--profiles", "medium", "--output", str(salida)]) == 1
    assert "EXCEDE" in capsys.readouterr().out


# --- integración real (lenta) ----------------------------------------------------------
@pytest.mark.slow
@pytest.mark.modelos("intfloat/multilingual-e5-small", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
                     "dewdev/mdeberta-v3-base-squad2-onnx")
def test_benchmark_real_light_y_medium_sobre_el_mismo_banco(tmp_path, capsys):
    salida = tmp_path / "reportes"
    codigo = main(["benchmark", "--bank", str(UNIVERSAL_ES), "--profiles", "bm25,light,medium",
                   "--output", str(salida)])
    reporte = ReporteBenchmark.model_validate_json((salida / "benchmark-profiles.json").read_text(encoding="utf-8"))
    bm25, light, medium = reporte.perfiles
    assert bm25.cascada["recuperacion"] == "dispersa" and light.cascada["recuperacion"] == "hibrida"
    assert codigo == codigo_salida(reporte)
    assert {f.caso_id for f in light.cobertura.casos} == {f.caso_id for f in medium.cobertura.casos}
    assert light.latencia.n == medium.latencia.n == 30
    assert "lectura" in medium.latencia.etapas and "lectura" not in light.latencia.etapas
    assert [m.rol for m in medium.modelos] == ["denso", "reranker", "lector"]
    assert medium.cobertura.por_grupo["exacta"].cobertura_directa >= light.cobertura.por_grupo["exacta"].cobertura_directa
