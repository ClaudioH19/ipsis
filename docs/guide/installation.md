# Installation

How to install ipsis, choose a profile, download the models and create
your first project. Everyday use and the command reference are in
[usage.md](usage.md); a server with HTTPS in [deployment.md](deployment.md).

## Requirements

- `uv` and Git. `uv` installs Python 3.12 automatically if needed; there is no separate Python installation step.
- CPU: no GPU needed. The models run with onnxruntime.
- Disk space for the profile's models. It is a global per-user cache shared
  by every project:

  | Profile | Models | Approx. disk | p95 target (`ipsis benchmark`) |
  |---|---|---|---|
  | `light` | dense e5-small | 0.5 GB | 150 ms |
  | `medium` | e5-small + reranker (bge-reranker-v2-m3 for Spanish and Portuguese, mMiniLM otherwise) | 1.0 GB (Spanish, Portuguese) · 0.6 GB (other languages) | 1 s |

  `bm25` is a diagnostic profile for `ipsis benchmark` only: it cannot be
  installed.
  Sizes are the ONNX files on disk (measured on 2026-10-16 after `ipsis models download`: e5-small
  470 MB, bge-reranker-v2-m3 int8 571 MB, mMiniLM 119 MB). The extractive QA reader (mDeBERTa) is loaded only when the
  optional `v2.qa_highlights` is on; otherwise neither the engine nor `ipsis models download` fetches it, and
  `ipsis models list` shows what the active configuration uses.
  Measured latency of a whole `medium` query (v2; synthetic passage bank, 116 questions, 4 CPUs of an Intel Xeon
  2.1 GHz, 2026-10-16): Spanish with bge-reranker-v2-m3, p50 604 ms and p95 749 ms; English with mMiniLM,
  p50 349 ms and p95 620 ms. That bank has short passages: with real Spanish documents the p95 was 1.7 s (see
  [ADR 0003](../decisions/0003-onnx-and-profiles.md)).
  The "p95 target" is the profile's `p95_budget_ms`: the reference `ipsis benchmark` uses to mark whether a
  profile meets its latency, shown also by `ipsis profile` and the panel. The default engine (v2) does not apply
  it to queries: a v2 query is bounded by `v2.query_budget_ms` (2500 ms), the same for both profiles.
  `medium` is the recommended default for `ipsis init`.
- Network only to download the models. Afterwards the service works offline.

## Install the package

**uv** manages Python and all Python dependencies. You do not need to create
or activate an environment, or clone the repository, to use ipsis.

### 1. Install uv (once)

On Windows, in PowerShell:

```powershell
winget install --id astral-sh.uv -e
```

On Linux or macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal. Check `uv --version` and `git --version`; Git is needed
to install from the repository. On Windows, install it if missing with
`winget install --id Git.Git -e`; on Linux or macOS use your system's package manager.

### 2. Install ipsis (the same command on every system)

```bash
uv tool install --python 3.12 "ipsis @ git+https://github.com/ClaudioH19/ipsis.git"
uv tool update-shell
```

Open a new terminal and run `ipsis --version`. You can now use `ipsis` from
any folder. `uv` maintains an internal isolated environment to avoid conflicts;
you do not need to create or activate it. Installing the command is separate
from creating a project: each assistant still lives in its own folder.

### Update

```bash
uv tool upgrade ipsis
```

Stop the service before updating and start it again from the same project
directory. Documents, indexes and configuration are preserved; presentation
changes need no reindexing. Existing `styles.yaml` files are retained: apply a
preset or edit individual settings to adopt new options. Reload the browser
and replace exported `widget.js` copies if your website uses them.

Git branch installations update to a new commit on that branch. To pin the
1.1 release, install `ipsis @
git+https://github.com/ClaudioH19/ipsis.git@v1.1.0`. Tag or commit installations
need a changed reference to move to another release.

**In Docker:** `ipsis deploy prepare` generates your project's image;
it also installs the package with uv (see [deployment.md](deployment.md#3-docker)).

### Only if you develop the repository

These steps are not required to use ipsis. To change its code:

```bash
git clone https://github.com/ClaudioH19/ipsis.git
cd ipsis
uv sync --locked --extra test
uv run --locked --extra test ipsis --help
uv run --locked --extra test pytest -m "not slow and not browser"
```

`uv sync` creates and manages `.venv` automatically using `uv.lock`;
`uv run` executes inside it without activation. For browser tests use
`uv sync --locked --extra test --extra browser` and
`uv run --locked --extra test --extra browser playwright install chromium`.
Keep those extras on the `uv run` commands that need them.

| Extra | Install in the clone | What for |
|---|---|---|
| `test` | `uv sync --locked --extra test` | pytest |
| `browser` | `uv sync --locked --extra test --extra browser` | Playwright |
| `export` | `uv sync --locked --extra export` | Export models to ONNX; development only |
| `ocr` | `uv sync --locked --extra ocr` | Read scanned PDFs; also needs Tesseract |

Production does not install torch. If you move the clone, run `uv sync` again.

## Create a project

Each assistant is a folder with its configuration, its documents and its
index:

```bash
mkdir my-assistant && cd my-assistant
ipsis init --profile medium --language en \
  --assistant-name "Support assistant" --domain-description "the product manuals"
ipsis models download          # the profile's models to the global cache (once per machine)
ipsis models verify            # loads each model and runs a minimal inference
ipsis load /path/to/documents  # PDF with text, DOCX, Markdown or TXT
ipsis index
ipsis doctor                   # can it run? If not, which command to run
ipsis serve                    # opens the widget and enables /admin/panel with a temporary token if needed
```

In another terminal:

```bash
ipsis ask "How often should the filter be changed?"
```

- **Profile:** `light` or `medium` (see the requirements table).
  Change it later with `ipsis profile set <profile>`. `light` and `medium`
  share the index.
- **Language:** `es`, `en` and `pt` have their own pack. A regional variant
  (`pt-br`) uses its base language. Any other ISO code works with the
  universal rules and English texts. Without `--language`, `ipsis init`
  uses `en` (or `es` with `IPSIS_LANG=es`).
- **Shortcut:** `ipsis serve ./my-documents` creates a private project in
  `.ipsis-project/`, loads the files, indexes when needed and serves.

## Scanned PDFs (OCR, optional)

A PDF made of images (a scan, photos of pages) has no text to extract. With
OCR, `ipsis load` reads those pages with [Tesseract](https://github.com/tesseract-ocr/tesseract);
without it, the PDF is rejected and the rest of the folder still loads.

```bash
uv tool install --force --python 3.12 "ipsis[ocr] @ git+https://github.com/ClaudioH19/ipsis.git"
```

Then install the Tesseract program with the language of your documents:

| System | Command |
|---|---|
| Debian/Ubuntu | `sudo apt install tesseract-ocr tesseract-ocr-spa tesseract-ocr-por` |
| macOS | `brew install tesseract tesseract-lang` |
| Windows | `winget install UB-Mannheim.TesseractOCR` (choose the languages in the installer) |

- Only pages without text go through OCR; digital pages are read as usual.
- The project language picks the OCR language (`es` → `spa`, `pt` → `por`,
  `en` → `eng`), plus English for acronyms.
- `ipsis load` and `ipsis index` show each page as it is read, with its
  **confidence** (Tesseract's average over its words, 0–100 %), and list the
  files read with OCR. Under 85 % a page is flagged as low confidence: OCR
  starts to mistake letters there ("Horanos" for "Horarios"), so check its
  citations or scan it again.
- What `ipsis load` reads is kept in `.ipsis/ocr`: `ipsis index` reuses the
  same text instead of reading again, as long as the file, the languages and
  the Tesseract version do not change.
- `IPSIS_OCR=off` turns it off even when it is installed.

## Model cache and offline use

| Variable | Effect |
|---|---|
| `IPSIS_MODELS_DIR` | Folder of the global cache. Default: `~/.cache/ipsis/models` |
| `HF_HUB_OFFLINE=1` | Never use the network. If a model is missing, the error says what to do |
| `IPSIS_ONNX_THREADS` | onnxruntime threads per model |

On a machine without network, download on another machine with
`ipsis models download --profile <p>` and copy the cache folder.

## Qdrant

By default the index lives inside the project, in local mode
(`.ipsis/index/qdrant`). In that mode Qdrant locks the folder: stop
`ipsis serve` before running `ipsis index`, `ipsis doctor` or
`ipsis ask --diagnostics`.

To use a Qdrant server, in `config/engine.yaml`:

```yaml
qdrant:
  mode: "server"
  server_url: "http://localhost:6333"
```

The `QDRANT_MODE` and `QDRANT_URL` variables work too.

## Your own server

ipsis is built for self-hosting: your service, your documents and your
domain. The step by step (Caddy with HTTPS, Docker, `ipsis deploy prepare`,
development and production modes and the `/admin` panel) is in
[deployment.md](deployment.md).

## License

The project is AGPL-3.0 (`AGPL-3.0-only`), the same license as the avatar
library. Details in the License section of the [README](../../README.md):

- installing it unchanged on your server adds no new obligations;
- if you modify it and offer it as a service, you must publish your changes
  and point `IPSIS_SOURCE_URL` at your repository. The widget and the panel
  link to `GET /source`, which redirects there.
