# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project follows [SemVer](https://semver.org/). While the version is 0.x,
a minor change may break compatibility and is marked as such.

## [Unreleased]

### Added

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
- **Natural queries bank** (`tests/datos/banco_consultas`).

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

### Changed

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
