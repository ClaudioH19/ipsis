# The widget on your website

The integration has two parts:

- the **service**, running on your server (see [deployment.md](deployment.md));
- the **widget**, a single dependency-free `widget.js` file the service
  publishes at `/widget.js`.

For a complete setup with HTML, Astro, Svelte, React, Angular or Python,
see [framework integrations](integrations.md): runnable examples, CORS,
configuration and how to keep the widget mounted when navigating.

![V2 widget with numbered sources and literal context](../assets/widget-sources-en.png)

## Try the widget and configure the project

From a project folder, run `ipsis serve`. It opens `/widget/demo.html` using
the project's existing theme and enables `/admin/panel`; the test page links
to the panel and `/` redirects to the test page. Paste the admin token printed
in the terminal to enter the panel. An existing `IPSIS_ADMIN_TOKEN` is reused;
otherwise a temporary token is created for this run, without being saved.
Production mode is preserved, including HTTPS for remote admin access.

Use `ipsis serve --no-open` to keep the browser closed. `--no-demo` disables
the test page and suppresses opening; `--no-admin` disables the panel even if
a token is configured. The API and widget assets remain available. Run
`ipsis help serve` to see all options.

## Guidance separate from search results

With engine v2, a guidance section sits above the ranked sources. It uses a
fixed catalog of 118 messages for each of Spanish, English and Portuguese,
selected using the project's document language. Other languages use English
guidance as a fallback. The thirteen categories are `welcome`, `greeting`, `thanks`,
`farewell`, `capability`, `tips`, `searching`, `results`, `continuation` and
`no_results`, `about`, `limits` and `examples`. The YAML catalogs live in `ipsis/recursos/voz/`, independently
of the existing tones and source templates. This is interface text, never
documentary evidence or generated answers.

The `results` and `continuation` templates can use `{count}` (the number with its noun, already singular or plural in the
language: "3 resultados", "1 result"), `{n}` (the bare number) and `{query}` (what was searched). A template that uses none
of them gets the count prepended ("3 resultados. …"), so the count always reaches the reader without taking a line of its own
(the "N results for …" heading is kept only for screen readers). The help menu is a "?" icon in the assistant's header. While
the assistant is not speaking, or has not started yet, a dot fades in and out after its message to show it is waiting.

**Search tips**, **What I can do**, **About the assistant**, **Scope** and
**Examples** rotate through their messages locally,
without sending a search request. Typed greetings, thanks and farewells go to
this section too, preserving expanded sources and the continuation button.
Only complete courtesy expressions bypass document retrieval; a mixed query
such as “hello, what is the stock of product A?” still searches the corpus.

Guidance is revealed character by character, without delaying network requests
or displaying sources character by character. **Show full message** finishes
the animation immediately. A newer message cancels the previous animation.
Reduced motion preferences, including changes while typing, reveal the complete
text; `ipsis widget style set animations.enabled=false` also disables typing.
Screen readers receive the complete message once instead of character updates.
Search errors appear in guidance and leave existing results available.

`GET /config` adds `assistant_messages` (category → list of fixed strings),
`suggested_questions`, `animations_enabled`, and localized guidance labels in
`interface`. Engine v1 retains its existing chat flow.

## Add it

The simplest way: ask for the ready-made code and paste it before `</body>`.

```bash
ipsis widget snippet --api https://assistant.your-domain.com
ipsis widget snippet --api https://assistant.your-domain.com --component   # as a Web Component
```

With the `<script>` tag:

```html
<script src="https://assistant.your-domain.com/widget.js"
        data-api="https://assistant.your-domain.com"
        data-position="bottom-right" data-size="normal" data-launcher="bubble"
        defer></script>
```

Or as a Web Component:

```html
<ipsis-chat api="https://assistant.your-domain.com" position="bottom-left"></ipsis-chat>
<script src="https://assistant.your-domain.com/widget.js" defer></script>
```

Add the exact origin of your site to CORS
(`ipsis configure cors_origins=https://www.your-site.com`). If you use widget
keys (`data-widget-key`), remember they are public: they identify and limit
traffic, they are not a secret.

## Placement, size and launcher

They are set in `config/styles.yaml` (the `placement` section) or with
attributes on the tag. **When the site declares an attribute, it wins.**

| Option | Attribute (`data-` on the `<script>`) | Values |
|---|---|---|
| Position | `position` | `bottom-right` (default), `bottom-left`, `top-right`, `top-left`, `embedded` |
| Distance from the edge | `offset-x`, `offset-y` | pixels (24 by default) |
| Layer | `z-index` | integer (2147483000 by default) |
| Panel size | `size` | `compact` (340×520), `normal` (390×600), `wide` (440×680) |
| Launcher | `launcher` | `bubble` (round button), `tab` (button with the name), `hidden` |

Other attributes: `title` and `greeting` (used only if `/config` does not
answer), `color` (accent) and `widget-key`.

**Embedded.** The chat lives inside a container of your page, always open,
with no button or floating window. The container decides the height:

```html
<div style="height:560px">
  <ipsis-chat api="https://assistant.your-domain.com" mode="embedded"></ipsis-chat>
</div>
<script src="https://assistant.your-domain.com/widget.js" defer></script>
```

**Hidden launcher.** Your site opens the chat with its own button:

```html
<button onclick="window.Ipsis.open()">Questions? Ask the manual</button>
```

## JavaScript API for the site

One widget per page is assumed.

| Call | What it does |
|---|---|
| `window.Ipsis.open()` | Opens the panel |
| `window.Ipsis.close()` | Closes it |
| `window.Ipsis.state()` | `{open, position, size, launcher, session}` |
| `window.Ipsis.avatar.trigger(event)` | Makes the avatar react to an event from the table in [personality.md](personality.md#how-the-avatar-reacts). Returns `false` when there is no avatar yet |
| `window.Ipsis.avatar.state()` | `{ready, persistent, transient, gaze}` |

Events emitted by the element: `ipsis:open`, `ipsis:close`,
`ipsis:question` (`{question}`), `ipsis:answer` (`{status, answer}`, where
`answer` is the full `POST /ask` response), `ipsis:error` (`{message}`) and
`ipsis:avatar`. The last one carries `{state: "ready", name}` when the avatar
is mounted, `{state: "error", message}` when it could not be and the icon
stayed, and `{state: "event", event, key}` on each reaction.

## HTTP API

The `session_id` is created on each page load, without `localStorage`.
Reloading or navigating starts a new conversation; closing and reopening
the panel preserves it. The server forgets conversations after the configured
inactivity period (30 minutes by default). Memory is local to each worker.

The widget uses three public endpoints; you can call them too:

| Endpoint | What it returns |
|---|---|
| `POST /ask` with `{"question": "...", "session_id": "..."}` | `status` (`ok`, `related`, `no_answer`, `conversational`, `degraded`, `saturated`), `answer`, `answer_blocks` (`answer` by paragraph: `type` is `lead`, `passage` or `message`, with `text`, `connector`, `citation` and `chunk_id`; `passage` text is literal from the document), `fragments` (`doc_title`, `section`, `offset_start`, `offset_end`, `text`, `score`…), `plan` (`clarification` when the question has no topic: the assistant asks for it), `confidence_level` (`high`: direct answer read by the QA reader, 96.6 % correct on the measured banks; `medium`: direct answer without a reader, 85 %; `low`: related passage; absent when there is no answer), `confidence`, `latency_ms`, `exact_answer` when the reader marked a span, `alternatives` (only in `no_answer` with the proactive posture: similar literal passages, same fields as `fragments`; they do not answer the question) and `conversational_category` With engine v2 and `v2.presentation.enabled` the first page also carries `result_shape`: `variants` (the first two sources are variants of the same thing), `documents` (they come from different documents) or `neutral`. It describes the page, not whether the first source answers; `clear` only appears with an explicit `clear_margin`, which is not recommended. Further pages (`continuation`) never carry it. |
| `GET /config` | What the widget needs: `assistant_name`, `greeting`, `response_mode`, `preset`, `density`, `citations`, `interface` texts, `microcopy` of the tone, `assistant_messages`, `animations_enabled`, `placement` and `avatar` |
| `GET /health`, `GET /ready` | Liveness and readiness (with the same diagnosis as `ipsis doctor` under `project`) |

With widget keys configured, `POST /ask` needs the `X-Ipsis-Widget-Key`
header.

## Avatar

When `personality.yaml` has an active and valid avatar, the widget shows it
instead of the icon:

- **Loaded on demand:** the engine (`/avatar.js`, 52 KB compressed) is
  requested the first time the panel opens. With `avatar.in_launcher: true`
  it is requested earlier, when the browser is idle, to show it on the
  button.
- **It never breaks the chat:** if the network, the definition or the CSP
  fails, the icon stays and `ipsis:avatar` is emitted with the error.
- **Decorative:** it carries `aria-hidden`; the states already have text.

## Screens

- **Phone** (≤ 480 px wide, or low landscape): a full-screen sheet.
  - It respects the safe areas (`safe-area-inset`, with
    `viewport-fit=cover` on your page).
  - It follows the visible height, so the virtual keyboard never hides the
    text field.
- **Tablet** (481–1024 px): a panel fitted to the available space.
- **Desktop:** a floating panel in the chosen corner.
- **System preferences:** dark mode, `prefers-reduced-motion` (no
  animations) and high contrast (`forced-colors`).

## Search layout

With engine v2 (`response_mode: ranked_sources` in `GET /config`) the widget uses a search layout:

- **Search box at the bottom**, like a chat: the results scroll above it, on desktop and on phones. The
  box has a clear button.
- **Assistant message above the box**, where attention is: it says how many results there are (see the
  `{count}` templates above). With `avatar.placement: message` (the default for new projects) the avatar
  sits to its right; `header`, `top-corner` and `bottom-corner` still work
  ([personality.md](personality.md)). While the phone keyboard is open the avatar is hidden to save space.
- **Loading:** while a search runs, grey skeleton cards fall into place one after another, with a status
  line that moves through "Reading the documents…", "Comparing sources…" and "Sorting by relevance…"; the
  results then enter one at a time. "Show more results" adds a single skeleton card below the list. It
  respects `prefers-reduced-motion` and `animations.enabled: false`.
- **Scope label:** each result shows, next to its document title, a small label with what tells it apart
  from its sibling units (for example "Práctica Profesional II"). The API returns it as `scope`, and the
  terms that tell similar units apart as `distinctive_terms`.
- **Test page:** `/widget/demo.html` takes the whole screen on phones (no page header; the access-key
  form is at `#clave-acceso`) and fits the window on desktop.

## Citations

Every answer with evidence shows, **underneath**, a block of citations to
check it:

- an invitation to check the source (from the active tone);
- for each citation: document, section and character position, with the
  literal text;
- the exact span that answered, highlighted.

`styles.yaml::presentation.citations` chooses how they look, never whether
they show:

- `accordion`: collapsible; the one with the exact span comes open;
- `list`: all of them visible.

## Texts

- **From the active tone** (see [personality.md](personality.md)): the
  v1 welcome, "searching…", the invitation to the citations and the error
  messages come from `/config` in 7 variants, and the widget rotates them.
- **v2 guidance:** its separate fixed catalog has 118 messages per supported
  language, with examples and information about the assistant and its scope.
- **Interface texts** (button labels, placeholder…) come from the language
  pack of the project.
- **Accessibility:** "searching…" and the errors are announced to screen
  readers with an `aria-live` region.
- **Security:** no text from the API is inserted as HTML; everything uses
  `textContent`.

## Style

Results use cards (`cards`), dividers (`lines`) or an editorial margin
(`editorial`). The `classic`, `minimal`, `editorial`, `contrast`, `search`,
`search_compact`, `ocean`, `forest` and `midnight` presets combine these layouts
with distinct palettes and typography.

Headings have their own color, font, size and weight. Section colors, result
backgrounds and dividers can be adjusted independently of button colors:

```bash
ipsis widget theme apply forest
ipsis widget style set presentation.result_layout=cards colors.heading="#14532d" typography.heading_family="Georgia, serif" typography.heading_size=20px
ipsis widget style set shape.result_radius=12px shape.result_gap=18px
ipsis widget style set content.title="Help center" content.welcome_title="What would you like to review?"
ipsis widget theme preview --output preview.html
```

| `styles.yaml` key | Effect |
|---|---|
| `colors.heading`, `colors.section` | Heading and section colors |
| `colors.result_surface`, `colors.result_border` | Result backgrounds and dividers |
| `typography.heading_family`, `heading_size`, `heading_weight`, `section_size` | Heading and section typography |
| `shape.result_radius`, `result_gap`, `result_padding` | Corners, spacing and padding |
| `presentation.show_result_numbers`, `show_section_path` | Numbering and section paths |
| `presentation.expand_context` | Opens full contexts by default |
| `presentation.show_suggestions` | Displays example questions |
| `content.title`, `subtitle`, `welcome_title`, `welcome_text` | Header and welcome text; empty uses the project language |

These settings are also available in **Widget → Full style** in
`/admin/panel`. Changing presets preserves `content` text and custom CSS.
The standalone preview uses the real widget with sample sources and works
without a service or index.

In Spanish, English and Portuguese, six example questions fill the input
without submitting it. **About the assistant**, **Scope** and **Examples**
offer additional fixed messages. These interface messages are separate from
document sources and do not execute searches.

**Frequently asked questions** exposes at least 100 complete questions per
language across ten topics. `/config::default_questions` publishes questions
and topics; the service resolves each fixed answer. Queries with added document
information still search the index. The 118 message variants form a separate
catalog from the recognized questions.

Guidance occupies two lines by default. **Show full message** expands a
scrollable area; **Show less** returns that space to the sources. The **Help**
menu overlays its actions without changing the results area's height. Loading
progress and source-card transitions make new queries visible; they respect
`animations.enabled` and reduced motion preferences.

The whole look lives in `config/styles.yaml` and applies without restarting
the service:

- **Presets:** `ipsis widget theme list` and `ipsis widget theme apply editorial`
  (`classic`, `minimal`, `editorial`, `contrast`).
- **Each value:** `ipsis widget style show` and, for example,
  `ipsis widget style set colors.accent=#0ea5e9 shape.panel_radius=10px
  typography.family="Inter, sans-serif"`. Sections: `colors`,
  `dark_colors`, `typography`, `shape`, `shadows`, `animations`,
  `placement` and `presentation`.
- **No terminal needed:** the `/admin/panel`, Widget tab, "Full style" (see
  [personality.md](personality.md#admin-panel-adminpanel)).
- **Preview without the service:** `ipsis widget theme preview`.

## Your site's CSP

If your site uses a Content Security Policy, allow the assistant's domain:

```text
script-src  'self' https://assistant.your-domain.com;
connect-src 'self' https://assistant.your-domain.com;
style-src   'self' https://assistant.your-domain.com 'unsafe-inline';
```

- `style-src` allows the `/styles.css` sheet and the widget's own style,
  which lives isolated in its Shadow DOM.
- The animated avatar also needs `'unsafe-eval'` in `script-src`, because
  its library validates the definition with ajv, which compiles the schema
  in the browser. Without it, the widget shows the icon and the chat works
  anyway.
- If the widget is served from another domain, the service must allow your
  site in `cors_origins`: the avatar engine is an ES module and the browser
  requests it with CORS.

## Export static files

```bash
ipsis widget export ./public/ipsis --api https://assistant.your-domain.com --position bottom-left
```

It generates, to serve them from another server:

- `widget.js` and `snippet.html`;
- `avatar.js` and `avatar.js.LICENSE.txt` (the engine and its licenses);
- `avatars/<name>.avatar.json`: the active avatar, with the project's
  colors. When there is an avatar, the snippet carries `avatar-base="."`:
  the widget loads the engine and the definition from that folder, not from
  the service.

## Runnable examples

- `examples/html`: a static page configurable from `config.js`;
- `examples/react`: a Vite project and an event adapter for React;
- `examples/astro`, `examples/svelte`, `examples/angular`: framework adapters;
- `examples/python`: a FastAPI page embedding the widget;
- `examples/wordpress`: an installable plugin with the `[ipsis]` shortcode.

Commands and local URLs are in [examples/README.md](../../examples/README.md).

The browser tests (`pytest -m browser`) use a real Chromium and check:

- keyboard, focus and dialog;
- every position on phone, tablet and desktop, with no overflow and the
  field visible with the keyboard open;
- the citations with the exact span marked;
- the `window.Ipsis` API.
