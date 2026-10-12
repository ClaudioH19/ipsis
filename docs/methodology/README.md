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
3. [Reranker](reranker.md): cross-encoder in medium.
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

[Full-answer evaluation v2](evaluacion-v2/README.md) separates published-answer
coverage from QA span completeness, compares light, medium and the former
heavy on the same Spanish bank, and includes raw artifacts and deployment configuration
instructions. Historical measurements retain their original criteria.

[Heavy model candidate review](modelos-heavy-2026-10-08/README.md) records
current multilingual CPU/ONNX options, integration contracts and an ablation
matrix, followed by local measurements of the supported candidates. No
candidate beat medium, and the heavy profile was removed (ADR 0003).

[Informal paraphrases](informal-paraphrases.md) measures colloquial, misspelled
and abbreviated questions in es/en/pt with a held-out informal bank, and
records the fixes kept and the relaxations rejected.

[General document regression](../../herramientas/evaluacion/README.md) exercises
four topics and formats at three formatting qualities, with frozen evidence,
per-case content guards, model variants and automatic CI execution. The six
2026 candidates now have working CPU/ONNX adapters; the research note retains
its original proposal and links to the subsequent local measurements.

The notes use the internal names of the code (signals such as `s_foco`,
rules such as `ok_lector`), because they describe the implementation.

[Motor v2 layer map and proposal](motor-v2.md) documents the current request
path and a CPU-only, non-generative comparison design with fewer semantic
heuristics. The experimental engine is implemented; v1 remains the default.

[Structured document preparation](preparacion-estructural.md) describes the
experimental DOCX representation, parent/child retrieval, isolated indexes,
preview command and supported structures. It does not imply better answer quality.

[V2 quality diagnosis](motor-v2-diagnostico.md) traces losses in retrieval,
reranking and QA with controlled budgets, oracle passages, table representations
and an alternate reranker. It separates literal citations from answer correctness.

[V2 mapped reading changes](motor-v2-mejoras-lectura.md) records field/value
contexts, independent budgets and QA highlights that cannot override ranking.
It reports real-case improvements, the rejected search representation and
remaining ranking failures.

[V2 ranked sources](fuentes-v2.md) describes the query router, independent
publication budget, literal neighboring context and expandable source cards.
It uses at most one reranker and disables QA by default.

[Retired reranking council](consejo-v2.md) preserves the CPU measurements
that led to removing the ensemble and its runtime/configuration support.
