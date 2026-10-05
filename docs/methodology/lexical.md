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
| focus | the 2 question terms with the highest IDF that exist in the corpus | "what it is about" |
| `s_foco` | fraction of focus terms present in the answer sentence (1 when there is no focus) | the right span in the wrong place: the filter's "6 months" for a question about the warranty gives `s_foco = 0` |
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
  `s_foco` drops and the system abstains more than needed. It is the safe
  side of the error; `τ_foco` is calibrated with the golden set's paraphrase
  category.
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
