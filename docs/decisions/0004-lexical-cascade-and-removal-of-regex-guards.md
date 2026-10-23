# ADR 0004: cascade with lexical signals and removal of the regex guards

> **Superseded by [ADR 0012](0012-retire-the-v1-engine.md).** The cascade this record describes lived in the v1 engine, retired in October 2026. The record stays as history.

## Context

The previous policy (`layered_v1`) decided in layers with a similarity
threshold and, to avoid wrong answers, added **regex guards per question
type** ("how much?" requires a number, "when?" a date…). They had three
problems:

- **Tied to Spanish:** word lists and expressions in the code.
- **Fragile:** a rephrased question slipped past them.
- **Blind to "looks related but does not answer":** for "How long is the
  warranty?", the filter passage ("it is changed every 6 months") has a
  number, a similar topic and a high score.

A curated list of "general words" also dragged leftovers from a previous
domain.

## Decision

- **A cascade of stages** (`consulta/etapas/`): conversational → analysis
  → confidence → filters → retrieval → reranking → reading → evidence →
  policy → rendering → verification. Each profile lists its own; the cheap
  ones go first.
- **Explainable lexical signals** (`ipsis/lenguaje/lexico.py`), computed
  with a single `terminos()` (the language's Snowball stem) and the corpus
  IDF:
  - `s_oov`: IDF mass of the question that is absent from the corpus;
  - focus terms: the 2 with the highest IDF that exist in the corpus;
  - `s_foco`: fraction of focus present in the answer sentence;
  - `s_cov`: IDF coverage.

  `s_foco = 0` solves the warranty/filter case without per-language rules.
- **Early exit:** if no candidate contains a focus term, the reranker and
  the reader do not run.
- **`cascade_v1`:** rules in order (premise, out of domain, ok, related,
  no answer) in a pure function, `regla_cascada`, shared by production and
  calibration.
- **Removed:** the regex guards, the "general words", the Latin `[a-z0-9]+`
  tokenization and the BM25 with its own vocabulary. BM25 moves to hashed ids
  with the IDF applied in Qdrant.
- Everything that depends on the language moves to packs
  (`ipsis/recursos/idiomas/`).

## Consequences

- The same logic works in Spanish, English and Portuguese; other languages
  use universal rules.
- Every decision leaves its rule and its signals in the diagnostics and in
  the log: it is auditable and reproducible.
- **Known limit:** a synonym absent from the document ("cartridge" for
  "filter") lowers `s_foco` and the system abstains more than needed. It is
  the safe side of the error, and `τ_foco` is calibrated with the paraphrase
  category.
- False `ok` answers on the synthetic bank v1.1.0: 0 in light and in medium.
  On the universal bank, "same topic" traps with a high `s_qa` remain in
  medium and heavy; a per-client calibrated `τ_ok` controls them.

## Status

Accepted and implemented (`cascade_v1` is the default; projects with
`layered_v1` migrate by themselves).
