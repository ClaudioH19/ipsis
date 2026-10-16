# The `cascade_v1` policy

Status: stable, engine v1 only. The default engine (v2) does not run the answer policy.

## 1. Purpose

Decide the status of every answer (`ok`, `related` or `no_answer`) with all
the cascade's signals, so that an `ok` is always literal text that answers
the question, and abstain when it is not.

## 2. Scope and non-scope

- **Scope:** apply the rules in order and leave the deciding rule and every
  signal in the diagnostics.
- **Non-scope:** retrieving, reading or writing. The policy knows nothing of
  Qdrant or the models.

## 3. Versioned inputs and outputs

- **Input:** `SenalesPolitica` (`s_ret`, `s_oov`, `s_foco`, `s_cov`, `s_rr`,
  `s_qa`; `None` when the stage did not run) and the effective thresholds.
- **Output:** `DecisionAbstencion` (result, reason, rule and the domain
  signal used). The rule travels in the diagnostics
  (`ipsis ask --diagnostics`) and in the query log.

## 4. Algorithm and tie-breaking

Before the policy, right after retrieval, a question that does not say what
it is about ends as **`necesita_aclaracion`** (needs clarification; HTTP
`no_answer` with `plan: clarification`): no content word left, a single
content word with an anaphoric pronoun, or a question of up to three words
whose single content word is in two or more documents or in none
(`ipsis/lenguaje/aclaracion.py`; see
[informal paraphrases](informal-paraphrases.md)).

Rules in order; the first that holds decides (`regla_cascada`, a pure
function). Rule names are the internal ones shown in the diagnostics:

1. **`premisa` (premise):** the question asks for a closed entity (date,
   amount, article) that is neither in the candidates nor in the corpus →
   `no_answer`.
2. **`fuera_dominio` (out of domain):** `s_oov ≥ τ_oov_domain` and
   domain < `τ_domain` → `no_answer`. Domain = `max(s_ret, s_rr)` (see
   [reranker](reranker.md)).
3. **`ok_lector` / `ok_lexico`:** `s_foco ≥ τ_focus` and
   `s_oov < τ_oov_ok` and (see "Answerability" below):
   - with a reader: `s_qa ≥ τ_ok`;
   - without a reader (light): `s_ret ≥ τ_ok` and `s_cov ≥ τ_cov`.

   With a reader there is a second, optional tier (`lector_seguro`):
   `s_foco ≥ τ_focus`, `s_qa ≥ τ_ok_strong` and `s_oov < τ_oov_ok_strong`.
   Informal questions bring words the corpus lacks ("quien **anota** las
   muestras", "cuanta **plata** da la beca") and push `s_oov` just past 0.6
   while the answering sentence has every focus term; a nearly sure reader
   tolerates a little more. Without both thresholds the tier does not exist.

   **Colloquial questions** (`foco_exigido`): a question written colloquially
   (`ipsis.lenguaje.estilo`: it starts in lowercase, in Spanish without «¿», or
   carries an informal abbreviation of the pack) with the reader at
   `τ_ok_strong` needs `s_foco ≥ τ_focus_informal` (0.5 in medium) instead of
   `τ_focus`, in both `ok` rules. The detector looks only at the form, never
   at the vocabulary or the documents. Re-deciding the stored signals showed
   that on colloquial questions the full focus blocked mostly correct answers
   (21 correct for 3 wrong when switched off), while on formal ones it blocks
   about one error per correct answer; requiring the nearly sure reader keeps
   colloquial traps out. Without `focus_informal` the full focus applies.
4. **`relacionado` (related):** domain ≥ `τ_related`. If the focus failed,
   the message names the missing term ("I couldn't find specific information
   about «warranty»…").
5. **`sin_respuesta` (no answer)** in any other case.

With the optional **agreement** (`profile_overrides.cascade.agreement_check`,
off in every profile), an `ok` drops to `related` if two reliable spans
contradict each other.

**The decision rules over the reader.** In `related` there is no
`exact_answer` and the passages go under a "not a direct answer" heading. In
`ok`, the answering sentence goes first.

After the policy, verification checks that every piece of evidence is
`corpus[start:end]` and that the entities of the answer are in the source.

**After a `no_answer`.** With the proactive posture, a `premisa` or
`sin_respuesta` decision may carry alternatives: lines of the family of a
missing declared entity or with nearly all the question words, literal and
verified. They never change the
decision, the state or the evidence
([ADR 0008](../decisions/0008-proactive-posture-and-metadata-similarity.md)).

## 5. Assumptions

The signals are in [0, 1] and comparable across queries of the same profile
(that is why `s_ret` is normalized from the dense model's floor).

## 6. Invariants

- Production and [calibration](calibration.md) use the **same**
  `regla_cascada`: they cannot diverge.
- An `ok` always carries literal, verified evidence.
- Re-deciding the stored signals with the profile thresholds reproduces
  every status (a non-regression test over 180 cases of the universal bank).

## 7. Parameters and defaults

The profile's default thresholds (conservative, uncalibrated):

| Threshold | light | medium |
|---|---|---|
| `oov_domain`, `oov_ok` | 0.6 | 0.6 |
| `domain`, `related` | 0.33 | 0.33 |
| `focus` | 1.0 | 1.0 |
| `ok` | 0.5 (on `s_ret`) | 0.8 (on `s_qa`) |
| `cov` | 0.6 | 0.6 (not used with a reader) |
| `ok_strong`, `oov_ok_strong` | — | 0.99, 0.67 |
| `focus_informal` | — | 0.5 (colloquial question with the reader at `ok_strong`) |

Order of application: profile ← `engine.yaml::profile_overrides` ←
`calibration.yaml` (only when its provenance matches).

**Answerability (`focus` = 1.0).** An `ok` needs the answering sentence to
contain every focus term. Focus terms are chosen only among words that exist
in the corpus, and never among the relation's words ("when… start") or the
pack's generic words (support verbs and units: "do", "have", "days"). So a
missing focus term means the corpus uses that word, but not in this
sentence: "Who approves the payment… in Finance?" answered with "Purchasing
sends the record to Finance for the payment" ("approves" is in another
sentence), or "How many days does the supplier have to deliver?" answered
with "…two working days to accept the order". With `0.5` (the previous
default) one of the two focus terms could be missing. Measured in
[ADR 0005](../decisions/0005-deterministic-query-understanding.md): both
false `ok` of the query bank become `related` and no correct answer is lost
in either bank.

## 8. Complexity and resources

Constant; under 1 ms.

## 9. Failures and fallback

A missing threshold prevents building the engine, with a message naming the
thresholds. Without a current calibration the profile's are used and
`ipsis doctor` warns about it.

## 10. Security and privacy

It uses no data beyond the query.

## 11. Technical tests

`tests/consulta/test_cascada.py`, the synthetic bank v1.1.0 (27 cases, 56%
unanswerable) and the universal bank (90 cases in es, en and pt).

## 12. Limitations

Universal bank benchmark (regression, it **does not certify**; uncalibrated
defaults; local CPU):

| Profile | Direct coverage | False ok | p95 | Budget |
|---|---|---|---|---|
| light | 22/45 | 1/45 | 85 ms | 150 ms |
| medium | 32/45 | 3/45 | 815 ms | 1,000 ms |
| former heavy (removed) | 31/45 | 2/45 | 2,130 ms | 4,000 ms |

Out-of-domain and false-premise questions are rejected 100% of the time in
every profile. "Same topic, missing fact" traps are the residual risk; a
calibrated `τ_ok` controls them.

## 13. References and provenance

Our own design; it replaces the previous layered policy and the per-question
regex guards (see [ADR 0004](../decisions/0004-lexical-cascade-and-removal-of-regex-guards.md)).

## 14. Status

Stable; thresholds pending calibration per project. Applies to the v1 engine only: v2 does not run
the answer policy.
