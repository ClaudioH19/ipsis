# Embed ipsis in HTML and web frameworks

Your website serves the page; `ipsis serve` serves the assistant, its index
and `/widget.js`. The browser loads that script and calls `/config` and
`/ask` on the assistant's URL. There is no ipsis npm package to install or
JavaScript module to import. Use a **classic script**, not `type="module"`.

## 1. Prepare the assistant

In an assistant project, with ipsis already [installed](installation.md):

```bash
ipsis init --profile light --language en
ipsis models download
ipsis load ./documents
ipsis index
ipsis widget theme apply search
ipsis configure cors_origins=http://127.0.0.1:8080
ipsis serve --no-open
```

Skip `init` if the project already exists. Use the origin of **your page**
for `cors_origins`, including the scheme and port; it is not the assistant's
URL. For React use `http://127.0.0.1:5173`, Svelte `:5174`, Astro `:4321`,
Angular `:4200`, or the Python example `:8080`. `localhost` and `127.0.0.1`
are different origins. Restart the service after changing CORS. If you allow
multiple sites, list their origins in `config/assistant.yaml`:

```yaml
cors_origins:
  - http://127.0.0.1:8080
  - http://127.0.0.1:5173
```

Open `http://127.0.0.1:8000/ready` to check that the assistant is ready.
The example site runs in a **second terminal**, while ipsis keeps running.

## 2. HTML: paste the script

Save this as `index.html` in your site's folder:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>My website</title>
  </head>
  <body>
    <h1>Knowledge base</h1>
    <script src="http://127.0.0.1:8000/widget.js"
            data-api="http://127.0.0.1:8000"
            data-position="bottom-right" defer></script>
  </body>
</html>
```

Serve that folder with `python -m http.server 8080 --bind 127.0.0.1` and
open `http://127.0.0.1:8080`. Use HTTP rather than opening a `file://` URL.
The script creates the floating widget. To generate the snippet yourself:

```bash
ipsis widget snippet --api https://assistant.your-domain.com
```

For a chat **inside the page**, replace the script above with:

```html
<div style="height:560px">
  <ipsis-chat api="http://127.0.0.1:8000" mode="embedded"></ipsis-chat>
</div>
<script src="http://127.0.0.1:8000/widget.js" defer></script>
```

The host element must exist before the script executes. Choose the automatic
script or the explicit element; loading both snippets creates duplicate widgets.
Only one widget per browser document is supported. Page CSS stays outside
its Shadow DOM; configure the widget with `ipsis widget style` or `/admin/panel`.

## 3. Choose your framework

The repository contains standalone examples. Clone the repository to get
them, or copy the linked component into an existing app. The JavaScript
examples use Node **22.12+** on the 22.x line. Dependencies are pinned in
each `package.json`; run the commands from the selected example's folder.

| Site | Example folder | Integration file | Local page |
|---|---|---|---|
| HTML | [examples/html](../../examples/html) | [index.html](../../examples/html/index.html), [config.js](../../examples/html/config.js) | `http://127.0.0.1:8080` |
| Astro | [examples/astro](../../examples/astro) | [IpsisChat.astro](../../examples/astro/src/components/IpsisChat.astro) | `http://127.0.0.1:4321` |
| Svelte 5 | [examples/svelte](../../examples/svelte) | [IpsisChat.svelte](../../examples/svelte/src/IpsisChat.svelte) | `http://127.0.0.1:5174` |
| React 19 | [examples/react](../../examples/react) | [IpsisChat.jsx](../../examples/react/src/IpsisChat.jsx) | `http://127.0.0.1:5173` |
| Angular 20 | [examples/angular](../../examples/angular) | [ipsis-chat.component.ts](../../examples/angular/src/ipsis-chat.component.ts) | `http://127.0.0.1:4200` |
| Python / FastAPI | [examples/python](../../examples/python) | [app.py](../../examples/python/app.py) | `http://127.0.0.1:8080` |

### Astro

From `examples/astro`, copy `.env.example` to `.env`, then run `npm install`
and `npm run dev`. `npm run build` produces the static site in `dist/`.
Set `PUBLIC_IPSIS_API` to the assistant's URL and `PUBLIC_IPSIS_WIDGET_KEY`
only if widget keys are configured.

In an existing Astro app, copy `IpsisChat.astro` and include it once near
the end of the shared layout's `<body>`:

```astro
---
import IpsisChat from '../components/IpsisChat.astro';
---
<IpsisChat />
```

The component uses `<script is:inline src={...} defer>` so Astro leaves the
remote classic script intact. It needs no `client:load` directive. This
example uses ordinary full-page navigation. If your site uses `ClientRouter`,
keep the host across transitions and handle script initialization explicitly;
the current widget does not automatically attach to replacement elements.
See [Astro's script documentation](https://docs.astro.build/en/guides/client-side-scripts/).

### Svelte

From `examples/svelte`, copy `.env.example` to `.env`, then run `npm install`
and `npm run dev`. Set `VITE_IPSIS_API` and optionally `VITE_IPSIS_WIDGET_KEY`.
Build with `npm run build`.

Copy `IpsisChat.svelte` into an existing Svelte app and render it once in
the root component:

```svelte
<script>
  import IpsisChat from './IpsisChat.svelte';
</script>
<IpsisChat api="https://assistant.your-domain.com"
           onAnswer={(detail) => console.info(detail.status)} />
```

It loads the script in `onMount`, after the host exists, and removes its
event listeners when destroyed. In SvelteKit place it in the persistent
root `+layout.svelte`; use `PUBLIC_IPSIS_API` from `$env/static/public`
instead of the Vite-only env variables. `onMount` does not execute during
SSR. See [Svelte's lifecycle documentation](https://svelte.dev/docs/svelte/lifecycle-hooks).

### React

From `examples/react`, copy `.env.example` to `.env`, then run `npm install`
and `npm run dev`. Set `VITE_IPSIS_API` and optionally `VITE_IPSIS_WIDGET_KEY`.
Build with `npm run build`.

Copy `IpsisChat.jsx` into an existing React app:

```jsx
import { IpsisChat } from './IpsisChat.jsx';

export default function App() {
  return <IpsisChat api="https://assistant.your-domain.com"
    onAnswer={(detail) => console.info(detail.status)}
    onError={(detail) => console.error(detail.message)} />;
}
```

The adapter loads the script once and registers native DOM events. Updating
callbacks and React Strict Mode do not load it again. Keep it outside your
route outlet in the persistent app layout. For an SSR framework, mark the
adapter as a client component where required (for example `'use client'` in
Next.js). See [React's effect documentation](https://react.dev/reference/react/useEffect).

### Angular

From `examples/angular`, edit `src/config.ts` with the assistant URL and
optional widget key, then run `npm install` and `npm run dev`.
Build with `npm run build`.

For an existing Angular app, copy `config.ts` and `ipsis-chat.component.ts`,
add `IpsisChatComponent` to the root component's `imports`, and render
`<app-ipsis-chat />` outside the router outlet. The standalone adapter uses
`CUSTOM_ELEMENTS_SCHEMA` to accept `<ipsis-chat>`, `[attr.api]` to set its
HTML attribute, and `afterNextRender` to load the script in the browser
after rendering. See Angular's [custom element schema](https://angular.dev/api/core/CUSTOM_ELEMENTS_SCHEMA)
and [render hook](https://angular.dev/api/core/afterNextRender).

### Python: serve the HTML with FastAPI

From `examples/python`:

```bash
uv run --no-project --with fastapi --with uvicorn uvicorn app:app --host 127.0.0.1 --port 8080
```

The page reads `IPSIS_API` and `IPSIS_WIDGET_KEY` from the environment;
defaults are the local assistant and no key. The example escapes these
values in HTML attributes. FastAPI serves the HTML at `/`; the browser
loads the widget from ipsis on port 8000. Keep `ipsis serve` running in
its own project. This does not start a second ipsis engine or use an
internal Python API. The same HTML tags work in Flask or Django templates.
See [FastAPI's HTML responses](https://fastapi.tiangolo.com/advanced/custom-response/#html-response).

## Events, routing and configuration

Listen on the `<ipsis-chat>` element with
`element.addEventListener('ipsis:answer', handler)`. `event.detail.status`
contains the status and `event.detail.answer` contains the full `/ask`
response, including `fragments`. There are also `ipsis:error`, `ipsis:open`,
`ipsis:close` and `ipsis:question` events. The framework adapters expose or
listen to these same events; they do not generate responses.

The current widget initializes on script execution, rather than a custom
element's reconnect lifecycle. Keep its element mounted, load `widget.js`
once per document and keep its API URL/key fixed during that document's
lifetime. Changing routes should not recreate it. For a different assistant,
reload the page. `window.Ipsis.open()` and `.close()` control the panel once
the script has loaded; there is no public `mount()` or `destroy()` API.

## Deploy and troubleshoot

Replace the local assistant URL with its HTTPS URL, allow your site's
production origin, rebuild the frontend when changing build-time env values,
and follow the [deployment guide](deployment.md). A browser's `127.0.0.1`
refers to the visitor's machine. A page served over HTTPS must also load the
assistant over HTTPS. Widget keys are public; the admin token stays on the server.

| Symptom | Check |
|---|---|
| No widget | `/widget.js` returns JavaScript; browser console has no script/CSP errors; the host exists before loading |
| CORS error | The page's exact origin is in `cors_origins`, then restart ipsis |
| 401/403 on `/ask` | Set `widget-key` on the element or `data-widget-key` on the script if the project requires it |
| 503 / not ready | Check `/ready`, run `ipsis doctor`, and load/index the documents |
| Duplicate widget | Include it once in the shared layout; do not also paste the automatic script snippet |

See the [widget guide](web.md) for placement, embedded sizing, themes, CSP,
avatar assets, static export and the complete JavaScript API. On Windows,
use `npm.cmd` if PowerShell blocks the `npm.ps1` launcher.
