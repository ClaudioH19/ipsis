# ADR 0005: deterministic query understanding (intentions and cues)

## Context

"when does the purchase start?" ("cuando empieza la compra?") failed on an
administrative manual whose answer is "Once the Requirement Form is approved,
the purchase will be made" ("Una vez aprobado el Formulario de Requerimiento…
se realizará la compra"). The new diagnostics (`ipsis ask --diagnostics`
now shows each candidate's place in the dense, BM25, fusion and reranker
rankings, and the best scored sentences) located the failure:

- retrieval was fine: the right chunk was a candidate;
- "empieza" (start) is not in the corpus, so it counted as an absent term
  (`s_oov`) and lowered coverage;
- every sentence shared only "compra", so the selection anchored on a later
  step ("…starts a new purchase with another supplier") and the QA reader,
  which reads around the anchor, found nothing;
- in `medium`, the reranker put a passage about opening hours above the
  right chunk, so the reader never read it.

The question asks for a **relation** (the start) of a **topic** (the
purchase), and the system treated both the same.

## Decision

Each language pack declares `intenciones` (`ipsis/recursos/idiomas/*.yaml`):
general relations (`umbral`, `inicio`, `fin`, `consecuencia`, `responsable`,
`requisito`, `procedimiento`), each with **patterns** that recognize it in
the question and **cues** that usually appear in the sentence that answers
("once", "after", "until"…). `ipsis/lenguaje/consultas.py` uses them in
three places, and only there:

1. **A relation word absent from the corpus is not missing topic:** it
   leaves the focus terms, `s_oov` and `s_cov` ("start" when the answer says
   "Once…"). One that is in the corpus stays and helps coverage (Portuguese
   "até" in "Até quando…?" and in its answer). A relation word is never a
   focus term ("amount" in "from what amount…?": the answer has "100 UTM").
   Only the words written in the patterns count as relation; the topic
   inside a pattern's gap stays.
2. **Selection and reader window:** among sentences that already share
   topic with the question, one with a cue weighs more (×2 when the cue is
   in its first words, ×1.5 further in).
3. **Reading by cue:** if the best sentence with a cue is in a candidate the
   reranker left out of the reading (below `leer_m` or outside `rerank_k`),
   the reader also reads it (one extra passage, only when an intention was
   recognized).

`QueryAnalysis.intencion` carries the intention; the original question is
always the one retrieved and answered.

### Why this is not the regex guards that ADR 0004 removed

The guards **decided**: "how much?" without a number was rejected. These
rules only **steer where to look** and never accept or reject an answer:
the QA reader and `cascade_v1` still decide, with the same thresholds. They
live in the language packs (es, en, pt, with parity), not in the code.

## Measurements

Query bank (`tests/datos/banco_consultas`, the manual plus the universal
documents as distractors, 11 answerable cases and 6 traps):

| | direct answers (`ok`) | false `ok` |
|---|---|---|
| `light`, before → after | 5 → 9 | 1 → 1 (the same, pre-existing) |
| `medium`, before → after | 7 → 11 | 1 → 1 (the same, pre-existing) |

Correction: these counts are direct answers, not correct ones. Checking that
the answer shows the case's literal answer, `light` had 6 correct after this
step: three of its direct answers showed another sentence ("¿Desde cuándo se
hace la compra?" answered with "Para hacer un reclamo…"). See
"Answerability" below.

Universal bank (light and medium, es/en/pt): no new false `ok` and nothing
lost; one more exact answer in `light`/en; latency within noise.

## Follow-up questions

> Partly superseded by [ADR 0006](0006-conversation-memory.md): the memory now
> keeps the whole conversation as topics, with expiry; the rules below
> describe the first version (one turn per session).

"and with 90?" after "what happens above 100 UTM?" carries almost no topic.
`ipsis/consulta/seguimiento.py` remembers, per session and in memory, the
last effective question and the words of the passage that answered it. A
question is a follow-up when it brings no topic term present in the corpus
(and is short), or brings one or two that all appear in that passage and is
short or starts with a follow-up marker of the language (`seguimiento` in
the pack: "y", "and", "e se"…). Then the previous topic words are added to
it ("¿y si la acepta? proveedor rechaza orden"): the *interpreted question*
is what is retrieved and selected.

Three guards keep it safe:

- a question with its own topic outside the previous passage ("What are the
  library hours?" after the warranty) never inherits;
- when the user brought topic of their own, the lexical signals (focus,
  `s_oov`, `s_cov`) are measured on it, so "and if they accept it?" is not
  answered with the sentence about rejecting;
- in the selection, the user's own words weigh fully and the interpreted
  question half: inside a passage the user's words rule, and between similar
  passages of different documents the context decides.

## Synonyms

"¿Desde qué monto se **necesita** una Resolución?" when the manual says
"…**requieren** una Resolución": "necesita" is not in the corpus, so it
counted as a missing term and lowered the coverage. Each pack declares
`sinonimos`: groups of words with their common forms (the stemmer does not
take "requieren" to the stem of "requerir"). A question word is replaced by
the forms of its group that are in the corpus, only when:

- the word itself is not in the corpus (a word that is never changes);
- it is a content word, not part of the recognised relation ("empieza" in
  "¿cuándo empieza la compra?" is left to the cues: "inicia" would bring
  sentences of another topic).

The forms are appended to the searched query and replace the word in the
lexical signals and the selection; the diagnostic shows them
(`sinonimos`). The result is memoized per question, pack and corpus
statistics: without it, light latency doubled.

Measured: the target case goes from "related" to a direct answer in
`medium` (in `light` the retrieval signal stays under its calibrated
threshold, which this does not touch); no other case of the query bank or
the universal bank changes, and there are no new false `ok`.

## Answerability

The two false `ok` of the query bank had the same shape: one of the two
focus terms was missing from the answering sentence ("aprueba" in "¿Quién
aprueba el pago… en Finanzas?", "entregar" in "¿Cuántos días tiene el
proveedor para entregar…?"), and `τ_focus = 0.5` allowed it. Focus terms are
chosen among words that exist in the corpus, so a missing one is used
elsewhere, not in this sentence: same topic, another question.

Decision: `τ_focus = 1.0` in every profile (the answering sentence contains
every focus term), with the pack's `genericas` (support verbs and units)
left out of the focus and the selection. Without them, requiring every
focus term cost "¿Desde cuándo se **hace** la compra?" and "¿…una tercera vez
en los **meses** de calor?". They still count for `s_oov` and `s_cov`.

Measured (correct = direct and showing the literal answer):

| | correct | direct but wrong (false `ok` or another sentence) |
|---|---|---|
| query bank `light` | 6 → 6 | 4 → 2 |
| query bank `medium` | 11 → 11 | 1 → 0 |
| universal bank, light and medium × es/en/pt | unchanged | unchanged |

Latency within noise. `τ_focus` is still calibrated per project with the
golden set.

Not solved: in `light`, "cuando parte la compra?" and "¿Quién firma la
Resolución de compra?" are direct answers with another sentence of the same
topic (every focus term is in it). The universal bank keeps its pre-existing
false `ok` ("¿Cuántas muestras se rechazan cada mes?": both focus terms are
in the sentence that answers another question).

## Other languages

The query bank now has the same 18 cases in English and Portuguese, written
as each language would ask them, with that language's universal documents as
distractors. Measuring them showed three gaps that Spanish hid:

- **Derived nouns.** "Who signs the purchase Resolution?" is answered by
  "…for **signature**", and the English stemmer keeps "signatur" apart from
  "sign" (the same with "assinatura" / "assina"). Spanish's "firma" is both
  verb and noun. Each pack now declares `sufijos_derivados`, used only to
  check the focus terms.
- **Synonyms in another sense.** "Above what amount do you **need** a
  Resolution?": "need" is in the corpus ("the justification of the need"),
  so it is not expanded, and the answer says "require". The pack's synonym
  groups now also count when checking the focus terms.
- **The relation's verb in another sentence.** "…the Purchasing Officer
  **starts** a new purchase with another supplier" contains "start"; since
  "start" is in the corpus it counted as content and that sentence beat
  "Once the Requisition Form has been approved…". The relation's words no
  longer score in the selection (the cues represent the relation), and in
  the coverage they add when the sentence has them but do not subtract.

Correct answers (direct and showing the literal answer) / direct but wrong,
before the layer (`6b25921`) and now:

| | es | en | pt |
|---|---|---|---|
| `light`, before → now | 3 / 3 → 7 / 2 | 1 / 1 → 3 / 0 | 3 / 2 → 8 / 2 |
| `medium`, before → now | 7 / 1 → 11 / 0 | 6 / 0 → 8 / 0 | 7 / 0 → 10 / 0 |

The universal bank (light and medium × es/en/pt) does not change; latency
within noise. Follow-up questions are covered by unit tests in the three
languages.

Still wrong in `light`: "cuando parte la compra?", "¿Quién firma la
Resolución de compra?" and "Quem assina a Resolução de compra?" (another
sentence on the same topic, with every focus term), and "Quando se começa a
comprar?", whose answering chunk does not reach `light`'s three candidates.

## Similarity fallback (plan V4, F3)

Patterns remain authoritative. For an unknown intention, a question with a
nongeneric corpus topic can compare its existing dense query vector with
ten natural examples per intention and language, encoded once at startup
using query prefixes on both sides. Each intention scores with its maximum
example cosine; the margin is against the second **intention**, not another
example of the winning intention.

Both thresholds must be exceeded. Settings are keyed by dense model in the
language pack. No encoder, BM25, or no measured setting means no fallback;
E5 base remains inactive until separately measured. Diagnostics record
pattern/similarity origin, candidate, cosine, margin, nearest example and
acceptance, including rejected attempts.

The inferred intention supplies only cues for selection and the reader
window, including the extra candidate by cue. It cannot locate relation
words: all query terms remain in focus, coverage and OOV checks. No text is
generated, no answer threshold changes and no model weights are trained.

Dev selects thresholds on a fixed grid with zero incorrect fallback
intentions: maximize correct coverage, then minimize margin and cosine.
Only categories actually accepted correctly on dev are enabled; the margin
still compares all seven categories. Other categories keep their patterns.
Test never enters threshold search. Iterations and their test errors are
retained; this small bank is a regression check, not an untouched statistical
certification set. Prepared queries use runtime manual synonym expansion;
automatic WordNet expansion remains BM25-only.

| Language | E5-small minimum cosine | Minimum margin (strict) | Enabled fallback |
|---|---|---|---|
| es | 0.850 | > 0.000 | end, procedure |
| en | 0.870 | > 0.000 | end |
| pt | 0.895 | > 0.000 | procedure |

Intent examples, enabled categories and thresholds participate in lexical
calibration provenance. Rebuild the motor and regenerate stale calibrations
after changing them.

Follow-up intent recognition uses the current user's question, not its
inherited topic words. Compatibility forms (`respaldo_patrones`) add a
necessary condition for the measured end/procedure fallback: a similar
amount or actor question cannot become a deadline or a procedure solely
because its topic resembles an example. These forms do not recognize an
intent independently and remove no words. Thresholds remain unchanged;
the [correction measurements](../methodology/mediciones/v4-correcciones/README.md)
repeat dev/test and the response banks after this change.

The [V4 evaluation](../methodology/v4-results.md) records actual fallback
activation: eight additional correctly labelled intentions per profile in
the natural-query bank, without a change in answer correctness or wrong
answers. Recognition coverage is small and does not establish a general
answer-quality improvement.

## Remaining proposal

From the proposal that motivated this: parent/neighbor expansion. It should
come with a failing case and a measurement, like these.
