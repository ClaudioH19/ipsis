# ADR 0007: versioned lexical sources and offline rebuilds

- Status: accepted for data preparation and conservative runtime integration.
- Date: 2026-10-06.

## Context

Manual language-pack synonyms cover only a small vocabulary. A first
WordNet conversion restricted to one sense retained 32,984 distinct words
across es/en/pt. The user approved the three proposed sources and asked for
broader coverage and permanent local files to continue development without
repeating downloads.

## Decision

- Pin Spanish MCR/OMW and Portuguese OpenWN-PT/OMW to an immutable OMW
  commit, and English Open English Wordnet to the 2025 release. URLs, sizes,
  hashes and notices are in `herramientas/sinonimos/fuentes.json`.
- Store lossless original downloads and notices in
  `herramientas/sinonimos/datos/fuentes/`. The TAB files are compressed;
  the original English gzip is retained unchanged. Verify the original
  download hash after decompression of stored TAB files.
- Store a full per-language `*.lexicon.tsv` preserving all lemma groups,
  synset identities and POS, including phrases and ambiguous lemmas. The
  original files preserve definitions and other information for future work.
- Store separately a filtered per-language `*.tsv` for later retrieval
  experiments: lowercase alphabetic words, up to three senses per lemma,
  groups of at most eight words, at least two surviving members. Preserve
  each sense separately; never merge groups or follow semantic links.
- Rebuild and check offline by default. Network access requires an explicit
  `--download` for a deliberate source update. Installation never downloads
  dictionaries. Sources and code are sufficient after cloning without cache.
- Preserve original license/citation notices in the package. Each dataset
  retains its own license; it is not relicensed as AGPL with the code.
- Wheel: derived resources and notices. Sdist: also the converter and all
  archived originals. Verify package contents against the repository bytes
  in an isolated build directory.
- Extend data preparation with four pinned LibreOffice/MyThes thesauri
  (Spanish, English, European and Brazilian Portuguese). Archive lossless
  originals and notices under `herramientas/sinonimos/datos/tesauros/`.
  Preserve directed records, labels and relation annotations in separate
  `*.thesaurus.tsv` files; never treat these rows as WordNet synsets.
  Generate `*.vocabulary.tsv` as a deduplicated inventory with source IDs.
  Exclude explicitly annotated non-synonym terms from this inventory;
  preserve them in the thesaurus records for later review.

## Measurements

| Language | Full unique lemmas/expressions | Filtered unique words | Filtered groups |
|---|---|---|---|
| es | 90,899 | 24,289 | 11,737 |
| en | 128,009 | 31,671 | 15,214 |
| pt | 54,071 | 11,405 | 5,612 |

Counts are distinct written forms within each language, not guaranteed
usable query expansions. Master TSV files total 8,045,838 bytes; filtered
TSV files total 1,285,441 bytes. Archived originals and notices take about
13.4 MB. Manifests record exact hashes, sizes, filters and provenance.

The combined inventory after this extension contains 96,633 Spanish,
193,124 English and 94,108 Portuguese written forms/expressions: 383,865
total, up 110,886 (40.6%). Counts preserve case and phrases; they are not
counts of interchangeable single words. There are 57,315 additional
lowercase alphabetic forms. The four archived thesauri and notices take
10,236,338 bytes (excluding their archive manifest). Existing filtered
synonym tables retain their data and hashes.

## Consequences

The subsequent request to expand all three languages adds complete frozen
Kaikki/Wiktionary snapshots (enwiktionary 2026-09-02, extraction 2026-10-03).
All 675,305,401 downloaded gzip bytes are preserved losslessly in ordered
parts of at most 24 MiB. Verified lexical projections retain the fields
needed for reproducible conversion; complete originals remain available.
The default rebuild verifies both the original and projection hashes.

| Language | Previous inventory | Extended inventory | Dictionary lemma forms | Explicit synonym records |
|---|---|---|---|---|
| es | 96,633 | 1,325,362 | 108,026 | 56,585 |
| en | 193,124 | 1,740,739 | 758,100 | 725,169 |
| pt | 94,108 | 569,099 | 73,068 | 62,643 |

The combined inventory now holds 3,635,200 distinct written forms counted
per language, adding 3,251,335. Typed indexes distinguish lemma, inflection,
variant and legacy membership; classifications may overlap. Proper names
and phrases remain identifiable. Synonym records preserve original direction,
sense and qualifiers, without converting morphology or other relations into
equivalence groups. Source notices and licenses remain separate from AGPL.
Data resources take 264,459,554 bytes including the earlier resources.

- No repeated downloads are needed to review or change filters.
- Dataset size and runtime behavior are distinct: automatic loading is not
  enabled by this data-preparation change. No answer-quality improvement is
  claimed from the counts alone.
- Before activation, measure false direct answers and lost correct answers
  per profile/language. An automatic dictionary must not be inserted wholesale
  into `equivalentes()`, which affects focus validation, independently of
  the OOV guard on retrieval expansion.
- Runtime uses only filtered groups for BM25 expansion, reusing the original
  dense vector and retaining the original question for focus, QA and policy.
  It counts senses in the full WordNet lexicon first; excluded senses still
  block ambiguous lemmas. Stem collisions, relation words, manual groups and
  project overrides block automatic expansion. No transitive group union.
- Project `domain.yaml::synonyms` matches whole phrases (such as OC / orden
  de compra) and overrides overlapping single-word groups. A replacement
  requires all its content roots in the corpus.
- Effective lexical hashes enter calibration provenance: behavior version,
  language rules, project groups and both WordNet resource byte streams.
  Missing or different hashes invalidate previously calibrated thresholds.
  Restart the service after lexical changes; a new motor has fresh topic
  memory and query caches. Dataset updates require a process restart.
- Evaluate literal correctness on the selected QA span; an expected fact
  elsewhere in its enclosing sentence is not a correct answer. Keep the
  corrected baseline's previous wrong spans by ID, without changing policy
  thresholds or treating those errors as acceptable production behavior.

Runtime validation is recorded in
[the F2 evaluation](../methodology/mediciones/f2/README.md): 1,031 tests pass,
two are skipped, and all 18 profile/language/bank combinations retain
their states and correct/wrong answer identities. Three alternating timing
rounds meet the light latency budget in every language. Original timing
failures and variance are retained; no general speedup is inferred from
these measurements. Startup and RSS are measured separately. Cache the
query's content analysis and normalized stopwords to avoid repeated stemming.
