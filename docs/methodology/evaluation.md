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
| Natural queries | `tests/datos/banco_consultas/{es,en,pt}` | 54 cases (18 per language): short, natural questions ("cuando empieza la compra?", "when does buying begin") on an administrative manual, with the universal documents of the language as distractors and same-topic traps; see [ADR 0005](../decisions/0005-deterministic-query-understanding.md) |
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
  correct only when its text and evidence contain the case's literal
  answer);
- risk of the accepted answers `x/n` with its Clopper-Pearson bound;
- Recall@k and MRR over the evidence, offset accuracy;
- p50/p95 latency, total and per stage.

A false `ok` takes priority over recall: retrieving more evidence does not
make up for asserting something the corpus does not support. `ipsis evaluate`
exits with ≠ 0 if it finds any.

`ipsis benchmark --bank … --profiles bm25,light,medium,heavy` creates a
temporary project per profile and bank, evaluates with a warm engine and
writes `benchmark-profiles.{json,md}` plus one artifact per profile for
`ipsis compare`. It exits with ≠ 0 if a profile exceeds its budget or, with
an evaluation bank, gives false `ok` answers. `--latency-only` measures
p50/p95 per stage.

`ipsis compare` requires the same bank hash, version and `k`.

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

## 13. References and provenance

Export format compatible with SQuAD 2.0 (`ipsis golden export --format
squad2`).

## 14. Status

Stable.
