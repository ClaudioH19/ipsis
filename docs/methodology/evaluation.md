# Evaluation banks and metrics

## 1. Purpose

Separate expected quality from current behavior. Characterization detects
changes; a normative bank says whether those changes are improvements or
regressions, and the client's golden set makes it possible to
[calibrate](calibration.md).

## 2. Scope and non-scope

- **Scope:** the versioned bank format, coverage and risk metrics,
  `ipsis evaluate`, `ipsis benchmark` and `ipsis compare`.
- **Non-scope:** choosing thresholds (`ipsis calibrate` does it) or changing
  defaults automatically.

## 3. Versioned inputs and outputs

Each bank is a manifest (`manifest.json` in the golden set,
`manifiesto.json` in the test banks; schema `1`: id, version, type, status,
`uso` (use), the corpus with its joint SHA-256 and the categories) and a JSONL
of cases. Each case declares `id`, `split`, `categoria` (category),
`pregunta` (question), `estado_esperado` (expected status), `respondible`
(answerable) and, if answerable, the `respuesta_literal` (literal answer) and
the evidence with `doc_id` and exact offsets. The bank schema keeps its
internal field names; the golden set's CSV uses English columns (see the
[guide](../guide/golden.md)).

| Bank | Where | Use |
|---|---|---|
| Synthetic `aqualis_sintetico@1.1.0` | `tests/datos/banco/` | 27 cases (56% unanswerable), regression and characterization |
| Universal | `tests/datos/banco_universal/{es,en,pt}` | 90 cases (30 per language), `uso: regresion`: it cannot be used to calibrate |
| Natural queries | `tests/datos/banco_consultas/{es,en,pt}` | 180 cases (60 per language: 14 exact, 20 paraphrase, 16 same-topic traps, 4 out of domain, 3 false premise, 3 ambiguous): short, colloquial questions ("cuando empieza la compra?", "olvidé la clave, cómo la cambio?") on four institutional documents (a procedures manual, a regulation with numbered articles, a help-desk FAQ and an allowance policy), with the universal documents of the language as distractors; see [ADR 0005](../decisions/0005-deterministic-query-understanding.md) |
| Conversations | `tests/datos/banco_conversaciones/{es,en,pt}` | 60 conversations (20 per language, 2 to 4 turns): per turn, whether it must inherit the topic, the literal answer or that it must not be a direct answer. Follow-ups over several turns, deliberate topic changes (also starting with "and"), an out-of-domain question in the middle, traps and false premises inside a follow-up, and a return to a topic two turns back. Measured with `tests/datos/banco_conversaciones/medir.py` |
| Client golden set | the project's `golden/bank/` | the only one that calibrates (see the [guide](../guide/golden.md)) |

## 4. Algorithm and tie-breaking

Categories: exact, paraphrase, no answer, false premise, ambiguous and
conversational. A no-answer or false-premise case may carry the subtype
"same topic trap" and its `pair` (the answerable case on the same topic): it
is the minimal pair that measures whether the system tells "looks similar"
from "answers". The expected status also distinguishes out of domain.

Metrics (`ipsis/evaluacion/metricas.py`), global, per group and per
language:

- direct and related coverage over the answerable cases;
- abstention recall over the unanswerable ones;
- **false `ok`:** an unanswerable case that ends in a direct answer;
- direct answers without the literal answer (a direct answer counts as
  correct under criterion `respuesta_completa_v2` when the published answer
  contains the expected literal and evidence from the expected document/range
  also contains it, identically for every profile);
- QA span completeness against the expected literal, measured separately on
  direct answerable cases with a QA span; no reader means not applicable;
  this is literal completeness, not semantic span accuracy, and a long golden
  clause can penalize an otherwise correct selected actor;
- risk of the accepted answers `x/n` with its Clopper-Pearson bound;
- Recall@k and MRR over the evidence, offset accuracy;
- p50/p95 latency, total and per stage.

**Sample size.** A per-language bank of 60 cases has about 34 answerable
ones: enough to detect regressions and compare changes, not to certify a
risk α = 0.05 per language (that needs ≥ 59 accepted answers with no error).
The three languages together reach that order of magnitude.

A false `ok` takes priority over recall: retrieving more evidence does not
make up for asserting something the corpus does not support. `ipsis evaluate`
exits with ≠ 0 if it finds any false `ok` or direct answer lacking the expected
literal. An insufficient QA span alone does not fail the full-answer guard.

`ipsis benchmark --bank … --profiles bm25,light,medium` creates a
temporary project per profile and bank, evaluates with a warm engine and
writes `benchmark-profiles.{json,md}` plus one artifact per profile for
`ipsis compare`. It exits with ≠ 0 if a profile exceeds its budget or, with
an evaluation bank, gives false `ok` or direct answers without the expected literal. `--latency-only` measures
p50/p95 per stage.

New artifacts use schema 2 and explicitly identify the answer criterion.
`ipsis compare` requires the same bank hash, version, `k` and answer criterion.
Legacy artifacts remain readable as `tramo_o_respuesta_v1`; their stored numbers
are not reinterpreted and cannot be mixed with v2. Re-evaluate both configurations.
The bank itself keeps schema 1. Literal matching does not prove all semantics
or remove irrelevant additional passages; curate relational and conditional cases.

## 5. Assumptions

The cases and their offsets were reviewed by a person. The synthetic and
universal banks are fictitious: they contain no data from any institution.

## 6. Invariants

- `test` never chooses thresholds.
- A bank with `uso: regresion` is not accepted for calibration.
- Each artifact stores the bank hash, the effective configuration and the
  index identity.

## 7. Parameters and defaults

A 50/50 split stratified by type, ordered by hash (deterministic).

## 8. Complexity and resources

Linear in the cases; the cost is that of the profile's queries.

## 9. Failures and fallback

The bank's corpus changed: the hash does not match and the command says so
(`ipsis golden validate` for the golden set).

## 10. Security and privacy

The client's golden set stays in their project; the repository distributes
no corpus, profiles or metrics of any specific institution.

## 11. Technical tests

`tests/evaluacion/` and the slow test of the universal bank, which fails if
a new false `ok` appears relative to its baseline.

## 12. Limitations

The included banks are small: they serve to detect defects and verify the
process, not to certify a profile or choose defaults on their own.

The [V4 evaluation](v4-results.md) remeasures F1 using the selected-span
metric before comparing final results. It reports memory inheritance and
negative-turn checks separately from positive literal answers; improved
inheritance does not compensate for a lost correct answer.

## 13. References and provenance

Export format compatible with SQuAD 2.0 (`ipsis golden export --format
squad2`).

## 14. Status

Stable.
