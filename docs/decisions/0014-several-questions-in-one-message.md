# ADR 0014: several questions in one message, searched separately and shown by question

Status: implemented, **on by default** (2026-11-02). A message with one question behaves exactly as before.

## Context

A message such as "how much does the P1 cost? and how long is the warranty?" was searched as one text: one dense vector
halfway between the two topics, one BM25 query that summed both vocabularies and one ranking. One topic tended to push
the other out of the three published sources, and when both had answers the page mixed them with no way to tell which
source belonged to which question.

## Decision

**Detect and split, deterministically** (`ipsis/lenguaje/subpreguntas.py`, no model, no generated text). Two signals,
from the safest to the least safe:

1. **Question marks.** Every piece that ends in `?` is a question. This is punctuation, so it works in any language
   without a language pack. Greetings, thanks and farewells ("hola", "gracias") are dropped (the pack's existing
   courtesy patterns); a piece with no topic term of its own ("¿ok?") is joined to its neighbour.
2. **A question that starts inside another**, with no mark of its own: "how much is the P1 **and how long** is the
   warranty?". It is cut only before an interrogative word of the language, preceded by a link word ("and", "además") or a
   comma, and only if **both halves** have at least two content terms. "How and when do I pay?" and "what is X and how is
   it used?" stay whole: one half would be left with no topic, and searching it alone would be worse than not splitting.

**No word lives in the code.** Interrogatives and link words are in the language packs (`varias_preguntas` in
`ipsis/recursos/idiomas/{es,en,pt}.yaml`), as are the courtesy patterns it reuses and every text of the interface. A
language without a pack splits on question marks only. Splitting a part again returns the same part, and a message with
one question is returned untouched, so none of the existing behavior or its tests changes.

**Search each question on its own path.** `MotorV2._recuperar_parte` (preparation, retrieval, context, reranking and
reading) is the former body of a query, now shared. Each question runs it separately, so each has its own vectors,
candidates, reranking and key line. The time budget is split in equal shares with absolute deadlines: time a question does
not use goes to the next one.

**Group the answer by question.** The API adds `question_groups` (each with its `question`, its `fragments`, its own
`has_more`/`continuation`, its `result_shape` and `media`), `question_index` on every fragment and `unsearched_questions`.
`fragments` still lists everything in group order, for a client that does not know about groups. Each group's page shows
`results_per_question` sources (2 by default; one question keeps 3).

**Continuation without new server logic.** Each question's ranking is stored under **its own text**, so a group's
cursor is the cursor of an ordinary question: the widget posts `{question: <the group's text>, continuation: <its
cursor>}` and gets an ordinary single-question page back. A cursor cannot be used for another question (the existing
check). Nothing about groups survives on the server after the first page.

**More than the limit.** `max_questions` (3 by default, at most 6) bounds the work. The rest is not dropped in silence: the
API returns them in `unsearched_questions` and the widget shows each as a button that searches it alone.

### Presentation

Presentation is the point of the feature, so it is decided here and not left to the client:

- One **section per question**: a numbered title (the question as the person wrote it, without its leading "and"),
  a count ("2 results") and the sources of that question, **numbered from 1 in the ranking order of that question**.
  Grouping changes where a source is shown, never which one or in what order (ADR 0001, ADR 0010).
- A **fixed index** at the top (one numbered button per question, the one being read marked with `aria-current`). A
  question with no sources looks muted and says so to screen readers. It scrolls only sideways, keeps the active button in
  view and moves the focus to the question's title when used.
- **Each group has its own "Show more results"**, its own skeleton while loading and its own empty state ("I found no
  sources for this question. Try rephrasing it."). One empty question never hides the others.
- **The same source may appear under two questions** when it is the best for both; the "already seen" set is per group.
- The assistant's voice says how many questions it found and how many results there are (`results_multi` in the voice
  bank, by language), and never says that a source answers: it describes the page (ADR 0001).
- A single question does not get a group, an index or a heading: its page is untouched.

## Cost in the widget

The widget budget moved from 41 to 44 KB gzip (it weighed 41.5 KB before and now weighs about 43.5 KB, with roughly 450
bytes of headroom): the sections, the index, the per-group "Show more" and their texts in the fallback dictionary. The
widget is served without minification, so the budget measures what is sent.

## Alternatives considered

- **Search the whole message once and cluster the results afterwards.** The vector still sits halfway between the topics,
  so the right sources may never be retrieved, and clustering would be a guess about which question each belongs to.
- **Split on any "and".** "Payment and refund" is one topic. The interrogative-plus-content rule is deliberately
  conservative: a missed split costs what the message cost before, a wrong split costs a broken query.
- **Inherit the topic of the first question for an elided second one** ("how much is the P1 and how long does it last?").
  It needs coreference, which is exactly what ADR 0006 and ADR 0012 left out of v2. Such a message is not split.
- **A model for splitting.** Rejected for the same reason as ADR 0001: it adds a component that can invent text.

## Consequences

- **Cost.** *n* questions cost about *n* single queries of retrieval and key line; reranking shares one budget
  (`query_budget_ms`), so each question is scored with less time than a lone question would have. Raise
  `query_budget_ms` if the reranker budget is exhausted often (`reranking_progresivo.presupuesto_agotado` per question in the
  diagnostics).
- **Diagnostics.** The engine's diagnostics, and so the query log, carry `preguntas`: one entry per question with its rule,
  stages, candidate count, pagination, progressive reranking and shape. `ipsis ask` prints the citations of each
  question under its own heading.
- **Elliptical questions.** "How much is the P1? And the P2?" is split by its two question marks, and the second question is
  searched with its own words ("the P2"), because inheriting the first one's topic needs coreference (see the alternatives).
  The group title shows exactly what was searched, so the person can see it and rephrase.
- **Misses.** A message with several questions and no question marks and no interrogative after a link word is searched as
  before. Anything the splitter does not recognize degrades to the old behavior, never to something worse.
- **Configuration** (`config/engine.yaml`): `v2.multi_question.enabled`, `max_questions`, `results_per_question`,
  `split_on_interrogatives` (turn off the cut by interrogative word and keep only question marks).
