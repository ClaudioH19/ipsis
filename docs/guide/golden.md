# Your golden set

The golden set is the bank of real questions you use to measure and
calibrate the assistant. It lives in the `golden/` folder of each project and
is never mixed with the synthetic bank of the tests (`tests/datos/banco/`).

The versioned bank lives in `golden/bank/` (`manifest.json` plus the cases in
JSONL). It is built from a simple CSV that a person fills in. With 30 to 60
questions reviewed by someone who knows the documents, it is good for tuning
and comparing profiles (certifying a risk takes more: see "Calibrate"). It
should cover the six internal categories (exact, paraphrase, no answer,
false premise, ambiguous, conversational) and split `dev` and `test` cases
before calibrating.

## Step by step

```bash
ipsis golden template                # golden/golden.csv with questions suggested from your documents
# fill in the CSV with Excel, LibreOffice or a text editor
ipsis golden import golden/golden.csv
ipsis golden validate                # does it still match the corpus?
ipsis evaluate                       # coverage, false "ok" answers and latency of the profile
ipsis calibrate                      # see "Calibrate"
```

1. **Template.** `ipsis golden template [--n N]` picks diverse sections of
   your documents (TF-IDF and MMR, no models) and writes rows with
   `instructions`, `suggested_passage` and `key_terms` to help you. About
   35% are traps: questions on the **same topic** whose answer is not there.
   It never overwrites an existing `golden.csv` without `--force`. A
   `README.txt` in the project language sits next to the CSV.
2. **Fill in.** Columns:

   | Column | Content |
   |---|---|
   | `question` | The way a real user would write it |
   | `type` | `answerable`, `no_answer`, `false_premise`, `ambiguous` or `conversational` |
   | `literal_answer` | Only for answerable rows: the minimal answer, copied exactly from the document |
   | `document` | The document where it is (name or id) |
   | `subtype`, `pair` | `same_topic_trap` and the `id` of the answerable row on the same topic |
   | `id`, `notes` | Optional |

   The helper columns are ignored on import. CSV files written before ipsis
   0.9 with Spanish column names (`pregunta`, `tipo`, `respuesta_literal`…)
   and types (`respondible`, `sin_respuesta`…) still import.
3. **Import.** `ipsis golden import` accepts the CSV (comma or semicolon,
   with or without BOM), a `.jsonl` or a SQuAD 2.0 file. It locates each
   literal answer in the document and stores its offsets, and classifies
   answerable rows as exact or paraphrase. If there are errors, it lists all
   of them with their row and writes nothing. It warns when there are fewer
   than 30 rows or fewer than 30% without an answer.
4. **Export.** `ipsis golden export --format squad2|csv` to use it in other
   tools.

## Curation rules

- `dev` can be used to tune thresholds; `test` stays closed until the final
  comparison.
- The dev/test split happens on import. It is 50/50 within each stratum:
  - the internal category (exact, paraphrase, no answer…);
  - plus the subtype (same-topic trap).

  This way, with small banks, the exact questions do not all end up on one
  side. It is deterministic: importing the same file again gives the same
  split.
- Every answerable question includes a literal answer and evidence with
  offsets.
- The questions used to find or fix a defect should not be the only
  measurement of that behavior.
- Sensitive institutional documents are never copied into the repository;
  the manifest identifies and hashes the corpus evaluated locally.

## Reading evaluation results and comparing profiles

```bash
ipsis evaluate --output reports/evaluation.json
ipsis benchmark --bank golden/bank/manifest.json --profiles light,medium --output reports/profiles
```

Every profile uses `respuesta_completa_v2`: the expected literal must appear
in the published answer and in evidence from the golden document and range.
A fact only present in an unused citation does not count; `related` does not
count as a correct direct answer.

- `directas_con_literal` and `cobertura_literal`: full-answer successes and
  their proportion over answerable questions.
- `riesgo_aceptadas`: false `ok` plus direct answers missing the expected fact,
  divided by direct answers. Abstentions are outside this denominator.
- `tramos_qa_evaluados`, `tramos_qa_sin_literal`, `exactitud_tramo_qa`: selected
  span quality against the golden literal. Without a reader, not applicable.
  Highlighting “two” instead of “two business days” fails this metric even
  when the full answer contains the expected information.
  A correct actor can also fail when the golden literal requires a longer clause;
  this failure alone does not mean the QA fact is false. Curate `literal_answer`
  as the minimal fact with its required units or conditions.
- `exactitud_offsets`: citation fidelity against source text.

`evaluate` exits 1 for false `ok` or direct answers missing the expected fact;
an insufficient highlight alone is reported separately. Literal matching does
not validate all semantics: review actions, conditions and added passages.

New reports use schema 2 and declare the criterion. Old reports remain readable,
but `compare` rejects mixed criteria: re-evaluate both configurations. Historical
measurements are retained, not silently reinterpreted.

## Calibrate

```text
ipsis calibrate [--alpha 0.05] [--apply]
```

It needs the index (`ipsis index`) and the imported golden set
(`ipsis golden import`). It runs the profile over the golden set and
**chooses scalar thresholds** (`ok`, `oov_ok`, `focus`) using `dev` only. It
looks for the combination that answers directly most often while the upper
bound of its risk (Clopper-Pearson at 95%) is ≤ `--alpha`; `test` only
verifies. It never trains or modifies models. Among combinations with the
same coverage it prefers:

1. the one with fewer errors;
2. the one closest to the profile thresholds;
3. only then, the strictest.

If `dev` cannot tell two values of a threshold apart, that threshold does
not move.

| Result | Meaning | Exit |
|---|---|---|
| `CALIBRATED` | There is enough sample and a combination meets α | 0 |
| `INSUFFICIENT_SAMPLE` | α cannot be certified yet: there are not enough direct answers without errors in `dev` (with 0 errors, 59 for α = 0.05). It does **not** mean the profile is unsafe | 0 |
| `NO_SAFE_THRESHOLD` | There is enough sample, but no combination meets α | 1 |

- Without `--apply` it only reports and writes nothing.
- Calibration version 2 measures full-answer risk with expected-source evidence;
  QA span quality is separate. Version 1 is retained but ignored; recalibrate.
- With `--apply` it writes `config/calibration.yaml` in any state, for
  auditing. The engine uses its thresholds **only** when the status is
  `calibrated` and its provenance matches the project: profile, models and
  the index's `corpus_hash`. If the corpus or the profile changes, the
  calibration is ignored and the profile thresholds return.
- If the corpus changed since the golden set was imported, run
  `ipsis golden validate` first and, if needed, import again.
- The universal bank of the tests (`tests/datos/banco_universal/`) is a
  regression bank and cannot be used to calibrate.
