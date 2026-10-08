# Methodology notes

Every technique of the library is documented in a note before it is
considered stable. The note goes with the code and is updated whenever its
algorithm changes.

## Required template

1. Purpose.
2. Scope and non-scope.
3. Versioned inputs and outputs.
4. Algorithm and tie-breaking.
5. Assumptions.
6. Invariants.
7. Parameters and defaults.
8. Complexity and resources.
9. Failures and fallback.
10. Security and privacy.
11. Technical tests.
12. Limitations.
13. References and provenance.
14. Status: experimental, stable, deprecated or pending calibration.

Values not yet checked against a golden set are marked as
`pending calibration`; never as a precision guarantee.

## Notes, in the order of a question

1. [Hybrid retrieval](retrieval.md): e5 + BM25 in Qdrant with RRF.
2. [Lexical layer](lexical.md): `terminos()`, BM25, TF-IDF and the signals
   `s_oov`, focus, `s_foco`, `s_cov` and `s_lex`.
3. [Reranker](reranker.md): cross-encoder in medium and heavy.
4. [QA reader](reader.md): a literal span or "no answer", the `s_qa` signal.
5. [`cascade_v1` policy](policy.md): `ok`, `related` or `no_answer`.
   With the proactive posture, a `no_answer` may carry
   [alternatives](../decisions/0008-proactive-posture-and-metadata-similarity.md)
   ([measurements](mediciones/v5-alternativas/README.md)).
6. [Calibration](calibration.md): thresholds with risk ≤ α
   (Clopper-Pearson).
7. [Multilingual](multilingual.md): language packs and tones.
8. [Evaluation bank](evaluation.md): format, categories and splits.

[V4 evaluation results](v4-results.md) compare memory, local synonyms and
intent fallback against F1 with the corrected selected-span metric, including
raw evidence and observed limitations.

[V4 correction measurements](mediciones/v4-correcciones/README.md) track
the follow-up reader, topic compaction and intent compatibility changes
against that initial snapshot and F1.

The notes use the internal names of the code (signals such as `s_foco`,
rules such as `ok_lector`), because they describe the implementation.
