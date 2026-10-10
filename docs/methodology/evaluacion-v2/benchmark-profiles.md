# Benchmark by profile

- Bank `consultas_es@1.0.0` (es, use regresion, 60 cases)

> Regression bank: it compares profiles on the same cases. Its risk bounds certify no client; 'ipsis calibrate' does that with the client's golden set.

## Quality, safety and latency

| Profile | Direct coverage | Exact | Paraphrase | False ok | Traps with false ok | Accepted risk x/n | p50 ms | p95 ms | p95 budget | Meets |
|---|---|---|---|---|---|---|---|---|---|---|
| light | 16/34 (47.1%) | 10/14 | 6/20 | 1/26 | 1/16 | 3/17 | 45.5 | 69.0 | 150 | yes |
| medium | 25/34 (73.5%) | 13/14 | 12/20 | 0/26 | 0/16 | 0/25 | 2825.0 | 3099.6 | 1000 | NO |
| heavy | 21/34 (61.8%) | 12/14 | 9/20 | 2/26 | 0/16 | 2/23 | 15473.5 | 17081.8 | 4000 | NO |

## Full answers and QA spans (separate metrics)

| Profile | Full answers with expected literal / direct | Answerable coverage | QA with complete literal / evaluated | QA missing literal |
|---|---|---|---|---|
| light | 14/17 | 41.2% | — | — |
| medium | 25/25 | 73.5% | 8/25 | 17 |
| heavy | 21/23 | 61.8% | 6/21 | 15 |

## Correct rejection

| Profile | Out of domain | False premise | Ambiguous with false ok | Related (answerable) | Direct without literal |
|---|---|---|---|---|---|
| light | 100.0% | 100.0% | 0/3 | 52.9% | 2 |
| medium | 100.0% | 100.0% | 0/3 | 26.5% | 0 |
| heavy | 100.0% | 100.0% | 2/3 | 38.2% | 0 |

## False ok per profile (hard negatives)

- **light**: `es-trampa-004` «¿Qué pasa si la unidad requirente rechaza los productos recibidos?»
- **medium**: none
- **heavy**: `es-ambigua-002` «¿Quién lo aprueba?»; `es-ambigua-003` «¿Cuánto es?»

## Cost

| Profile | Models (parameters · ONNX on disk) | retrieve_n / rerank_k / read_m | Indexing (s) | Extra |
|---|---|---|---|---|
| light | denso: multilingual-e5-small (118 M · 470 MB) | 10 / 0 / 0 | 6.3 | — |
| medium | denso: multilingual-e5-small (118 M · 470 MB)<br>reranker: mmarco-mMiniLMv2-L12-H384-v1 (118 M · 119 MB)<br>lector: mdeberta-v3-base-squad2-onnx (278 M · 1114 MB) | 20 / 4 / 2 | 5.0 | — |
| heavy | denso: multilingual-e5-base (278 M · 1110 MB)<br>reranker: bge-reranker-v2-m3-ONNX (568 M · 571 MB)<br>lector: mdeberta-v3-base-squad2-onnx (278 M · 1114 MB) | 30 / 8 / 4 | 11.5 | — |

The ONNX size is that of the file on disk, not the memory used (RSS is not measured).

## Latency per stage (p95 ms)

| Profile | conversacional | analisis | confianza | filtros | recuperacion | evidencia | politica | redaccion | verificacion | reranking | lectura |
|---|---|---|---|---|---|---|---|---|---|---|---|
| light | 0.0 | 3.0 | 1.5 | 0.0 | 21.1 | 25.0 | 3.0 | 0.0 | 10.0 | — | — |
| medium | 0.0 | 3.0 | 1.5 | 0.0 | 44.1 | 35.1 | 6.0 | 0.0 | 11.0 | 2378.7 | 738.1 |
| heavy | 0.0 | 4.0 | 3.5 | 1.0 | 47.0 | 49.0 | 4.1 | 0.0 | 10.6 | 14971.4 | 2213.5 |
