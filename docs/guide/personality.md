# Personality: answer tone and avatar

The **tone** decides how the assistant sounds around the text of your
documents. It never decides what it answers. The document text goes
literally and the citations go underneath, to check it. Changing the tone
does not change the status of any answer, and needs no reindexing or
recalibrating.

## Configuration: `config/personality.yaml`

`ipsis init` creates it with comments. Edit it by hand or with
`ipsis personality …` (reference in [usage.md](usage.md)). Every change
from the terminal is fully validated before it is written; if it does not
pass, the file stays the same.

```bash
ipsis personality tone list                     # the 7 tones, with an example
ipsis personality tone apply formal
ipsis personality tone try --situation no_answer
ipsis personality validate                      # exits with 1 if something prevents the engine from starting
```

`tone.variety: fixed` always uses the first variant of each situation
(`rotating` is the default).

```yaml
config_version: 1
tone:
  active: cordial          # cordial | formal | serious | upbeat | friendly | empathetic | direct
  variety: rotating        # rotating | fixed
  templates: {}            # your own texts per situation
avatar:
  enabled: true
  definition: folio
  placement: header        # header | top-corner | bottom-corner
  size: 56
  in_launcher: true
  gaze: {enabled: true, eye_range: 6, head_range: 8, dead_zone: 24}
  idle_minutes: 2
  colors: {}               # {body: "#rrggbb", eyes: "#rrggbb"}
  events: {}               # event → animation or expression
```

## Avatar

The widget shows an avatar made with
[@bible-strong/avatar-web](https://github.com/smontlouis/bible-strong-avatar-lab).
It is designed in the Studio ([avatars.bible-strong.app](https://avatars.bible-strong.app))
and exported as `.avatar.json`.

```bash
ipsis personality avatar import ./my-avatar.avatar.json --name my-avatar
ipsis personality avatar apply my-avatar
ipsis personality avatar events                  # event → animation (and fallbacks)
ipsis personality avatar assign thinking looking-up
ipsis personality avatar colors --body "#f5f1e8" --eyes "#1e293b"
```

- **On import** it checks: up to 256 KiB, JSON without duplicate keys,
  required fields, the `neutral` expression, keys in `lowercase-and-hyphens`
  format and `#rrggbb` colors. The library validates the rest when the
  avatar loads in the browser.
- **Every event** of the widget has a suggested key and a fallback. When
  the avatar lacks the key, the fallback chain is used, down to `neutral`.
  So any avatar works, even if it does not define every animation.
- **If the avatar is missing or invalid,** the widget shows the icon and
  `ipsis doctor` flags a warning: it never blocks the service.

### Folio, the default avatar

A living sheet of paper: tilted, with a lifting corner and two ink eyes. It
has no mouth: it expresses itself with its eyes and the turn of its head.
It does what the project does: it reads, looks at the citation before
asserting and never exaggerates.

- `happy` is sober: it first looks at the citations and only then lights up.
- `unsure` and `sorry` never show a gesture of success.
- Colors: paper `#f5f1e8` and ink `#1e293b`; change them with
  `ipsis personality avatar colors`.

To review all its animations, from the repository root:
`python -m http.server 8765` and open
`http://127.0.0.1:8765/herramientas/avatar/muestra.html`.

### How the avatar reacts

| Event | When | Kind |
|---|---|---|
| `idle` | panel closed | persistent |
| `attentive` | panel open, not typing | persistent |
| `typing` | while typing; back to `attentive` 1.2 s later | persistent |
| `thinking` · `thinking_long` | waiting for the answer; "long" after 3 s | persistent |
| `sleepy` | no activity for `avatar.idle_minutes` minutes | persistent |
| `greeting` · `farewell` | first opening · on closing | transient |
| `sent` | when the question is sent | transient |
| `answer_ok` · `answer_related` · `no_answer` · `conversational` | depending on the answer status | transient |
| `error` | network or service failure | transient |
| `wake_up` | first activity after `sleepy` | transient |

- A transient event plays once and returns to the current persistent one. A
  higher-priority one interrupts another: errors win over everything, and
  answers win over `sent`.
- **Gaze:** with `avatar.gaze.enabled`, the eyes and head follow the pointer
  at rest (`idle` or `attentive`). There is a dead zone in the center
  (`dead_zone`, in px) and it returns to the center after 1.5 s without
  movement. With the system's "reduce motion" it does not follow the
  pointer.
- A hidden tab pauses the animation.
- On a phone the avatar is 40 px and hides while the keyboard is open.

## Included tones

In English, Spanish and Portuguese:

| Tone | Character | Example for `no_answer` (en) |
|---|---|---|
| `cordial` (default) | kind and clear | "I couldn't find that information in the available documents." |
| `formal` | polite, careful, no exclamations | "Unfortunately, that information is not included in the available documents." |
| `serious` | sober, short sentences | "That information is not in the documents." |
| `upbeat` | enthusiastic, without exaggerating facts | "I searched thoroughly, but that is not in the documents! Try another question." |
| `friendly` | casual and close, still respectful | "Hmm, I can't find that in your documents." |
| `empathetic` | acknowledges what the person needs | "I'm sorry, that information is not in the available documents." |
| `direct` | blunt and imperative, never aggressive | "Not in the documents. Ask something else." |

Each tone brings 18 situations with 5 variants each: 90 per tone and
language, 1,890 in total.

## Situations

| Situation | When it is used | Variables |
|---|---|---|
| `greeting`, `thanks`, `farewell`, `capability` | conversational answers | `{assistant_name}`, `{domain_description}` (thanks: only the second; farewell: none) |
| `opening` | before the document text | — |
| `addition`, `condition`, `exception` | between document fragments | — |
| `related_intro` | a related, not direct, answer | — |
| `missing_focus` | related, the main term is missing | `{term}` (required) |
| `no_answer` | it is not in the documents | — |
| `premise_not_found` | the question asked about something that does not exist | `{entity}` (required) |
| `welcome`, `waiting`, `citations_hint`, `network_error`, `rate_limit_error`, `service_error` | widget texts | `welcome`: `{assistant_name}` |

## Variety and traceability

- Within a conversation, the variant is chosen by session, turn and
  situation, and it does not repeat in consecutive turns.
- The same session and turn always give the same text.
- Every variant used is recorded as a template id (for example
  `formal.opening.3`) in `ipsis ask --diagnostics` and in the query log.
  `ipsis audit` counts queries per tone.

## Your project's own texts

In `config/personality.yaml` you can replace any situations you like:

```yaml
tone:
  templates:
    no_answer:
    - That is not in the team handbook.
    - The handbook does not cover that question.
```

## Rules for every template

A linter checks them; the same rules apply to your overrides:

- Shape:
  - one line, up to 200 characters;
  - if it opens «¡» or «¿», it closes them.
- Forbidden content:
  - digits, because they would assert a fact that does not come from the
    document;
  - URLs, HTML, Markdown and emojis;
  - whole words in capitals.
- Variables: only those of its situation, without formatting.
- Connectors: those that introduce document text end with ":".
- Variety: the 5 variants are different, and none repeats in another
  situation of the same tone.
- None of the language's forbidden expressions
  (`ipsis/recursos/tonos/<language>/_reglas.yaml`): insults, blaming the
  user, condescension.

## Configure over HTTP (`/admin`)

With `IPSIS_ADMIN_TOKEN` set, the service exposes an API to change the
personality and the widget without a terminal (see modes and security in
[deployment.md](deployment.md)). Every call carries
`Authorization: Bearer <token>`. Bodies use the same names as the YAML
files.

| Method and path | What it does |
|---|---|
| `GET /admin/personality` | Configuration, tones (with an example), situations, events, avatars and avatar status |
| `PUT /admin/personality` | A partial change, e.g. `{"tone": {"active": "formal"}}`. Fully validated; on failure it answers 422 with the `errors` and writes nothing |
| `POST /admin/personality/preview` | `{"tone": "formal", "situation": "no_answer"}` → the variants with the project variables |
| `GET /admin/avatars` · `POST /admin/avatars` | Lists, or imports `{"name": "my-avatar", "definition": {…}}` |
| `GET /admin/styles` · `PUT /admin/styles` | Widget theme and placement (`styles.yaml`), with the same validation as the terminal |
| `GET /admin/styles/flat` · `POST /admin/styles/set` | Every `section.key` value, or `{"assignments": ["colors.accent=#0ea5e9"]}` |
| `GET /admin/styles/presets` · `POST /admin/styles/preset` | Lists the visual presets, or applies one: `{"name": "editorial"}` (`classic`, `minimal`, `editorial`, `contrast`) |

Changes, over HTTP or from the terminal, show without restarting:

- the service checks the date of `personality.yaml`, `language.yaml` and
  `assistant.yaml` on every query, and the engine takes the new templates;
- `/config` gives the widget the current microcopy and avatar.

## Admin panel (`/admin/panel`)

![Avatar tab of the panel: Folio, colors, events and preview](../assets/panel-avatar.png)

It is the same API, with forms. Open `https://your-domain/admin/panel` (or
`http://127.0.0.1:8000/admin/panel` on your machine) and paste the token.
The panel speaks English by default and Spanish with `IPSIS_LANG=es` on the
service.

| Tab | What it does |
|---|---|
| **Tone** | Chooses the tone and the variety. Per situation, it shows the 5 variants with the project variables and lets you write your own texts. If a text fails the linter, it shows the errors and saves nothing |
| **Avatar** | Imports an `.avatar.json` (validated before saving), chooses the avatar, its colors, placement and size, and assigns each event to an animation. The ▶ button triggers the event in the preview |
| **Widget** | Applies a preset and changes the accent color, position, size, launcher and how citations show. "Full style" edits every value of `styles.yaml`: light and dark colors, typography, shapes, shadows and animations |

- **Preview:** the real widget, served by your service. It reloads by
  itself after each saved change.
- **Token:** stored only in the browser tab (`sessionStorage`). It is
  cleared when the tab closes or with "Sign out".
- **Security:**
  - the panel loads nothing from other domains;
  - its content policy (CSP) forbids inline scripts;
  - it follows the same transport rules as the API: in production, HTTPS
    except from the machine itself;
  - without `IPSIS_ADMIN_TOKEN`, the panel does not exist (404).
- Its files carry no data: everything it shows arrives through the API with
  the token.

## Neutrality of the included tones

The tones shipped in the package are neutral:

- **No regionalisms:** nothing like "no worries", «pega», «chao», «e aí».
- **No gendered forms for the person:** «Te doy la bienvenida» instead of
  «Bienvenido»; nothing like «o senhor».
- **No greetings that depend on the time of day:** nothing like "Good
  morning".
- **In Portuguese,** forms valid in both Brazil and Portugal: nouns instead
  of gerunds («Busca em andamento»).

Each language's list is in `_reglas.yaml` (`regionalisms`) and a test
enforces it.

Your own texts (`tone.templates`) are checked against the same list, but as
a **warning**, not an error: they are saved anyway, because a local site may
want to speak like its audience. The warning shows in
`ipsis personality validate`, in `ipsis doctor` and in the panel's Tone tab.
If the project language has no pack of its own (for example `fr`), it is not
checked.

## Human review of a new tone

The linter does not judge meaning. Before publishing a tone, a person
checks:

1. **Recognizable tone:** the 90 variants sound like the same character.
2. **Honesty:** `related_intro` and `missing_focus` say it is not a direct
   answer; `no_answer` and `premise_not_found` never suggest the
   information exists elsewhere.
3. **No content:** no template reads as something the document says.
4. **The connector fits:** `opening`, `addition`, `condition` and
   `exception` read well followed by a citation that starts with a capital
   letter.
5. **Natural in the language:** no calques or confusing regionalisms.
6. **`direct` without aggression:** blunt, never hurtful.
