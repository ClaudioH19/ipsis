# ADR 0003: ONNX models on CPU and installation profiles

Update 2026-10-08: **the `heavy` profile is removed**; two installable
profiles remain, `light` and `medium`. The decision and table below are kept
as history. See [Removal of heavy](#update-removal-of-heavy-2026-10-08).

## Context

The assistant is installed on its user's server (a server without a GPU).
The previous version depended on torch and sentence-transformers: installs
of several GB and a single quality level. It had to be possible to trade
latency for quality without changing product, and every model had to be
pretrained, multilingual, with a compatible license and no fine-tuning.

## Decision

- **Our own runtime on onnxruntime and tokenizers.** No torch,
  sentence-transformers or fastembed in production. A shared base,
  `ModeloOnnx` (Template Method), loads the session and the tokenizer; each
  model implements its own part: `CodificadorDenso`, `RerankerOnnx` and
  `LectorOnnx`. torch only appears in the `[export]` development extra.
- **A global model cache** (`IPSIS_MODELS_DIR`) and offline use
  (`HF_HUB_OFFLINE=1`).
- **Three profiles** in `ipsis/recursos/perfiles/`, plus `bm25` for
  diagnostics only:

  | Profile | Models | p95 target | Measured p95 (universal bank) |
  |---|---|---|---|
  | light | e5-small | 150 ms | 85 ms |
  | medium | e5-small + mmarco (int8) + mdeberta (fp32) | 1 s | 815 ms |
  | heavy | e5-base + bge-reranker-v2-m3 (int8) + mdeberta (fp32), more passages and agreement | 4 s (max. 5) | 2,130 ms |

- **A profile means more computation and more checks**, not necessarily a
  different model at every stage. Heavy uses the same reader as medium,
  reading more passages: `deepset/xlm-roberta-large-squad2` has no reliable
  ONNX with a declared license, and a doubtful export is not introduced just
  to tell profiles apart.
- **Quantization by evidence:** the reranker uses the published int8; the
  reader runs in fp32 (the published int8 gives flat logits and the int16
  does not load); e5 runs in fp32 (its int8 needs AVX-512 VNNI).
- **Layered configuration:** profile ← `engine.yaml::profile_overrides` ←
  `calibration.yaml`, the latter only when its provenance matches.

## Consequences

- The production install weighs hundreds of MB plus the profile's models,
  and runs the same on Linux, Windows and macOS.
- Changing the dense model needs reindexing: the collection carries the
  model in its name and the manifest checks it.
- A new model only gets in if it is pretrained, multilingual, with a
  compatible license and ONNX for CPU, without fine-tuning, improves the
  benchmark significantly and respects the profile budget.
- On the universal bank, heavy buys no material safety over medium (2.6
  times the p95). It stays for large corpora and as an option.

## Status

Accepted and implemented; amended on 2026-10-08 by the removal of heavy.

## Update: removal of heavy (2026-10-08)

Under the full-answer criterion (v2), the original heavy (e5-base + BGE,
cascade 30/8/4, agreement) got 21/34 correct answers on the Spanish query
bank with two accepted errors and a p95 of 17 s, against medium's 25/34,
zero errors and 3.1 s. Six newer candidates were then measured on top of
medium's cascade, changing one model at a time: Granite-311M R2,
Granite-97M R2, Harrier-270M and EmbeddingGemma 2 as retriever; Horizon
base/small as reranker. **All six got exactly the same 25 correct answers as
medium**; the Horizon rerankers added an accepted error and exceeded the 4 s
budget.

The reason is structural, not a weakness of the models. In all 240
comparisons the reranker score `s_rr` was identical to medium's: with
`retrieve_n=20` over a small corpus the hybrid search already brings the
right passage into the candidate set, so the dense model cannot change what
reaches the reranker and the reader. The nine questions medium misses are
lost downstream, the same nine for every variant: four have the correct
evidence but the focus/coverage gate rejects it (a paraphrase does not repeat
the question's words), and five are colloquial paraphrases where the
reranker ranks another passage of the same document higher. A larger
embedding also compresses the cosine scale (Granite: 0.73–0.94 for
out-of-corpus questions too), which breaks the domain threshold calibrated
for e5.

Decision: a profile has to buy measurable quality, and heavy bought none.
It is removed. A project whose `assistant.yaml` says `heavy` loads as
`medium` (and `ipsis profile show` asks to reindex if its index used another
dense model). The candidate models stay in the catalog and can be tried
through `profile_overrides`; the model variants of the general regression
(`herramientas/evaluacion/general.py --variants`) are built on medium. The
improvement effort moves to the focus gate and paraphrase handling, which
benefit both profiles. Evidence: [evaluation v2](../methodology/evaluacion-v2/README.md),
[candidate research](../methodology/modelos-heavy-2026-10-08/README.md).
