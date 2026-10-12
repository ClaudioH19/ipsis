# Web integration examples

The examples use the same Web Component and do not duplicate the interface.
Follow the complete integration guide in [English](../docs/guide/integrations.md)
or [Spanish](../docs/es/guia/integraciones.md) for assistant setup, CORS,
copyable components, SSR, routing and deployment.

- `html/`: a static page; change `API` in `config.js` and serve it over HTTP.
- `react/`: a Vite app with a React adapter that listens to the component's
  events.
- `astro/`: a static Astro page with a remote classic script.
- `svelte/`: a Svelte 5 / Vite app with a browser-only lifecycle adapter.
- `angular/`: an Angular 20 standalone app with a custom-element adapter.
- `python/`: a FastAPI page that embeds the widget from a separate ipsis service.
- `wordpress/`: an installable plugin that registers the `[ipsis]`
  shortcode.

Before opening them, start the service with `ipsis serve` and allow the
site's origin with `ipsis configure cors_origins=...`, then restart the service.
Keep ipsis running in a separate terminal. The widget's public key
identifies the integration, but it does not replace the protection of the
server or the proxy.

## HTML

Change `api` in [html/config.js](html/config.js), then from the repository root:

```bash
python -m http.server 8080 --bind 127.0.0.1 --directory examples/html
```

Open `http://127.0.0.1:8080` and allow that origin in ipsis. Do not open
the page as `file://`.

## React, Astro and Svelte

Use Node 22.12+ on the 22.x line. From `examples/react`, `examples/astro`
or `examples/svelte`:

1. Copy `.env.example` to `.env` and set the URL and the public key.
2. Run `npm install`.
3. Run `npm run dev`, or check the build with `npm run build`.

| Example | API variable | Optional key variable | Page / CORS origin |
|---|---|---|---|
| React | `VITE_IPSIS_API` | `VITE_IPSIS_WIDGET_KEY` | `http://127.0.0.1:5173` |
| Astro | `PUBLIC_IPSIS_API` | `PUBLIC_IPSIS_WIDGET_KEY` | `http://127.0.0.1:4321` |
| Svelte | `VITE_IPSIS_API` | `VITE_IPSIS_WIDGET_KEY` | `http://127.0.0.1:5174` |

The React and Svelte adapters turn `ipsis:answer` and `ipsis:error` into
callbacks. Keep the widget in a persistent root layout, outside route outlets.
Load the script once; its API URL and key stay fixed for the page's lifetime.
The Astro example uses full-page navigation, without `ClientRouter`.

## Angular

From `examples/angular`, set `IPSIS_API` and optionally `IPSIS_WIDGET_KEY`
in [src/config.ts](angular/src/config.ts). Run `npm install` and `npm run dev`.
Open `http://127.0.0.1:4200` and allow that origin in ipsis.
`npm run build` validates and compiles the app. The component declares
`CUSTOM_ELEMENTS_SCHEMA` and loads the script after rendering in the browser.

## Python / FastAPI

From `examples/python`:

```bash
uv run --no-project --with fastapi --with uvicorn uvicorn app:app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` and allow that origin in ipsis. Set `IPSIS_API`
and optionally `IPSIS_WIDGET_KEY` in the environment to override the defaults
(local port 8000, no key). The Python app serves HTML; ipsis still runs
separately. The same markup works in Flask and Django templates.

## WordPress

1. Copy this folder to `wp-content/plugins/ipsis-widget`.
2. Activate **ipsis Widget** in the plugins panel.
3. Insert the shortcode in a page:

```text
[ipsis api="https://ipsis.example" key="public-site" color="#7c3aed"]
```

Allow the WordPress origin in the service's `cors_origins`. The key is
visible in the HTML and is therefore a public identifier, not a secret.
