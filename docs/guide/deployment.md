# Deploying on your own server

How to put the assistant on a server with HTTPS: the service, Caddy, Docker,
`ipsis deploy prepare` and the run modes. Installation and profiles are in
[installation.md](installation.md).

ipsis is built for self-hosting: your service, your documents and your
domain.

## Continuous integration

`.github/workflows/servicio.yml` runs on pushes, pull requests and manual starts.
Its contract job checks the engine and HTTP boundary without downloading models.
Its container job builds a wheel from the current checkout, creates a Spanish
light-profile project containing a known inventory record, downloads the required
CPU model, loads and indexes the document, then runs `ipsis deploy prepare --wheel`.
The generated Dockerfile installs that wheel, so the check tests the commit in
question rather than another branch or a published version.

Docker Compose builds with the runner's UID/GID for writable mounted configuration
and index directories, starts the service and waits for its `/ready` healthcheck.
`herramientas/ci/comprobar_servicio.py` then verifies a nonempty v2 index, production
mode, the widget catalog, four kinds of conversation and literal source retrieval
with correct offsets. A question prefixed with “hola” must still retrieve the
known inventory value. Replies with HTTP 200 but empty or incorrect bodies fail.
The helper saves a JSON report even on failure; Actions also uploads container
status and logs and stops only its own test deployment afterwards.

The manual `.github/workflows/regresion-general.yml` retains the historical
direct-answer evaluation and artifacts. Its optional `comparar_referencia` input
enables comparison with the frozen baseline. Those answer/abstention metrics
are not ranking metrics: v2 intentionally returns sources for review. This
evaluation is separate from the automatic service startup gate; the baseline
has not been rewritten to conceal that difference.

To reproduce the container check on Linux with Docker Compose and uv:

```bash
uv sync --locked --extra test
uv build --wheel --out-dir .cache/ci/wheels
uv run python herramientas/ci/preparar_contenedor.py --output .cache/ci --wheels .cache/ci/wheels
export COMPOSE_FILE="$PWD/.cache/ci/deploy/docker-compose.yml"
export COMPOSE_PROJECT_NAME=ipsis-ci
docker compose build --build-arg APP_UID="$(id -u)" --build-arg APP_GID="$(id -g)"
docker compose up -d --no-build --wait --wait-timeout 180
uv run python herramientas/ci/comprobar_servicio.py --url http://127.0.0.1:8000 --output .cache/ci/reporte.json
docker compose down --remove-orphans
```

Use a fresh output directory when repeating preparation. Port 8000 must be
available. The check proves packaging, startup and basic interaction with a
real indexed corpus; it does not certify search quality on every document.

## 1. Service on loopback

`ipsis serve` listens on `127.0.0.1:8000` by default. Keep it that way and put
an HTTPS proxy in front. An example with systemd:

```ini
# /etc/systemd/system/ipsis-assistant.service
[Unit]
Description=ipsis
After=network.target

[Service]
User=ipsis
WorkingDirectory=/srv/my-assistant
Environment=HF_HUB_OFFLINE=1
ExecStart=/srv/venv/bin/ipsis serve --host 127.0.0.1 --port 8000 --no-open --no-demo
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## 2. HTTPS with Caddy

Caddy gets and renews the certificate by itself:

```caddyfile
assistant.your-domain.com {
    reverse_proxy 127.0.0.1:8000
}
```

Then, in the project:

```bash
ipsis configure cors_origins=https://www.your-site.com
ipsis configure widget_keys=public-site-key   # optional
```

## 3. Docker

`ipsis deploy prepare` (next section) generates the image together with
your project: one `Dockerfile` per profile, with the models included, and a
`docker-compose.yml`. At run time it uses no network.

- It installs the package (your wheel with `--wheel`, or the repository's)
  and downloads the profile's models at build time (the only step with
  network).
- It runs as a non-root user (uid 10001), with `HF_HUB_OFFLINE=1` and
  `IPSIS_MODE=production`.
- Without `IPSIS_ADMIN_TOKEN`, `/admin` does not exist; set it at run time.
- Healthcheck on `/ready`, which answers 503 when something blocks (with the
  action in `project.blocking`).
- The project (`config/`, `documents/` and `.ipsis/`) is mounted from the
  generated folder: configuration changes do not need a rebuild.

## 4. `ipsis deploy prepare`

It generates a folder ready to copy to the server:

```bash
ipsis deploy prepare --domain assistant.your-domain.com
```

`dist/` contains:

- the configuration (with `personality.yaml`, `styles.yaml`, the calibration
  and the imported avatars), the documents and the index;
- `Dockerfile`, `docker-compose.yml` (with an optional Caddy, `https`
  profile, already declared as a trusted proxy), `Caddyfile` and
  `.env.example`;
- `DEPLOY.md` in the project language, with the widget snippet and how to
  enable `/admin`.

The query logs and the secrets are not copied.

- **Exact version:** without `--wheel`, the image installs the current
  version of the public repository. To pin yours, build the wheel
  (`uv build --wheel`) and pass it with `--wheel`.
- **Regenerate:** `--force` replaces a previously prepared folder. It never
  deletes a folder this command did not generate.

On the server:

```bash
cp .env.example .env
sudo chown -R 10001:10001 config .ipsis
docker compose --profile https up -d --build
```

## Run modes: development and production

The service runs in one of two modes, with `ipsis serve --mode` or
`IPSIS_MODE`. **The default is `production`.**

| Aspect | `development` | `production` |
|---|---|---|
| `/admin` panel over plain HTTP | allowed from any IP, with a warning | only from the machine itself; from outside it requires HTTPS |
| `/admin` token | required; `serve` prints a temporary token if one is not configured | required; `serve` prints a temporary token if one is not configured; `--no-admin` disables the panel |
| Proxy headers | accepted from the machine itself | only from the proxy in `IPSIS_TRUSTED_PROXY` |
| `/docs` (OpenAPI) | enabled | disabled unless `IPSIS_DOCS=1` |
| Widget files | not cached, to see changes on reload | long versioned cache |
| 500 errors | with details | only an id; the details go to the log |

Use `development` on your machine or to try a server without a
certificate. Use `production` for any public service. The mode does not
change the assistant's answers. `ipsis serve` enables the test widget and admin
panel and opens the browser by default. Use `--no-open --no-demo` for a service
without a browser or test page, and add `--no-admin` if you do not need the panel.
For a persistent admin credential, configure `IPSIS_ADMIN_TOKEN`; temporary
tokens change at every startup and are not written to the project. Direct ASGI
startup with `crear_app` keeps the environment-based defaults.

Variables of the mode and the `/admin` panel:

| Variable | Effect |
|---|---|
| `IPSIS_ADMIN_TOKEN` | Enables `/admin`; at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `IPSIS_TRUSTED_PROXY` | IP of the proxy (for example Caddy) whose `X-Forwarded-*` headers are accepted |
| `IPSIS_ADMIN_IPS` | Optional: IPs allowed on `/admin` |
| `IPSIS_MODE` | `production` (default) or `development`; also `ipsis serve --mode` |
| `IPSIS_DOCS=1`, `IPSIS_DEMO=1` | `/docs` and `/widget/demo.html` also in production |
| `IPSIS_SOURCE_URL` | URL of your source code (AGPL §13) that `GET /source` redirects to. Default: this repository |
| `IPSIS_LANG` | `es` to serve the `/admin/panel` in Spanish |

After 5 wrong tokens, the IP is blocked for 15 minutes. Every change is
logged in `.ipsis/logs/admin.jsonl`: date, IP, action and keys, never the
token. The panel can also change thresholds and upload documents (up to
20 MiB each, PDF, DOCX, MD, TXT, XLSX, XLS, CSV or TSV) and reindex: treat the token like a
deployment credential. A reload replaces the engine in the background and
`/ask` answers 503 meanwhile, so reindex outside busy hours. `ipsis doctor` checks the mode: it warns in development and fails
with a short token.

On a server with Caddy in front:

```bash
export IPSIS_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export IPSIS_TRUSTED_PROXY=127.0.0.1      # Caddy on the same machine
ipsis serve --mode production --no-open --no-demo
```

To rotate the token, change it and restart the service.

## Before launching with real users

A checklist with the real corpus. The person publishing decides it; no
command ticks it automatically.

- [ ] **Real golden set:** written and reviewed by a person, with at least
  30% of questions without an answer or with a false premise, and "same
  topic, missing fact" pairs (see [golden.md](golden.md)).
- [ ] **Calibration:** inspect `dev` and `test` separately: `CALIBRATED` describes
  selection on `dev` and is insufficient if `test` fails. In `test`, the 95%
  upper bound of incorrect direct-answer risk should be ≤ 5%; with 0 errors it
  needs at least 59 accepted answers in `test`). If it gives
  `INSUFFICIENT_SAMPLE`, you can launch with the profile thresholds, without
  claiming the 5%. Regenerate v1 calibrations: v2 measures full answers and
  separates QA span quality. For command/file adjustments and restart/indexing
  requirements, see [deployment configuration](configuration.md#changing-configuration-for-deployment).
  Generated `DEPLOY.md` includes configuration and container CLI instructions.
- [ ] **Latency:** `ipsis benchmark` meets the profile budget on the
  production machine (light ≤ 150 ms and medium ≤ 1 s at p95).
- [ ] **Tests green** on the version being deployed (`uv run --locked --extra test --extra browser pytest`).
- [x] **License:** AGPL-3.0-only.
