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

| | correct answers | false `ok` |
|---|---|---|
| `light`, before → after | 5 → 9 | 1 → 1 (the same, pre-existing) |
| `medium`, before → after | 7 → 11 | 1 → 1 (the same, pre-existing) |

Universal bank (light and medium, es/en/pt): no new false `ok` and nothing
lost; one more exact answer in `light`/en; latency within noise.

## Follow-up questions

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

## Not done yet

From the proposal that motivated this: multi-query retrieval expansion
(retrieval was not where these cases failed), parent/neighbor expansion and
an explicit answerability signal in the policy. Each one should come with a
failing case and a measurement, like these.
