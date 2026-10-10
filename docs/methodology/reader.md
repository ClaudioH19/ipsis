# Extractive QA reader

## 1. Purpose

Mark, within a passage, the literal span that answers the question, or say
the passage does not answer it (SQuAD 2.0 style). It provides the `s_qa`
signal.

## 2. Scope and non-scope

- **Scope:** read `read_m` candidates, choose the best span and compare it
  with the "no answer" option.
- **Non-scope:** writing; deciding the final status (the
  [policy](policy.md) rules over the reader).

## 3. Versioned inputs and outputs

Input: the question and the passages. Output: one `LecturaQA` per passage
with `indice_pasaje`, `inicio`, `fin` (character offsets),
`texto == pasaje[inicio:fin]`, `prob_respuesta` and `prob_sin_respuesta`.
The HTTP contract publishes `exact_answer` only when the status is `ok`.

## 4. Algorithm and tie-breaking

1. The passage is read in windows of `max_passage_tokens` tokens with a
   `stride` overlap (`only_second` truncation).
2. Per window, the 20 best start and end edges are considered (spans of up
   to 30 tokens) and the highest sum of logits wins.
3. It is compared with "no answer" (`[CLS]`): softmax over {best span, no
   answer}.
4. The window with the highest `prob_respuesta` wins; offsets are trimmed of
   whitespace.
5. `s_qa = max(0, prob_respuesta − prob_sin_respuesta)`; the policy uses the
   maximum across passages.

The reader receives a window of `max_reading_chars` around the anchor
sentence (centered, with context on both sides), not the whole passage: it
cut reading from ~1 s to ~0.5 s in medium. What is **shown** starts at the
anchor sentence and only adds context to the right.

For follow-ups expressing a recognized relation or multiple content terms,
the reader receives the current user's question. A bare qualifier ("and in
summer?") retains the interpreted question; the current question alone
does not say what the qualifier modifies. The interpreted question with
inherited topic terms also retrieves context.
Actor questions use the single sentence selected for the current action,
even when the passage fits within `max_reading_chars`. This keeps other
question/answer pairs in the same passage from selecting an unrelated role.

After selection, follow-up quantity spans can be completed with adjacent
units, bounds and a reference point. An actor span can be completed with
its immediately following matching action clause, stopping before a
different role/action. Language forms live in `bordes_respuesta`; the raw
span stays in `lecturas` and `tramo_completado`. Confidence and policy
thresholds are unchanged. These boundaries are literal offsets, never a
newly written answer or a replacement actor/number. The
[correction measurements](mediciones/v4-correcciones/README.md) compare
the published exact answer rather than crediting facts elsewhere in a citation.

## 5. Assumptions

The question and the corpus are in the same language; the model is
multilingual (it also reads an English question about a Spanish text, with
no guarantee).

## 6. Invariants

- The span is always a literal substring of the passage.
- In `related`, the span is never published as the answer.
- Completing a span preserves its selected actor or quantity and its source
  offsets; an incorrect actor is not repaired by widening to the entire citation.

## 7. Parameters and defaults

| Profile | `read_m` | `max_reading_chars` | Windows |
|---|---|---|---|
| medium | 2 | 600 | 384 tokens, stride 128 |

`semantic_reading` (on in medium) replaces the lexical window: the reader
reads the 3 sentences of the reranked candidates that an RRF of
cross-encoder, e5 cosine and `s_lex` ranks first, each with the previous
sentence of its line; headings are never read, nor the introduction of a
document with sections (the text under its top-level title only). Medium: 68 → 72 correct on
the query bank and 10 → 16 on the informal bank, one extra accepted error,
+0.8 s at p50 on a 2-thread CPU. Set it to `false` in `profile_overrides` to
go back to the lexical window; see [informal paraphrases](informal-paraphrases.md).

Model: [dewdev/mdeberta-v3-base-squad2-onnx](https://huggingface.co/dewdev/mdeberta-v3-base-squad2-onnx),
an export of `timpal0l/mdeberta-v3-base-squad2` (MIT, 278 M), in **fp32**:
the published int8 gives flat logits and the int16 does not load.

**Optional agreement (`profile_overrides.cascade.agreement_check`):** if the two best reliable spans from different
passages carry entities of the same type with different values, an `ok`
drops to `related` (the `concordancia` rule).
No profile enables it: more passages and agreement did not improve the
former heavy's full-answer results.

## 8. Complexity and resources

50–110 ms per passage; p95 of the stage on the universal bank: 513 ms
(medium) and 874 ms (former heavy, 4 passages). Disk: 1.1 GB.

## 9. Failures and fallback

- No model: the profile does not start and the action is
  `ipsis models download`.
- Lexical early exit: it does not run.

## 10. Security and privacy

Local inference.

## 11. Technical tests

`tests/modelos/` with the real ONNX (verified offsets: «6 meses»,
«24 meses»; the warranty question against the filter passage gives
`s_qa = 0`) and the stage with doubles in `tests/consulta/`.

## 12. Limitations

- The reader gives the same span to "When does the warranty expire?" and
  "What does the warranty cover?": telling the expected answer type apart
  would need per-language rules. `s_oov < τ_oov_ok` and `s_foco` cover it.
- Two traps of the universal bank (`es-trampa-001`, `en-trampa-004`) give
  `s_qa` 0.82–0.83 with `τ_ok` 0.8: false `ok` answers in medium
  without calibration. With `τ_ok` 0.85 they disappear without losing
  coverage; `ipsis calibrate` chooses each project's threshold.
- There is no larger reader: `deepset/xlm-roberta-large-squad2` has no
  reliable ONNX export yet.

## 13. References and provenance

- Rajpurkar et al., *Know What You Don't Know: Unanswerable Questions for
  SQuAD* (2018).
- He et al., *DeBERTaV3* (2021).

## 14. Status

Stable; `τ_ok` pending calibration per project.
