# Usage

The everyday workflow of an assistant and the reference of every command.
Installation and profiles are in [installation.md](installation.md); the
server, Docker and run modes in [deployment.md](deployment.md). Every
configuration file is described in [configuration.md](configuration.md).

> The CLI speaks English by default. Set `IPSIS_LANG=es` to get every message
> in Spanish; commands and file names stay the same.

## Workflow

```text
ipsis init → ipsis models download → ipsis load → ipsis index → ipsis doctor → ipsis chat / ipsis serve
                                         ↑                                │
                     new or changed documents                             ↓
                                                 ipsis ask / the widget on your site
```

Optional, to measure and tune:

```text
ipsis golden template → (a person fills in golden.csv) → ipsis golden import
  → ipsis evaluate → ipsis calibrate --apply
```

## What the assistant answers

To inspect experimental structural DOCX preparation in a separate project:

```bash
ipsis prepare --project /path/project --output /path/new-copy
cd /path/new-copy
ipsis index
```

`ipsis prepare --index` also builds the index during preparation. The output
folder must be new and outside the source project. The copy uses v2 and a
separate structural index; the source keeps its configuration. This variant
supports DOCX body structures and XLSX/XLS/CSV/TSV records with explicit
extraction warnings. Preparation does not guarantee better answers. See
[structural preparation](../methodology/preparacion-estructural.md).

Every answer has a status, and the widget renders each one differently:

| Status | Meaning |
|---|---|
| `ok` | It found the text that answers; it shows it literally, with the citation |
| `related` | There is no direct answer; it shows the closest passage and says so |
| `no_answer` | It is not in the documents. With `plan: clarification`, the question does not say what it is about ("Who approves it?" with no previous conversation) and the assistant asks for the topic |
| `conversational` | A greeting, thanks, goodbye or "what can you do?" |

Each answer also carries a confidence level (`confidence_level`): `high` for a
direct answer read by the QA reader (medium), `medium` for a direct answer
without a reader (light; the widget shows "Check the citation"), `low` for a
related passage. The levels come from measured precision, not from a new
threshold; see [informal paraphrases](../methodology/informal-paraphrases.md).

The assistant never writes content: the text comes literally from your
documents, and the citations (document, section and offsets) go underneath
so anyone can check it.

## The terminal: menu and interactive mode

`ipsis help` prints every command grouped by task (Start, Documents, Ask,
Customize, Measure and calibrate, Deploy and operate) with examples;
`ipsis` with no arguments does the same when its output is not a terminal. `ipsis help <command>` prints the options of one command, the same
as `ipsis <command> --help`.

`ipsis` alone (or `ipsis chat`) opens the interactive mode, in the style of
Claude Code or Codex, with Folio and the project of the folder. Typing `/`
unfolds a menu of commands with their description; `Tab` shows subcommands
and options with their help and completes paths after `/load`; arrow up
recalls history (`~/.ipsis_history`). What you type is a question; what
starts with `/` is a command:

| In `ipsis chat` | What it does |
|---|---|
| any text | Asks the engine of the project in this folder; follow-up questions keep the topic |
| `/help` | Lists the commands of the interactive mode |
| `/diagnostics on\|off` | Shows, for every answer, the stages, signals, the deciding rule and the exact span (what `ipsis ask --diagnostics` prints) |
| `/reload` | Reloads the engine after changing configuration or documents |
| `/<command> …` | Any ipsis command: `/doctor`, `/load ./docs`, `/index`, `/profile show`, `/calibrate --help` |
| `/exit`, `/quit`, Ctrl+D | Leaves |

The models load once, with the first question. Before running a command the
engine is closed (the local index admits one client) and it reloads with the
next question. Like `ipsis ask --diagnostics`, it needs `ipsis serve` stopped
when the index is local.

Commands show real stages and elapsed time: file reading, passage preparation,
vector computation, or search and citation verification. Folio's answers
separate the text from its sources. `Ctrl+C` cancels and lets you keep chatting;
`/exit` or Ctrl+D leave. Unclosed quotes are explained without ending the
session. Progress goes to stderr and command output to stdout; redirected
output has no animation or color codes. `ipsis --help`, `ipsis help` and
`/help` include the uv installation command, with no manual environment
creation or activation.

On Enter, `/ser --demo --open` resolves to `/serve --demo --open` and
`/widg the app search` resolves nested command names. This also works in the
shell (`ipsis ser --demo`). The console shows corrections and leaves arguments,
paths and options intact. Ambiguous names list choices without executing.

For inventory formats and extraction limits, see [inventories](inventories.md).
`ipsis serve --demo` serves the themed page at `/widget/demo.html`;
`ipsis serve --open` also opens it once ready. Add `--mode development`
to enable the admin panel with a temporary token; the demo alone keeps the
current service mode and access controls.

## Command reference

### Project

| Command | What it does |
|---|---|
| `ipsis init [--profile light\|medium] [--language en] [--assistant-name N] [--domain-description D] [--force]` | Creates `config/` and `documents/`. The language defaults to `en` (or `es` with `IPSIS_LANG=es`). Without `--force` it never overwrites an existing project |
| `ipsis configure key=value …` | Edits `assistant.yaml`: `assistant_name`, `domain_description`, `language`, `profile`, `cors_origins`, `widget_keys` (lists separated by commas) and `query_log.enabled` (true or false) |
| `ipsis profile show` | Active profile, models, p95 budget and whether the index and the calibration fit it |
| `ipsis profile set <profile>` | Changes the profile. It tells you when to reindex; the previous calibration stops applying |
| `ipsis snapshot-config [--output PATH]` | Writes the effective configuration with every default resolved |

### Models

| Command | What it does |
|---|---|
| `ipsis models list` | Models of the active profile: license, ONNX file for your CPU and whether they are cached |
| `ipsis models download [--profile P]` | Downloads whatever is missing to the global cache. With `--profile` it prepares another profile without activating it |
| `ipsis models verify` | Checks that the files are complete and runs a minimal inference per model. It never downloads |
| `ipsis models export <hf_id> [--int8]` | Development only, with the `[export]` extra: converts a model to ONNX in `exported/` |

### Corpus

| Command | What it does |
|---|---|
| `ipsis load <file\|folder>` | Copies the documents (PDF with text, DOCX, MD, TXT, XLSX, XLS, CSV, TSV) to `documents/` and catalogs them. A file with the same name as one already loaded but different content is added separately: to retire the old one, set `active: false` in `documents/catalog.yaml` |
| `ipsis index [--corpus FOLDER]` | Rebuilds the whole index. Run it after every document change or after a profile change that asks for it |

### Asking

| Command | What it does |
|---|---|
| `ipsis serve [folder] [--host H] [--port P] [--reindex] [--mode production\|development] [--demo] [--open]` | Starts the API and the widget. Given a folder of documents, it creates and prepares a private project in `.ipsis-project/`. `--mode`: see [deployment.md](deployment.md#run-modes-development-and-production); in development, without `IPSIS_ADMIN_TOKEN`, it prints a temporary token |
| `ipsis chat [--diagnostics]` | Interactive mode: questions and `/commands` (see above) |
| `ipsis ask "<question>" [--url URL] [--timeout S]` | Asks the running service |
| `ipsis ask "<question>" --diagnostics` | Runs the engine locally, without the service, and shows each stage with its latency, the signals, focus terms, the deciding rule, the exact span, the tone and the templates used. With local Qdrant, stop `ipsis serve` first |

### Operations

| Command | What it does |
|---|---|
| `ipsis doctor` | Read-only diagnosis: configuration, profile, language, stemmer, models, index, calibration, golden set, CORS, personality and mode. Every error comes with its action. Exits with 0 when there are no errors |
| `ipsis audit [--from DATE] [--to DATE]` / `ipsis audit --trace ID` | Reviews the query log: statuses, rules, tones and whether every piece of evidence is still literal in the corpus. With `--from`/`--to` (`YYYY-MM-DD` or ISO 8601, UTC by default, inclusive) it only counts that range. `--trace` shows an original query and its steps by `consulta_id`, without running it or accessing the corpus. Turn the log on with `ipsis configure query_log.enabled=true` |

### Personality

Details in [personality.md](personality.md). Presentation only: it never
requires reindexing or recalibrating.

| Command | What it does |
|---|---|
| `ipsis personality show` | Active tone, variety and avatar (placement, size, gaze, colors, events with a fallback) |
| `ipsis personality validate` | Checks `personality.yaml`, your own templates and the avatar. Exits with 1 on errors |
| `ipsis personality tone list` | Tones for the project language, with an example of each |
| `ipsis personality tone apply <tone>` | Activates `cordial`, `formal`, `serious`, `upbeat`, `friendly`, `empathetic` or `direct` |
| `ipsis personality tone try [--tone T] [--situation S]` | Prints the variants with the project variables filled in |
| `ipsis personality avatar list` | Included and imported avatars |
| `ipsis personality avatar import <file.avatar.json> [--name N]` | Validates an avatar exported from the Studio and copies it to `config/avatars/` |
| `ipsis personality avatar apply <name>` | Uses that avatar in the widget |
| `ipsis personality avatar events` | Which animation or expression each event triggers, and which ones use a fallback |
| `ipsis personality avatar assign <event> <key>` | Assigns one of the avatar's keys to an event |
| `ipsis personality avatar colors [--body #rrggbb] [--eyes #rrggbb]` | Avatar colors, without modifying its file |

No terminal needed: the `/admin/panel` does the same with forms and a live
preview of the widget. It needs `IPSIS_ADMIN_TOKEN`; see
[personality.md](personality.md#admin-panel-adminpanel).

### Golden set and evaluation

Details in [golden.md](golden.md).

| Command | What it does |
|---|---|
| `ipsis golden template [--n 40] [--force]` | Generates `golden/golden.csv` and `golden/README.txt` from your documents |
| `ipsis golden import <file>` | Validates the CSV, JSONL or SQuAD 2.0 file, locates the answers, splits dev and test, and writes `golden/bank/` |
| `ipsis golden validate` | Checks the bank against the current corpus |
| `ipsis golden export --format squad2\|csv [--output PATH]` | Exports the bank |
| `ipsis evaluate [--bank MANIFEST] [--output PATH]` | Metrics of the active profile, with the bound on false `ok` answers |
| `ipsis calibrate [--alpha 0.05] [--apply]` | Chooses thresholds under risk control using dev only. It trains nothing |
| `ipsis compare <a.json> <b.json> [--output PATH]` | Compares two reports from `ipsis evaluate` |
| `ipsis benchmark --bank M [--bank M2…] [--profiles …] [--experiments] [--latency-only] [--repetitions N] [--output DIR]` | Compares profiles: safety, coverage, latency and cost |

### Widget

Details in [web.md](web.md).

| Command | What it does |
|---|---|
| `ipsis widget theme list` | Available visual presets |
| `ipsis widget theme apply <preset> [--path PATH]` | Applies a preset to `config/styles.yaml` |
| `ipsis widget theme preview [--path PATH] [--output PATH]` | Generates an HTML file to look at the theme |
| `ipsis widget style show [--section S]` | Every style value: `presentation`, `placement`, `colors`, `dark_colors`, `typography`, `shape`, `shadows` and `animations` |
| `ipsis widget style set section.key=value …` | Changes one or more values (e.g. `colors.accent=#0ea5e9 shape.panel_radius=10px`). It rejects unknown keys and dangerous CSS characters; if anything fails, nothing is written |
| `ipsis widget export <folder> [--api URL] [--position P]` | Exports `widget.js`, `snippet.html`, the avatar engine (`avatar.js` and its licenses) and the active avatar definition, to serve them elsewhere. `P`: `bottom-right`, `bottom-left`, `top-right`, `top-left` or `embedded` |
| `ipsis widget snippet [--api URL] [--component] [--key K]` | Prints the code to paste into your site, following `styles.yaml::placement` |

### Deployment

| Command | What it does |
|---|---|
| `ipsis deploy prepare [--target D] [--domain DOM] [--wheel W] [--force]` | Generates in `dist/` everything a server needs: project, index, `Dockerfile`, `docker-compose.yml` with optional Caddy and `DEPLOY.md`. See [deployment.md](deployment.md) |

## Environment variables

V2 is the default engine for new projects and configurations without a pipeline
selector. It routes queries to ranked sources for review. An explicit
`pipeline: v1` in `config/engine.yaml` keeps the legacy engine; change it to
`pipeline: v2` and restart the service to switch an existing project.
It publishes up to three source dropdowns per page with literal neighboring
context and a button to continue searching, and
keeps QA disabled by default. Reranking is progressive, with a 2500 ms work
budget; pending candidates remain available for continuation. See [ranked sources](../methodology/fuentes-v2.md)
for budgets, API fields and the retired council migration.
Use `ipsis widget theme apply search` (or `search_compact`) for visible
source titles and excerpts, a top search field and expandable context.

| Variable | Effect |
|---|---|
| `IPSIS_LANG` | `es` for Spanish messages (CLI and admin panel); English otherwise |
| `IPSIS_MODELS_DIR` | Folder of the global model cache |
| `HF_HUB_OFFLINE=1` | Never use the network |
| `IPSIS_ONNX_THREADS` | onnxruntime threads |
| `QDRANT_MODE`, `QDRANT_URL` | Qdrant `local` or `server` |
| `IPSIS_MODE`, `IPSIS_ADMIN_TOKEN`, `IPSIS_TRUSTED_PROXY`, `IPSIS_ADMIN_IPS`, `IPSIS_DOCS`, `IPSIS_DEMO`, `IPSIS_SOURCE_URL` | Run mode and `/admin`; see [deployment.md](deployment.md) |

## Troubleshooting

| Symptom | What to do |
|---|---|
| "already accessed" while indexing or diagnosing | Local Qdrant is locked by `ipsis serve`: stop the service or run Qdrant in server mode |
| `ipsis doctor` says models are missing | `ipsis models download` |
| Incompatible index after changing profile | `ipsis index` |
| The documents changed | `ipsis index` (`ipsis doctor` detects it) |
| The browser blocks the widget | Add the exact origin of the site with `ipsis configure cors_origins=https://…` |
| The widget shows an icon instead of the avatar | Your site's CSP does not allow `'unsafe-eval'` (the avatar engine needs it), or the avatar is invalid: `ipsis personality validate`. The chat works anyway |
| `/ready` answers 503 | Read `project.blocking`: it brings the failing check and the command that fixes it (the same as `ipsis doctor`) |
