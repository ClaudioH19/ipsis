# Installation

How to install ipsis, choose a profile, download the models and create
your first project. Everyday use and the command reference are in
[usage.md](usage.md); a server with HTTPS in [deployment.md](deployment.md).

## Requirements

- Python 3.11 or 3.12.
- CPU: no GPU needed. The models run with onnxruntime.
- Disk space for the profile's models. It is a global per-user cache shared
  by every project:

  | Profile | Models | Approx. disk | p95 target |
  |---|---|---|---|
  | `light` | dense e5-small | 0.5 GB | 150 ms |
  | `medium` | e5-small + mMiniLM reranker + mDeBERTa reader | 1.7 GB | 1 s |
  | `heavy` | e5-base + bge-m3 reranker + mDeBERTa reader | 2.8 GB | 5 s |

  `bm25` is a diagnostic profile for `ipsis benchmark` only: it cannot be
  installed.
- Network only to download the models. Afterwards the service works offline.

## Install the package

Use one virtual environment per server or machine. The package installs the
`ipsis` command.

**Linux and macOS**

```bash
python3 -m venv ~/.venvs/ipsis
source ~/.venvs/ipsis/bin/activate
pip install "ipsis @ git+https://github.com/ClaudioH19/ipsis.git"
ipsis --version
```

**Windows (PowerShell)**

```powershell
py -3.12 -m venv $HOME\.venvs\ipsis
& $HOME\.venvs\ipsis\Scripts\Activate.ps1
pip install "ipsis @ git+https://github.com/ClaudioH19/ipsis.git"
ipsis --version
```

**On a server with Docker:** `ipsis deploy prepare` generates the image and
the compose file for your project (see [deployment.md](deployment.md#3-docker)).

### For development

```bash
git clone https://github.com/ClaudioH19/ipsis.git
cd ipsis
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"        # Linux/macOS
.venv\Scripts\python.exe -m pip install -e ".[test]" # Windows
```

Optional extras:

| Extra | What for | Production? |
|---|---|---|
| `test` | pytest | no |
| `browser` | browser tests with Playwright (`python -m playwright install chromium`) | no |
| `export` | `ipsis models export`: converts a Hugging Face model to ONNX (`optimum-onnx` and `torch`) | no; development only |

Production never installs torch. An editable install stores absolute paths:
if you move the clone, reinstall.

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
ipsis serve                    # http://127.0.0.1:8000 (open /widget/demo.html with --mode development)
```

In another terminal:

```bash
ipsis ask "How often should the filter be changed?"
```

- **Profile:** `light`, `medium` or `heavy` (see the requirements table).
  Change it later with `ipsis profile set <profile>`. `light` and `medium`
  share the index; `heavy` needs reindexing.
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
pip install "ipsis[ocr]"
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
- `ipsis load` lists the pages read with OCR: check their citations, since
  OCR can mistake letters.
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
