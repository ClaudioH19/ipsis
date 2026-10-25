# ADR 0013: a key line in each ranked source (experimental, off by default)

Status: implemented, **off by default** (2026-10-25).

## Context

The right source is usually among the first three but often not the first (hit@1 0.83, hit@3 0.91 on the real-document
bank; [lab log OBS-0014](../../laboratorio_reranker/bitacora.md)). More reranking time does not fix it: giving the
reranker unlimited time left hit@1 at 53/64 and only moved cases around. If the card showed the line that is closest to
the question, a correct source in second or third place would read as a hit instead of a mistake (ADR 0010).

## Decision

- With `v2.presentation.key_line: true`, each of the first three published sources may carry `key_line`
  (`offset_start`, `offset_end`, `margin`, `method: dense`): the line of that source's own text whose dense similarity
  to the question beats the second-best line by at least `key_line_margin` (default 0.01). The text is always a literal
  span of the published source; nothing is generated and the sources, their order and their text do not change
  (ADR 0001).
- The line is chosen with the retriever's own encoder (`multilingual-e5-small` in `medium`). Line vectors are cached,
  so a repeated source costs milliseconds. The step runs after publishing and only if time is left for the lines not
  yet cached; otherwise the source gets no line and the diagnostics say so.
- The widget shows the line in a callout ("Closest to your question") and marks its table row. It says "closest", not
  "answer".

## Evidence

Real-document bank, 64 questions, 83 of the 192 top-three sources contain the answer on some line. Chance would pick it
29 % of the time:

| Selector | Right line | Cost per question |
|---|---|---|
| First line | 24 % | 0 |
| Lexical overlap (IDF) | 58 % | 0 |
| Dense (e5-small) | 71 % | 0.8 s cold, ~0 cached |
| Extractive reader (mdeberta) | 85 % | 5.7 s |

End to end with the dense selector and the 2.5 s budget: latency does not change (p50 1.97 s against 1.99 s, p95
2.35 s against 2.47 s). With the default margin it marks 45 % of the sources that contain the answer, **70 % of those
marks are the right line**, and it also marks a line in 39 % of the sources that do not contain the answer. Raising the
margin trades coverage for precision without reaching a usable point: 0.03 marks 19 % at 81 %; 0.05 marks 7 % at 100 %.
With a cold cache the reranker uses the whole budget and the step is skipped in 14 of 64 questions.

## Why it stays off

A wrong line inside the right card looks worse than no line. 70 % is not enough, and the reader, which reaches 94 % at
61 % coverage with a confidence threshold, costs more than the 3 s the product allows. The code is kept because the
contract (`key_line`), the widget and the tests are what a better selector needs.

## Next

- Encode each chunk's lines once at indexing time, so the cost leaves the query and the cache starts warm.
- Combine selectors: the dense and the reader agree on 70 % of the cases with 93 % precision (offline); a cheap reader
  restricted to the top candidate line may be affordable.
- Measure with questions from real people before enabling it ([plan P5](../plan/README.md)).

The widget budget moved from 40 to 41 KB gzip with this change; it had 50 bytes of headroom.
