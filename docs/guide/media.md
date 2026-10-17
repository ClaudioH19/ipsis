# Audio and video records

ipsis can point to an audio or a video that belongs to the question, **without transcribing or analysing it**. You write a
short record (a YAML file) per audio or video; ipsis finds the record whose text matches the question and shows it in a
card of its own, **after** the document sources. Nothing is generated: the card shows the record's own text
([ADR 0011](../decisions/0011-media-records-in-a-separate-lane.md)).

## A record

One file per audio or video in `media/` (next to `documents/`), named like its id (`media/induction.yaml`):

```yaml
title: Induction to the enrollment platform      # required
kind: video                                      # required: video | audio
url: https://example.org/induction               # required: an http(s) link
description: How to sign in, enroll in courses and check your timetable.   # required
keywords: [enrollment, timetable]                # optional
language: en                                     # optional
version: "2026-03"                               # optional; shown next to the title
duration: "14:32"                                # optional: MM:SS or HH:MM:SS (quote it)
active: true                                     # optional: false keeps it out of the index
chapters:                                        # optional
  - at: "01:10"
    title: Sign in with your single sign-on
  - at: "06:45"
    title: Enroll in courses
    description: Choose sections and confirm.
```

- The text of the record is what is searched: write the title, description and chapter titles the way people ask.
- A **chapter** lets the card say "From 6:45" and, for YouTube and Vimeo, open the link at that minute. Whichever is
  closer to the question is shown: the video for a question about the whole video, a chapter for a question about it.
- `transcript` is rejected: ipsis does not read or transcribe media.
- `file:` (a file under `media/files/`) is accepted by the format but **is not served and not shown yet**: use `url`.
  ipsis does not publish your files, which keeps them private ([ADR 0011](../decisions/0011-media-records-in-a-separate-lane.md)).

## Indexing

`ipsis index` (and `ipsis sync`, which notices changed records) indexes the records in their own collection, apart from the
documents, and prints the invalid ones with what is wrong (`[!] media/induction.yaml: …`). The document index is the same
with or without `media/`.

## Turning it on and the threshold

```yaml
# config/engine.yaml
media:
  enabled: true      # on by default; with no media/ folder it does nothing
  min_score: 0.874   # nothing is shown below this dense cosine; null shows nothing at all
  max_results: 1     # records per page (1 to 5)
  budget_ms: 150     # the lane is skipped if the query has less time left
```

A record is shown only if its cosine reaches `min_score`; without it **nothing is shown**. The default was measured on a
synthetic bank (`tests/datos/banco_multimedia/es/`, 90 questions, 20 records) with `intfloat/multilingual-e5-small`: **0 records
shown without matching in dev (36 questions) and 1 of 24 in test**, and the right record shown in 78 % (dev) and 92 % (test) of
the questions that have one. The questions were written by the same assistant that wrote the records, so treat the figures as
optimistic and measure your own:

```bash
python herramientas/evaluacion/carril_multimedia.py --banco <your bank> --salida /tmp/mm/carril
```

The report is in [`docs/methodology/mediciones/multimedia/carril.md`](../methodology/mediciones/multimedia/carril.md). If the
card appears when it should not, raise `min_score`; if it never appears, lower it a little and re-measure.

## What the widget shows

After the sources and "Show more results", a separate block: "There is also a video about this", with the type, duration,
version, title, chapter and minute, the record's description ("According to the video description") and an "Open the video"
button that opens the link in a new tab. There is no embedded player. It never changes the document sources or their order,
and appears only on the first page. The API returns it as `media` ([widget guide](web.md)).
