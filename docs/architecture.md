# Architecture

How ipsis is organized, what each module does and how a question travels
from the widget to a cited answer. The techniques in detail are in the
[methodology notes](methodology/README.md); the decisions in the
[ADRs](decisions/).

Three criteria guide the structure:

- **Minimal:** each folder groups one responsibility; there are no loose
  files in `ipsis/`.
- **Understandable:** a folder's name says what is inside and dependencies
  go in one direction only.
- **Auditable:** every decision can be rebuilt from readable files, and a
  test (`tests/test_arquitectura.py`) enforces the dependency rules.

The source code (modules, functions and internal data) is written in
Spanish, the language the project started in. Everything a user sees is in
English, with Spanish as the second language: commands and messages
(`IPSIS_LANG=es`), project files, the HTTP API, the widget and the admin
panel. The translation between the two happens at the edges
(`ipsis/configuracion/glosario.py`, `ipsis/recursos/mensajes/` and the API
models).

## 1. Overview

```mermaid
flowchart LR
    subgraph Site["Your website"]
        W["Widget<br/>widget.js + avatar.js"]
    end
    subgraph Server["Your server"]
        C["Caddy<br/>HTTPS"] --> API["FastAPI service<br/>ipsis serve"]
        API --> M["Engine<br/>cascade of stages"]
        M --> Q[("Qdrant<br/>.ipsis/index")]
        M --> O["ONNX models<br/>global cache"]
        API --> P["/admin panel"]
    end
    subgraph Project["Project folder"]
        CFG["config/*.yaml"]
        DOC["documents/"]
        G["golden/"]
    end
    W -- "POST /ask" --> C
    CLI["ipsis CLI"] --> CFG
    CLI --> DOC
    CLI -- "ipsis index" --> Q
    CFG --> API
```

- **No network at run time:** models are downloaded once to the global
  cache (`IPSIS_MODELS_DIR`) and the service runs with `HF_HUB_OFFLINE=1`.
- **No generative model:** the text that answers is always a literal span of
  `documents/`; what is added around it comes from fixed templates (tones).

## 2. Layers of `ipsis/`

```mermaid
flowchart RL
    nucleo["nucleo"]
    configuracion["configuracion"] --> nucleo
    lenguaje["lenguaje"] --> configuracion
    ingesta["ingesta"] --> lenguaje
    modelos["modelos"] --> lenguaje
    indice["indice"] --> lenguaje
    consulta["consulta"] --> ingesta & modelos & indice
    evaluacion["evaluacion"] --> consulta
    aplicacion["aplicacion"] --> evaluacion
    cli["cli"] --> aplicacion
    servicio["servicio"] --> aplicacion
```

Rules, checked by `tests/test_arquitectura.py`:

- a module only imports from its own layer or the ones below;
- `nucleo`, `configuracion` and `lenguaje` do not load `onnxruntime`,
  `qdrant_client` or `fastapi` when imported;
- `cli` and `servicio` only import `aplicacion`, `nucleo` and `recursos`:
  the logic lives in the use cases, shared by the terminal and the API.

## 3. Modules

### `nucleo/` — contracts

| Module | What it does |
|---|---|
| `contratos.py` | Protocols of the swappable components: parser, chunker, dense and sparse encoders, retriever, fusion, reranker, abstention policy, verifier, renderer and `Etapa` (stage) |
| `esquemas.py` | Strict Pydantic schemas crossing boundaries: `ChunkRecord`, `RetrievalCandidate`, `LecturaQA`, `EvidenceSpan`, `AssistantResult`, diagnostics |
| `registro.py` | Registry of factories by type and name |

### `configuracion/` — project files

| Module | What it does |
|---|---|
| `esquemas.py` | Schemas of `assistant.yaml` and `engine.yaml`, with `config_version` migrations up to 5 |
| `glosario.py` | English names on disk ↔ internal names, for every project file |
| `archivos.py` | Reads and writes project YAML through the glossary (atomic writes) |
| `carga.py` | Loads and validates the configuration; copies the templates on `ipsis init` |
| `migraciones.py` | Migrates older projects (folders, files and Spanish keys) |
| `perfiles.py` | Profiles `light`, `medium` and `bm25`; merge profile ← `engine.yaml` ← calibration |
| `calibracion.py` | `calibration.yaml` and when it applies (provenance) |
| `personalidad.py` | `personality.yaml`: tone, avatar and the event catalog |
| `rutas.py` | Relative paths of a project |

### `lenguaje/` — everything that depends on the language

| Module | What it does |
|---|---|
| `paquete.py` | Language packs (`es`, `en`, `pt`) and the universal fallback |
| `texto.py` | `terminos()` (the only path from text to terms) and `dividir_oraciones()` |
| `lexico.py` | BM25, TF-IDF, MMR and the signals `s_oov`, focus, `s_foco`, `s_cov`, `s_lex` |
| `consultas.py` | Query understanding: intention and relation words, cues, synonyms, generic words, derived nouns |
| `intenciones.py` | Similarity fallback: cached examples, cosine and margin between intentions |
| `respuestas.py` | Literal QA boundary completion: quantities with units and limits, actors with their current action |
| `sinonimos.py` | Packaged WordNet stem index, OOV expansion for BM25, project phrase equivalences and lexical provenance hash |
| `entidades.py` | Universal and pack entities (dates, amounts, deadlines, references) |
| `dominio.py` | Your own domain rules (`domain.yaml`) |
| `tonos.py` | Answer tones, their linter and neutrality |

### `ingesta/` — from files to fragments

| Module | What it does |
|---|---|
| `catalogo.py` | `documents/catalog.yaml`: what is loaded and active |
| `parsear.py` | PDF, DOCX, Markdown and TXT to text with structure and offsets |
| `ocr.py` | Optional OCR of PDF pages without text (Tesseract), with cache and confidence per page |
| `chunking.py` | Fixed-size strategies (`CH-F256`, and `CH-F256S`, which never crosses sections); new projects use the structural preparation instead (`preparacion.py`, `unidades.py`, [ADR 0009](decisions/0009-structural-preparation-by-default.md)) |
| `metadata.py` | Entities, TF-IDF keywords and a deterministic category |
| `ingesta.py` | The full `ipsis index` sequence |

### `modelos/` — ONNX on CPU

| Module | What it does |
|---|---|
| `onnx.py` | `ModeloOnnx`: shared session and tokenizer (Template Method) |
| `denso.py` | e5 encoder with prefixes and pooling |
| `reranker.py` | Cross-encoder: one logit per (question, passage) pair |
| `lector.py` | QA reader: a literal span or "no answer" |
| `catalogo.py`, `descarga.py`, `verificacion.py`, `exportacion.py` | Which models exist, offline cache, minimal check and export (development) |

### `indice/` — Qdrant and what describes it

| Module | What it does |
|---|---|
| `qdrant.py` | Dense + sparse BM25 collection, indexing and hybrid search with RRF |
| `estadisticas.py` | `stats.json`: df, N and mean length for the signals |
| `manifiesto.py` | What the index was built with (model, stemmer, corpus hash) |
| `payload.py` | Qdrant payload ↔ `ChunkRecord` |

### `consulta/` — the engine

| Module | What it does |
|---|---|
| `motor.py` | Runs the profile's stages, times each one and builds the result |
| `contexto.py` | `ContextoConsulta`: what each stage reads and fills in |
| `seguimiento.py` | Conversation memory: topics per session, follow-ups, expiry ([ADR 0006](decisions/0006-conversation-memory.md)) |
| `alternativas.py` | Proactive posture: similar literal paragraphs after a `no_answer`, chosen by the family of a missing declared entity ("TP-400" for "TP-500") or by nearly all the question words ([ADR 0008](decisions/0008-proactive-posture-and-metadata-similarity.md)) |
| `admision.py` | Limit of concurrent queries (503 when saturated) |
| `variantes.py` | Picks the tone variant by session and turn |
| `etapas/` | One file per stage (see §4) |

### `evaluacion/` — measuring and calibrating (pure functions)

| Module | What it does |
|---|---|
| `banco.py` | The versioned bank format |
| `golden.py` | CSV, JSONL and SQuAD 2.0 ↔ bank; question template |
| `metricas.py` | Coverage, false `ok`, Clopper-Pearson risk, latencies |
| `calibracion.py` | Chooses thresholds on `dev` with risk ≤ α |
| `benchmark.py`, `comparacion.py` | Per-profile reports and comparison |

### `aplicacion/` — use cases

One per area, shared by the CLI and the API: `proyecto`, `corpus`,
`consulta`, `modelos`, `golden`, `evaluacion`, `benchmark`, `diagnostico`
(`ipsis doctor` and `/ready`), `registro` (queries and `ipsis audit`),
`personalidad`, `avatar`, `widget`, `estilos`, `modo` (development or
production), `despliegue` and `publico` (public ↔ internal names).
`registro_base.py` registers the default implementations.

### `cli/` and `servicio/` — presentation

| Module | What it does |
|---|---|
| `cli/base.py`, `cli/comandos/*` | One command per class (Command pattern), grouped as in `ipsis --help`; texts from the message catalog |
| `cli/menu.py`, `cli/comandos/chat.py` | `ipsis` alone (or `ipsis help`): the commands grouped by task with examples; `ipsis chat`: the interactive mode, questions to one engine loaded once and `/commands` dispatched to the same CLI |
| `servicio/api.py` | FastAPI: `/ask`, `/config`, `/ready`, static files, CORS, cache and errors; translates the engine contract to the public one |
| `servicio/admin.py` | `/admin` (API with a token) and `/admin/panel`: personality and styles, and also status, thresholds, document upload and reindexing (`aplicacion/panel.py`); a reload replaces the engine in the background (`servicio/api.py::recargar_motor`) |
| `servicio/seguridad.py` | Rate limit and widget keys |
| `servicio/estaticos/` | `widget.js`, `avatar.js` (the bundled avatar engine) and the panel |

### `recursos/` — data shipped in the package

`plantillas/` (what `ipsis init` copies), `mensajes/` (the en/es message
catalog), `idiomas/`, `tonos/<language>/`, `perfiles/`, `avatares/` (Folio)
and `despliegue/` (templates of `ipsis deploy prepare`).

## 4. Life of a question

```mermaid
flowchart TD
    P([Question]) --> C{conversational}
    C -- "hello, thanks…" --> RF([Fixed answer from the tone])
    C -- no --> A["analysis<br/>follow-up? → inherit the topic<br/>intention and relation words<br/>synonyms of missing words"]
    MEM[("conversation memory<br/>current and earlier topics")] -.->|"“and with 90?”"| A
    WN[("filtered local WordNet<br/>source + sense + POS")] -.->|"OOV, one sense only"| A
    A --> CF[confidence<br/>dense cosine → s_ret]
    CF --> IF["unknown intention + corpus topic?<br/>reuse vector → example similarity"]
    IF --> F["filters<br/>focus terms (not relation<br/>nor generic words), s_oov"]
    F --> R[retrieval<br/>original e5 vector + expanded BM25<br/>RRF + entity-directed]
    R --> T{any candidate<br/>with a focus term?}
    T -- no --> E
    T -- yes --> RR[reranking<br/>cross-encoder → s_rr]
    RR --> L["reading<br/>QA reader → span, s_qa<br/>+ the candidate with a cue"]
    L --> E["evidence<br/>anchor sentence, cue bonus<br/>→ s_foco, s_cov"]
    E --> PO{policy<br/>cascade_v1}
    PO -- ok --> RD[rendering<br/>tone + citation]
    PO -- related --> RD
    PO -- no_answer --> ALT["alternatives (proactive posture)<br/>premise or no answer only<br/>declared-entity family or<br/>nearly all question words<br/>→ literal paragraphs, verified"]
    ALT --> RD
    RD --> V[verification<br/>text == corpus start:end]
    V -.->|"first cited source passage<br/>same topic and turn only"| MEM
    V --> S([Answer + citations + diagnostics])
```

| Stage | light | medium |
|---|:-:|:-:|
| conversational, analysis (typo correction), confidence, filters, retrieval | ✓ | ✓ |
| clarification (inside retrieval: no topic → `necesita_aclaracion`) | ✓ | ✓ |
| reranking | — | ✓ (mmarco, k=4) |
| reading | — | ✓ (semantic reading: top 3 sentences by RRF of cross-encoder, e5, lexical) |
| evidence, policy, rendering, verification | ✓ | ✓ |
| historical p95 (universal bank) | 85 ms | 815 ms |

The former `heavy` profile was removed on 2026-10-08 (ADR 0003). See
[general regression](../herramientas/evaluacion/README.md) for reproducible
measurements and alternative-model comparisons.

Each stage receives the `ContextoConsulta`, fills it in and may close the
query. A `no_answer` from a false premise or without an answer may carry
alternatives: similar paragraphs that are in the documents, never an answer
and never part of the conversation memory
([configuration](guide/configuration.md#when-the-answer-is-not-there-posture)). If no candidate contains a focus term, the reranker and the reader
are skipped (early exit). The rules in detail: [policy](methodology/policy.md).

### Understanding the question

The analysis stage reads the question with the language pack's rules
(`ipsis/recursos/idiomas/<language>.yaml`), without any model: patterns,
word lists and the corpus statistics. Nothing is generated and the question
the user wrote is the one that is answered. Three things come out of it:

After dense confidence, an unrecognized intention can use example similarity
with a cached query vector. Examples are encoded at startup. In a follow-up,
both pattern recognition and similarity use the current user's question;
inherited words supply retrieval context, not a different relation. This
fallback needs a corpus topic, measured model/language settings, minimum
cosine, a margin against the second intention and language-declared compatible
question forms. The extra check rejects amount/actor questions that resemble
deadline/procedure examples. It supplies answer cues;
it removes no query terms and changes no acceptance thresholds. BM25 skips it.
Shipped E5-small settings enable only categories with correct dev fallback
cases: end/procedure in Spanish, end in English and procedure in Portuguese.

The QA reader receives the current follow-up when it expresses a recognized
relation or multiple content terms. A bare qualifier ("and in summer?")
retains the interpreted question so the topic and preceding relation remain
available. Intent recognition still uses the current turn. For actor
questions, it reads the sentence selected for that action, excluding other
roles elsewhere in the passage. Selected quantity spans can include their
adjacent unit, limit and reference point; selected actor spans can include
the matching action clause. This completion is literal, retains exact
offsets and records the raw model span in diagnostics. It does not replace
the selected actor or number with another one, and answer thresholds remain
unchanged.

| | What it looks for | Example | What changes afterwards |
|---|---|---|---|
| **Follow-up** | Whether the question follows the conversation's current topic, returns to an earlier one or opens a new one, by its topic terms and a follow-up marker ("and", "y", "e") | "¿y con 90?" after "¿Qué pasa si el proveedor rechaza la orden?" | Retrieval uses "¿y con 90? proveedor rechaza orden"; the selection weighs the user's own words fully and the inherited ones half |
| **Intention** | Which relation is asked for: start, end, threshold, consequence, person in charge, requirement, procedure | "cuando empieza la compra?" → start; relation words "cuando", "empieza" | Relation words are not topic (not focus, not scored in the selection); a sentence with one of the intention's cues ("Una vez…", "después de…") weighs ×2, and the reader also reads the candidate with the best cued sentence |
| **Synonyms** | A question word missing from the corpus whose synonym is in it | "necesita" → "requieren" | The synonym is searched and measured instead of the missing word |

The conversation memory keeps, per `session_id`, the current topic (its
core terms, the last follow-up and the vocabulary of the passages that
answered it) and up to four earlier ones, so a question can return to them.
An out-of-domain question in the middle does not change the topic; a
deliberate change of topic never inherits, even if it starts with "and". A
conversation is forgotten after `conversation.expiry_minutes` without
questions (30 by default, in `engine.yaml`), and the widget starts a new one
on every page load. The rationale and the measurements are in
[ADR 0005](decisions/0005-deterministic-query-understanding.md) and
[ADR 0006](decisions/0006-conversation-memory.md); the signals in
[lexical](methodology/lexical.md).

Vocabulary enters memory only after final verification, from the source
passage containing the first displayed citation. That context lets the next
question refer to a neighboring step; other candidates are excluded. An
out-of-domain turn cannot replace the vocabulary. Turn tokens reject stale
concurrent replies, and compaction also removes obsolete surface forms.

`genericas_memoria` is separate from the answer's generic-word list:
`tiempo/tempo` do not open or contaminate a topic, but keep their original
weight in focus and answer selection. Topic compaction must not change
how an independent question is answered.

## 5. Ingestion

```mermaid
flowchart LR
    D["documents/<br/>PDF · DOCX · MD · TXT"] --> PA[parse<br/>text + sections + offsets]
    D -.->|"PDF page without text"| OCR["OCR (optional)<br/>Tesseract, confidence per page"]
    OCR -.-> PA
    PA --> CH[chunking<br/>never across sections]
    CH --> ME[metadata<br/>entities, keywords]
    ME --> EM[e5 encoder<br/>passage: …]
    ME --> BM[BM25<br/>stemmed terms]
    EM --> Q[(Qdrant)]
    BM --> Q
    CH --> ES[stats.json]
    Q --> MA[manifest.json<br/>model, stemmer, hash]
```

`ipsis index` rebuilds everything. `ipsis doctor` compares the manifest with
the profile and the language, and a fingerprint of the documents with the
indexed one, to tell when reindexing is needed.

## 6. Service and widget

```mermaid
sequenceDiagram
    participant U as User
    participant W as Widget (Shadow DOM)
    participant S as Service
    participant M as Engine
    W->>S: GET /config (language texts, tone, placement, avatar)
    U->>W: types the question
    W->>W: avatar typing → sent → thinking
    W->>S: POST /ask {question, session_id}
    S->>S: CORS, widget key, rate limit, admission
    S->>M: consultar()
    M-->>S: AssistantResult (status, text, citations with offsets)
    S-->>W: answer + exact_answer (only when ok)
    W->>U: literal text + citations with the span marked
    W->>W: avatar by status (happy · unsure · sorry)
```

| Route | What for |
|---|---|
| `POST /ask` | The question |
| `GET /config` | What the widget needs: language texts, tone microcopy, styles, placement and avatar |
| `GET /widget.js`, `/avatar.js`, `/styles.css`, `/avatars/*.avatar.json` | Static files (long cache in production) |
| `GET /health` · `GET /ready` | Alive · ready, with the project diagnosis (503 when something blocks) |
| `/admin/*`, `/admin/panel` | Personality, styles, status, thresholds, documents and reindexing over HTTP, with a token and HTTPS |
| `GET /source` | Source code (AGPL §13) |

## 7. Deployment

```mermaid
flowchart LR
    subgraph Team["Your team"]
        R1["ipsis load · index · calibrate"] --> R2["ipsis deploy prepare"]
    end
    R2 -- "dist/" --> VPS
    subgraph VPS["Server (docker compose)"]
        CA["caddy<br/>https profile"] -- "X-Forwarded-*<br/>trusted IP" --> AS["assistant<br/>image per profile<br/>offline, non-root"]
        AS --- V[("config/ · documents/ · .ipsis/")]
    end
    Internet((Internet)) -- "443" --> CA
```

Step by step in the [deployment guide](guide/deployment.md).

## 8. Auditing

| The auditor's question | Where it is answered |
|---|---|
| What was the index built with? | `.ipsis/index/*.manifest.json`: model, stemmer, corpus hash, payload version |
| Why does this term weigh so much? | `.ipsis/index/*.stats.json`: df, N, mean length |
| Where do the thresholds come from? | `config/calibration.yaml`: bank, hashes, α and the `test` result |
| Why was this question `related`? | `ipsis ask --diagnostics` or the query log: stages, signals and rule |
| Is the answer literal? | `ipsis audit`: checks every logged piece of evidence against the corpus |
| Who changed the personality? | `.ipsis/logs/admin.jsonl`: date, IP, action and keys (never the token) |

## 9. Design patterns

| Pattern | Where | What for |
|---|---|---|
| Strategy + Protocol | `nucleo/contratos.py` | Swappable components |
| Registry / Factory | `nucleo/registro.py`, `aplicacion/registro_base.py` | Build components by name; heavy imports live inside the factory |
| Pipeline | `consulta/motor.py` + `etapas/` | The profile lists the stages; the engine runs and times them |
| Template Method | `modelos/onnx.py` | What the three ONNX models share |
| Adapter | `indice/qdrant.py`, `modelos/*` | Isolate Qdrant and onnxruntime |
| Command | `cli/comandos/*` | One command, one class |
| Facade (use cases) | `aplicacion/*` | CLI and API share the logic |
| Layered configuration | `configuracion/perfiles.py` | profile ← `engine.yaml` ← calibration |
| Value objects | `nucleo/esquemas.py` | Every piece of data crossing a boundary is strict Pydantic |
| Glossary at the edges | `configuracion/glosario.py`, `recursos/mensajes/` | English for users, internal names for the code |
