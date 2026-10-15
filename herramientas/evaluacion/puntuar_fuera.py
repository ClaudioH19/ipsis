"""Puntúa con otros rerankers los pasajes que vio el reranker del motor (sin ONNX ni catálogo).

Sirve para decidir **qué modelo vale la pena integrar** antes de exportarlo y conectarlo al motor:
``ranking_pasajes.py --volcar-candidatos`` guarda, por pregunta, los pasajes exactos que recibe el
reranker (en el orden híbrido) y si tocan una evidencia; este script los puntúa con cada modelo y
calcula hit@1/3/5 y MRR sobre ese mismo conjunto, sin repetir la recuperación.

Es una herramienta de desarrollo: necesita ``torch`` y ``transformers`` (no son dependencias de ipsis),
así que se corre en un entorno aparte:

    uv venv /tmp/venv-eval && uv pip install --python /tmp/venv-eval/bin/python \\
        torch --index-url https://download.pytorch.org/whl/cpu
    uv pip install --python /tmp/venv-eval/bin/python transformers huggingface_hub sentencepiece mxbai-rerank
    /tmp/venv-eval/bin/python herramientas/evaluacion/puntuar_fuera.py candidatos.jsonl \\
        --modelo cross:BAAI/bge-reranker-v2-m3 --modelo qwen3:Qwen/Qwen3-Reranker-0.6B --salida resultado.json

Familias de modelo (``familia:id``): ``cross`` (clasificación de secuencias, un logit), ``qwen3``
(Qwen3-Reranker: probabilidad de «yes»), ``mxbai2`` (paquete mxbai-rerank) y ``lb`` (esperanza de la
nota 1 a 7 de lightblue/lb-reranker) y ``laya`` (modelo de decisión tipada: P(sí) a «¿responde?»). Los tiempos son de fp32 en CPU y solo ordenan los modelos entre
sí; la latencia que cuenta es la del modelo cuantizado dentro del motor.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

INSTRUCCION_QWEN3 = "Given a web search query, retrieve relevant passages that answer the query"


def cargar_candidatos(ruta, solo_particion=None, limite=None):
    filas = [json.loads(linea) for linea in Path(ruta).read_text(encoding="utf-8").splitlines() if linea.strip()]
    if solo_particion:
        filas = [f for f in filas if f["split"] == solo_particion]
    return filas[:limite] if limite else filas


def metricas(rangos):
    """hit@1/3/5 y MRR de los rangos de la primera evidencia (None = no aparece entre los candidatos)."""
    n = len(rangos)
    salida = {"n": n}
    for corte in (1, 3, 5):
        salida[f"hit@{corte}"] = round(sum(1 for r in rangos if r is not None and r <= corte) / n, 4) if n else 0.0
    salida["mrr"] = round(sum(1 / r for r in rangos if r) / n, 4) if n else 0.0
    return salida


def rango_de(puntajes, correctos):
    """Posición (desde 1) del mejor candidato correcto al ordenar por puntaje decreciente; desempate por posición."""
    orden = sorted(range(len(puntajes)), key=lambda i: (-puntajes[i], i))
    for rango, i in enumerate(orden, start=1):
        if correctos[i]:
            return rango
    return None


def evaluar(filas, puntuar, n_candidatos):
    """Rangos por pregunta usando solo los primeros ``n_candidatos`` pasajes del orden híbrido."""
    rangos, tiempos = {}, []
    for fila in filas:
        pasajes = fila["pasajes"][:n_candidatos]
        if not pasajes:
            continue
        inicio = time.perf_counter()
        puntajes = puntuar(fila["pregunta"], [p["texto"] for p in pasajes])
        tiempos.append(time.perf_counter() - inicio)
        rangos[fila["id"]] = rango_de(puntajes, [p["correcto"] for p in pasajes])
    return rangos, tiempos


def es_informal(id_caso):
    """Los bancos adversarios marcan con «i» final la redacción informal; el banco de pasajes, con «parafrasis»."""
    return id_caso.endswith("i") or "-parafrasis-" in id_caso


def resumir(rangos, tiempos):
    informal = [r for i, r in rangos.items() if es_informal(i)]
    formal = [r for i, r in rangos.items() if not es_informal(i)]
    return {"todo": metricas(list(rangos.values())), "formal": metricas(formal), "informal": metricas(informal),
            "s_por_pregunta_p50": round(statistics.median(tiempos), 3) if tiempos else None,
            "s_por_pregunta_max": round(max(tiempos), 3) if tiempos else None}


# ---------------------------------------------------------------------------
# Familias de modelo
# ---------------------------------------------------------------------------
def construir_cross(id_hf, torch, max_tokens):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(id_hf)
    modelo = AutoModelForSequenceClassification.from_pretrained(id_hf).eval()

    def puntuar(pregunta, pasajes):
        puntajes = []
        for i in range(0, len(pasajes), 8):
            lote = tok([pregunta] * len(pasajes[i:i + 8]), pasajes[i:i + 8], padding=True, truncation=True,
                       max_length=max_tokens, return_tensors="pt")
            with torch.no_grad():
                puntajes.extend(modelo(**lote).logits.reshape(len(lote["input_ids"]), -1)[:, 0].tolist())
        return puntajes
    return puntuar


def construir_qwen3(id_hf, torch, max_tokens):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(id_hf, padding_side="left")
    modelo = AutoModelForCausalLM.from_pretrained(id_hf, torch_dtype=torch.float32).eval()
    si, no = tok.convert_tokens_to_ids("yes"), tok.convert_tokens_to_ids("no")
    prefijo = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the "
               "Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
    sufijo = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

    def puntuar(pregunta, pasajes):
        puntajes = []
        for i in range(0, len(pasajes), 4):
            textos = [f"{prefijo}<Instruct>: {INSTRUCCION_QWEN3}\n<Query>: {pregunta}\n<Document>: {p}{sufijo}"
                      for p in pasajes[i:i + 4]]
            lote = tok(textos, padding=True, truncation=True, max_length=max_tokens + 128, return_tensors="pt")
            with torch.no_grad():
                logits = modelo(**lote).logits[:, -1, :]
            par = torch.stack([logits[:, no], logits[:, si]], dim=1)
            puntajes.extend(torch.log_softmax(par, dim=1)[:, 1].tolist())
        return puntajes
    return puntuar


def construir_lb(id_hf, torch, max_tokens):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(id_hf, padding_side="left")
    modelo = AutoModelForCausalLM.from_pretrained(id_hf, torch_dtype=torch.float32).eval()
    ids = [tok.encode(str(n), add_special_tokens=False)[0] for n in range(1, 8)]
    sistema = ("Given a query and a piece of text, output a score of 1-7 based on how related the query is to the "
               "text. 1 means least related and 7 is most related.")

    def puntuar(pregunta, pasajes):
        puntajes = []
        for i in range(0, len(pasajes), 4):
            textos = [tok.apply_chat_template(
                [{"role": "system", "content": sistema},
                 {"role": "user", "content": f"<<<Query>>>\n{pregunta}\n\n<<<Context>>>\n{p}"}],
                tokenize=False, add_generation_prompt=True) for p in pasajes[i:i + 4]]
            lote = tok(textos, padding=True, truncation=True, max_length=max_tokens + 128, return_tensors="pt")
            with torch.no_grad():
                logits = modelo(**lote).logits[:, -1, :][:, ids]
            prob = torch.softmax(logits, dim=1)
            puntajes.extend((prob * torch.arange(1, 8)).sum(dim=1).tolist())
        return puntajes
    return puntuar


def construir_mxbai2(id_hf, torch, max_tokens):
    from mxbai_rerank import MxbaiRerankV2

    modelo = MxbaiRerankV2(id_hf)

    def puntuar(pregunta, pasajes):
        resultados = modelo.rank(pregunta, pasajes, return_documents=False, top_k=len(pasajes))
        por_indice = {r.index: r.score for r in resultados}
        return [por_indice[i] for i in range(len(pasajes))]
    return puntuar


def construir_laya(id_hf, torch, max_tokens):
    """Laya (modelo de decisión tipada, no generativo): P(sí) de «¿el pasaje responde la pregunta?»."""
    import laya

    agente = laya.load(id_hf)
    preguntas = {"responde": {"type": "choice",
                              "instructions": "Does `passage` contain the answer to `question`?",
                              "criteria": {"A": "yes, the passage answers the question",
                                           "B": "no, the passage does not answer the question"}}}

    def puntuar(pregunta, pasajes):
        puntajes = []
        for p in pasajes:
            r = agente.predict({"question": pregunta, "passage": p}, preguntas)
            probs = r["answers"]["responde"].get("probabilities") or {}
            puntajes.append(float(probs.get("A", 0.0)))
        return puntajes
    return puntuar


FAMILIAS = {"laya": construir_laya, "cross": construir_cross, "qwen3": construir_qwen3, "lb": construir_lb, "mxbai2": construir_mxbai2}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("candidatos", help="JSONL de ranking_pasajes.py --volcar-candidatos")
    p.add_argument("--modelo", action="append", required=True, help="familia:id (repetible)")
    p.add_argument("--candidatos-n", type=int, default=20, help="pasajes del orden híbrido que se puntúan")
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--particion", choices=["dev", "test"])
    p.add_argument("--limite", type=int, help="solo las primeras N preguntas (pruebas rápidas)")
    p.add_argument("--hilos", type=int, default=4)
    p.add_argument("--salida", help="JSON con las métricas de cada modelo")
    args = p.parse_args(argv)
    import torch

    torch.set_num_threads(args.hilos)
    filas = cargar_candidatos(args.candidatos, args.particion, args.limite)
    informe = {"preguntas": len(filas), "candidatos_n": args.candidatos_n, "modelos": {}}
    informe["orden_hibrido"] = resumir(
        {f["id"]: rango_de(list(range(len(f["pasajes"][:args.candidatos_n]), 0, -1)),
                           [q["correcto"] for q in f["pasajes"][:args.candidatos_n]]) for f in filas if f["pasajes"]}, [])
    for especificacion in args.modelo:
        familia, id_hf = especificacion.split(":", 1)
        inicio = time.perf_counter()
        puntuar = FAMILIAS[familia](id_hf, torch, args.max_tokens)
        carga = time.perf_counter() - inicio
        rangos, tiempos = evaluar(filas, puntuar, args.candidatos_n)
        resumen = resumir(rangos, tiempos)
        resumen["carga_s"] = round(carga, 1)
        informe["modelos"][especificacion] = resumen
        print(f"{especificacion:60} todo={resumen['todo']['hit@1']:.3f} formal={resumen['formal']['hit@1']:.3f} "
              f"informal={resumen['informal']['hit@1']:.3f} hit@3={resumen['todo']['hit@3']:.3f} "
              f"s/pregunta={resumen['s_por_pregunta_p50']}", flush=True)
    if args.salida:
        Path(args.salida).write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
