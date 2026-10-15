# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project follows [SemVer](https://semver.org/). While the version is 0.x,
a minor change may break compatibility and is marked as such.

## [Unreleased]

### Added

- `retrieval.header_detail: extended` (with `with_header: true`): the embedded header gains a
  second line with the data types (deadline, amount, date...), condition and exception the
  fragment contains, in es/en/pt. Cited text and offsets are unchanged; the default is `basic`.
- `CH-F256S` chunking strategy: fixed size that never crosses a section, never
  exceeds 256 words (except a single longer sentence) and overlaps by whole
  sentences. Opt-in; `CH-F256` and the defaults are unchanged. On the passage
  bank corpus `CH-F256` produces 56 of 97 fragments that span more than one
  section; `CH-F256S` produces none.

## [1.0.0] - 2026-10-13

### Fixed

- HTTP presentation now accesses theme content through the application layer,
  restoring the architecture contract enforced by CI. Service checks validate a
  minimum of 100 message variants instead of rejecting larger catalogs.
- CI checks the fixed-question catalog independently from message variants,
  and runs real Chromium widget and panel tests before release.

### Changed

- CLI help now includes service examples, inventory loading and the demo/admin
  workflow. `ipsis help` accepts nested command paths and interactive `/help`
  shows command options without unloading the engine. Help skips configuration
  migrations. English and Spanish READMEs document default v2 search, source
  review and continuation, with the previous v1 rules and measurements labeled.

- Source reading now separates paragraphs and declared headings, applies the
  theme's justified alignment and renders verified DOCX/Markdown cells as
  accessible tables with horizontal scrolling. Empty columns remain visible;
  prepared DOCX tables retain merged cells. Original literal text stays
  available for comparison. No table layout is guessed from arbitrary pipes.

- V2 is now the default query engine in project templates, configuration
  loading (including old files without a selector) and the engine factory.
  Explicit `pipeline: v1` remains supported. The default output is ranked
  literal sources with continuation, without v1 focus rules or calibration.
  Project model downloads and doctor checks omit unused QA models in v2.
  Selecting an engine alone reuses the existing index.

### Added

- At least 100 recognized fixed questions per language in Spanish, English and
  Portuguese, covering ten assistant topics. FAQ matching uses complete inputs;
  mixed document queries still retrieve sources. The widget exposes a topic
  selector and fills queries without sending them automatically.
- Nine visual presets, including ocean, forest and midnight; card, divider and
  editorial result layouts; independent heading and section typography/colors;
  dark palettes, result numbering, context controls and editable welcome text.
- Visible loading progress and staggered transitions for new source cards,
  respecting disabled animation and reduced motion. Guidance uses two lines
  with optional expansion; help actions open an overlay menu to preserve reading
  space. Scrollbars are slim, rounded and adapt to the theme.
- Interactive offline previews reuse the real widget. English and Spanish
  READMEs, reproducible screenshots and package metadata now describe the
  default source router. V1 golden datasets and calibration are optional legacy
  tools, separate from assessing v2 source relevance.

- Runnable widget integrations for Astro, Svelte 5, Angular 20 and Python /
  FastAPI, alongside HTML, React and WordPress. English and Spanish guides
  document setup, CORS, public keys, embedded mode, SSR and persistent layouts.
  The React adapter loads the widget once, including under Strict Mode and
  callback updates.

- Inventory retrieval from XLSX, XLS, CSV and TSV, including admin uploads.
  Each row is indexed with its column labels without mixing neighboring
  products. Native source tables retain sheet/row/cell locators, empty fields,
  zero values and simple leading-zero number formats. Structural preparation
  accepts these formats. Formula results are read as saved, never recalculated.
- `ipsis serve --demo` serves a themed page with the embedded live widget;
  `--open` opens it when available. Demo and admin link to each other when
  enabled, without changing admin authentication or the service mode.
- Enter resolves unique partial command names and close misspellings in the
  shell and interactive terminal, including nested commands. Corrections are
  shown; ambiguous matches do not execute. Arguments and options are untouched.

- Search-style v2 presentation with a top query field, visible source titles
  and excerpts, literal query highlights, expandable context and one growing
  results list. New `search` and `search_compact` themes include offline previews.
  New queries replace the list; continuation appends new sources.

- V2 scores compact retrieved passages progressively within a query work
  budget (2500 ms by default). Unscored sources remain available; continuing
  scores only pending candidates, while cursor retries preserve their page.
  Optional HTTP deadlines reduce the server budget. Running ONNX inference
  is not interrupted. Default batches use two passages and 256 tokens.

- V2 routes queries to up to three ranked sources per page with search continuation,
  literal context, source
  offsets and an expandable result card in the widget. Publication is independent
  of QA, which is disabled by default in v2. Context expands after ranking within
  document/section/version boundaries, preserving scores and marking truncation.
  The experimental reranking council and its comparator were removed after the
  CPU comparison; configuration 7 migrates its retired settings automatically.

- CPU-only query pipeline v2, selected with `engine.yaml::pipeline`,
  with configuration migration 7 preserving explicit engine selections. A common engine
  contract and output adapter allow switching implementations in the factory.
  V2 reuses hybrid retrieval, spelling correction, ONNX reranking/QA and literal
  verification; it reads source chunks without v1 intent/focus rules or inherited
  topics, retains surrounding evidence and records each stage. Offline paired
  comparison runs on isolated copies and exports full answers and traces.
  V2 is the default source router; broader quality evaluation remains pending.

- Experimental DOCX preparation with canonical text, XML/cell references,
  empty and merged cells, source parents and searchable children. The v2
  reranker retains declared section context; tables offer mapped field/value
  contexts for QA while published evidence stays literal. Search/reranking
  retain their earlier representation after a field-format variant regressed.
  `ipsis prepare` creates an independent project and an escaped HTML preview,
  with optional indexing in a separate local collection that refuses recreation.
  Parser, structure, fragmenter and store fingerprints prevent mixed-version
  references. Unsupported structures produce notices. Table reading includes
  external headers with cell references; structured answer rendering remains pending.

- V2 has independent, validated retrieval/reranking/reading budgets (60/60/8/4
  by default) and reader windows. QA can suggest highlights with source maps
  but cannot replace passage ranking or certify a complete answer. Retrieved
  evidence remains `related`; optional API highlights preserve disjoint references
  without inventing contiguous source spans. V1 behavior and defaults remain unchanged.

- Query log version 2 records complete answers, diagnostics and original
  execution traces: stage inputs/outputs and skips, admission, every retrieval
  with candidates and filters, and exact reranker/reader inputs and outputs.
  Project traces include the effective profile and corpus/configuration
  fingerprints; failures retain partial traces without exception messages.
  `ipsis audit --trace <consulta_id>` inspects a recorded case without models
  or corpus access. Logging remains opt-in and version 1 logs remain readable.

- **Terms graph built at indexing:** the index stores the groups of
  equivalent names each corpus defines (`alias` in `.stats.json`): acronyms
  ("Práctica Profesional I (P1)"), short glossary definitions ("P1: primera
  práctica profesional del plan") and "en adelante / hereinafter /
  doravante" referents. Ordinals and Roman numerals are normalized ("primera"
  = "I" = "1"). A question that names a group in another way searches with
  all its forms, the focus recognizes the group in the sentence or its
  section title ("Evaluación de la P1"), and a different ordinal ("la tercera
  práctica" against the P1) sets the focus to 0 (`ordinal_distinto`). Never
  a hand-written list: every installation gets the groups of its own
  documents. A new `duracion` intent ("¿cuánto dura…?", "how long is…")
  requires a time unit in the answer, and glossary definition lines are only
  read for definition questions (`patrones_definicion`). New terms bank
  (`tests/datos/banco_terminos`, design and held-out validation).
- **Table rows keep their header:** the parser adds the table header as the
  last section level of each data row, so the focus sees "Pieza | Vida útil"
  framing "Filtro | seis meses". The row text and its offsets are unchanged.
- **The shown passage is the window the reader read:** in medium's semantic
  reading, when the window starts with the previous sentence of the line, the
  shown passage starts there too ("…antes del inicio de dicho período" comes
  with the sentence naming the period). Decisions are unchanged; the slice is
  literal (`ventana_mostrada`).

- Terminal progress with real ingestion and query stages, elapsed time,
  cancellation and separate output for answers and citations. Folio now has
  a folded corner and larger eyes; narrow and legacy terminals have fallbacks.
- A uv-only Python installation workflow: automatic Python and isolated tool
  management, a committed development lockfile, uv-based CI and Docker, and
  matching installation instructions in the CLI and both READMEs.

- Six pinned multilingual CPU/ONNX alternative models: Granite 311M/97M R2,
  Harrier-270M, EmbeddingGemma 2 (text only), Horizon base/small. Runtime
  supports model-specific pooling, padding, named embeddings and external
  weights. They are selected through `profile_overrides` on top of medium;
  none added a correct answer over medium in the measured Spanish bank.
- Frozen general regression bank: four topics/formats, three formatting
  qualities, 84 cases, full-answer/source verification, per-case guards,
  latency reports, model revisions and effective configuration. Run
  `python herramientas/evaluacion/general.py --download`; automatic CI and
  model-backed pytest integration accompany the reference.
- Project model overrides now drive indexing as well as querying; prepared
  Docker images read those overrides when downloading model weights.

- **Larger alternatives bank and round-5 weights:** 128 cases per language
  (from 58: an office catalog, a delivery and warranty policy, premises on
  measures and hard negatives in dev and test) and a new held-out validation
  of 20 per language. New signal `medida` (core-measure family with a shared
  word, weight 0). Calibration now weighs `familia` 1 and `terminos` 2
  (threshold 0.5): without a family, a line with three quarters of the
  question words is offered. Development: precision 0.98, coverage 129/136
  (was 30/44); held-out validation measured once: precision 1.0, coverage
  30/32 (light) and 32/34 (medium), no out-of-domain or hard-negative
  alternatives.

- **Proactive posture ([ADR 0008](docs/decisions/0008-proactive-posture-and-metadata-similarity.md)):**
  after a false premise or a question without an answer, `no_answer` can
  carry up to `posture.max_alternatives` (3) similar literal lines from the
  documents, cited and verified, under the new tone situation
  `alternatives_intro` (7 tones × es/en/pt, 162 variants per tone). The state
  does not change: alternatives travel in `alternatives` of `/ask`; the
  widget shows them with their citations. Affinity is a weighted mean of
  metadata signals (entity family, question words, section, keywords,
  category, dense similarity); the shipped profiles weigh only the family
  of a missing entity whose type `domain.yaml` declares ("TP-400" for
  "TP-500"). `posture.mode: strict` restores the previous replies;
  `ipsis ask --diagnostics` lists offered and discarded alternatives. New
  bank `tests/datos/banco_alternativas` (58 + 16 held-out cases per
  language): precision 1.0 and no out-of-domain alternatives in development
  and validation after the fourth round; the first held-out run (0.87/0.85)
  failed the 0.9 bar and removed core-measure families. The query,
  universal and conversation banks keep every state and rule.
  [Measurements](docs/methodology/mediciones/v5-alternativas/README.md).

- **Follow-up extraction corrections:** retain opening-topic terms outside
  the core for one follow-up and preserve their original order. Determine
  intentions from the current question and use it for reading when it
  expresses a relation or multiple content terms; bare qualifiers retain
  inherited context. Actor questions isolate the matching
  sentence; literal QA boundary completion retains quantity units, limits
  and reference points, or the selected actor's matching action clause.
  Preserve raw model spans and offsets in diagnostics. Add language-declared
  compatibility for end/procedure fallback without lowering cosine/margin
  or answer thresholds. Lexical behavior v5 invalidates stale calibrations.
  [Correction measurements](docs/methodology/mediciones/v4-correcciones/README.md)
  retain the initial V4 defects and each development round separately.
  Recover all eight targeted turns with no lost correct answers or new
  direct errors against F1 and initial V4 in the three banks. All 1,072 tests
  pass with two skips; paired light latency satisfies G5 against both bases.
  Existing medium reader errors in independent queries remain documented.

- **Initial V4 validation (`b23ad8a`):** 1,054 tests pass with two skips; the three evaluation
  banks and paired latency measurements satisfy G1–G6. Conversation topic
  inheritance improves, while four literal answers regress against F1 and
  five newly direct positive answers have incomplete or incorrect selected
  spans, including two wrong roles in `medium`. Secondary banks also expose
  mistaken intent labels. Preserve these limits, raw results and rejected
  measurements in the [V4 report](docs/methodology/v4-results.md).

- **Intent similarity fallback:** ten independent examples per intention in
  es/en/pt, encoded once at startup. Reuse the query vector for unknown
  intentions with corpus topic; require measured cosine/margin and categories
  with correct dev fallback cases. Patterns win; BM25 and unmeasured models
  skip it. Preserve focus terms and answer thresholds. Diagnostics expose
  origin, candidate, cosine, margin and rejected attempts. Example/threshold
  changes invalidate previous lexical calibrations.
- **Verified conversation context:** record vocabulary of the first cited
  source passage after final verification, excluding other candidates and
  out-of-domain turns. Reject stale concurrent evidence, discard obsolete
  surface forms and expire sessions at the exact configured boundary.
- **Separate topic and answer terms:** `genericas_memoria` keeps
  `tiempo/tempo` out of topic recognition without removing their original
  weight from answer focus and selection. The F1 comparison caught a lost
  correct answer when those words were treated as globally generic; retain
  the failed measurement and validate the correction separately.

- **Offline lexical retrieval:** load the filtered es/en/pt WordNet tables
  once per language/stemmer and expand only OOV content words with a single
  sense. Preserve source/synset/POS in diagnostics. Automatic groups expand
  BM25 while retaining the original dense vector and acceptance signals.
  Project `domain.yaml::synonyms` takes precedence, with complete phrase
  matching for abbreviations. Effective lexical hashes invalidate stale
  calibrations; older files without the hash require recalibration.
- **Literal evaluation:** count the QA reader's selected span, rather than
  a correct fact elsewhere in its enclosing evidence. Apply the same rule
  in query/conversation coverage and calibration risk estimates.
- **HTTP regression references:** refresh historical snapshots from the
  working tree before lexical integration after confirming identical
  before/after responses in both profiles. Record previous confidence and
  related-evidence changes, including Sunday queries moving from no answer
  to related before this integration; retain the original score tolerance.

- **Extended dictionaries for all supported languages:** complete frozen
  Kaikki/Wiktionary es/en/pt downloads expand the combined inventory to
  3,635,200 written forms/expressions. Archive original gzip bytes losslessly
  in parts and retain verified lexical projections for offline rebuilds.
  Separate compressed indexes distinguish lemmas, inflections, alternatives
  and legacy membership; preserve morphology and directed synonym records
  with original sense identities and qualifiers. No automatic runtime loading.

- **Development synonym converter:** pinned MCR/OMW Spanish, Open English
  Wordnet 2025 and OpenWN-PT/OMW sources with verified downloads, synset/POS
  preserving TSV conversion, conservative polysemy filters, original notices
  and deterministic per-language manifests. Approved original sources are
  stored losslessly in the repository; rebuilds are offline by default, with
  explicit `--download` only for source updates. Full lexical tables preserve
  272,979 written forms/expressions across es/en/pt; filtered tables retain
  67,365 words with senses kept separate. Derived files and notices ship in
  wheel/sdist; sdist also includes the originals and converter. Automatic
  filtered tables support conservative BM25 expansion in the answer engine. See ADR 0007 and
  `herramientas/sinonimos/README.md`.

- **Broader stored vocabulary:** four pinned LibreOffice/MyThes thesauri
  add 110,886 distinct written forms/expressions, bringing the combined
  es/en/pt inventory to 383,865. Preserve directed records, original
  labels, relation annotations and per-form provenance; archive original
  downloads and notices for offline rebuilds. Existing filtered WordNet
  groups remain separate. Runtime activation still requires evaluation.

- **Deterministic query understanding** ([ADR 0005](docs/decisions/0005-deterministic-query-understanding.md)):
  the language packs (es, en, pt) declare intentions (threshold, start, end,
  consequence, person in charge, requirement, procedure) with patterns and
  answer cues. The relation's words ("when… start") no longer count as
  missing topic; among sentences on the topic, one with a cue ("Once the
  form is approved…") is preferred by the selection and the reader window;
  and the reader also reads the candidate with the best cued sentence when
  the reranker left it out (even outside `rerank_k`). "cuando empieza la
  compra?" now gets its literal answer. Query bank: `light` 5 → 9 and
  `medium` 7 → 11 correct answers,
  with no new false `ok`; the universal bank loses nothing, gains one exact
  answer in `light`/en and has no new false `ok`.
- **Follow-up questions:** "and with 90?", "and if they accept it?" or "and
  what does it cover?" inherit the topic of the previous turn in the same
  session (in memory, per session), so they can be retrieved and answered. A
  question with a topic of its own never inherits, and the answer must still
  contain what the user asked now. See ADR 0005.
- **Synonyms for words missing from the corpus:** each language pack has
  groups of synonyms; a question word that is not in the corpus
  ("necesita") is searched and measured as its synonyms that are
  ("requieren"). Words of the asked relation are left to the cues. See ADR
  0005.
- **`ipsis ask --diagnostics` shows where each candidate is won or lost:**
  its place in the dense, BM25, fusion and reranker rankings, the QA
  reader's probability and the best scored sentences.
- **Natural queries bank** (`tests/datos/banco_consultas`) in Spanish,
  English and Portuguese: 60 cases per language on four institutional
  documents (manual, regulation, FAQ, policy), written as each language
  would ask them, with every category of the universal bank.
- **Conversations bank** (`tests/datos/banco_conversaciones`): 20
  conversations per language that measure topic inheritance turn by turn,
  deliberate topic changes and traps inside a follow-up.

- **OCR for scanned PDFs (optional):** `pip install "ipsis[ocr]"` plus the
  Tesseract program. Pages without text are rendered and read with
  Tesseract in the project language (plus English). `ipsis load` and
  `ipsis index` show each page as it is read with its confidence (average
  over its words), list the files read with OCR and flag pages under 85 %.
  What `load` reads is cached in `.ipsis/ocr`, so `index` reuses the same
  text. Without OCR, the scanned PDF is rejected as before and the message
  says what to install. `IPSIS_OCR=off` turns it off.
- **`answer_blocks` in `POST /ask`:** the answer by paragraph, so a site can
  render it with structure. Each block has a `type` (`lead` for the tone's
  opening or intro, `passage` for literal document text, `message` for
  abstentions and conversational replies), `text`, and, for passages,
  `connector`, `citation` and `chunk_id`. Joining them reproduces `answer`.
  The widget renders one paragraph per block, with the connector and the
  citation in a softer color.
- **`presentation.text_align` in `styles.yaml`:** `justify` (default) or
  `start`. Justified applies only to document passages and citations, with
  hyphenation in the assistant's language; `/config` now also returns
  `text_align` and `language`.

- **Related answers close with a question:** after the passages, a
  `related_check` tone message (21 packs) asks whether that is what the user
  wanted and invites rephrasing. Most colloquial questions end as `related`
  with the right passage; the reply no longer stops at "not a direct answer".
- **Clarification:** a question that does not say what it is about
  ("¿Cuánto es?", "Who approves it?", "¿Cuánto dura?" with several documents)
  gets the `necesita_aclaracion` state and a `needs_clarification` tone message
  (21 packs) instead of an answer; over HTTP it is `no_answer` with the new
  `plan` value `clarification`. Packs declare `pronombres_anaforicos`.
  Detects the 30 ambiguous questions of every bank and fires on no answerable one.
- **Same head, another modifier:** "gastos de electricidad" is no longer
  answered with "gastos de conexión" (`preposiciones_modificador`,
  `modificador_antepuesto` in the packs; diagnostic `modificador_distinto`).
- **Semantic reading** (`cascade.semantic_reading`, on in medium; `false` in
  `profile_overrides` restores the lexical window): the reader reads the sentences ranked first by a fusion of
  cross-encoder, dense cosine and `s_lex` instead of a word-overlap window.
  Medium 68 → 72 correct on the query bank and 10 → 16 on the informal bank;
  with clarification and the modifier rule, one extra accepted error and
  +0.8 s at p50 on a 2-thread CPU; see
  [informal paraphrases](docs/methodology/informal-paraphrases.md).
- **Faster medium:** the reranker scores only the first 5 fused candidates
  (`cascade.rerank_candidates`; all of them before). Same answers on 678
  questions (308 correct, 11 errors), p50 5.3 s → 2.5 s and p95 7.3 s → 4.2 s
  on a 2-thread CPU with a realistic corpus; see [reranker](docs/methodology/reranker.md).
- **Confidence level** (`confidence_level` in `/ask`: `high`, `medium`,
  `low`): high for a direct answer read by the QA reader (medium, 96.6 %
  correct on 319 direct answers, guaranteed ≥ 94.4 %), medium without a
  reader (light, 85.1 %; the widget shows "Check the citation"), low for a
  related passage. Derived from state and profile; `ipsis ask --diagnostics`
  shows it.
- **Guarantee bank** (`tests/datos/banco_garantias`, 134 questions × es/en/pt
  over six new documents) to narrow the risk bound of direct answers: medium
  96.6 % correct on 319 direct answers across banks, guaranteed ≥ 94.4 % at
  95 %; see [informal paraphrases](docs/methodology/informal-paraphrases.md).
- **Validation bank and fourth round** (`tests/datos/banco_validacion`, 99
  questions × es/en/pt over six more documents, written before the fixes):
  semantic reading skips the introduction of a document with sections;
  `modificador_distinto` also checks the section titles ("beca de idiomas" vs
  "Beca de Perfeccionamiento"); "someone"/"alguien"/"alguém" are generic; a
  strong reader tier (`ok_strong` 0.99, `oov_ok_strong` 0.67 in medium, kept
  by calibration, removed by deleting both) answers informal questions with
  colloquial words when the reader is nearly sure. Medium, measured once on
  the validation bank: errors 9 → 4 with the same 146 correct, 97.3 %
  precision, guaranteed ≥ 94.0 % (was ≥ 90.1 %); design banks 308 → 322
  correct, 11 → 7 errors, informal bank 16 → 21 of 60. See
  [informal paraphrases](docs/methodology/informal-paraphrases.md).
- **Personal pronouns in the packs:** Portuguese had no first- or
  second-person pronoun among its stopwords ("eu", "minha", "você", "numa");
  they are added, with "te", "usted", "conmigo"… in Spanish and "myself",
  "yours"… in English, and the forms of ir/vir/ter/dar/estar ("vou", "tiver",
  "der", "viene") become generic. Design banks: +2 correct (Portuguese
  informal questions), no new error.
- **Support verbs are not topic:** "cumplir", "quisiera", "saber" (es),
  "meet", "fulfil", "like", "know", "want" (en) and "cumprir", "gostaria",
  "saber" (pt) are generic words: "¿Qué requisitos debo cumplir para
  inscribir…?" failed the focus because "cumplir" counted as a topic word
  missing from the answering sentence. A closed class per language, valid for
  any corpus (domain words go in `config/domain.yaml`). Design banks: +1
  correct, no new error.
- **Colloquial focus tier:** a question written colloquially (lowercase
  start, in Spanish without «¿», or an informal abbreviation of the pack:
  `ipsis.lenguaje.estilo`, new pack field `abreviaturas_informales`) with the
  reader at `ok_strong` needs half of the focus terms (`focus_informal` 0.5
  in medium). The style travels in the stored signals, so calibration uses the
  same rule. Medium: held-out colloquial bank 18 → 36 of 72 answered directly
  (errors 3 → 5); held-out validation 148/4 → 165/5 (97.1 %, guaranteed
  ≥ 93.9 %); design banks +19 correct, +1 error.
- **Interactive terminal in the style of Claude Code:** `ipsis` alone (in a
  real terminal) opens it, with Folio and the project of the folder; typing
  `/` unfolds every command with its description, `Tab` shows subcommands and
  options with their help and completes paths after `/load`, with history and
  a bottom bar. Built from the CLI parser (a new command appears by itself),
  on `prompt_toolkit` (new dependency, BSD); without a terminal `ipsis`
  prints the menu. The README documents `uv tool install` / `pipx install` to
  use `ipsis` without activating a Python environment.
- **Terminal menu and interactive mode:** `ipsis` with no arguments (or
  `ipsis help`) prints the commands grouped by task, with examples;
  `ipsis help <command>` prints one command's options. `ipsis chat` is an
  interactive mode in the style of Claude Code: questions go to the project
  engine, loaded once, keeping the conversation topic; `/help`,
  `/diagnostics on|off`, `/reload`, `/exit` and any ipsis command as
  `/command` (`/doctor`, `/index`, `/load ./docs`).
- **`/admin` panel: Status and Documents tabs.** `GET /admin/status` (profile,
  index, calibration, thresholds in force with their source, documents and
  the `ipsis doctor` checks), `PUT /admin/thresholds` (writes
  `profile_overrides.default_thresholds` and reloads the engine),
  `GET`/`POST /admin/documents?name=` (upload up to 20 MiB, same path as
  `ipsis load`), `POST /admin/reindex` and `GET /admin/task` (background
  reload; `/ask` answers 503 meanwhile). Same token, HTTPS and lockout rules.
- **README rewritten as the manual:** what ipsis is (package + CLI + HTTP
  service; Docker only to deploy; no Python library API), every command, the
  project files, the current flow and layers with their techniques, the web
  interfaces, examples of loading documents, customizing and changing
  thresholds, and what calibrating with your corpus is for.
- **Typo normalization layer** (`ipsis/lenguaje/ortografia.py`): a
  SymSpell-style symmetric-delete index over the corpus forms and stems
  replaces the pass over the whole vocabulary, and the corrector now also
  compares stems ("covran" → "cobra" when the corpus has "cobra" but not
  "cobran"), corrects 4-letter words, splits joined words ("abreel" → "abre
  el") and joins split ones ("estacio namiento"). It never touches real words,
  proper nouns, acronyms or words of the synonym groups. New typo bank
  (`tests/datos/banco_erratas`, generated from existing questions): robustness
  (correct answers kept with typos) 81 → 90 % on design and 91 → 97 % on the
  held-out set, new errors from typos 5 → 3; clean questions unchanged. See
  [lexical](docs/methodology/lexical.md#typos).
- **Typo context from word pairs:** the index stores the pairs of
  neighbouring content words (`pares` in `.stats.json`, as presence, never
  frequency, and from the chunk text without the prepended title, so repeated
  titles or footers gain no weight). A real word absent from the corpus is
  corrected only if the pair exists with both neighbours ("paring permit" →
  "parking permit"); a non-word, with one. A self-test at indexing enables it
  (`contexto_erratas`) only if it recovers typos in the corpus's own
  sentences. Measured: no change on any bank (robustness 89.6 % / 96.6 %,
  clean banks identical); older indexes work without it until rebuilt.
- **Everyday equivalences in the packs** (`sinonimos`: plata ↔ dinero ↔
  monto, demora ↔ tarda, refri ↔ refrigerador, clave ↔ contraseña, fridge ↔
  refrigerator, boss ↔ manager, avião ↔ aéreo, gente ↔ pessoas…): they act only
  when the question's word is missing from the corpus. Groups that cost answers
  or turned a trap into an answer on the design banks were removed (biblio,
  software, deposita, mean, dinheiro, buy). Design banks +5 correct, no new
  error; the new held-out colloquial bank (`tests/datos/banco_coloquial`, 30
  questions × es/en/pt) did not move: 18 of 72 informal questions answered
  directly, 38 more shown as `related` with the right passage.
- **Informal questions:** a held-out informal bank
  (`tests/datos/banco_informal`, 32 questions × es/en/pt with typos,
  abbreviations and slang over the query bank's corpus). Typos are corrected
  against the corpus vocabulary before analysis ("pasword" → "password"),
  never into a real word of the language lexicon; `ipsis ask --diagnostics`
  shows them. A `frecuencia` intention ("¿cada cuánto…?", "how often…?",
  "a cada quanto…?") requires a period in the answer (`exige_pista`), and a
  `costo` intention ("¿cuánto cuesta…?") requires an amount (`entidades_pista:
  [monto]` or a currency word). See
  [informal paraphrases](docs/methodology/informal-paraphrases.md).

### Removed

- **Breaking: the `heavy` profile is removed** ([ADR 0003](docs/decisions/0003-onnx-and-profiles.md)).
  Installable profiles are now `light` and `medium`. Neither the original
  heavy (e5-base + BGE, 30/8/4: 21/34 correct, two accepted errors, p95 17 s)
  nor any of six newer candidates beat medium (25/34, zero errors): every
  variant got the same 25 answers, because with `retrieve_n=20` the reranker
  already sees the same passages whatever the embedding. A project whose
  `assistant.yaml` says `heavy` loads as `medium`; `ipsis profile show` asks
  for `ipsis index` if its index used another dense model. `ipsis init
  --profile heavy`, `profile set heavy` and `models download --profile heavy`
  are rejected. The model variants of `herramientas/evaluacion/general.py`
  are now `medium+<variant>`, and the general regression reference drops its
  heavy rows (six jobs instead of nine).

### Changed

- **Focus and language packs for paraphrases** (ADR 0005): the reader's
  evidence names the subsection of its sentence (it carried the chunk's
  top-level section, so a FAQ heading never counted for the focus); the
  previous sentence of the paragraph counts for the focus; question
  quantifiers ("quantos", "often", "long") and "tiempo/tempo" are generic
  words; informal abbreviations ("q", "pa", "pra", "vc", "u", "ur") and
  English contraction pieces ("don", "t") are stopwords. Medium: 56 → 68
  correct answers on the query bank (es/en/pt), 6 → 10 on the informal bank,
  no new accepted error. Light: 27 → 33 and 2 → 3. The lexical fingerprint
  changes: existing calibrations must be regenerated (`ipsis calibrate`).

- **A direct answer needs every focus term in its sentence** (`focus`
  threshold 0.5 → 1.0 in every profile). "¿Quién aprueba el pago… en
  Finanzas?" was answered with a sentence about the payment that does not
  say who approves it; it is now `related`. Support verbs and units
  ("hacer", "días"; the pack's `genericas`) are no longer focus terms nor
  count in the sentence selection. Query bank: direct but wrong answers 4 → 2
  in `light` and 1 → 0 in `medium`, no correct answer lost; the universal
  bank does not change. See ADR 0005. Projects with a `calibration.yaml` keep
  their calibrated value.
- **Query understanding measured and adjusted in English and Portuguese:**
  derived nouns count for the focus ("signature" for "signs", "assinatura"
  for "assina"), the pack's synonyms count when checking the focus ("need" /
  "require"), and the relation's words no longer pull the selection to a
  sentence that merely contains them ("…starts a new purchase" for "when
  does the purchase start?"). See ADR 0005.
- **Conversation memory** ([ADR 0006](docs/decisions/0006-conversation-memory.md)):
  follow-up questions inherit the topic of the whole conversation, not only
  of the previous turn. A question can return to an earlier topic ("back to
  the allowance, and abroad?"), an out-of-domain question in the middle does
  not break the thread, and a deliberate change of topic never inherits.
  Conversations expire after `conversation.expiry_minutes` without
  questions (30 by default, `engine.yaml`) instead of only dropping the least
  used session. Conversations bank (light): inherited correctly 26 → 36
  (es), 25 → 35 (en), 21 → 34 (pt) of 38, with no wrong inheritance.
- **The widget starts a new conversation on every page load** (it no longer
  keeps the `session_id` in `localStorage`): the server no longer remembers a
  topic the person no longer sees after a reload.
- **`ipsis ask --diagnostics` shows the query understanding:** the
  recognized intention, the synonyms used, what the turn did with the
  conversation and the interpreted question.
- **Numbered labels stay with their sentence:** "Artículo 4." or "4.2." is
  no longer split off as a sentence of its own, so answers and citations
  show "Artículo 4. Si el cliente no está…" and the label counts for the
  focus. The title of the evidence's section also counts for the focus.
- **Folio, the default avatar, now matches the logo:** the paper's
  proportions and outline, the folded corner as a triangle, two lines of
  text and larger pill-shaped eyes. Expressions are much more marked (eyes in
  an arc in `happy`, drooping in `sorry`, one open and one half-closed in
  `unsure`), and there are four new ones: `look-left`, `look-right`,
  `curious` and `wink`, used at rest, while typing and in greetings. The
  event keys do not change.
- **Widget icon:** the launcher and the header show the ipsis logo in
  miniature instead of a chat bubble (colors in `--rw-folio-*` variables).
- **Smoother widget motion:**
  - the panel grows from the launcher's corner and shrinks back into it
    when closing (it used to vanish at once);
  - the launcher's paper and close icons cross with a turn;
  - messages rise in with a light scale, and an answer reveals paragraph by
    paragraph before its citations;
  - the typing dots fade in, the list scrolls smoothly, the send button
    "flies" when a question is sent, and the field gets a focus ring.

  Everything respects `prefers-reduced-motion` and
  `animations.enabled: false`. New projects get the new durations
  (`.34s` panel, `.36s` bubble); existing `styles.yaml` files keep theirs.
- **Answers:** the opening, each passage and the related-answer intro go in
  their own paragraph (separated by a blank line) instead of one block. The
  widget already shows line breaks; integrations that render `answer` as
  plain text may want `white-space: pre-wrap`.
- **Tones:** every tone grows from 90 to 154 variants per language: 12 in
  `opening`, `addition`, `no_answer` and `related_intro`, 7 in the widget
  situations and 8 in the rest. Which variant an answer uses may change.
- **Parsing keeps the structure the text shows** (re-run `ipsis index`;
  offsets of affected documents change, so re-check a golden set built on
  them):
  - Markdown, TXT and PDF: each bullet or numbered item is its own block
    (`content_type` `lista`), so answers keep one item per line; DOCX list
    styles are marked the same way.
  - Markdown tables: one block per row (`a | b`), like DOCX tables.
  - TXT: a one-line paragraph that looks like a title and is followed by
    content becomes a section; the "no sections" warning appears only when
    there is none.
  - PDF: words hyphenated at a line break are joined; paragraphs are rebuilt
    when the PDF has no blank lines; without bookmarks, lines in a larger
    font become sections (largest size = level 1).
- **Embedding header** (`Document: … | Section: …`) is now in the corpus
  language; Spanish is unchanged, English and Portuguese projects need
  `ipsis index` again.
- **Tone linter:** in the bundled tones, rejects near-copies within a
  situation and checks the count per situation (project overrides keep the
  previous rules); a test keeps es, en and pt in
  parity.

### Fixed

- A `related` reply named the first focus term as missing even when the
  passage contained it ("Sobre «extranjero» no hay una respuesta directa…"
  over a sentence about trips abroad); it now names a focus term absent from
  the answering sentence ("viaje").

- **Concurrent requests:** `terminos()` shared one snowballstemmer instance
  across service threads; concurrent `/ask` calls could fail with an
  `IndexError` (16 of 240 requests under an 8-client load). One stemmer per
  thread.

- **The same passage no longer shows twice** when two overlapping chunks
  yield the same span.
- **A heading is never the answer sentence:** the selection does not anchor
  on it, the reader's evidence does not drag the heading above it, and a
  span the reader marks inside a heading comes with the sentence it titles.
- **`ipsis ask` (without `--diagnostics`) called the old endpoint:** it
  still posted `{"pregunta", "id_sesion"}` to `/consultar`, which a current
  server answers with 404. It now uses `POST /ask` with `question` and
  `session_id`, and reads `status`, `answer` and `fragments`.
- **Answers and citations by section:** a chunk can still span several
  sections (retrieval is unchanged), but it now records where each section
  starts. The passage shown stays within the section of the sentence that
  answers, without dragging in the next heading and its text, and the
  citation names that section (it used to name the chunk's first one).
  Re-run `ipsis index`. Measured on the universal bank: identical results
  and latency within noise. Splitting chunks by section was measured too and
  discarded: more exact answers in `light`, but a new false `ok` on a
  same-topic trap.
- **Condition and exception markers** count only as whole words: «si» no
  longer matches inside «sistema» or «visita», which marked almost every
  chunk as a condition and introduced passages with "This applies under a
  condition:" for no reason. Re-run `ipsis index`.
- **A caveat right after the answer is kept:** when the sentence that
  follows the answer is an exception («Salvo que…») or starts with a
  condition («Si…», «Siempre que…») and only missed the length limit, it is
  shown too (up to 50 % over the limit), still literal and contiguous.
- **Loading a folder with a scanned PDF** no longer aborts the whole load:
  the scanned or unreadable file is reported and skipped, the rest is
  loaded, and the command exits with 1.
- **PDFs with some scanned pages** warn which pages have no text (their
  content is not indexed) instead of losing them silently.
- **Connectors across documents:** a passage from another document is no
  longer introduced as a condition or an exception of the first one ("This
  applies under a condition:"); it is added with an `addition` connector.
- **PDF paragraphs:** a word hyphenated at the end of a paragraph's last
  line no longer glues the next paragraph to it, and a line ending in a
  hyphen is never taken for a title.
- **Tone wording:** Portuguese and English variants that were calques
  ("Tenha uma boa jornada", "O documento precisa, ainda:", "Demands:"…).

## [0.9.0] - 2026-10-05

The project is renamed **ipsis** (from *ipsissima verba*, "the very words")
and everything user-facing is now English first, with Spanish available.

**Breaking.** Existing projects migrate on their own the first time any
command runs (`config_version` 5): folders, files, keys and values are moved
and rewritten, keeping their comments, and the index is kept. What does
**not** migrate by itself:

- the command is `ipsis` (was `rag`) and its subcommands and options are in
  English (`ipsis load`, `ipsis ask --diagnostics`, `ipsis calibrate --apply`…);
- environment variables are `IPSIS_*` (`IPSIS_MODE`, `IPSIS_ADMIN_TOKEN`,
  `IPSIS_TRUSTED_PROXY`, `IPSIS_MODELS_DIR`…) and `QDRANT_MODE`;
- the model cache moves to `~/.cache/ipsis/models`: run
  `ipsis models download` again, or move the old folder;
- site integrations: `POST /ask` (was `/consultar`) with an English body and
  response, `ipsis:*` events, `window.Ipsis`, English widget attributes and
  values (`data-position="bottom-right"`…), `/source` and `/styles.css`;
- the `/admin` API routes and bodies (`/admin/personality`,
  `/admin/styles`…) use the names of the YAML files.

### Added

- Message catalog (`ipsis/recursos/mensajes/{en,es}.yaml`): the CLI and the
  `/admin/panel` speak English, or Spanish with `IPSIS_LANG=es`.
- `README.es.md` and the guides in Spanish (`docs/es/`).

### Changed

- Name: package `ipsis`, command `ipsis`, `<ipsis-chat>` element,
  `X-Ipsis-Widget-Key` header, `.ipsis/` internal folder and `ipsis-widget`
  WordPress plugin.
- Project layout and configuration in English: `config/assistant.yaml`,
  `engine.yaml`, `styles.yaml`, `personality.yaml`, `documents/`,
  `golden/bank/`, `.ipsis/index/`, with English keys and values.
- Tones (`serious`, `upbeat`, `friendly`, `empathetic`, `direct`),
  situations (`no_answer`, `missing_focus`…), template variables
  (`{assistant_name}`, `{term}`…) and avatar events (`thinking`, `answer_ok`…)
  have English names; the template texts stay in each language.
- Golden set CSV with English columns and types (`question`, `type`,
  `literal_answer`; `answerable`, `no_answer`…). CSV files with the previous
  Spanish columns and types still import.
- Answer statuses in the API and the CLI: `ok`, `related`, `no_answer`,
  `conversational`.
- `ipsis deploy prepare` writes `DEPLOY.md` and `.env.example`; the
  benchmark writes `benchmark-profiles.{json,md}`; the development extra is
  `[export]` and writes to `exported/`; the examples live in `examples/`.
- Documentation in English (guides, architecture, methodology notes and
  ADRs), plus `CONTRIBUTING.md`, `SECURITY.md`, the code of conduct and the
  issue and pull request templates.
- The tone linter, calibration results, bank and comparison errors, doctor
  reasons and the benchmark report (`benchmark-profiles.md`) come from the
  message catalog too, in English or Spanish.
- Screenshots, banners and the social preview in English, with the new
  name.

### Fixed

- The citation inside the answer text was always in Spanish
  ("(Fuente: …)"): it now comes from the language pack ("(Source: …)",
  "(Fonte: …)").
- `ipsis ask --diagnostics` listed the stages with their internal names.

## [0.8.0] - 2026-10-04

Closes plan V3: a cascade with lexical signals, ONNX models per profile,
multilingual support, risk-controlled calibration, the widget personality
and self-hosted deployment. The detailed history (tasks, measurements and
findings) stays in git, under the `plan-v3` tag; the decisions, in
`docs/decisions/` and `docs/methodology/`. Commands are listed with the
names they had in this version.

**Requires reindexing** and migrates the configuration by itself
(`config_version` 4).

### Added

- **Installation profiles** `light`, `medium` and `heavy` (plus `bm25`, for
  diagnosis only), with their own latency budget, models and thresholds.
  `rag perfil mostrar|cambiar`. See [ADR 0003](docs/decisions/0003-onnx-and-profiles.md).
- **ONNX models on CPU** without torch: e5 encoder, cross-encoder reranker
  and extractive QA reader (SQuAD 2.0 style), with a global cache and
  offline use. `rag modelos listar|descargar|verificar|exportar`.
- **Stage cascade** and the `cascada_v1` policy with explainable signals
  (`s_ret`, `s_oov`, focus, `s_foco`, `s_cov`, `s_rr`, `s_qa`), an early exit
  without models and agreement in heavy. See
  [ADR 0004](docs/decisions/0004-lexical-cascade-and-removal-of-regex-guards.md).
- **Own lexical layer:** a single `terminos()` with Snowball stemming, BM25
  with hashed ids and IDF in Qdrant, readable corpus statistics and TF-IDF.
- **Multilingual:** `es`, `en` and `pt` language packs (stemmer, entities
  written with words, conversational patterns, messages and widget texts);
  other languages with universal rules.
- **Client golden set:** `rag golden plantilla|importar|validar|exportar`
  (CSV, JSONL and SQuAD 2.0), with "same topic, missing fact" minimal pairs.
- **Calibration** `rag calibrar [--alfa] [--aplicar]`: chooses thresholds on
  `dev` with a Clopper-Pearson bound ≤ α, verifies on `test` and tells
  `CALIBRADO`, `MUESTRA_INSUFICIENTE` and `SIN_UMBRAL_SEGURO` apart. It
  applies only when its provenance matches the profile, the models and the
  indexed corpus.
- **Evaluation:** a universal regression bank (90 cases in three
  languages), coverage and risk metrics, `rag benchmark --perfiles`.
- **Operations:** `rag doctor` with actions, `rag preguntar --diagnostico`,
  an optional query log and `rag auditar [--desde] [--hasta]`, which checks
  that every piece of evidence is still literal.
- **Personality:** 7 tones × 18 situations × 5 variants per language (1,890
  templates with a linter and neutrality), the animated avatar "Folio" that
  reacts to every event and follows the pointer, `rag personalidad …`.
- A responsive **widget** with configurable placement, always-visible
  citations with the span marked, `RagChat.avatar` and a "Source code" link.
- **Administration:** the `/admin` API and the `/admin/panel` with a token,
  HTTPS in production, lockout after failed attempts and an audit trail;
  `desarrollo` and `produccion` modes.
- **Deployment:** `rag desplegar preparar` generates the profile's Docker
  image (with the models included), the compose file with Caddy and a README
  in the project language; `/ready` publishes the project diagnosis.
- `rag --version`.
- Widget style key by key: `rag widget estilo mostrar|cambiar` and the
  panel's "Full style" editor (colors, typography, shapes, shadows,
  animations, placement and presentation).
- Documentation: an [architecture](docs/architecture.md) with diagrams, a
  deployment guide, methodology notes, screenshots, `CONTRIBUTING.md`,
  `SECURITY.md`, a code of conduct and issue and pull request templates.

### Changed

- **License:** AGPL-3.0-only.
- Project structure: `configuracion/dominio.yaml` replaces
  `dominios/<perfil>/perfil.yaml` and `categorias.yaml`; texts move to the
  language pack (overridable in `idioma.yaml`); the index lives in
  `.rag/indice/` and the golden set in `golden/`. Any command migrates an
  older project.
- Code by layers (`nucleo`, `configuracion`, `lenguaje`, `ingesta`,
  `modelos`, `indice`, `consulta`, `evaluacion`, `aplicacion`, `cli`,
  `servicio`) with a test that forbids dependencies on upper layers; a CLI
  with one class per command.
- Entities written with words are generated from the pack and their
  `valor_norm` no longer depends on the language (`2024-03-15`, `6_mes`). New
  universal entities: numeric dates and amounts with a currency. The `nota`
  type is replaced by `decimal`.
- In `ok`, the answer shows the answering sentence first; in `relacionado` a
  span is never presented as the answer.

### Removed

- The regex guards per question type and the list of "general words":
  `s_foco` and `s_oov` replace them.
- torch and sentence-transformers in production (they stay in the
  `[exportar]` development extra).
- The `layered_v1` policy (projects migrate to `cascada_v1`).
- Earlier plans and logs, `requirements*.txt` and the old evaluator.
- GitHub Actions and Dependabot: it is a library you install; the tests run
  locally.
- The root `Dockerfile` and the old compose with a Qdrant server:
  `rag desplegar preparar` generates the image.

### Discarded after measuring

- SQLite FTS5 backend: it produced a false `ok` on an ambiguous question.
  Qdrant stays as the only backend.
- Chunking by lexical cohesion (`texttiling_v1`): the same statuses as
  cutting by section and more false `ok` answers than the current chunker.
- `acuerdo` (dense versus BM25 agreement) as a policy signal: no measurable
  effect and +4.6 ms of p95.

### Fixed

- The wheel did not include the profiles (`rag/recursos/perfiles/`): a
  normal installation failed with "unknown profile".
- `12,5%` was extracted as the percentage `5`.
- Sentence selection lost the text before a period not followed by a space
  (for example, "1.5").
- Passages were indexed without the `passage: ` prefix e5 requires.
- Deployment files generated on Windows came out with CRLF.
- `/ready` computed the diagnosis on every expired query (seconds when
  cold): it is now computed at startup and refreshed in the background.
- The header of each citation squeezed the position into a narrow column
  and repeated the title when the section has the same name as the
  document.
- The source code link pointed to a repository that does not exist.

## [0.7.0]

First version published in the repository.
