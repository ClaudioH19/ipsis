# Configuration reference

## Project files

`ipsis init` creates the project folder. Everything is readable YAML you can
keep under version control, except `.ipsis/`, which is generated.

```text
my-assistant/
├── config/
│   ├── assistant.yaml      # identity, language, profile, CORS, widget keys and query log
│   ├── engine.yaml         # retrieval, components, Qdrant, limits and profile overrides
│   ├── styles.yaml         # widget theme and placement
│   ├── personality.yaml    # answer tone and avatar
│   ├── domain.yaml         # optional: your own domain rules and categories
│   ├── language.yaml       # optional: overridden texts of the language pack
│   ├── calibration.yaml    # written by `ipsis calibrate --apply`, with provenance
│   └── avatars/            # imported avatars (.avatar.json)
├── documents/              # source files + catalog.yaml
├── golden/                 # golden.csv, the versioned bank/ and reports/
└── .ipsis/                 # generated: index/ (Qdrant, statistics, manifest) and logs/
```

| File | Edited with | Details |
|---|---|---|
| `assistant.yaml` | `ipsis configure key=value` | this guide |
| `engine.yaml` | by hand | this guide; thresholds live in the profile and in `calibration.yaml` |
| `styles.yaml` | `ipsis widget theme`, `ipsis widget style`, `/admin` panel | [web.md](web.md) |
| `personality.yaml` | `ipsis personality`, `/admin` panel | [personality.md](personality.md) |
| `calibration.yaml` | `ipsis calibrate --apply` | [methodology](../methodology/calibration.md) |

### `assistant.yaml`

```yaml
config_version: 7
assistant_name: "Support assistant"
domain_description: "the product manuals"
language: en              # ISO 639 code: es, en, pt, pt-br...
profile: medium           # light | medium
cors_origins: []          # origins allowed to embed the widget
widget_keys: []           # optional public keys for the widget
query_log:
  enabled: false          # .ipsis/logs/queries.jsonl, for `ipsis audit`
posture:
  mode: proactive         # proactive | strict: see "When the answer is not there"
  max_alternatives: 3     # 1 to 5
```

## Versioning

`assistant.yaml` and `engine.yaml` declare `config_version`. The current
version is `7`.

- Any `ipsis` command migrates an older project when it starts: files without
  `config_version` count as version 0 and move up step by step.
- Validation rejects unknown keys and a version newer than the supported one.

| Version | What changed |
|---|---|
| 2 | The reranker is chosen only with `components.reranker` |
| 3 | `domain.yaml` replaces domain profiles; `profile` becomes the installation profile (v2 projects end up on `light`); no torch; `.cache/` moves to `.ipsis/` |
| 4 | The `cascade_v1` policy replaces the previous one; thresholds move to the profile and to `calibration.yaml` |
| 5 | Folders, files, keys and values in English (`config/`, `documents/`, `assistant.yaml`, `assistant_name`…). Projects created with Spanish names are moved and rewritten automatically, keeping their comments |

The validated configuration can be loaded from Python:

```python
from ipsis.configuracion.carga import cargar_dominio, cargar_proyecto

engine = cargar_proyecto()
assistant = cargar_dominio()
```

These functions return the internal names the engine uses; the files on disk
use the English names shown in this guide.

## Components

### Engine selection

New projects and configurations without a selector use v2:

```yaml
config_version: 7
pipeline: v2
```

V2 publishes ranked literal sources with continuation and does not execute
v1 intent/focus rules, answer policies, conversation memory or calibration.
See [ranked sources](../methodology/fuentes-v2.md) for its options.
An explicit `pipeline: v1` remains valid and is preserved when loading older
configuration. Change that line and restart the service to switch engines;
changing only the engine does not require reindexing.

The `components` section selects implementations by name:

```yaml
components:
  parser: builtin
  chunker: builtin
  dense_encoder: onnx
  sparse_encoder: bm25
  retriever: qdrant
  fusion: rrf
  reranker: null
  intent_classifier: rules
  answer_extractor: sentence_selector
  evidence_verifier: literal_offsets
  response_renderer: templates
  abstention_policy: cascade_v1
```

The profile defines the reranker and the reader (`ipsis profile show`). A
`null` value turns an optional component off. An implementation can take
options with the extended form:

```yaml
components:
  fusion:
    name: rrf
    k: 60
```

The registry can be used from an integration:

```python
from ipsis.nucleo.contratos import RegistroComponentes
from ipsis.aplicacion.registro_base import registrar_componentes_base

registry = registrar_componentes_base(RegistroComponentes())
fusion = registry.crear("fusion", "rrf", k=60)
```

The base adapters never download models while registering. `onnx` opens the
model session only on first use. The Qdrant connection and the rerankers are
set up by the service, because they depend on the index, the collection and
the available resources.

### Retrieval backend

`qdrant` is the only supported backend. `retrieval.mode` chooses `dense` or
`hybrid`; both keep the same contract and need reindexing when the stored
representation changes.

## Installation profile

The active profile is in `config/assistant.yaml::profile` (`light` or
`medium`). `bm25` is a diagnostic profile of `ipsis benchmark` only and
cannot be installed.

```
ipsis profile show         # profile, models, p95 budget, index and calibration
ipsis profile set medium   # changes only assistant.yaml::profile
```

`ipsis profile set` downloads no models, indexes nothing, calibrates nothing
and deletes nothing. `profile_overrides`, the index and `calibration.yaml`
are kept. Before writing, it validates the project's `profile_overrides`
against the target profile. Setting the active profile again does nothing.

- **light ↔ medium:** they use the same dense model (e5-small, 384), so the
  index works for both.
- **Projects with `heavy`:** that profile was removed. An `assistant.yaml`
  that names it loads as `medium`; if its index was built with another dense
  model, `ipsis profile show` marks it incompatible and asks for `ipsis index`.
  Each dense model lives in its own collection: the previous index is kept.
- **Index compatibility:** it is decided by the manifest
  (`.ipsis/index/<collection>.manifest.json`), with the dense model, the
  dimension and the payload version. It is not decided by the profile name.
- **Calibration:** any profile change invalidates it, because its provenance
  records the profile, models and corpus. The engine ignores it and the
  profile thresholds apply. The file is kept for auditing. To get it back:
  `ipsis calibrate --apply`.

## Changing configuration for deployment

Run commands in the project directory containing `config/` and `documents/`.
With local Qdrant, stop `ipsis serve` before another process opens the index.

| Setting | Command or file | Follow-up |
|---|---|---|
| Profile | `ipsis profile set medium` | Download models, check `profile show`, evaluate and recalibrate |
| Identity and CORS | `ipsis configure assistant_name="Support" cors_origins=https://www.your-site.com` | Restart the service |
| Query log | `ipsis configure query_log.enabled=true` | Restart; `ipsis audit` checks logged citations |
| Abstention alternatives | `ipsis configure posture.mode=strict` or `posture.mode=proactive` | Restart; alternatives remain an abstention |
| Reading, retrieval and thresholds | `config/engine.yaml`, `profile_overrides` | Set aside the old calibration, restart, evaluate and recalibrate |
| Chunking, dense model or index representation | `config/engine.yaml`, `retrieval` | Reindex, validate the golden set, evaluate and recalibrate |
| Active documents | `documents/catalog.yaml`, `active` | Reindex, validate the golden set and recalibrate |
| Synonyms | `config/domain.yaml`, `synonyms` | Restart, evaluate and recalibrate |
| Tone and avatar | `ipsis personality` or `config/personality.yaml` | Service reload; see [personality](personality.md) |
| Widget theme and placement | `ipsis widget style` or `config/styles.yaml` | See [web](web.md) |

`ipsis configure` edits supported `assistant.yaml` keys. Engine adjustments
use YAML; leave the packaged profiles intact. Add or merge this block into
`config/engine.yaml`:

```yaml
profile_overrides:
  cascade:
    retrieve_n: 20
    rerank_k: 4
    read_m: 2
    max_reading_chars: 600
    early_exit_without_focus: true
  default_thresholds:
    ok: 0.80
    focus: 1.0
    oov_ok: 0.60
    cov: 0.60
    ok_strong: 0.99
    oov_ok_strong: 0.67
    focus_informal: 0.5
```

The **Status** tab of `/admin` and `PUT /admin/thresholds` write the same
`default_thresholds` of this file and reload the engine. These values reproduce `medium` defaults. Without a reader, `read_m` does not
apply. `ok` gates QA with a reader and similarity without one; `cov` gates
direct answers without a reader. `ok_strong` and `oov_ok_strong` are a second
tier for the reader: when it is nearly sure, an informal question may carry
somewhat more words the documents lack. Remove both to turn the tier off. More candidates or larger windows increase
work without guaranteeing better accuracy.

Precedence is **profile → `profile_overrides` → applicable calibration**.
To test manual thresholds, rename `config/calibration.yaml` and retain it
under another filename. Reading parameter changes do not automatically
invalidate calibration, so set it aside before measuring those changes too.
Version 1 calibrations are ignored under answer criterion v2; regenerate them.

Before preparing a deployment:

```bash
ipsis profile show
ipsis snapshot-config --output reports/config-review.yaml
ipsis golden validate
ipsis evaluate --output reports/evaluation.json
ipsis calibrate                    # inspect dev and test before applying
ipsis doctor
ipsis deploy prepare --domain assistant.your-site.com
```

The snapshot records validated settings and defaults. Full answers and QA
spans have separate metrics ([golden set](golden.md)). If you apply thresholds,
run `ipsis calibrate --apply` and evaluate again. A failed `test` does not
automatically block `--apply`; inspect that result before treating calibration
as validated. `doctor` and `/ready` check operation, not answer accuracy.
In Docker, edit the deployed `config/` directory and run
`docker compose restart asistente`. Changing models requires preparing the
image and index again. Generated `DEPLOY.md` includes these instructions.

## Models

### Alternative models

Until October 2026 there was a `heavy` profile with larger models. It was
removed because no variant beat medium: with Granite-311M R2, Granite-97M R2,
Harrier-270M or EmbeddingGemma 2 as the retriever, and Horizon base/small as
the reranker, the Spanish query bank gave exactly the same 25 correct answers
as medium, and both Horizon models added an accepted error. The former
e5-base/BGE 30/8/4 configuration had fewer correct answers and more errors.
See [ADR 0003](../decisions/0003-onnx-and-profiles.md).

The models stay in the catalog so they can be tried on top of medium with a
deployment's corpus. Merge this block into `config/engine.yaml`:

```yaml
retrieval:
  model: null
profile_overrides:
  models:
    dense: ibm-granite/granite-embedding-311m-multilingual-r2
```

| Role | Supported repository |
|---|---|
| Dense | `ibm-granite/granite-embedding-311m-multilingual-r2` |
| Dense | `ibm-granite/granite-embedding-97m-multilingual-r2` |
| Dense | `onnx-community/harrier-oss-v1-270m-ONNX` |
| Dense | `onnx-community/embeddinggemma-2-ONNX` (text only) |
| Dense | `intfloat/multilingual-e5-base` |
| Reranker | `Horizon-Labs/multilingual-reranker-base` |
| Reranker | `Horizon-Labs/multilingual-reranker-small` |
| Reranker | `onnx-community/bge-reranker-v2-m3-ONNX` |

The catalog pins their revisions and declares padding, prefixes, pooling,
outputs and required external weights. The profile thresholds were measured
with e5-small and **do not transfer**: Granite, for example, gives cosines of
0.73–0.94 to out-of-corpus questions too, so the `domain` threshold of 0.33
stops filtering. Calibrate with the deployment's golden set before using
another retriever; e5-small's intent fallback does not transfer either.

Stop the service, run `ipsis models download`, `ipsis models verify`,
`ipsis index`, `ipsis profile show`, `ipsis golden validate` and `ipsis evaluate`.
Reindex whenever the dense model changes, even at the same dimension. Set aside
old calibration and remeasure. Overrides persist across profile switches;
remove them to use packaged defaults.
The prepared Docker image reads project overrides during model download;
rebuild it after changing models (`docker compose build --no-cache asistente`).
See [repeatable regression and candidate commands](../../herramientas/evaluacion/README.md).

ONNX models live in a global per-user cache shared by every project. The
default is `~/.cache/ipsis/models`, and `IPSIS_MODELS_DIR` changes it. It
uses the `huggingface_hub` layout. Nothing is downloaded inside the project.
With `HF_HUB_OFFLINE=1` the network is never used.

```
ipsis models list                     # models of the active profile
ipsis models download                 # downloads what the active profile is missing
ipsis models download --profile medium # prepares another profile without activating it
ipsis models verify                   # complete files and a test inference
ipsis models export org/model --int8  # development: converts to ONNX
```

- **`list`** shows, for each model of the active profile:
  - role, repository, license (and attribution, when the catalog records one)
    and parameters;
  - the ONNX file for the current CPU (x86_64 or arm64);
  - whether it is cached, and its size.

  Everything comes from the catalog (`ipsis/modelos/catalogo.py`). light uses
  only the dense model; medium uses dense, reranker and reader.
- **`download`** fetches only what is missing. A model shared between
  profiles, such as e5-small (light and medium), is downloaded once.
  - With `--profile` it does not change the active profile, and it works
    outside a project.
  - Without `--profile` it needs a project (`ipsis init`).
  - `bm25` cannot be installed.
- **`verify`** only checks the active profile and never downloads. Per model:
  - the required files (ONNX, `tokenizer.json`, `config.json`);
  - that the onnxruntime session loads;
  - a minimal inference: a normalized vector of the expected dimension, a
    finite logit or a valid reading.

  Each model ends as `OK`, `MISSING` (action: `ipsis models download`),
  `DOES NOT LOAD` (the file is there but invalid) or `FAILS` (invalid
  inference). It exits with 0 only when all are `OK`.
- **`export`** is for development only. It needs the `[export]` extra
  (`uv sync --locked --extra export`, with `optimum-onnx` and `torch`).
  Production runs without torch.
  - It writes `exported/<org>--<model>/model.onnx` in the current folder
    and, with `--int8`, also `model_int8.onnx`, using onnxruntime's dynamic
    post-training quantization (`quantize_dynamic`).
  - It never overwrites a previous export or touches the cache.
  - It does not register the model in the catalog or the profiles: adopting
    it is a separate step.

## Language

`assistant.yaml::language` is an ISO 639 code, for example `es`, `en` or
`pt-br`. `es`, `en` and `pt` have their own pack: stemmer, stopwords,
numbers, dates, connectors, messages and interface. A regional variant
(`pt-br`, `es-cl`) uses its base language pack.

Questions are rarely written like the documents. Each pack treats informal
abbreviations and contraction pieces as function words ("q", "pa", "pra",
"vc", "u", "ur", the "t" of "don't"), and the analysis corrects typos against
the corpus vocabulary ("pasword" → "password", "covran" → "cobra", "abreel" →
"abre el", "estacio namiento" → "estacionamiento"; never a real word the corpus
lacks, such as "feriados", nor a proper noun). `ipsis ask --diagnostics` shows each correction.
See [informal paraphrases](../methodology/informal-paraphrases.md).

Any other code works with a fallback:

- only the universal rules (numeric dates, amounts, articles);
- unstemmed terms;
- the `en` interface and tones, which you can translate with
  `config/language.yaml` (interface) and `config/personality.yaml` (tone).

`ipsis init` and `ipsis configure language=` warn about it, and
`ipsis doctor` flags it as a warning.

The language of the documents is independent from the language of the
command line (`IPSIS_LANG`): a project in Portuguese can be managed with
English or Spanish messages.

## Local synonyms

### Intention fallback settings

The language pack contains `intenciones.<name>.ejemplos` and model-specific
`respaldo_intencion` settings. Override them in `config/language.yaml`:

```yaml
respaldo_intencion:
  intfloat/multilingual-e5-small:
    similitud: 0.85
    margen: 0.0
    habilitadas: [fin, procedimiento]
```

These are the measured Spanish values. English uses 0.87 with `[fin]` and
Portuguese 0.895 with `[procedimiento]`; both require a strictly positive
margin. Patterns retain priority. BM25 and models without measured settings
skip fallback; E5 base has no default setting. Changes require rebuilding
the motor and regenerating calibration. Measure new examples or categories
on dev before enabling them; neither threshold is an answer policy threshold.

### Synonym groups

Spanish, English and Portuguese use packaged, filtered WordNet tables for
BM25 retrieval expansion, reusing the original dense vector. Only a query word absent from the corpus can expand,
with a single sense after stemming; relation words and manual corrections
take precedence. Automatic groups do not change focus validation or the
acceptance thresholds. Full dictionaries and morphology indexes stay as
development resources, without installation downloads.

Declare project equivalences in `config/domain.yaml`:

```yaml
synonyms:
  - [OC, orden de compra]
```

Project groups override overlapping language groups. Phrases match in full,
and every content term of a replacement must exist in the corpus. Restart
the service after changing lexical configuration. A new motor starts with
empty conversation memory and new query caches. Calibration provenance
includes `lexical_hash`; a missing or different hash invalidates the old
calibration. `ipsis doctor` reports it; recalibrate with the project's golden.

## Answer tone

What the assistant says around the document text comes from a **tone**, in
`ipsis/recursos/tonos/<language>/<tone>.yaml`: `cordial` (default),
`formal`, `serious`, `upbeat`, `friendly`, `empathetic` and `direct`. See
[personality.md](personality.md).

Each tone has 19 situations, with 7 to 12 variants each:

- engine: `greeting`, `thanks`, `farewell`, `capability`, `opening`,
  `addition`, `condition`, `exception`, `related_intro`, `missing_focus`,
  `alternatives_intro`, `no_answer` and `premise_not_found`;
- widget: `welcome`, `waiting`, `citations_hint`, `network_error`,
  `rate_limit_error` and `service_error`.

The tone **only frames the answer**: the document text goes literally and
the citations go underneath. Changing the tone does not change the status of
an answer, and needs no reindexing or recalibrating.

**Variety without losing reproducibility.**

- Within a conversation, the variant is chosen by session, turn and
  situation. The same sentence is never repeated in consecutive turns of a
  session.
- The same session and turn always give the same text.
- Every variant used is recorded as a template id (`cordial.no_answer.3`) in
  `ipsis ask --diagnostics` and in the query log.

To change texts for your project without touching the pack, use
`config/personality.yaml`:

```yaml
tone:
  templates:
    no_answer:
    - That is not in the team handbook.
```

Each override goes through the same rules as the packs. If it breaks one,
the engine does not start and the error says which rule failed:

- one line, up to 200 characters;
- no digits, URLs, HTML, Markdown, emojis or whole words in capitals;
- only the variables of its situation (`{term}`, `{entity}`,
  `{assistant_name}`, `{domain_description}`);
- connectors end with ":";
- none of the language's forbidden expressions.

The texts of `config/language.yaml` older than tones
(`mensajes.sin_respuesta`, `mensajes.conectores.apertura`, `interfaz.saludo`…)
still work: they are taken as tone overrides. `personality.yaml` takes
precedence over them.

## Active documents

`documents/catalog.yaml` lists what has been loaded. An entry with
`active: false` is not indexed and is left out of the golden set (run
`ipsis index` after changing it).

When `ipsis load` gets a file with the same name as one already loaded but
different content:

- it adds it as a new document (`<name>-<hash>.<ext>`) and warns about it;
- both are indexed until the old one is set to `active: false`.

## Diagnosis (`ipsis doctor`)

`ipsis doctor` answers whether the project can run now and, if not, which
command to run. It only diagnoses:

- it uses no network and loads no ONNX models;
- it downloads, indexes and calibrates nothing;
- it writes nothing.

It checks, in this order: configuration, profile, language, stemmer, models,
index, calibration, golden set, CORS, personality and mode. The service
publishes the same diagnosis in `/ready`. Each check shows a mark:

| Mark | Meaning |
|---|---|
| `[OK]` | Ready. |
| `[WARNING]` | It works, but something optional is missing or needs attention. It does not change the exit code. |
| `[ERROR]` | It prevents or invalidates operation. It always comes with an `Action:`. |
| `[--]` | Not evaluated because it depends on a check that failed. |

The final summary counts errors and warnings and lists the actions without
repeating them. The command exits with 0 when there are no errors and with 1
otherwise. Outside a project, it asks for `ipsis init`.

- **Models:** it only checks that they are complete in the cache (ONNX,
  `tokenizer.json`, `config.json`). To test inference, use
  `ipsis models verify`.
- **Index:** its manifest is compared with the profile (model, dimension,
  payload) and with the language's stemmer. To know whether the corpus
  changed, it first compares a fingerprint of the bytes of the active
  documents, stored in the manifest: when it matches, nothing is parsed. When
  it differs, or the manifest is older and lacks it, it recomputes the exact
  hash by parsing and chunking, without models. No index and no documents is
  a warning; documents not indexed, a changed corpus or an incompatible index
  are an error whose action is `ipsis index`.
- **Calibration and golden set are optional.**
  - When missing, it is a warning and the profile thresholds apply.
  - A stale or disabled calibration is a warning; the action is
    `ipsis calibrate --apply`.
  - A golden set whose corpus changed is also a warning, and it should not be
    used to evaluate or calibrate until updated (`ipsis golden validate`).
  - A regression bank is good for evaluating, not for calibrating.
- **Language:**
  - A language without its own pack is a warning: the fallback applies (see
    "Language").
  - A `stemmer` unknown to snowballstemmer is an error.
  - `stemmer: null` is valid: terms stay unstemmed.

## Diagnosing a question (`ipsis ask --diagnostics`)

```
ipsis ask --diagnostics "How often should the filter be changed?"
```

It runs the question with the project engine in the same process, without
the HTTP service: the service never publishes the diagnosis. Before
measuring, it warms up the models so the latencies are those of normal
operation. It shows:

- the status and the answer;
- the deciding rule, the reason and the profile;
- each stage with its latency in ms, and the total;
- the signals the policy saw (`s_ret`, `s_oov`, `s_foco`, `s_cov`, `s_rr`,
  `s_qa`, `dominio`);
- the focus terms found and missing in the evaluated sentence, and the
  question terms that are not in the corpus;
- the exact span the reader marked, with its offsets;
- the evidence;
- the tone and the template ids used.

With local Qdrant, stop `ipsis serve` first, because Qdrant locks the index
folder.

## Conversation memory

Follow-up questions ("and abroad?") inherit the topic of the conversation
(see the [architecture](../architecture.md#understanding-the-question)). The
engine keeps each conversation in memory, per `session_id`, and forgets it
after a while without questions:

```yaml
# engine.yaml
conversation:
  expiry_minutes: 30     # forgotten after 30 minutes without questions
  max_sessions: 1024     # at most this many conversations at a time
```

Language packs distinguish `genericas` (support verbs, units and question
quantifiers such as `time/tiempo/tempo`, `often`, `quantos`: never focus
terms, ignored by answer selection) from `genericas_memoria` (ignored only by
topic memory). Both lists can be overridden in `config/language.yaml`.

The memory lives in the service process (each worker has its own), keeps
terms of the questions and of the passages that answered them, never the
answers, and is lost on restart. The widget starts a new conversation on
every page load.

## When the answer is not there (posture)

When the documents do not have what was asked, the assistant says so. With
the **proactive** posture (the default) it then offers up to
`max_alternatives` passages that are similar and are in the documents,
under a fixed sentence of the tone that says they are not what was asked:

```
No encontré "TP-500" en los documentos disponibles.

Te muestro lo más parecido que sí aparece en los documentos:

El taladro percutor TP-600 tiene un motor de 800 W … (Fuente: Catálogo …).
El taladro percutor TP-400 tiene un motor de 600 W … (Fuente: Catálogo …).
```

```
ipsis configure posture.mode=strict          # only "it is not there"
ipsis configure posture.max_alternatives=2
```

- **When:** only after a false premise (an entity of the question is not in
  the documents) or a question without an answer. Out-of-domain questions,
  related answers and conversational turns never carry alternatives.
- **What is shown:** each alternative is a literal paragraph of the
  documents with its citation, checked like the evidence of an answer.
  Nothing is generated. The status stays `no_answer`: alternatives travel in
  their own `alternatives` field of `/ask` and never count as an answer.
- **How they are chosen:** by the metadata the index already keeps for each
  fragment, without another model. Each candidate paragraph gets an
  affinity, the weighted mean of seven signals; the weights and the threshold
  are part of the installation profile
  ([ADR 0008](../decisions/0008-proactive-posture-and-metadata-similarity.md)):

  | Signal | Value for the paragraph | Shipped weight |
  |---|---|---|
  | `family` | 1 if it has an entity of the family of the missing one: same type and form ("TP-400" for "TP-500"), for the types `domain.yaml` declares | 1 |
  | `measure` | the same for a missing core measure ("90 days" for "60 days", "20 %"), only if it also shares a question word | 0 |
  | `terms` | fraction of the question words it has (over all of them, also the missing ones; the words of the entity itself do not count) | 2 |
  | `section`, `keywords` | the same fraction over its document title and section, or its keywords | 0 |
  | `category` | 1 if it is of the question category in the project taxonomy | 0 |
  | `similarity` | dense cosine with the question, from the model floor | 0 |

  With threshold 0.5 this means: the family of a missing code, or, without
  a family, a paragraph with at least three quarters of the question words
  ("Does delivery to the regions take 3 business days?" → "Delivery to the
  regions takes 5 business days."). The weights were chosen with the
  alternatives bank for a precision of at least 0.9 and the widest margin
  of thresholds; a held-out validation measured once gave 1.0. When the
  missing entity has a family, only paragraphs of that family are offered.
  Short questions are the weak spot: with a single content word, any
  paragraph that has it covers the whole question. Alternatives do not feed
  the conversation memory.
- **Your codes:** a product code is an entity only if `domain.yaml`
  declares it (`regex_extractors`, for example
  `'\b(?P<pre>[A-Z]{2})-(?P<num>\d{1,3})\b'` with `transform: {pre:
  minusculas}`). Without it, a missing code has no family and only
  paragraphs with nearly all the question words are offered. The category
  signal needs at least two categories of your own in `taxonomy`.
- **Tuning:** `profile_overrides.alternatives.threshold` and
  `profile_overrides.alternatives.weights` in `engine.yaml`. `ipsis ask
  --diagnostics` shows each alternative offered or discarded, with its
  affinity and signals.

## Query log and audit (`ipsis audit`)

The service can store one JSON line per query in
`.ipsis/logs/queries.jsonl`. It is off by default, for privacy:

```
ipsis configure query_log.enabled=true   # and restart 'ipsis serve'
ipsis audit
ipsis audit --from 2026-10-01 --to 2026-10-31
ipsis audit --trace <consulta_id>
```

- **What it stores (version 2):** a random `consulta_id`, UTC date, duration,
  question, complete answer, output contract and diagnostic: status, rule,
  reason, profile, policy signals, tone, templates, evidence (document,
  offsets and text) and exact span. It does not store the session identifier
  or IP; questions and document text are retained.
- **Execution trace:** `traza` contains ordered events with timings and
  status. Each stage records its inputs and outputs: corrected or interpreted
  question, intent, signals, candidates, discarded candidates, evidence and
  decision. Skipped stages include reasons, as do early exits and admission
  or saturation. Every actual retrieval (confidence, main, premise or alternatives)
  preserves question, limit, filter, mode and candidates with text, offsets
  and scores. The reranker and reader record the exact questions and passages
  they received and their outputs, including sentence reranking before
  semantic reading.
- **Execution context:** the project motor trace preserves Ipsis version,
  components, effective profile, models, thresholds, corpus and lexicon hashes
  and a configuration fingerprint. It does not dump service tokens or keys.
  Hashes identify the environment; they do not archive the entire corpus or
  guarantee exact replay.
- **Who writes it:** only the service's `POST /ask`. `ipsis ask
  --diagnostics`, `ipsis evaluate` and `ipsis benchmark` do not write. If
  writing fails, the answer is not affected; a warning goes to the service
  log. Execution failures also produce an entry with `estado: error`, exception
  type and partial trace; internal exception messages are omitted. Concurrent
  requests have separate traces.
- **Inspect a case:** take the `consulta_id` from a JSONL line and run
  `ipsis audit --trace <consulta_id>`. It returns the original record as JSON
  without models, searches or corpus access; date filters cannot be combined
  with this option. Older version 1 records remain supported by `ipsis audit`.
- **What `ipsis audit` checks:** it counts queries by status, rule and tone,
  and verifies that the text of each piece of evidence and each span is
  still at those offsets of the current corpus.
  - Possible problems: `altered`, `altered_span`, `missing_document` (the
    document was retired) or `out_of_range`.
  - `--from` and `--to` (a date or ISO 8601, UTC by default, inclusive) limit
    the range; lines without a date are excluded and reported.
  - It exits with 0 when everything matches and with 1 when there are
    problems, unreadable lines or no log.
  - It uses no models and no index.

The trace documents observable steps and explicit system decisions, not a
model's internal reasoning. It lets you audit what happened; the literalness
checked by `ipsis audit` does not establish answer correctness or completeness.
Review real cases and turn failures into regression bank cases. The local
JSONL is editable, without automatic rotation or tamper protection; manage
its access and retention alongside the corpus when enabling logging.

## Widget presentation

`config/styles.yaml` accepts a `preset` and options independent from the
documents:

```yaml
preset: editorial
presentation:
  density: comfortable
  citations: list          # accordion | list (citations are always shown)
  show_status_label: true
  text_align: justify      # justify | start (document passages)
```

Presets are managed with `ipsis widget theme`, and each value with
`ipsis widget style show|set` (for example
`ipsis widget style set colors.accent=#0ea5e9`), or from the `/admin/panel`
(Widget tab, "Full style"). `/config` exposes these values for the widget to
apply them and accepts no writes; changes over HTTP go through `/admin`,
with a token (see [personality.md](personality.md)). The public widget key
authorizes questions and cannot be used to administer.

## Effective snapshot

To get a copy of the configuration with every default and value resolved:

```bash
ipsis snapshot-config
ipsis snapshot-config --output .ipsis/production-config.yaml
```

It is also available from Python:

```python
from ipsis.configuracion.carga import configuracion_efectiva

snapshot = configuracion_efectiva()
```

The snapshot contains `engine`, `assistant`, `personality`, `config_version`
and `snapshot_version`. It contains no derived secrets.
