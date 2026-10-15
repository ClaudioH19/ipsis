# ADR 0009: structural preparation is the default for new projects

Status: accepted (2026-10-15).

## Context

The top-1 source was often not first even when the right one was among the first
five. The plan in `docs/plan/precision-ingesta*.md` measured why. With the fixed-size
chunker `CH-F256` (256 words or more, crossing sections, no header) the hybrid order
already had the right source in the first five in 100 % of the synthetic passage
bank, but the cross-encoder, which reads only the first ~256 tokens of
question plus passage, pushed it down in `medium` (hit@1 0.736 against 0.792 in the
hybrid order). Details and tables: `docs/plan/precision-ingesta-avance.md`.

## Decision

- `ipsis init` writes `retrieval.preparation.mode: structural_v1` in the new
  `config/engine.yaml` (small children with title and section, expanded to the whole
  source unit for ranking and citation). It now covers DOCX, PDF, Markdown, text and
  spreadsheets.
- The schema default stays `legacy`. A project whose `engine.yaml` has no
  `preparation` block keeps fixed-size chunks and its existing index; nothing is
  migrated or reindexed behind the user's back. Switching is opt-in: add the block
  (or run `ipsis prepare`) and run `ipsis index`. The structural index lives in its
  own collection (`<name>_estructura1`).
- `CH-F256S`, `header_detail: extended` and the corpus fingerprint change (the
  embedded text now counts when the header is on) ship as opt-in options.

## Evidence

Hit@1 of the final order, `dev` / `test` partitions, one change against the same base:

| Corpus | Profile | Legacy (`CH-F256`) | Structural |
|---|---|---|---|
| Synthetic passage bank, test | light | 0.864 | 1.000 |
| Synthetic passage bank, test | medium | 0.727 | 0.977 (p95 2.4 s -> 1.1 s) |
| Real institutional documents (3 DOCX), dev | medium | 0.550 | 0.800 |
| Real institutional documents (3 DOCX), test | medium | 0.692 | 0.846 |

The real documents are small (33 questions) and are not in the repository. Alternatives
measured and discarded as the default: `CH-SEC` with a 512-token reranker (0.955 in
the synthetic test partition, slower, no gain on real documents), `CH-PAR`
(worse in `medium`) and the header alone (+1 case in `medium`).

## Consequences

- New projects index with the structural preparation: a different collection name and
  directory, and `ipsis index` required after changing the setting on an existing project.
- Migrating an existing project does not change its answers until it opts in.
- Calibrations stay valid for projects that do not change their header.
- Known residuals: Markdown tables stay as paragraphs; PDF has no page numbers or
  tables; a few real-document questions still rank 3 to 4 (small sample).
