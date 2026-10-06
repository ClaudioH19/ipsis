# Contributing

Thanks for wanting to improve ipsis! This guide sums up how to work in the
repository. Before proposing a large change, open an issue to discuss it.
Issues and pull requests are welcome in English or Spanish.

## Non-negotiable principles

- **Nothing generative.** Every statement is a literal span of the
  document; the only additions are fixed, reviewed templates
  ([ADR 0001](docs/decisions/0001-non-generative-answers.md)).
- **No training.** No fine-tuning and no learned weights: calibration only
  chooses thresholds among observed values.
- **Abstaining beats being wrong.** A change that raises coverage at the
  cost of false `ok` answers is not accepted.
- **No language text in Python.** Words, patterns and messages go in the
  packs of `ipsis/recursos/idiomas/` and `ipsis/recursos/tonos/`, and the
  CLI messages in the catalog `ipsis/recursos/mensajes/{en,es}.yaml`.
- **Layers in one direction only.** `tests/test_arquitectura.py` checks it
  (see the [architecture](docs/architecture.md)).

## Set up the environment

```bash
git clone https://github.com/ClaudioH19/ipsis.git
cd ipsis
python -m venv .venv
.venv/bin/python -m pip install -e ".[test,browser]"     # .venv\Scripts\python.exe on Windows
.venv/bin/python -m playwright install chromium
```

## Tests

```bash
python -m pytest -m "not slow and not browser"   # fast (seconds)
python -m pytest -m browser                      # widget and panel in Chromium
python -m pytest                                 # everything; the slow ones download or use real models
```

- A test lives in the folder of the module it tests (`tests/<layer>/`).
- The engine stages are tested with in-memory doubles, without models.
- If a change alters answers on purpose, regenerate the characterization
  and explain why in the commit.
- Run the tests on Python 3.11 or 3.12 before opening the pull request: the
  repository has no continuous integration.

## The avatar engine

`ipsis/servicio/estaticos/avatar.js` is generated; it is not edited by hand:

```bash
cd herramientas/avatar
npm ci && npm run construir    # or npm run verificar to check the sha256
```

See [herramientas/avatar/LEEME.md](herramientas/avatar/LEEME.md).

## Style

- Internal identifiers and code comments are in Spanish; comments explain
  the why. Everything user-facing (commands, files, keys, API, messages) is
  in English, with a Spanish translation in the message catalog.
- A new CLI message needs its key in both `en.yaml` and `es.yaml`;
  `tests/cli/test_mensajes.py` checks they stay in sync.
- Actionable error messages: they say which command to run.
- A new technique needs its [methodology note](docs/methodology/README.md),
  and an architecture decision its ADR in `docs/decisions/`.
- Update the matching guide in `docs/guide/` (and its Spanish version in
  `docs/es/guia/`) and the `CHANGELOG.md`. `tests/test_documentacion.py`
  fails if a command is missing from `docs/guide/usage.md` or
  `docs/es/guia/uso.md`, or if a link breaks.

## Pull requests

1. One branch per change, with small commits and descriptive messages.
2. The fast and browser tests green.
3. Fill in the PR template: what changes, how it was tested and whether it
   affects answers, indexes or the configuration (`config_version`).

By contributing you agree to publish your contribution under the
[AGPL-3.0](LICENSE) license and the [code of conduct](CODE_OF_CONDUCT.md).
