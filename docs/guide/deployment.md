# Deploying on your own server

How to put the assistant on a server with HTTPS: the service, Caddy, Docker,
`ipsis deploy prepare` and the run modes. Installation and profiles are in
[installation.md](installation.md).

ipsis is built for self-hosting: your service, your documents and your
domain.

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
ExecStart=/srv/venv/bin/ipsis serve --host 127.0.0.1 --port 8000
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
  (`python -m pip wheel . --no-deps`) and pass it with `--wheel`.
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
| `/admin` token | required; if `IPSIS_ADMIN_TOKEN` is not set, a temporary one is printed at startup | required; without `IPSIS_ADMIN_TOKEN` the panel does not exist |
| Proxy headers | accepted from the machine itself | only from the proxy in `IPSIS_TRUSTED_PROXY` |
| `/docs` (OpenAPI) | enabled | disabled unless `IPSIS_DOCS=1` |
| Widget files | not cached, to see changes on reload | long versioned cache |
| 500 errors | with details | only an id; the details go to the log |

Use `development` on your machine or to try a server without a
certificate. Use `production` for any public service. The mode does not
change the assistant's answers.

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
token. `ipsis doctor` checks the mode: it warns in development and fails
with a short token.

On a server with Caddy in front:

```bash
export IPSIS_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export IPSIS_TRUSTED_PROXY=127.0.0.1      # Caddy on the same machine
ipsis serve --mode production
```

To rotate the token, change it and restart the service.

## Before launching with real users

A checklist with the real corpus. The person publishing decides it; no
command ticks it automatically.

- [ ] **Real golden set:** written and reviewed by a person, with at least
  30% of questions without an answer or with a false premise, and "same
  topic, missing fact" pairs (see [golden.md](golden.md)).
- [ ] **Calibration:** `ipsis calibrate --alpha 0.05` gives `CALIBRATED` (in
  `test`, the 95% upper bound of false `ok` answers is ≤ 5%; with 0 errors it
  needs at least 59 accepted answers in `test`). If it gives
  `INSUFFICIENT_SAMPLE`, you can launch with the profile thresholds, without
  claiming the 5%.
- [ ] **Latency:** `ipsis benchmark` meets the profile budget on the
  production machine (light ≤ 150 ms, medium ≤ 1 s and heavy ≤ 5 s at p95).
- [ ] **Tests green** on the version being deployed (`python -m pytest`).
- [x] **License:** AGPL-3.0-only.
