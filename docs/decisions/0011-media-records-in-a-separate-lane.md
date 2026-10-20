# ADR 0011: audio and video records in a separate lane

Status: accepted (2026-10-16).

## Context

Some questions are best answered by an audio or a video the institution already has. ipsis is non-generative
(ADR 0001) and self-hosted: it must not transcribe, summarise or invent text about a media file, and the documents and
questions never leave the server.

## Decision

- **A record, not the media.** A person writes a short YAML record per audio or video in `media/` (title, description,
  keywords, chapters; `ipsis/ingesta/fichas.py`). ipsis never opens, transcribes or analyses the file; `transcript` is
  rejected. What is searched and shown is the record's own text.
- **A separate lane.** Records are indexed in their own collection (`…__media`) with their own manifest, apart from the
  documents, so the document index, ranking, windows and scores are the same with or without `media/`. The lane runs after
  the document sources are published, on the first page only, within its own time budget (`media.budget_ms`), and its
  failures never break a document query (`ipsis/consulta/media.py`, `MotorV2._anadir_multimedia`).
- **Shown in its own card**, after the sources and "Show more results", never mixed into them. The API returns it as `media`;
  the widget shows the record's text and a button that opens the link in a new tab, with the chapter's minute for YouTube and
  Vimeo. No iframe or player (the content-security policy does not grow).
- **Only if it is close enough.** The shown unit (record or chapter) is the one with the highest dense cosine, and it is
  published only if that cosine reaches `media.min_score`. Without `min_score` nothing is shown. The fused hybrid order
  only orders candidates: it is relative to the query and says nothing about relevance.
- **On by default, no migration.** The schema default is `media.enabled: true` and `media.min_score: 0.874` (and `ipsis init`
  writes them in the new `config/engine.yaml` so they are visible). `config_version` stays 8: an existing v2 project receives
  them when it loads. With no `media/` folder indexed nothing happens, and `media: enabled: false` turns the lane off.
- **ipsis does not serve media files.** `file:` is accepted by the record format but is neither served nor shown; a record
  needs a `url`. Serving files over HTTP would make the institution's media reachable by anyone who can reach the service,
  which does not fit "documents and questions never leave the server" and would need its own access control. Chosen with
  the user (2026-10-16); it can be revisited with an explicit access design.

## Evidence

Synthetic Spanish bank (`tests/datos/banco_multimedia/es/`: 20 records, 90 questions: 30 with a record, 30 about a document
topic with no suitable record, 30 out of domain; 10 informal), `intfloat/multilingual-e5-small`, one run of
`herramientas/evaluacion/carril_multimedia.py` (`docs/methodology/mediciones/multimedia/`). The threshold is the smallest
one with zero records shown without matching in `dev` (rounded up): **0.874**. Results at 0.874:

| Set | Shown without matching | Right record shown | Chapter right |
|---|---|---|---|
| dev (36 / 18 questions) | 0 / 36 | 14 / 18 | 4 / 4 |
| test (24 / 12) | 1 / 24 (4.2 %; Wilson 95 % upper 20 %) | 11 / 12 | 4 / 5 |

The smallest threshold that only met the 5 % objective in `dev` (0.857, one false record) gave 3 of 24 (12.5 %) in `test`, which is
why the stricter one is the default. Search latency of the lane: p50 about 11 ms, p95 about 14 ms (model loaded).

## Limits

- The bank was written by the same assistant that wrote the lane, in Spanish only: the figures are optimistic and a different
  corpus, language or set of records can need another `min_score`. The guide says how to measure your own.
- 36 negative questions in `dev` cannot certify 5 %: zero errors still leaves a 95 % upper bound near 10 %.
- The lane does not rerank: `light` and `medium` share the dense model, so the threshold is the same for both.
- Records without `url` (only `file`) are indexed but never shown.
