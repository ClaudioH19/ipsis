"""Registro de consultas (apagado por defecto) y ``ipsis audit``, con un motor falso."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ipsis.cli import main
from ipsis.nucleo.esquemas import AssistantResult, AssistantState, EvidenceSpan
from apoyo import escribir_proyecto, leer_proyecto

MANUAL = "# Manual\n\n## Filtro\n\nEl filtro de sedimentos se cambia cada 6 meses.\n"
ORACION = "El filtro de sedimentos se cambia cada 6 meses."
REGISTRO = Path(".ipsis/logs/queries.jsonl")


@pytest.fixture(autouse=True)
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Proyecto propio por prueba: el de la suite es compartido y esto escribe en él."""
    carpeta = tmp_path / "proyecto"
    carpeta.mkdir()
    monkeypatch.chdir(carpeta)
    assert main(["init", "--profile", "light"]) == 0
    return carpeta


@pytest.fixture
def corpus(tmp_path: Path) -> dict[str, int]:
    """Un documento cargado en el proyecto; offsets reales de ORACION."""
    from ipsis.ingesta.ingesta import parsear_corpus

    origen = tmp_path / "fuente" / "manual.md"
    origen.parent.mkdir()
    origen.write_text(MANUAL, encoding="utf-8")
    assert main(["load", str(origen)]) == 0
    texto = parsear_corpus("documents")[0].texto_completo
    inicio = texto.index(ORACION)
    return {"inicio": inicio, "fin": inicio + len(ORACION), "tramo": texto.index("6 meses")}


class MotorFalso:
    def __init__(self, offsets):
        self.o = offsets

    def consultar(self, pregunta, id_sesion):
        o = self.o
        contrato = {"estado": "ok", "nivel_servicio": "normal", "respuesta": ORACION, "plan": "dato_puntual",
                    "fragmentos": [], "confianza": {"top1": 0.9, "margen": 0.1, "acuerdo_bm25": None},
                    "latencia_ms": 1,
                    "respuesta_exacta": {"chunk_id": "manual__c0000", "texto": "6 meses",
                                         "offset_inicio": o["tramo"], "offset_fin": o["tramo"] + 7}}
        evidencia = EvidenceSpan(doc_id="manual", chunk_id="manual__c0000", texto=ORACION,
                                 offset_inicio=o["inicio"], offset_fin=o["fin"])
        return AssistantResult(estado=AssistantState.RESPUESTA_DIRECTA, motivo="lector", mensaje_usuario=ORACION,
                               evidencias=[evidencia],
                               diagnostico={"contrato_http": contrato, "regla": "ok_lector", "perfil": "medium",
                                            "senales_politica": {"s_qa": 0.97, "s_foco": 1.0},
                                            "tono": "cordial", "plantillas": ["cordial.apertura.3"]})


def _preguntar(offsets, *preguntas):
    from ipsis.servicio.api import crear_app

    cliente = TestClient(crear_app(MotorFalso(offsets)))
    for pregunta in preguntas:
        assert cliente.post("/consultar", json={"pregunta": pregunta, "id_sesion": "sesion-secreta"}).status_code == 200


def test_con_el_registro_apagado_no_se_escribe_nada(corpus):
    from ipsis.aplicacion.proyecto import configuracion_asistente

    assert configuracion_asistente()["registro"] == {"activo": False}  # apagado por defecto
    _preguntar(corpus, "¿Cada cuánto se cambia el filtro?")
    assert not Path(".ipsis/logs").exists()


def test_activo_registra_una_linea_por_consulta_sin_datos_de_sesion(corpus, capsys):
    assert main(["configure", "query_log.enabled=true"]) == 0
    _preguntar(corpus, "¿Cada cuánto se cambia el filtro?", "¿Y el filtro?")
    lineas = REGISTRO.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2
    entrada = json.loads(lineas[0])
    assert {k: entrada[k] for k in ("pregunta", "estado", "regla", "motivo", "perfil")} == {
        "pregunta": "¿Cada cuánto se cambia el filtro?", "estado": "ok", "regla": "ok_lector",
        "motivo": "lector", "perfil": "medium"}
    assert entrada["senales"] == {"s_qa": 0.97, "s_foco": 1.0}
    assert entrada["tono"] == "cordial" and entrada["plantillas"] == ["cordial.apertura.3"]
    assert entrada["evidencias"][0]["offset_inicio"] == corpus["inicio"]
    assert entrada["respuesta_exacta"]["doc_id"] == "manual"
    assert "sesion-secreta" not in REGISTRO.read_text(encoding="utf-8")

    capsys.readouterr()
    assert main(["audit"]) == 0
    salida = capsys.readouterr().out
    assert "(2 consultas)" in salida and "ok 2" in salida and "ok_lector 2" in salida
    assert "Tonos:   cordial 2" in salida
    assert "Evidencias verificadas contra el corpus vigente: 4, con problemas: 0" in salida


def test_una_evidencia_alterada_a_mano_se_reporta(corpus, capsys):
    assert main(["configure", "query_log.enabled=true"]) == 0
    _preguntar(corpus, "a", "b")
    lineas = REGISTRO.read_text(encoding="utf-8").splitlines()
    alterada = json.loads(lineas[1])
    alterada["evidencias"][0]["texto"] = ORACION.replace("6 meses", "9 meses")
    alterada["respuesta_exacta"]["texto"] = "9 meses"
    REGISTRO.write_text("\n".join([lineas[0], json.dumps(alterada, ensure_ascii=False), "{roto"]) + "\n",
                        encoding="utf-8")
    capsys.readouterr()
    assert main(["audit"]) == 1
    salida = capsys.readouterr().out
    assert "con problemas: 2" in salida
    assert f"línea 2: manual offsets {corpus['inicio']}-{corpus['fin']}: alterada" in salida
    assert "tramo_alterado" in salida and "«9 meses»" in salida
    assert "Líneas ilegibles: 3" in salida


def test_documento_retirado_del_corpus_se_reporta(corpus):
    from ipsis.aplicacion.registro import auditar_registro

    assert main(["configure", "query_log.enabled=true"]) == 0
    _preguntar(corpus, "a")
    catalogo = Path("documents/catalog.yaml")
    datos = leer_proyecto(catalogo)
    datos["documentos"][0]["vigente"] = False
    escribir_proyecto(catalogo, datos)
    r = auditar_registro()
    assert not r.ok and {p.motivo for p in r.problemas} == {"documento_ausente"}


def test_sin_registro_auditar_dice_como_activarlo(capsys):
    assert main(["audit"]) == 1
    assert "Acción: ipsis configure query_log.enabled=true" in capsys.readouterr().out


def test_un_fallo_al_escribir_el_registro_no_tumba_la_respuesta(corpus, monkeypatch):
    def falla(self, pregunta, resultado):
        raise OSError("disco lleno")

    assert main(["configure", "query_log.enabled=true"]) == 0
    monkeypatch.setattr("ipsis.aplicacion.registro.RegistroConsultas.registrar", falla)
    _preguntar(corpus, "a")


def test_configurar_registro_activo_valida_el_booleano(capsys):
    assert main(["configure", "query_log.enabled=quizas"]) == 1
    assert "espera true o false" in capsys.readouterr().out


def test_auditar_por_rango_de_fechas(corpus, capsys):
    assert main(["configure", "query_log.enabled=true"]) == 0
    _preguntar(corpus, "a", "b", "c")
    lineas = [json.loads(linea) for linea in REGISTRO.read_text(encoding="utf-8").splitlines()]
    lineas[0]["fecha"] = "2026-09-30T23:59:59+00:00"
    lineas[1]["fecha"] = "2026-10-01T08:00:00+00:00"
    lineas[2]["fecha"] = "2026-10-02T00:00:00+00:00"
    sin_fecha = dict(lineas[2])
    del sin_fecha["fecha"]
    REGISTRO.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in [*lineas, sin_fecha]) + "\n",
                        encoding="utf-8")
    capsys.readouterr()
    assert main(["audit", "--from", "2026-10-01", "--to", "2026-10-01"]) == 0  # el día completo
    salida = capsys.readouterr().out
    assert "(1 consultas, rango 2026-10-01T00:00:00+00:00 a 2026-10-01T23:59:59.999999+00:00; 2 fuera del rango)" \
        in salida
    assert "Líneas sin fecha legible (excluidas del rango): 4" in salida
    assert main(["audit", "--from", "2026-10-01T08:00"]) == 0
    assert "(2 consultas" in capsys.readouterr().out
    assert main(["audit"]) == 0
    assert "(4 consultas)" in capsys.readouterr().out  # sin filtro no se excluye nada


def test_auditar_con_fecha_invalida_dice_el_formato(corpus, capsys):
    assert main(["configure", "query_log.enabled=true"]) == 0
    _preguntar(corpus, "a")
    capsys.readouterr()
    assert main(["audit", "--from", "ayer"]) == 2
    assert "AAAA-MM-DD" in capsys.readouterr().out
    assert main(["audit", "--from", "2026-10-02", "--to", "2026-10-01"]) == 2
    assert "posterior" in capsys.readouterr().out
