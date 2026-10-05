# ADR 0001: non-generative answers

- Status: accepted
- Date: 2026-09-21

## Context

The library must answer questions about your own documents with
traceability and without depending on generation services.

## Decision

Every factual statement is a literal span of a document. Encoders,
classifiers, rerankers and extractive readers are allowed because they
score or select evidence; they never produce new prose. The only additional
texts are configured and tested templates.

## Consequences

- Answers can be audited through document, section and offsets.
- The system must abstain or ask for clarification more often.
- Free summaries and open synthesis are out of scope.
- Interaction improves with statuses (`ok`, `related`, `no_answer`) and with
  tones: fixed templates, checked by a linter, that never assert facts (see
  [personality.md](../guide/personality.md)).
