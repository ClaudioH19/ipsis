# Informal paraphrases (2026-10-08)

Users do not write like documents. They paraphrase, drop accents and
question marks, abbreviate ("q", "pra", "wfh"), use slang ("refri", "der
pau") and make typos ("pasword"). This note records what was measured, what
changed, and what was tried and rejected, so the next attempt starts from
the evidence.

## Banks

- **Design:** the query bank (`tests/datos/banco_consultas`, 60 questions
  per language, es/en/pt; 34 answerable).
- **Validation:** a new informal bank (`tests/datos/banco_informal`, 32 per
  language: 20 colloquial paraphrases, 8 same-topic traps, 2 false premises,
  2 out of domain) over a byte-identical copy of the same corpus. None of its
  questions was used to design a rule or choose a threshold; it was measured
  before and after the changes, once.

Metrics per profile and bank: **ok** = direct answers that show the expected
literal / answerable; **seen** = answerable questions whose right passage
reached the user, as `ok` or as `related`; **err** = accepted wrong answers
(false `ok` on a negative, or a direct answer without the literal).

## Diagnosis

Every failure was classified by the gate that decided it
(`s_foco`, `s_oov`, `s_qa`, `s_ret`, `s_cov`) and by whether the evidence
held the expected answer.

1. **Retrieval works with colloquial questions.** Medium showed the right
   passage for 14–16 of 20 informal questions, light for 10–18. What drops is
   the decision to call it a direct answer.
2. **Several losses were plain bugs or pack gaps,** fixed below: the reader's
   evidence carried the chunk's top-level section instead of its own
   subsection; question quantifiers ("quantos", "often") were chosen as focus
   terms; a sentence's referent in the previous sentence ("Si no rinde a
   tiempo…" after "…rinde los gastos…") was ignored; typos and informal
   abbreviations counted as words absent from the corpus; English
   contractions left "don" and "t" as content words.
3. **The rest is a real ambiguity the signals cannot resolve.** A word of the
   question that the answering sentence does not contain can be a
   paraphrase ("anticipación" → "siete días antes", "keep a book" → "book
   loans last") or the missing fact of a trap ("¿Cuántos días tiene el
   proveedor para **entregar**…?" → "…para **aceptar** la Orden"; "abre nos
   **feriados**" → the weekday hours). Both get the reader at 0.99–1.0 and the
   reranker up to 0.90.

## Changes (kept)

| Change | Where | Why |
|---|---|---|
| The reader's evidence names the innermost section of its sentence | `consulta/etapas/lectura.py::seccion_de` | a chunk can hold a whole FAQ; "¿Qué horario tiene la Mesa de Ayuda?" is the heading of its answer |
| The previous sentence of the paragraph counts for the focus (not for coverage, never across a line break) | `consulta/etapas/seleccion.py::oracion_previa` | "Si no rinde a tiempo, el monto se descuenta…" is about the expenses named just before |
| Question quantifiers are generic words (never focus; still in `s_oov`/`s_cov`) | `genericas` of `en`/`pt` (`es` already had "cuánto" as a stopword), plus `tiempo`/`tempo` | "Quantos dias o fornecedor tem…?" rejected "O fornecedor tem dois dias úteis…" |
| Informal abbreviations and contraction pieces are stopwords | `stopwords` of the three packs | "a q hora…" had `s_oov` 0.70 |
| Typo correction against the corpus vocabulary, guarded by the language lexicon (a SymSpell-style layer since 2026-10-10, see [lexical](lexical.md#typos)) | `lenguaje/ortografia.py`, analysis stage | "pasword", "telatrabajo", "viatcio" were absent words |
| `frecuencia` intention whose cue is required (`exige_pista`) | `intenciones` of the three packs | "How often should I change my password?" was answered with the procedure |

## Tried and rejected

- **A heavier profile.** Six newer retrievers/rerankers gave exactly medium's
  25/34 on the Spanish bank (ADR 0003): the reranker saw the same passages.
- **Semantic focus.** Sentence-level cross-encoder and e5 cosine did not
  separate correct evidence from same-topic traps ("pasajes de bus" vs
  "pasajes aéreos": 0.86); neither did removing each missing word and
  measuring the cross-encoder's change.
- **Partial focus with a confident reader and reranker.** It admits
  "entregar"/"aceptar" (reader 0.99, reranker 0.90).
- **Tolerating a high `s_oov` with a full focus and a confident reader.** It
  frees colloquial paraphrases, but the validation bank already contains the
  counterexample: "que horas a biblioteca abre nos feriados" passes every
  other gate. Not adopted.
- **Question quantifiers as stopwords.** With "many" gone, "How many days is
  it?" had no topic left and passed; with "often" gone, light answered "how
  often do I change my password" with the procedure. They stay generic, and
  the frequency intention covers the second case.
- **Sentence-level cosine instead of the chunk's in light.** +11 correct and
  +2 wrong on the design bank; not adopted without a type check.

## Results

Same CPU (2 ONNX threads), same banks, before → after all the kept changes.
Format: ok · seen · err.

| Profile | Bank | Before | After |
|---|---|---|---|
| light | query es | 14/34 · 25/34 · 3 | 14/34 · 25/34 · 3 |
| light | query en | 5/34 · 25/34 · 1 | 6/34 · 25/34 · 1 |
| light | query pt | 8/34 · 24/34 · 4 | 13/34 · 24/34 · 4 |
| light | informal es | 2/20 · 15/20 · 0 | 2/20 · 16/20 · 0 |
| light | informal en | 0/20 · 10/20 · 0 | 1/20 · 11/20 · 0 |
| light | informal pt | 0/20 · 18/20 · 0 | 0/20 · 18/20 · 0 |
| medium | query es | 25/34 · 30/34 · 0 | 26/34 · 30/34 · 0 |
| medium | query en | 16/34 · 27/34 · 1 | 20/34 · 27/34 · 1 |
| medium | query pt | 15/34 · 30/34 · 0 | 22/34 · 30/34 · 0 |
| medium | informal es | 3/20 · 14/20 · 0 | 4/20 · 14/20 · 0 |
| medium | informal en | 1/20 · 14/20 · 0 | 2/20 · 14/20 · 0 |
| medium | informal pt | 2/20 · 16/20 · 1 | 4/20 · 16/20 · 1 |

Totals: medium 56 → 68 correct on the design bank and 6 → 10 on the
validation bank; light 27 → 33 and 2 → 3. **No new accepted error:** the
remaining ten are the same cases before and after (light's eight
same-topic sentences; medium's "Who approves it?" and "…abre nos
feriados"). The informal bank confirms the direction but its absolute
numbers stay low: most colloquial questions end as `related` with the
right passage, by design.

Intermediate runs attribute the gains: the subsection fix and the
quantifiers gave medium pt 15 → 22 and en 16 → 18; the previous sentence
recovered a Spanish answer the quantifier change had cost; abbreviations,
contractions and typos gave en 18 → 20. Medium latency is unchanged within
noise (p95 2.7–3.4 s on this 2-thread CPU, as before); the first typo
check per language loads the lexicon once, at engine start.

## Second round: the ceiling and a judge

**Where the right passage is lost.** Of the 31 answerable questions whose
literal never reached the user in medium, 28 had the right chunk among the
final candidates (usually first): the loss is the choice of sentence inside
the chunk, and of the 600-character window the reader reads, both by word
overlap (`s_lex`). Ranking every sentence of the candidates offline:

| Order of the sentences | top-1 | top-3 (query bank) | top-3 (informal) |
|---|---|---|---|
| `s_lex` (current) | 58% | 76% | 75% |
| cross-encoder on "section title. sentence" | 82% | 99% | 92% |
| RRF of cross-encoder, e5 cosine and `s_lex` | 88% | 99% | 98% |

**Semantic reading** (`cascade.semantic_reading`; first measured as an
opt-in, now on in medium after the third round): the reader reads the 3 sentences the fusion ranks first
(each with the previous sentence of its line; headings never). Medium:
68 → 72 correct on the query bank and 10 → 17 on the informal bank, but
accepted errors 1 → 6 and 1 → 2. With more reach the reader also finds
"answers" to questions without a topic ("¿Cuánto es?", "Who approves it?",
"Quem aprova?") and to absent-qualifier traps ("gastos de **electricidad**"
→ "…para gastos de conexión"). The gates had partly relied on the reader not
seeing those sentences. It stays opt-in until those are closed.

**An NLI judge** (`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`,
ONNX, CPU) on the hardest pairs (the right sentence with its question vs the
same sentence with its paired trap): AUC 0.75–0.78 for three hypothesis
forms; at a threshold with no trap above it, 7–44 of 162 correct answers
pass. It is fooled by one-word substitutions inside the topic ("crachá" vs
"senha", "bus" vs "aéreos", "requesting unit" vs "supplier") and rejects
informal paraphrases. Rejected as a judge or as a second opinion.

**Rules rejected on the semantic-reading run:** no `ok` without at least two
topic terms (avoids 4 errors, loses 13: "¿cuándo empieza la compra?" has
one); no `ok` with a corpus-absent noun of the lexicon (avoids 1, loses 7:
"biblio", "pc", "geladeira").

**Missing piece found:** nothing produced `necesita_aclaracion`. A question
without topic or antecedent should ask for it instead of reading.

## Third round: clarification and modifiers

**Clarification** (`ipsis/lenguaje/aclaracion.py`, after retrieval, on the
interpreted question, so a follow-up that inherits its topic never triggers
it). It asks for the topic when no content word is left ("¿Cuánto es?"),
when the only content word comes with an anaphoric pronoun of the pack ("Who
approves it?"), or when a question of up to three words has one content word
found in two or more documents, or in none ("¿Cuánto dura?", "¿Cuánto
tarda?"). On every bank it detects the 30 ambiguous questions and fires on no
answerable one. State `necesita_aclaracion`; over HTTP, `no_answer` with
`plan: clarification`, so clients that validate `status` keep working. A
grammatical-category rule from the lexicon was tried first and discarded:
the stemmer joins "tarda" and "tarde", and "aprueba" never matches the lemma
"aprobar".

**Same head, another modifier** (`seleccion.modificador_distinto`): a
question word absent from the corpus that modifies a head the sentence has
("gastos **de** electricidad", "electricity costs"), while the sentence gives
that head another content modifier ("gastos de conexión") — the sentence is
about something else; `s_foco` is capped at 0.5 and the `related` message
names the missing word. Linking prepositions and the English pre-modifier
order are pack data. Offline on the hardest pairs it catches electricity,
energia, bus, train, urine/orina/urina and access card traps; numbers and
generic words are not modifiers. Known cost: synonyms in the modifier slot
("plane" vs "air", "home office" vs "teletrabalho") become `related`.

**Small instruction-tuned judges** (one forward pass, logit YES − NO):
Qwen2.5-0.5B-Instruct fp32, AUC 0.74 at 1.1 s per pair; at a threshold it
admits 6/72 traps while passing 61/162 correct answers. The published int8
exports of 0.5B and 1.5B are broken (their top token is "." or "You"); 1.5B
fp32 is 6.2 GB. Rejected for a CPU product.

| Medium, all banks | Query bank correct | Informal correct | Accepted errors |
|---|---|---|---|
| default, before this round | 68/102 | 10/60 | 2 |
| default + clarification + modifiers | 68/102 | 10/60 | 1 ("…nos feriados") |
| + `semantic_reading` | **72/102** | **16/60** | 2 (+ "derrubei a cafeteira") |

Semantic reading costs +0.8 s at p50 on this 2-thread CPU (reading stage
0.47 → 1.27 s); the chunk-level reranking (2.25 s) becomes partly redundant
with it, which is where that time can be recovered.

## Final state (semantic reading on in medium)

A `costo` intention requiring an amount closed the last regression the
semantic reading introduced ("¿Cuánto cuesta cambiar el filtro?" → "cada 45
días"). Medium, same banks, start of this work → now: query bank 56 → 72/102
correct with 1 → 0 accepted errors, right passage shown 87 → 91; informal
bank 6 → 16/60 with 1 → 2 accepted errors ("…nos feriados", "derrubei a
cafeteira…"), right passage shown 44 → 49. The frozen general regression was
re-recorded: medium keeps 10/12 with no error per quality, light goes from 9
to 10 correct and from 3 to 1 error; medium p95 rises from 0.63–0.96 s to
0.86–1.40 s on the reference CPU.

## Confidence and guarantees (2026-10-09)

Can the reply say how sure it is? Risk-coverage over every case with
evidence (medium, query + informal + guarantee banks, 678 cases): `s_qa`
separates correct from incorrect best (AUROC 0.92), then `s_cov` (0.83),
`s_rr` (0.82), `s_foco` (0.71), `s_ret` (0.68). The reader alone at
`s_qa ≥ 0.99` still errs 12.7 % of the time — the same-topic traps; the
gates bring the risk of direct answers to about 3 %.

A **guarantee bank** (`tests/datos/banco_garantias`: six new documents,
98 answerable and 36 negative questions per language, the query-bank
documents as distractors) was added to narrow the Clopper-Pearson bound.
Medium's direct answers, all banks together:

| | n | correct | observed precision | guaranteed at 95 % |
|---|---|---|---|---|
| before the guarantee bank | 90 | 88 | 97.8 % | ≥ 93.2 % |
| with it | 319 | 308 | 96.6 % | ≥ 94.4 % |
| light, with it | 121 | 103 | 85.1 % | ≥ 78.7 % |

The new bank found errors the old ones did not: 8 of the 11 are
absent-qualifier traps ("beca de idiomas", "moto eléctrica", "nos
feriados", "equipos de sonido"), and 3 answer "who may apply?" with the
document's introductory line ("…para funcionarios"). The banks hold about
15 % same-topic traps, probably more than real traffic, so the per-question
risk is pessimistic. Splitting medium's `ok` into finer tiers is still not
supported: 309 of 319 direct answers meet "full focus and `s_qa ≥ 0.95`".

These numbers define the `confidence_level` of `/ask`: `high` for medium's
direct answers, `medium` for light's, `low` for related passages
(`Motor.nivel_confianza`).

Fixing those patterns with this bank would spend it as design data; a new
held-out bank would then be needed to re-estimate the guarantee.

Latency on this bank exposed a cost the smaller banks hid: with 15
documents retrieval reaches its 20 candidates, and cross-encoder reranking
of long chunks rises from 2.3 s to 4.2 s (p50 5.9 s, p95 7.6 s on the
2-thread reference CPU). Scoring only the first 5 fused candidates
(`rerank_candidates`) kept every answer and brought medium to p50 2.5 s,
p95 4.2 s ([reranker](reranker.md)).

## Fourth round: held-out validation (2026-10-09)

A **validation bank** (`tests/datos/banco_validacion`: six more documents, 99
questions per language, the query-bank documents as distractors) was written
before the fixes below and not inspected while designing them. They were
designed on the guarantee bank, which is now design data.

- **The document's introduction is not read.** In a document with sections,
  semantic reading skips the units under the top-level title only ("Establece
  las condiciones de la beca de perfeccionamiento para funcionarios"): they
  repeat the topic of every section and answer none. "Who may apply…?" is
  read in "Requisitos".
- **Modifier in the section title.** `modificador_distinto` also looks for the
  head in the section titles of the sentence: "beca **de idiomas**" against
  "Bases de la Beca **de Perfeccionamiento**". A conflicting modifier must not
  be a word of the question. Plain adjacency without a preposition ("moto
  elétrica" vs "veículos elétricos") was measured and discarded: it cost 10
  correct answers ("carro elétrico", "espacio libre", verbs like "take") for
  2 traps.
- **Indefinite pronouns are generic** ("someone", "anyone", "alguien",
  "alguém"): "What happens if someone parks without a permit?" is answered
  with "Anyone who parks…".
- **Strong reader tier** (`ok_strong` 0.99, `oov_ok_strong` 0.67 in medium;
  [policy](policy.md)). In 35 of the 41 informal questions shown as `related`
  the shown passage had the answer; with the reader `s_cov` is not a gate, the
  blocker was `s_oov ≥ 0.6` from colloquial words the corpus lacks. With the
  reader nearly sure and full focus, `s_oov < 0.67` is tolerated: +10 correct
  and 0 errors on the design banks; every error near the cut sits above 0.67
  or below 0.99.

| Medium | Design banks: correct / errors | Informal bank | Validation: correct / errors | Precision | Guaranteed at 95 % |
|---|---|---|---|---|---|
| before | 308 / 11 | 16/60 | 146 / 9 | 94.2 % | ≥ 90.1 % |
| after | 322 / 7 | 21/60 | 146 / 4 | **97.3 %** | **≥ 94.0 %** |

On the validation bank the false answers to traps went from 6 to 1; the
correct answers did not change, and its paraphrases stayed at 23/69 direct
(the rest mostly `related` with the right passage). The strong tier helped
the design banks' informal questions but none of the validation bank's: the
informal coverage gap is the open problem. Both validation measurements were
aggregate only; a design that reads its failures spends this bank too.

### Pronouns and the limits of WordNet (2026-10-09)

Of the content words of 261 paraphrases that the corpus lacks, 1 is a typo
("pasword"), 173 are real words the documents do not use ("plata",
"aguanta", "anota", "logs", "fridge") and 38 neither. Portuguese personal
pronouns ("eu", "minha", "numa") were among the latter: added as stopwords
(+2 correct, no new error), the 38 drop to 14.

WordNet does not close the vocabulary gap. The automatic expansion only uses
single-sense lemmas, and everyday words are polysemous ("plata" 4 senses,
"anotar" 7, "keep" 25): it fired on none of 678 questions. Letting the corpus
pick among all senses was measured offline and rejected: it maps "orina" →
"piso", "dinheiro" → "cobre", "moto" → "apelaciones", and fires on 35
negative questions for 36 answerable ones.

### Curated everyday equivalences (2026-10-10)

The packs' `sinonimos` groups already reach `s_oov` and the focus terms: an
absent word is replaced by the member of its group that the corpus has. They
only held formal verbs ("necesita"/"requiere"). Everyday equivalences valid in
any office document were added and pruned on the design banks: a group goes if
it costs answers or turns a trap into an answer. "biblio ↔ biblioteca" exposed
the holiday trap; "software ↔ programas" made "programas" a focus term the
answering sentence lacked; "buy ↔ purchasing" answered "Who authorizes buying
software licenses?". Kept groups: design banks +5 correct, no new error.

A **colloquial bank** (`tests/datos/banco_coloquial`: 24 informal paraphrases,
4 traps and 2 out-of-domain questions per language, over the validation
bank's documents) was written before the curation and measured once before and
after, in aggregate:

| Medium, colloquial bank | Before | After |
|---|---|---|
| Direct and correct (of 72) | 18 | 18 |
| Errors among direct answers | 3 | 3 (one false `ok` became a direct answer without the literal) |

The lists did not generalize: colloquial vocabulary is open, and a short list
covers only the words it names. After the change, of the 72 answerable
informal questions 18 are answered directly and **38 more show the right
passage as `related`**, with the confirmation question: 78 % see the answer.
The open lever is not more vocabulary but deciding `ok` with less lexical
evidence, which needs a signal beyond words (the reader alone admits traps).

### Support verbs (2026-10-10)

Testing with real documents, "¿Qué requisitos debo cumplir para inscribir la
Práctica Profesional I?" ended as `related` with the right passage and the
reader at 1.0: "cumplir" counted as a focus term and the answering sentence
does not contain it. Support verbs (wanting, knowing, meeting a requirement)
are a closed class per language, unlike colloquial vocabulary, so they go to
the packs' generic words. Deciding it from the part of speech in WordNet was
examined and rejected: stems mix nouns and verbs ("contrato", "práctica",
"cover"), and content verbs ("cubre", "devolver") must keep counting, or
"who signs?" traps pass. Design banks: +1 correct ("where do we meet if we
evacuate"), no new error. Words of one installation's domain belong in its
`config/domain.yaml`, and the document-dependent lever is calibrating
`focus` with the project's golden set.

## Open

- Related answers end with a `related_check` question ("Is this what you were
  looking for? If not, tell me in other words…"): for an informal user who
  gets the right passage as `related`, the reply invites confirmation or a
  rephrase instead of stopping at "not a direct answer". No signal changes.
- Light cannot say `ok` to most colloquial questions: without a reader its
  only evidence is lexical coverage. It still shows the right passage as
  `related` for most of them.
- Same-topic traps with an absent qualifier that is not a modifier remain
  the residual risk of `medium` ("…abre nos feriados", "moto elétrica" when
  the documents say "veículos elétricos"), and polar questions
  answered with the opposite clause ("derrubei a cafeteira, a garantia
  cobre?" → the coverage sentence instead of the exclusion). A per-project calibration of `τ_oov_ok` and
  `τ_foco` with the golden set's informal questions is the supported lever.
- Irregular inflections ("keep"/"kept") and colloquial synonyms ("plata",
  "me pasan") need lexical resources the packs do not have.
