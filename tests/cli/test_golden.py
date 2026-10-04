"""``ipsis golden``: plantilla, importar, validar y exportar en un proyecto real.

Sin modelos ni red: el golden solo mide. El banco interno (manifiesto + JSONL)
es la representación rigurosa; SQuAD 2.0 y CSV son formatos de intercambio.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from apoyo import CORPUS

from ipsis.cli import main


@pytest.fixture
def proyecto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--perfil", "light"]) == 0
    assert main(["cargar", str(CORPUS)]) == 0
    return tmp_path


def _leer(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _escribir(ruta: Path, filas: list[dict], separador: str = ",") -> None:
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]), delimiter=separador)
        escritor.writeheader()
        escritor.writerows(filas)


def _completar_un_par(ruta: Path) -> tuple[str, str]:
    """El cliente completa la primera trampa y su respondible: la respuesta
    literal sale del fragmento sugerido (texto del documento)."""
    filas = _leer(ruta)
    trampa = next(f for f in filas if f["subtipo"] == "trampa_mismo_tema")
    respondible = next(f for f in filas if f["id"] == trampa["par"])
    respondible["pregunta"] = "¿Qué dice esta sección?"
    respondible["respuesta_literal"] = " ".join(respondible["fragmento_sugerido"].split()[:6])
    trampa["pregunta"] = "¿Quién aprueba esto?"
    _escribir(ruta, filas)
    return respondible["id"], trampa["id"]


def _banco(proyecto: Path) -> dict[str, dict]:
    lineas = (proyecto / "golden" / "banco" / "golden.jsonl").read_text(encoding="utf-8").splitlines()
    return {c["id"]: c for c in map(json.loads, lineas)}


# --- plantilla -----------------------------------------------------------------
def test_plantilla_crea_csv_y_leeme_y_no_pisa_lo_escrito(proyecto: Path, capsys):
    assert main(["golden", "plantilla", "--n", "20"]) == 0
    ruta = proyecto / "golden" / "golden.csv"
    assert ruta.read_bytes().startswith(b"\xef\xbb\xbf")
    assert (proyecto / "golden" / "LEEME.txt").is_file()
    assert "9 secciones" in capsys.readouterr().out  # explica por qué hay menos de 20 filas

    _completar_un_par(ruta)
    escrito = ruta.read_bytes()
    assert main(["golden", "plantilla"]) == 1
    assert "--force" in capsys.readouterr().out
    assert ruta.read_bytes() == escrito  # no se pisó
    assert main(["golden", "plantilla", "--force"]) == 0
    assert ruta.read_bytes() != escrito


def test_plantilla_sin_documentos_falla_con_mensaje(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--perfil", "light"]) == 0
    assert main(["golden", "plantilla"]) == 1
    assert "ipsis cargar" in capsys.readouterr().out


# --- ida y vuelta (criterio de P9.3) ----------------------------------------------
def test_ida_y_vuelta_plantilla_importar_squad2_importar(proyecto: Path):
    assert main(["golden", "plantilla", "--n", "20"]) == 0
    id_r, id_t = _completar_un_par(proyecto / "golden" / "golden.csv")
    assert main(["golden", "importar", "golden/golden.csv"]) == 0
    original = _banco(proyecto)
    manifiesto = json.loads((proyecto / "golden" / "banco" / "manifiesto.json").read_text(encoding="utf-8"))
    assert manifiesto["procedencia"] == {"formato": "csv", "archivo": "golden.csv"}

    assert main(["golden", "exportar", "--formato", "squad2"]) == 0
    squad = json.loads((proyecto / "golden" / "exportado.squad2.json").read_text(encoding="utf-8"))
    qas = {qa["id"]: (parrafo, qa) for art in squad["data"] for parrafo in art["paragraphs"] for qa in parrafo["qas"]}
    parrafo, qa = qas[id_r]
    respuesta = qa["answers"][0]
    # answer_start es relativo al context, no al documento…
    inicio = respuesta["answer_start"]
    assert parrafo["context"][inicio:inicio + len(respuesta["text"])] == respuesta["text"]
    # …y el context, ubicado en el documento, lleva a la misma posición global.
    from ipsis.ingesta.ingesta import parsear_corpus

    evidencia = original[id_r]["evidencias"][0]
    documento = {d.doc_id: d.texto_completo for d in parsear_corpus("documentos")}[evidencia["doc_id"]]
    global_respuesta = evidencia["offset_inicio"] + evidencia["texto"].index(respuesta["text"])
    assert documento.index(parrafo["context"]) + inicio == global_respuesta
    parrafo_t, trampa = qas[id_t]
    assert (trampa["is_impossible"], trampa["answers"]) == (True, [])
    assert parrafo_t["context"] == parrafo["context"]  # la trampa va en el párrafo de su par

    assert main(["golden", "importar", "golden/exportado.squad2.json"]) == 0
    reimportado = _banco(proyecto)
    # Conservado: la semántica QA completa, el split y la metadata de la extensión «rag».
    preguntas_qa = {i for i, c in original.items() if c["categoria"] != "conversacional"}
    assert set(reimportado) == preguntas_qa
    campos = ("pregunta", "respondible", "respuesta_literal", "evidencias", "split", "categoria", "subtipo", "par")
    for id_ in preguntas_qa:
        assert {k: reimportado[id_].get(k) for k in campos} == {k: original[id_].get(k) for k in campos}, id_
    assert reimportado[id_t]["par"] == id_r
    # Perdido a propósito: las conversacionales (SQuAD 2.0 es QA extractivo).
    assert {c["categoria"] for c in original.values()} - {c["categoria"] for c in reimportado.values()} == \
        {"conversacional"}


def test_exportar_csv_e_importar_da_el_mismo_banco(proyecto: Path):
    assert main(["golden", "plantilla", "--n", "20"]) == 0
    _completar_un_par(proyecto / "golden" / "golden.csv")
    assert main(["golden", "importar", "golden/golden.csv"]) == 0
    original = _banco(proyecto)
    assert main(["golden", "exportar", "--formato", "csv"]) == 0
    exportado = proyecto / "golden" / "exportado.csv"
    assert exportado.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "offset" not in exportado.read_text(encoding="utf-8-sig").splitlines()[0]  # legible: sin internos
    assert main(["golden", "importar", "golden/exportado.csv"]) == 0
    assert _banco(proyecto) == original


def test_importar_csv_con_punto_y_coma(proyecto: Path):
    assert main(["golden", "plantilla", "--n", "20"]) == 0
    ruta = proyecto / "golden" / "golden.csv"
    _completar_un_par(ruta)
    _escribir(ruta, _leer(ruta), separador=";")
    assert main(["golden", "importar", "golden/golden.csv"]) == 0
    assert any(c["respondible"] for c in _banco(proyecto).values())


# --- SQuAD 2.0 externo -------------------------------------------------------------
def _squad(ruta: Path, qas: list[dict], contexto: str, titulo: str = "reglamento_servicio") -> None:
    ruta.write_text(json.dumps({"version": "v2.0", "data": [{"title": titulo, "paragraphs": [
        {"context": contexto, "qas": qas}]}]}, ensure_ascii=False), encoding="utf-8")


def test_squad2_externo_sin_extension_y_ocurrencia_exacta_por_contexto(proyecto: Path):
    # «días hábiles» aparece en el Artículo 3 y en el 8: el contexto elige el 8.
    texto = "Artículo 8. El reembolso se paga en un plazo de 10 días hábiles mediante transferencia " \
            "a la cuenta registrada por el cliente."
    from ipsis.ingesta.ingesta import parsear_corpus

    documento = {d.doc_id: d.texto_completo for d in parsear_corpus("documentos")}["reglamento-servicio"]
    assert texto in documento and documento.count("días hábiles") == 2
    _squad(proyecto / "externo.json", [
        {"id": "q1", "question": "¿En cuánto se paga?", "is_impossible": False,
         "answers": [{"text": "días hábiles", "answer_start": texto.index("días hábiles")}]},
        {"id": "q2", "question": "¿Quién lo aprueba?", "is_impossible": True, "answers": []},
    ], texto, titulo="reglamento-servicio")
    assert main(["golden", "importar", "externo.json"]) == 0
    banco = _banco(proyecto)
    evidencia = banco["q1"]["evidencias"][0]
    assert documento.index(texto) <= evidencia["offset_inicio"] < documento.index(texto) + len(texto)
    assert (banco["q2"]["categoria"], banco["q2"]["respondible"]) == ("sin_respuesta", False)


# --- validar y errores ---------------------------------------------------------------
def test_validar_detecta_corpus_modificado_sin_tocar_nada(proyecto: Path, capsys):
    assert main(["golden", "validar"]) == 1
    assert "ipsis golden importar" in capsys.readouterr().out

    assert main(["golden", "plantilla", "--n", "20"]) == 0
    _completar_un_par(proyecto / "golden" / "golden.csv")
    assert main(["golden", "importar", "golden/golden.csv"]) == 0
    assert main(["golden", "validar"]) == 0

    banco = proyecto / "golden" / "banco"
    antes = {p.name: p.read_bytes() for p in banco.iterdir()}
    documento = proyecto / "documentos" / "manual_purificador.md"
    documento.write_text(documento.read_text(encoding="utf-8").replace("24 meses", "36 meses"), encoding="utf-8")
    capsys.readouterr()
    assert main(["golden", "validar"]) == 1
    assert "corpus cambió" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in banco.iterdir()} == antes  # solo lectura
    assert main(["golden", "exportar", "--formato", "csv"]) == 1  # no exporta un banco obsoleto


def test_importar_con_errores_los_lista_y_no_escribe_el_banco(proyecto: Path, capsys):
    ruta = proyecto / "golden" / "malo.csv"
    ruta.parent.mkdir(exist_ok=True)
    _escribir(ruta, [
        {"id": "a1", "pregunta": "¿Cuánto cuesta?", "tipo": "respondible", "respuesta_literal": "999 pesos"},
        {"id": "a2", "pregunta": "¿Otra?", "tipo": "inventado", "respuesta_literal": ""},
    ])
    assert main(["golden", "importar", "golden/malo.csv"]) == 1
    salida = capsys.readouterr().out
    assert "malo.csv:2" in salida and "999 pesos" in salida and "malo.csv:3" in salida
    assert "Traceback" not in salida
    assert not (proyecto / "golden" / "banco").exists()
    assert main(["golden", "importar", "golden/no_existe.csv"]) == 1
