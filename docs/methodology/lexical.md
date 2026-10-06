# Lexical layer: BM25, TF-IDF and signals

## 1. Purpose

Provide cheap, deterministic and explainable signals for three things:
retrieval (BM25 in the hybrid search), detecting "looks related but does
not answer" and saving latency with early exits that avoid running models.

## 2. Scope and non-scope

- **Scope:** turning text into terms, corpus statistics, the BM25 vector,
  TF-IDF and the signals `s_oov`, focus, `s_foco`, `s_cov` and `s_lex`.
- **Non-scope:** understanding paraphrases; the [reranker](reranker.md) and
  the [reader](reader.md) make up for it in medium and heavy.

## 3. Versioned inputs and outputs

- `terminos(text, pack)`: the **only** path from text to terms, the same at
  indexing and at query time.
- `.ipsis/index/<collection>.stats.json`: `n_chunks`, `largo_medio` (mean
  length), `df[term]` and `superficie[term]` (the most frequent original
  form, to display it). Readable JSON, with the corpus hash.

## 4. Algorithm and tie-breaking

`terminos()`: Unicode tokenization (`\w+`) → casefold → strip accents
(Latin script only) → the language's Snowball stem, if the pack defines
one.

- **IDF:** `ln(1 + (N − df + 0.5) / (df + 0.5))`.
- **BM25 in Qdrant without a vocabulary:** term id = `zlib.crc32`; the
  document carries `tf·(k1+1) / (tf + k1·(1 − b + b·length/mean_length))`
  and the query 1 per term; Qdrant applies the IDF (`modifier: idf`).

| Signal | Definition | What it detects |
|---|---|---|
| `s_oov` | IDF mass of the question terms absent from the corpus / total mass (an unknown term gets the maximum IDF) | an out-of-domain question |
| focus | the 2 question terms with the highest IDF that exist in the corpus, leaving out the relation's words and the pack's generic words | "what it is about" |
| `s_foco` | fraction of focus terms present in the answer sentence or in the title of its section (1 when there is no focus) | the right span in the wrong place: the filter's "6 months" for a question about the warranty gives `s_foco = 0` |
| `s_cov` | IDF mass of the question present in the sentence / total mass | overall coverage |
| `s_lex` | BM25(question, sentence) / the question's ideal BM25 | picks the anchor sentence in light |

**Early exit:** if no candidate contains a focus term, the reranker and the
reader do not run; the policy decides between `related` and `no_answer` with
what there is.

Other uses of TF-IDF: the keywords of each fragment, `ipsis golden template`
(MMR over sections to propose diverse questions) and the exact/paraphrase
classification when importing the golden set (`s_cov ≥ 0.6`).

## 5. Assumptions

IDF is enough to down-weight frequent words: stopword lists are not required
(the pack's are optional).

## 6. Invariants

- A single `terminos()`; what is indexed and what is queried match, and any
  score can be reproduced.
- Every signal is a pure function in `ipsis/lenguaje/lexico.py`, with a
  result in [0, 1].

## 7. Parameters and defaults

`k1 = 1.2`, `b = 0.75`, `max_focus_terms = 2`,
`early_exit_without_focus: true` (profile, `lexical` and `cascade`
sections).

## 8. Complexity and resources

Under 5 ms per query; the statistics take a few KB per document.

## 9. Failures and fallback

- A language without a stemmer: unstemmed terms.
- Missing statistics, or from another corpus: `ipsis doctor` asks for
  `ipsis index`.

## 10. Security and privacy

No I/O in the signals; the statistics only hold terms and counts.

## 11. Technical tests

`tests/lenguaje/test_lexico.py`, `tests/lenguaje/test_texto.py` and the
evaluation banks ("same topic, missing fact" traps).

## 12. Limitations

- **Synonyms:** if the user says "cartridge" and the document "filter",
  and the pair is not in the language pack's `sinonimos`, `s_foco` drops and
  the answer is `related` instead of direct. It is the safe side of the
  error; `τ_foco` is calibrated with the golden set's paraphrase category.
- `acuerdo` (agreement: dense top-1 in BM25's top-3 and vice versa) was
  measured and discarded as a policy signal: no effect on the universal bank
  and +4.6 ms of p95. The function is kept for the benchmark experiment.
- Chunking by lexical cohesion (`texttiling_v1`) was tried and discarded:
  the same statuses as cutting by section and more false `ok` answers than
  the current chunker.

## 13. References and provenance

- Robertson and Zaragoza, *The Probabilistic Relevance Framework: BM25 and
  Beyond* (2009).
- [snowballstemmer](https://pypi.org/project/snowballstemmer/) (BSD-3-Clause).
- Carbonell and Goldstein, *MMR* (SIGIR 1998).

## 14. Status

Stable. `τ_foco` and `τ_oov_ok` are calibrated per project.

## Relation words and cues

The language pack's `intenciones` ([ADR 0005](../decisions/0005-deterministic-query-understanding.md))
separate the relation a question asks for from its topic. In "when does the
purchase start?", "when" and "start" are the relation:

- they are never focus terms, and they do not score in the selection: "…the
  Purchasing Officer **starts** a new purchase" does not say when the
  purchase starts, although it has "starts";
- in `s_oov` and `s_cov` they count only when they help: a relation word
  absent from the corpus is left out, and one in the corpus adds to the
  coverage if the sentence has it ("até" in "…reembolso até 30 dias") but
  does not subtract if it does not ("Once the form is approved…").

In the selection, a sentence that shares topic with the question and
contains one of the intention's cues ("once", "after") weighs ×2 if the cue
is in its first words and ×1.5 if it is further in.
`ipsis ask --diagnostics` shows the recognized intention's effect on the
best scored sentences.

## Generic words and synonyms

Each language pack also declares:

- **`genericas`:** support verbs and units ("hacer", "tener", "días",
  "veces"). They are never focus terms and do not count in the selection: in
  "¿Desde cuándo se hace la compra?", "hace" has a higher IDF than "compra"
  (which is everywhere) and brought "Para hacer un reclamo…" first. They do
  count for `s_oov` and `s_cov`: without "meses", the absent part of "¿…en
  los meses de calor?" would weigh more than it does in the question.
- **`sinonimos`:** groups of words with their common forms. A question word
  that is not in the corpus and is not part of the relation is searched and
  measured as the forms of its group that are ("necesita" → "requieren").
  The diagnostic shows them (`sinonimos`). The groups also count when
  checking the focus terms: "Above what amount do you **need** a
  Resolution?" is answered by "…**require** a Resolution" ("need" is in the
  corpus with another meaning, so the question is not expanded).
- **`sufijos_derivados`:** derived-noun suffixes the stemmer keeps ("signatur",
  "assinatur"). When checking the focus terms, "signature" counts as "signs"
  and "assinatura" as "assina". Spanish needs none: its stemmer already takes
  "aprobación" and "firma" to the verb's stem.

## Numbered labels

A label such as "Artículo 4." or "4.2." is not a sentence: the sentence
splitter keeps it with the sentence that follows ("Artículo 4. Si el cliente
no está…"). Without it, "¿Qué recargo se cobra según el artículo 4?" lost
"artículo" from the answering sentence, and the citation lost the article.
The title of the evidence's section also counts for `s_foco` (not for
`s_cov`): it frames every sentence under it.

