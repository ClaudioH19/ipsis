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
config_version: 5
assistant_name: "Support assistant"
domain_description: "the product manuals"
language: en              # ISO 639 code: es, en, pt, pt-br...
profile: medium           # light | medium | heavy
cors_origins: []          # origins allowed to embed the widget
widget_keys: []           # optional public keys for the widget
query_log:
  enabled: false          # .ipsis/logs/queries.jsonl, for `ipsis audit`
```

## Versioning

`assistant.yaml` and `engine.yaml` declare `config_version`. The current
version is `5`.

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

The active profile is in `config/assistant.yaml::profile` (`light`, `medium`
or `heavy`). `bm25` is a diagnostic profile of `ipsis benchmark` only and
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
- **heavy:** it uses e5-base (768) and needs its own index (`ipsis index`).
  Each dense model lives in its own collection: the previous index is kept,
  and going back to the previous profile makes it compatible again without
  reindexing.
- **Index compatibility:** it is decided by the manifest
  (`.ipsis/index/<collection>.manifest.json`), with the dense model, the
  dimension and the payload version. It is not decided by the profile name.
- **Calibration:** any profile change invalidates it, because its provenance
  records the profile, models and corpus. The engine ignores it and the
  profile thresholds apply. The file is kept for auditing. To get it back:
  `ipsis calibrate --apply`.

## Models

ONNX models live in a global per-user cache shared by every project. The
default is `~/.cache/ipsis/models`, and `IPSIS_MODELS_DIR` changes it. It
uses the `huggingface_hub` layout. Nothing is downloaded inside the project.
With `HF_HUB_OFFLINE=1` the network is never used.

```
ipsis models list                     # models of the active profile
ipsis models download                 # downloads what the active profile is missing
ipsis models download --profile heavy # prepares another profile without activating it
ipsis models verify                   # complete files and a test inference
ipsis models export org/model --int8  # development: converts to ONNX
```

- **`list`** shows, for each model of the active profile:
  - role, repository, license (and attribution, when the catalog records one)
    and parameters;
  - the ONNX file for the current CPU (x86_64 or arm64);
  - whether it is cached, and its size.

  Everything comes from the catalog (`ipsis/modelos/catalogo.py`). light uses
  only the dense model; medium and heavy use dense, reranker and reader.
- **`download`** fetches only what is missing. A model shared between
  profiles, such as e5-small (light and medium) or the reader (medium and
  heavy), is downloaded once.
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
  (`pip install "ipsis[export]"`, with `optimum-onnx` and `torch`).
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

## Answer tone

What the assistant says around the document text comes from a **tone**, in
`ipsis/recursos/tonos/<language>/<tone>.yaml`: `cordial` (default),
`formal`, `serious`, `upbeat`, `friendly`, `empathetic` and `direct`. See
[personality.md](personality.md).

Each tone has 18 situations with 5 variants each:

- engine: `greeting`, `thanks`, `farewell`, `capability`, `opening`,
  `addition`, `condition`, `exception`, `related_intro`, `missing_focus`,
  `no_answer` and `premise_not_found`;
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

## Query log and audit (`ipsis audit`)

The service can store one JSON line per query in
`.ipsis/logs/queries.jsonl`. It is off by default, for privacy:

```
ipsis configure query_log.enabled=true   # and restart 'ipsis serve'
ipsis audit
ipsis audit --from 2026-10-01 --to 2026-10-31
```

- **What it stores:** the question, status, rule, reason, profile, the
  policy signals, the tone and the template ids used, the evidence
  (document, offsets and text) and the exact span. It does not store the
  session or the IP.
- **Who writes it:** only the service's `POST /ask`. `ipsis ask
  --diagnostics`, `ipsis evaluate` and `ipsis benchmark` do not write. If
  writing fails, the answer is not affected; a warning goes to the service
  log.
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

## Widget presentation

`config/styles.yaml` accepts a `preset` and options independent from the
documents:

```yaml
preset: editorial
presentation:
  density: comfortable
  citations: list          # accordion | list (citations are always shown)
  show_status_label: true
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
