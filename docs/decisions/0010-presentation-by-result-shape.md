# ADR 0010: presentation follows the shape of the results

Status: accepted (2026-10-16).

## Context

The right source is often among the three shown but not the first one. Showing it as a second card
reads like an assistant mistake. Making the engine answer "this one" would need a confidence that the
retrieval scores do not provide (ADR 0001: nothing shown is generated, and nothing claims to be the
answer). The plan is in `docs/plan/presentacion*.md`.

## Decision

- The engine **describes the page**, it does not change it. `MotorV2` computes the shape of the first
  page from what is already published (`ipsis/consulta/v2/forma.py`) and the API returns it as
  `result_shape`: `variants` (the first two sources are variants of the same thing: same document and
  sibling sections, or different scopes), `documents` (they come from different documents) or `neutral`.
  Which sources are shown, their order, windows and scores do not change.
- The widget picks messages and layout from the shape: "It depends on your case" and a "Choose your case"
  row of shortcuts for `variants`; "Found in several documents" and a mark at each document change for
  `documents`; the usual message for `neutral`. Two correction paths exist only with the shape: opening
  a source that is not the first says where it is from (`opened_source`), and a "This isn't it" button
  asks for the next page (`results_retry`) and compacts the earlier cards. Everything is interface text
  or literal fields the API already publishes.
- **On by default.** The schema default is `v2.presentation.enabled: true` (and `ipsis init` writes it in the new
  `config/engine.yaml` so it is visible). There is **no migration** (`config_version` stays 8): an existing v2 project
  receives it when it loads, with nothing to add. Turning it off is `v2: presentation: enabled: false`.
- **`clear` is not used.** A "clear answer" page (first source far ahead of the second) would be the only
  shape that hints "this is it". It stays off: `clear_margin` is unset and the widget has no `clear`
  layout.

## Evidence

Measured on three real institutional documents (56 questions, `docs/plan/presentacion-avance.md`,
"P0.2"). The margin between the first two scores separates correct first sources only in `medium`
(reranker logit): a margin of about 3.6 gave 21 of 21 correct on the first source, but the Wilson 95 %
lower bound does not reach 0.98 with so few cases, and the questions were written by the same assistant
that builds the system. In `light` (retrieval score, relative to the query) no margin reached 0.98.
Among `variants` pages the first source was right in 83 % (dev) and 62.5 % (test) of the cases, which is
where "It depends on your case" helps most. About 40 % of `medium` pages would stay `neutral`.

## Limits

- `variants` and `documents` say how the page looks, not which source answers.
- To enable `clear` later: measure `clear_margin` by profile with questions from real people (plan P5)
  and add the layout; nothing else changes.
- The shape is computed on the first page only; "Keep searching" pages never carry it.
