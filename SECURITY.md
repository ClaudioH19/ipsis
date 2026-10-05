# Security

## Supported versions

| Version | Supported |
|---|---|
| 0.9.x | ✅ |
| < 0.9 | ❌ |

## Reporting a vulnerability

Do not open a public issue. Use GitHub's private reporting
(**Security → Report a vulnerability**) in this repository, with:

- the version (`ipsis --version`) and the mode (`IPSIS_MODE`);
- the steps to reproduce it and its impact;
- whether it affects the service, the widget, the `/admin` panel or the
  Docker image.

You will get an initial answer within 7 days.

## Surface and protections

| Component | Protection |
|---|---|
| `POST /ask` | CORS per origin, the widget's public key, rate limiting and admission control (503) |
| Widget | Shadow DOM; every text from the API is inserted with `textContent`, never `innerHTML` |
| `/admin` and `/admin/panel` | Only with `IPSIS_ADMIN_TOKEN` (≥ 32 characters), constant-time comparison, HTTPS in production, lockout after 5 failed attempts, no CORS, strict CSP and an audit trail in `.ipsis/logs/admin.jsonl` |
| Proxy | `X-Forwarded-*` is only accepted from `IPSIS_TRUSTED_PROXY` |
| Docker image | Non-root user, no network at run time (`HF_HUB_OFFLINE=1`) |
| Data | Documents and questions never leave the server; the query log is off by default |

The widget's public key identifies an integration, but it is not a secret:
the service's protection is completed at the proxy. Details in the
[deployment guide](docs/guide/deployment.md).
