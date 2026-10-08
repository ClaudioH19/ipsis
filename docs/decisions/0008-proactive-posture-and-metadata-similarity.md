# ADR 0008: proactive posture and similarity from metadata

- Status: accepted and implemented.
- Date: 2026-10-08.

## Context

When the assistant finds no direct answer, it says so and stops. A
salesperson or a warehouse manager who cannot find the product asked for
offers the closest one: "we don't have the X-500, but we have the X-400 and
the X-600". A consultation assistant could do the same with documents.

That question ended in the `premisa` rule (the entity is not in the
candidates) or in `sin_respuesta`, and the reply was an abstention message.
The retriever had usually already found the neighboring passages, and the
index keeps metadata for every chunk, but neither was used to offer
anything.

Two alternatives were rejected:

- **A "proactive" tone.** Offering alternatives changes what is shown, not
  how it is said. The tone packs are presentation only
  (`tests/evaluacion/test_tono_no_cambia_estados.py`).
- **Roles** (consultation, sales, inventory) bundling a tone, a posture,
  per-role weights and per-role wording. Every part is covered without
  them: one weighting measured on a bank; the domain's wording comes from
  `domain_description` and `tone.templates`; the tone sets the register.

## Decision

### 1. Proactive posture

When the abstention comes from `premisa` or `sin_respuesta`, the assistant
attaches up to `posture.max_alternatives` (3 by default, 1 to 5)
alternatives, after the abstention message and under a fixed sentence of
the tone (`alternatives_intro`) that says they are similar, not what was
asked.

- `posture.mode: proactive` is the default in `assistant.yaml`; `strict`
  keeps the previous behavior (`ipsis configure posture.mode=strict`).
  `personality.yaml` stays presentation only. No reindexing.
- An alternative is a **line of a retrieved chunk** (the parser leaves a
  paragraph per line; section titles are skipped; a line longer than
  `max_fragment_chars` is split into sentences), with document offsets and
  the route of its own section for the citation. It passes the same literal
  verifier as the evidence of an answer.
- The state stays `sin_respuesta`. Alternatives travel in their own field
  (`alternativas` in the engine contract, `alternatives` in `/ask`, same
  fields as `fragments`); `fragments` and `evidencias` stay empty. The
  cascade, the golden, calibration and every bank cannot move.
- `fuera_dominio`, `sin_fragmentos`, `guardia`, related answers and
  conversational turns never carry alternatives. Alternatives never feed the
  conversation memory ([ADR 0006](0006-conversation-memory.md)): they skip
  the verification stage, which is the only one that records vocabulary.

### 2. Similarity from metadata

Candidates are the chunks the cascade already retrieved plus, for each
missing entity of a type the project declares, the chunks with the
nearest values of its **family**: same form with the digits masked
(`codigo_tp-#`), nearest number first, at most four, through the entity
inventory that premise verification already uses. Each candidate line gets
six signals, all from data the index already keeps, no new model:

| Signal | Value |
|---|---|
| `familia` | 1 if the line has a family value of a missing declared entity |
| `terminos` | fraction of the question's content words in the line, over all of them (also the ones missing from the corpus); the words of the question's entities do not count |
| `seccion`, `keywords` | the same fraction over the document title and the line's section, or over the chunk keywords |
| `categoria` | 1 if the chunk category equals the question's category in a taxonomy with at least two categories of the project |
| `similitud` | dense cosine with the question from the model floor; computed only if it weighs (or when recording for calibration) |

A line is eligible if `familia` or `terminos` is positive. Affinity is the
weighted mean of the signals; a line is offered if it reaches the
threshold. When some eligible line has the family, only family lines are
offered. Weights and threshold live in the installation profile
(`alternatives.threshold`, `alternatives.weights`), overridable in
`profile_overrides`.

**Shipped values:** `familia` 1, every other signal 0, threshold 0.5. In
practice: alternatives are the family of a missing declared entity.

**Only declared types have a family.** A core measure ("90 días", "20 %",
an amount) appears in unrelated documents. Requiring a shared question word
as well was measured and failed (below).

## Measurement

### Alternatives bank

`tests/datos/banco_alternativas/{es,en,pt}`: a hardware catalog and a
stock document per language, with product codes declared in `dominio.yaml`
(`regex_extractors`) and four categories in the taxonomy, plus the query
bank's documents as distractors. 58 cases per language in `casos.yaml`
(exact, missing code with family, missing product described, absent without
neighbor, document premises with a neighbor, document topics without one,
out of domain), split dev/test, and 16 per language in `validacion.yaml`
(written before the rule was frozen). `medir.py` records every eligible
line with its signals; `--calibrar` and `--resumir` re-decide offline with
the engine's rule.

Calibration chooses one weight set (each weight in {0, 1, 2}) and a
threshold per profile: valid thresholds keep precision ≥ 0.9 and no
out-of-domain case with alternatives; the coverage floor is 90 % of the best
reachable; the widest contiguous range of valid thresholds wins and the
threshold is its center. Maximizing coverage alone left every combination
on a 0.05-wide edge, and those thresholds let through cases that
development did not show.

### Rounds (light and medium × es/en/pt; full data in [measurements](../methodology/mediciones/v5-alternativas/README.md))

| Round | Change | Result |
|---|---|---|
| 1 | first signals; coverage-first calibration on dev | test precision 0.86 (light): "work gloves" counted as full coverage, stopwords made Portuguese questions match a category |
| 2 | fractions over all question words; category with the ingestion's term filter; family lines first | dev 1.0 but one out-of-domain test case with alternatives ("¿A qué distancia está la Luna?" → "trabajo a distancia") |
| 3 | core measures need a shared word; entity words excluded; calibration on dev + test with the widest margin | only `familia` survives; development precision 0.99, coverage 39/44 |
| validation (once) | round 3 frozen, `validacion.yaml` | precision **0.87** light, **0.85** medium: below 0.9. Codes 24/24 correct; "N días" premises offered unrelated requests |
| 4 | family only for declared types | development and validation (no longer untouched) precision **1.0**, coverage 30/44 and 12/18 |

Final rule, light and medium alike:

| | Development (dev + test) | Validation |
|---|---|---|
| alternatives offered | 74 / 71 | 27 / 27 |
| precision | 1.0 / 1.0 | 1.0 / 1.0 |
| out-of-domain cases with alternatives | 0 | 0 |
| missing items with a neighbor that ended in `no_answer` and got one | 30 of 44 | 12 of 18 |

Every missing product code with a family got its neighbors. The uncovered
cases are premises on core measures ("¿Puedo teletrabajar cuatro días por
semana?"), which now get no alternatives.

### Existing banks

Same commit measured before and after, light and medium × es/en/pt: the
query bank (360 cases), the universal bank (180) and the conversations
bank (348 turns) keep **every state and rule**; correct and wrong counts are
identical.

### Latency

Warm engine, light, 118 Spanish questions × 3 rounds, proactive and strict
alternated per question: mean 57.1 vs 56.1 ms, p95 89.9 vs 89.0 ms (budget
150). On the 10 questions that get alternatives, mean 83.9 vs 70.3 ms (the
family retrieval: one filtered search per neighbor). Medium: 2,793 vs
2,791 ms, no measurable difference. HTTP load (light, 8 clients, 240
requests per posture): 9.4 vs 9.7 requests/s, p95 1,043 vs 1,049 ms, no
errors. The first load run exposed a thread-safety bug in the stemmer, older
than this change, now fixed (see the measurements).

## Consequences

- The default changes: a false premise on a declared code now shows its
  neighbors. `posture.mode: strict` restores the previous replies.
- A project gets alternatives only if it declares its codes in
  `domain.yaml`. Without declared entities, the proactive posture behaves
  as strict. The documentation says so.
- `alternatives_none` was not added: when nothing qualifies, the existing
  `no_answer` and `premise_not_found` messages already say so.
- `tipo_contenido` was not used: the bank has no tables to measure it.
- The other signals stay computed and recorded for future calibration with
  other corpora; their weight is 0 because, alone or combined, they did not
  hold 0.9 with a margin.
- The bank is small and synthetic (one catalog per language). The test split
  was examined during development; only the first validation run is a
  held-out measurement, and it failed the bar before round 4.
