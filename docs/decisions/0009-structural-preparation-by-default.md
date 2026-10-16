# ADR 0009: structural preparation is the default

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
- **Existing projects migrate** (`config_version` 7 -> 8, run by any `ipsis` command): a
  v2 project whose `engine.yaml` has no `retrieval.preparation` block gets the structural
  block written to disk, and the command prints that `ipsis index` must be run. The old
  index is not touched: it lives in another collection, so going back is one line
  (`retrieval.preparation.mode: legacy`). An explicit choice (including `legacy`) and
  v1 projects are left alone. The schema default itself stays `legacy`.
- Until `ipsis index` runs, a migrated project has no index for the new collection and the
  service reports it as not ready (the usual "run `ipsis index`" message).
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

- Every v2 project that did not choose a preparation must run `ipsis index` after upgrading
  (new collection name and directory). Nothing else changes: same documents, same answers format.
- Calibrations stay valid for projects that do not change their header.
- Known residuals: Markdown tables stay as paragraphs; PDF has no page numbers or
  tables; a few real-document questions still rank 3 to 4 (small sample).

## Update (2026-10-16): distinctive terms on by default

The default structural block also turns on `distinctive_terms: 5` with `sibling_threshold: 0.6`: units that are
nearly identical (the P1 and P2 weighting tables) get the terms that tell them apart added to what is indexed and ranked,
and shown with each result together with the unit's scope. On the 56 real adversarial questions hit@1 went from 0.857
to 0.893 (2 cases; informal 0.786 to 0.821); the 33 formal questions and the synthetic bank were unchanged. Adding the scope text
to the index (`scope: true`) measured worse and stays off. Projects that already had a `preparation` block keep it.
See [the methodology note](../methodology/preparacion-estructural.md).
