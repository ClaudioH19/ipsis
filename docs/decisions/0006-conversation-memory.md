# ADR 0006: conversation memory (topics, expiry and per-page sessions)

> **Not active in v2 ([ADR 0012](0012-retire-the-v1-engine.md)).** The memory (`consulta/seguimiento.py`) was wired only into the v1 engine. The module and its tests are kept as the base of the "Conversation in v2" plan in [docs/plan](../plan/README.md); the measurements below are v1's.

## Context

[ADR 0005](0005-deterministic-query-understanding.md) added follow-up
questions: "¿y con 90?" inherited the topic of the previous turn. The memory
kept one turn per session and dropped the least used session past 1,024.
That was too little:

- a follow-up after an unrelated turn lost the topic: "¿Quién firma la
  Resolución?" → "¿Cuál es la capital de Mongolia?" → "¿y quién la redacta?";
- a return to an earlier topic was impossible ("volviendo al viático, ¿y en
  el extranjero?" two turns later);
- a conversation never expired, and the widget kept the `session_id` in
  `localStorage` without keeping the visible chat: after a reload the person
  saw an empty chat while the server still remembered the old topic.

The conversations bank (`tests/datos/banco_conversaciones`, 20
conversations per language) measured it: the follow-ups were never
inherited where they should not be, but 9 to 17 per language (of 38) were
lost.

## Decision

`ipsis/consulta/seguimiento.py` keeps each conversation as a sequence of
**topics**, without any generative model:

- **core:** the most specific terms (highest IDF, at most 3) of the question
  that opened the topic; inherited while the topic lasts;
- **last follow-up:** the user's own terms of the previous turn; inherited
  once and then folded (the compaction: what was said several turns ago is
  not dragged along, the core is);
- **vocabulary:** that of the last three source passages containing the
  first displayed citation of a verified direct or related reply. Source
  context supplies neighboring steps; the short display window alone loses
  valid follow-ups. Candidates of other topics are excluded.

The opening turn's terms outside the core remain available for the first
follow-up, then are compacted like any other turn. IDF selects the core;
inheritance preserves the original word order. Dropping the remaining terms
immediately or emitting them in descending IDF order lost two Portuguese
answers despite otherwise correct inheritance.

The interpreted question is retrieval context. Patterns and semantic intent
compatibility use the current follow-up. The reader uses it when it expresses
a recognized relation or multiple content terms; a bare qualifier ("and in
summer?") keeps the interpreted question to retain what it modifies. For actor
questions, the reader window isolates the sentence on the current action:
the previous turn asking who signs must not override who now drafts. See
the [correction measurements](../methodology/mediciones/v4-correcciones/README.md).

A question is a follow-up of the current topic when its topic terms (those
in the corpus, minus the pack's generic words) are:

- none, and it starts with a follow-up marker or has a single content word;
- with a marker at the start ("y", "and", "e"), up to three, at most one
  outside the topic's vocabulary;
- without a marker, one or two, all in the vocabulary, in a short question.

Otherwise, a question with topic terms **returns** to an earlier topic (up to
4 kept) when all its terms are in that topic's vocabulary, or **opens a new
topic** and inherits nothing: a deliberate change never drags the previous
one along, even if it starts with "and". A question without topic terms in
the corpus (out of domain) does not change the topic.

**Lifetime.** A conversation is forgotten after `conversation.expiry_minutes`
without questions (30 by default) and at most `conversation.max_sessions`
(1,024) are kept, in `engine.yaml`. The widget creates a new `session_id` on
every page load: leaving or reloading the page starts a new conversation,
as the person sees it; closing and reopening the panel keeps it. A page-exit
signal (`sendBeacon`) was discarded because it cannot carry the widget key.

**Diagnostics.** `ipsis ask --diagnostics` shows what the turn did with the
conversation (follows the topic, returns to an earlier one, new topic, no
change), the topic's core, the recognized intention and the synonyms used.

**Privacy.** The memory lives in the service process (each worker has its
own), keeps terms and the words of the questions that opened or followed a
topic, never answers, and is lost on restart.

Vocabulary is recorded after evidence and final fidelity verification,
never during candidate selection. A turn that leaves the topic unchanged
(for example, an out-of-domain question) does not replace its vocabulary.
Each resolution has a monotonically increasing turn token: late replies
cannot update a newer turn or a recreated session. Expiry applies at the
exact inactivity boundary. Compaction also removes old surface forms;
an empty passage cannot displace useful vocabulary.

Topic-only generic terms (`genericas_memoria` in a language pack) are
separate from the generic terms ignored by answer selection. `tiempo/tempo`
must not open or contaminate a conversation topic, but retain their original
weight for focus and the reader. Applying their topic treatment globally
lost a previously correct Spanish answer and failed G3; that iteration is
retained and the corrected behavior is remeasured.

## Measurements

Conversations bank, inherited correctly (of 38 per language), before → after
(light):

| | es | en | pt |
|---|---|---|---|
| inherited correctly | 26 → 36 | 25 → 35 | 21 → 34 |
| inherited where it should not | 0 → 0 | 0 → 0 | 0 → 0 |

The [V4 evaluation](../methodology/v4-results.md) records both profiles,
the three banks and the four correct literal conversational answers lost relative to F1.
Negative-turn and inheritance checks remain separate from positive literal
answer quality.

## Consequences

- The rules were tuned with the conversations bank; they are general
  (markers, how many topic terms and how many are in the topic), but the
  bank is small. A larger conversation set may move them.
- Navigating to another page of the same site starts a new conversation
  (decision D5 of plan V4).
- Without a marker, a short new question keeps its own topic ("¿Qué es el
  teletrabajo?" after talking about allowances): some elliptical follow-ups
  without "and" ("¿con cuánta anticipación lo pido?") are still lost.
