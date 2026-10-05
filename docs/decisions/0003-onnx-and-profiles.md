# ADR 0003: ONNX models on CPU and installation profiles

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

Accepted and implemented. Open: a larger reader for heavy, if a reliable
ONNX appears.
