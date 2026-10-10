# Calibration with risk control

## 1. Purpose

Choose the thresholds of the [policy](policy.md) for a specific project so
that, with 95% confidence, the rate of wrong `ok` answers is ≤ α (5% by
default), while maximizing direct coverage.

## 2. Scope and non-scope

- **Scope:** select scalar thresholds among observed values of signals
  already computed over the golden set.
- **Non-scope:** training, learning weights, changing models or touching
  indexes. The product does no fine-tuning of any kind.

## 3. Versioned inputs and outputs

- **Input:** the `golden/bank/` bank (cases with a dev/test `split` and
  literal evidence) and the observations of an evaluation of the active
  profile, with their signals.
- **Output:** `config/calibration.yaml` (version 2) with the status,
  `alpha`, `confidence`, thresholds, result per split and **provenance**
  (profile, models, the index's `corpus_hash`, effective `lexical_hash`, bank
  and its hash). The lexical hash covers runtime behavior version, effective
  language rules, project synonym groups, the active filtered table and
  its full WordNet sense-count lexicon.

Version 2 measures risk on the published full answer with expected-source
evidence (`respuesta_completa_v2`), equally across profiles. QA span quality
is separate. Version 1 calibrations are preserved but ignored; recalibrate
under the new criterion. This is literal golden matching, not semantic entailment.

## 4. Algorithm and tie-breaking

1. Evaluate the profile over the golden set and keep each case's signals.
2. Reject the universal bank (`uso: regresion`): it is for regression, not
   for calibrating a project.
3. **Only `dev` chooses.** Candidates: the values observed in `dev` plus the
   profile's (`τ_ok` on `s_qa`, or `s_ret` without a reader; `τ_focus` on
   `s_foco`; `τ_oov_ok` on `s_oov` + ε).
4. Joint search over (`τ_focus`, `τ_oov_ok`) × `τ_ok`: for each pair, sort
   the cases and sweep `τ_ok` accumulating `n` (accepted) and `x` (false ok
   plus direct answers without the literal answer). A combination is safe
   if the Clopper-Pearson upper bound of `x/n` is ≤ α.
5. Among the safe ones, the highest direct coverage wins; on ties, the one
   closest to the profile, then the strictest.
6. Re-decide without models with `regla_cascada`, the same function used in
   production.
7. `τ_oov_domain`, `τ_domain`, `τ_related` and `τ_cov` keep the profile's
   value: they do not change the risk of an accepted answer. `τ_ok_strong`
   and `τ_oov_ok_strong` also keep it, but their answers do count: a case
   the strong reader tier accepts enters the sweep at every `τ_ok`.
   `τ_focus_informal` keeps the profile's value too; the style of each
   question travels in the stored signals (`coloquial`), so the sweep applies
   the same `foco_exigido` as production.
8. Verify the combination on `dev` with the full policy and report it on
   `test` separately (`cumple` = meets, `excede` = exceeds or
   `muestra_insuficiente` = insufficient sample). **`test` never chooses.**

**Sample size.** With 0 errors, the 95% bound is `1 − 0.05^(1/n)`:

| accepted n | 20 | 30 | 40 | 58 | **59** | 100 |
|---|---|---|---|---|---|---|
| bound | 13.9% | 9.5% | 7.2% | 5.03% | **4.95%** | 2.95% |

Certifying α = 5% needs **at least 59 accepted answers without errors** in
the split where it is measured (more if there are errors). Three possible
results:

| Status | Meaning | Exit of `ipsis calibrate` |
|---|---|---|
| `CALIBRATED` | There is enough sample and a combination meets α | 0; with `--apply` the engine uses it |
| `INSUFFICIENT_SAMPLE` | The results may be good, but n is not enough | 0; keeps the profile thresholds and reports how many accepted answers are missing |
| `NO_SAFE_THRESHOLD` | There is enough sample and no combination meets α | 1; keeps the profile's |

## 5. Assumptions

The golden set represents the real questions: ≥ 30% without an answer or
with a false premise, and minimal "same topic, missing fact" pairs curated
by a person.

## 6. Invariants

- The engine applies the calibration only when its status is `calibrated`
  and its version is 2,
  **and** its provenance matches the profile, the models and the
  `corpus_hash` of the open index and effective lexical rules. A missing
  lexical hash in an old calibration also invalidates it. If something changed, it ignores it and
  `ipsis doctor` says so.
- `calibration.yaml` is written in any status, for auditing.
- `test` is reported independently but currently does not block application
  when it fails or has insufficient samples. Reading/cascade overrides are
  not fully covered by provenance: set aside calibration and re-evaluate after
  changing them. A dev-selected bound does not by itself guarantee production risk.

## 7. Parameters and defaults

`ipsis calibrate [--alpha 0.05] [--apply]`; confidence 0.95. Calibratable
thresholds: `ok`, `oov_ok` and `focus`.

## 8. Complexity and resources

One evaluation of the golden set with models plus an in-memory search
(polynomial in the observed values; seconds).

## 9. Failures and fallback

No index: "ipsis index". Corpus changed since the golden set was imported:
"ipsis golden validate". In the statuses that do not certify, the profile
keeps its thresholds: the product works, without claiming the 5%.

## 10. Security and privacy

The golden set and the report stay in the project; nothing leaves the
machine.

## 11. Technical tests

`tests/evaluacion/test_calibracion.py` (the three statuses, ties,
provenance) and the CLI tests of `ipsis calibrate` with a fake engine.

## 12. Limitations

- With small banks, the stratified 50/50 split may leave internal categories
  unbalanced.
- The guarantee is statistical over the golden set's distribution: questions
  very different from the golden set's are not covered.

## 13. References and provenance

- Clopper and Pearson, *The use of confidence or fiducial limits illustrated
  in the case of the binomial* (1934).
- Angelopoulos et al., *Learn then Test: Calibrating Predictive Algorithms to
  Achieve Risk Control* (2021).

## 14. Status

Stable. No project is calibrated by default.
