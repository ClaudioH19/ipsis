# Lexical layer: BM25, TF-IDF and signals

## 1. Purpose

Provide cheap, deterministic and explainable signals for three things:
retrieval (BM25 in the hybrid search), detecting "looks related but does
not answer" and saving latency with early exits that avoid running models.

## 2. Scope and non-scope

- **Scope:** turning text into terms, corpus statistics, the BM25 vector,
  TF-IDF and the signals `s_oov`, focus, `s_foco`, `s_cov` and `s_lex`.
- **Non-scope:** understanding paraphrases; the [reranker](reranker.md) and
  the [reader](reader.md) make up for it in medium.

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
| `s_foco` | fraction of focus terms present in the answer sentence, the title of its own (sub)section or the previous sentence of its paragraph (1 when there is no focus) | the right span in the wrong place: the filter's "6 months" for a question about the warranty gives `s_foco = 0` |
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
  Relaxing the focus with model scores was measured and rejected (2026-10-08):
  "¿Cuántos días tiene el proveedor para **entregar** los productos?" against
  "…dos días hábiles para **aceptar** la Orden" gets reader 0.99 and reranker
  0.90, the same as a legitimate paraphrase ("anticipación" → "antes"); a
  sentence-level cross-encoder, e5 cosine and a per-word ablation did not
  separate them either. See [informal paraphrases](informal-paraphrases.md).
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

An intention can also **require** its cue (`exige_pista: true`), and accept
entity types as cues (`entidades_pista`). `costo` ("¿cuánto cuesta…?", "how
much does it cost…?", "quanto custa…?") requires an amount — a `monto` entity
("$ 15.000", "USD 40") or a currency or "free" word — so "¿Cuánto cuesta
cambiar el filtro?" is not answered with "…cada 45 días" (semantic reading
reached that sentence because it is about the filter). `frecuencia` does ("¿cada cuánto…?", "how often…?", "a cada quanto…?"): its
answer states a period ("cada 90 días", "every six months", "a cada 90
dias"). If the answering sentence has no cue, `s_foco` is capped at 0.5 and
the diagnostic shows `forma_ausente`: "How often should I change my
password?" has every topic word in "Go to the portal and select 'Change
password'", which is not its answer. Before, light answered it `ok` (in
Spanish already before this change; in English and Portuguese the question
quantifier happened to be a focus term).

## Generic words and synonyms

Each language pack also declares:

- **`genericas`:** support verbs, units and question quantifiers ("hacer",
  "tener", "días", "veces", "tiempo"; "quantos", "often", "long"). They are
  never focus terms: with "quantos" as a focus term, "Quantos dias o
  fornecedor tem para aceitar a Ordem de Compra?" rejected "O fornecedor tem
  dois dias úteis…". Quantifiers were also tried as stopwords and reverted:
  out of `s_oov` and `s_cov`, "How many days is it?" (no topic left) and
  light's "how often do I change my password" (answered with the procedure,
  not the period) became false `ok`. Light has no other sign of the answer
  type. Generic words and do not count in the selection: in
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

## Versioned WordNet resources

The package also includes prepared lexical data under
`ipsis/recursos/sinonimos/` ([ADR 0007](../decisions/0007-versioned-lexical-sources.md)):
full `*.lexicon.tsv` files preserve lemma/synset membership, POS, phrases and
polysemy; separate `*.tsv` files apply reproducible filters (up to three
senses, at most eight members, lowercase single words). Runtime uses only
the filtered table for expansion and builds a cached stem index per language/stemmer.
It counts senses in the full WordNet lexicon before applying runtime guards:
a sense discarded by the group-size filter still blocks an ambiguous lemma.
An automatic expansion requires an OOV content word, exactly one sense
after stemming, and a replacement present in the corpus. Relation words,
manual groups and project overrides take precedence. Only the BM25 query
expands: dense confidence, focus validation, QA and acceptance retain the
original question and vector. Automatic groups never enter `equivalentes()`.
The diagnostic retains source, synset, POS and chosen forms.

Project `domain.yaml::synonyms` groups override overlapping manual and
automatic groups. Multiword forms require complete phrase matching and
all replacement content stems in the corpus. Rebuild the motor after changing
lexical rules; its conversation state and query caches start empty.
Calibration provenance includes a SHA-256 of the behavior version, effective
rules, project groups, filtered TSV and sense-count lexicon bytes. Old or mismatching hashes
prevent the old calibration from applying.

Original downloads and notices are permanently stored in
`herramientas/sinonimos/datos/fuentes/`. The developer converter uses them
offline by default, verifies source hashes and produces per-language
manifests and attribution files. Only an explicit `--download` for a source
update allows network access; installation uses packaged resources.

Pinned LibreOffice/MyThes supplements add directed `*.thesaurus.tsv`
records and a `*.vocabulary.tsv` inventory with source IDs. Records retain
relation annotations; generic, related, similar and antonym terms are not
turned into synonym groups. The combined inventory contains 383,865
written forms/expressions across the three languages. Case variants and
phrases count separately; this is a coverage inventory, not a runtime
equivalence map. Supplemental originals are stored under
`herramientas/sinonimos/datos/tesauros/` and rebuild offline as well.

Preparation/reproducibility is validated. Runtime acceptance is measured
against the query, conversation and universal banks with the corrected
literal metric: a reader's selected span takes precedence over its enclosing
sentence. Vocabulary counts do not establish answer correctness.
The [F2 results](mediciones/f2/README.md) preserve all raw comparisons:
no new wrong answers, lost correct answers or state changes in the 18
profile/language/bank combinations; alternating timing repeats meet the
light budget. Query content and normalized stopwords are cached without
changing the effective rules.

`genericas_memoria` is a separate topic-memory word list: `tiempo/tempo`
are ignored when recognizing or compacting a topic, while keeping their
original role in answer focus and sentence selection. Moving them to global
generic words lost a correct Spanish answer in the F1 comparison. The final
[V4 results](v4-results.md) preserve that failed iteration and the correction.

The extended dictionary inventory also includes frozen Kaikki/Wiktionary
snapshots for es/en/pt (extraction 2026-10-03, enwiktionary 2026-09-02).
Complete downloads are archived losslessly in parts. Verified lexical
projections support faster offline rebuilds; `--raw-dictionaries` audits
directly from the complete originals. Separate compressed resources retain
lemma/form/variant classifications, morphology records and explicit directed
synonym edges with sense identifiers and qualifiers. Inflections, translations,
antonyms and related terms never become synonym groups through this conversion.
These files remain development data; the answer engine does not load them.

## Intent similarity fallback

Each pack includes ten independent examples for seven intentions. Patterns
win. With no pattern and a nongeneric corpus topic, `intenciones.py` compares
the cached dense query vector with example vectors computed at startup.
The best example scores each intention; cosine and margin against a different
intention must exceed the measured model/language settings. BM25 and
unmeasured models skip this.

For follow-ups, the vector for the current question is memoized separately
from the interpreted retrieval question. Pattern recognition and the
`respaldo_patrones` compatibility gate also use that current question. The
gate requires a compatible question form for end/procedure fallback; it
does not infer a relation on its own. This prevents inherited deadline words
or a similar topic from changing an amount or actor question into another
intent. The lexical behavior version is v5, invalidating stale calibrations.

Follow-up QA answers use literal offsets when quantity boundaries
are completed with adjacent units/limits/reference points, or a selected
actor is extended with the matching action clause. `bordes_respuesta` stores
language-dependent forms; the raw span remains in `tramo_completado` and
`lecturas`. No other actor or quantity is substituted. The
[correction measurements](mediciones/v4-correcciones/README.md) separate
these extraction changes from intent coverage.

Only natural-query dev and human relation labels in
`tests/datos/banco_consultas/intenciones.yaml` select thresholds. Unsupported
duration, frequency, simple amounts and descriptions remain unknown. The
search maximizes correct fallback coverage without dev errors, then minimizes
margin and cosine. Shipped categories also require a correct dev fallback;
other relations keep their patterns. Test is reported separately and raw
development iterations are retained, including incorrect predictions.

The inferred intention supplies sentence cues and reader-window selection,
including the extra candidate by cue. It removes no content word and changes
no answer acceptance threshold. Example/threshold/activation data and the
behavior version invalidate older calibration hashes. See
[ADR 0005](../decisions/0005-deterministic-query-understanding.md).

## Numbered labels

A label such as "Artículo 4." or "4.2." is not a sentence: the sentence
splitter keeps it with the sentence that follows ("Artículo 4. Si el cliente
no está…"). Without it, "¿Qué recargo se cobra según el artículo 4?" lost
"artículo" from the answering sentence, and the citation lost the article.
The title of the evidence's section also counts for `s_foco` (not for
`s_cov`): it frames every sentence under it. It is the innermost section that
contains the sentence, also with the reader: a chunk can hold a whole FAQ, and
"¿Qué horario tiene la Mesa de Ayuda?" is the heading of "La Mesa de Ayuda
atiende de lunes a viernes…", not the document title. The previous sentence of
the same paragraph counts too (never across a line break): "Si no rinde a
tiempo, el monto se descuenta…" is about the expenses named by the sentence
before it.

## Same head, another modifier

"¿Qué asignación se da para gastos **de electricidad**?" is not answered by
"…para gastos **de conexión**": the head ("gastos") is the same, its modifier
differs, and "electricidad" is absent from the corpus. When a question word
absent from the corpus modifies a head the answering sentence has — through a
linking preposition of the pack (`preposiciones_modificador`: "de", "of",
"para"…) or before it in English (`modificador_antepuesto`: "electricity
costs") — and the sentence gives that head another content modifier,
`s_foco` is capped at 0.5 and the diagnostic shows `modificador_distinto`
("electricidad≠conexion"). Numbers ("12 characters") and generic words ("how
many days") are not modifiers.

## Typos

A hurried user writes "pasword", "covran", "abreel" or "estacio namiento".
The analysis stage normalizes the question against the corpus vocabulary
before anything else (`ipsis/lenguaje/ortografia.py`), so BM25, the dense
model, the reader, the focus and `s_oov` all see the corrected words. The
diagnostic shows each correction (`ortografia`). It follows SymSpell (a
symmetric-delete index over the corpus forms and stems, built once per
engine) and its compound mode (joining and splitting words), always towards
words of the documents. The rules are conservative:

- never a word that is recognized: stopwords, generic words, corpus words,
  words of the pack's synonym groups ("compu"), or words whose stem is a
  lemma of the language's master lexicon (`<lang>.lexicon.tsv`). "feriados",
  "orina" or "bus" are real words the corpus lacks, and correcting them
  would turn an unanswerable question into a false `ok`. Fallback packs have
  no lexicon and correct nothing;
- never a proper noun or an acronym: a capital letter outside the first word
  ("Atacama", "Copa", "HDMI") is left as written;
- edit: Damerau-Levenshtein distance 1 (2 from 8 letters) to a corpus form,
  from 4 letters, and a single candidate stem at that distance; a tie is left
  alone. If no form is that close, stems are compared ("covran" → "covr", one
  edit from "cobr": the corpus says "cobra", not "cobran"), with the same
  first letter and the corpus form not far from what was typed;
- split: "abreel" → "abre el" when one part is a function word and the other
  is in the corpus (or both are exact corpus forms);
- join: "estacio namiento" → "estacionamiento" when the joined word is in
  the corpus and one of the parts is not a word.

Measured with the typo bank (`tests/datos/banco_erratas`: existing questions
with omissions, duplications, transpositions, neighbouring keys, sound
confusions, joined and split words). Robustness is the share of the
questions answered correctly when clean that are still answered correctly
with typos (medium):

| | Design (354 questions) | Validation, measured once (261) |
|---|---|---|
| previous corrector | 81.3 % (43 lost, 3 new errors) | 91.2 % (13 lost, 5 new errors) |
| normalization layer | **89.6 %** (24 lost, 3 new errors) | **96.6 %** (5 lost, 3 new errors) |

Clean questions are unchanged on every bank (the layer touches 2 of 678 clean
design questions, the same real typos as before). On the design questions it
recovers the full question in 278 of 354 cases (203 before) and is faster:
the index replaces a pass over the whole vocabulary per word. What remains
are typos that form another real word ("paring", "wright", "férias" →
"feias"), left alone on purpose, and short words whose stem collides with a
real word ("veca"). KenLM and a general frequency dictionary were not needed:
correcting towards the corpus is what retrieval and the policy need.

**Context from word pairs.** For typos that form another real word ("paring
permit") or a tie between candidates, the index stores the pairs of
neighbouring content words of each chunk (`pares` in `.stats.json`, stems,
function words skipped). They count as presence, not frequency, and come from
the chunk text, not from the embedded text with the section title prepended:
a repeated title, header or footer never weighs more than one occurrence. A
word absent from the corpus is replaced by a corpus form at distance 1 if
that pair exists with its neighbour and the original pair does not. A real
word needs the pair on both sides ("issues paring permit" → "parking"); a
non-word, on one. With one side for real words it recovered 6 more design
questions but changed a clean one ("paper weight" → "weigh", because the
document says "weigh"); with both sides, 1 more and no clean change. Bigrams
on both sides were chosen over trigrams or 5-grams: client corpora are small
and questions reorder the documents' words, so longer n-grams would almost
never match.

At indexing, a self-test puts one typo in each of up to 300 corpus sentences
and corrects them with and without context; context is enabled
(`contexto_erratas`) only if it recovers at least one word and errs at most
once per four recoveries. It measures whether the corpus has enough pairs to
help; it cannot detect the "weight" risk (real words the corpus lacks never
appear in its sentences), which the two-sided rule guards. An index built
before this has no pairs and corrects without context until it is rebuilt.
Measured end to end it changed nothing: robustness 89.6 % (design) and 96.6 %
(validation) with or without it, and every clean bank identical. It stays on
because it costs nothing and can help corpora with many real-word typos.

Accents are not typos: "contrasena" already matches "contraseña" because
`terminos()` strips them.

Informal spellings of function words are stopwords of each pack: "q", "pa",
"xq" (es), "q", "pra", "vc" (pt), "u", "ur", "pls" (en), and the pieces of an
English contraction ("don't" is tokenized as "don" + "t"; "what's" leaves
"s"). Before, each counted as a question word absent from the corpus, with
the maximum IDF: "a q hora se riega el invernadero" had `s_oov` 0.70 and
"What happens if I don't report my expenses on time?" 0.73.

