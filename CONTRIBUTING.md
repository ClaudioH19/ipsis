# Contributing

Thanks for wanting to improve ipsis! This guide sums up how to work in the
repository. Before proposing a large change, open an issue to discuss it.
Issues and pull requests are welcome in English or Spanish.

## Non-negotiable principles

- **Nothing generative.** Every statement is a literal span of the
  document; the only additions are fixed, reviewed templates
  ([ADR 0001](docs/decisions/0001-non-generative-answers.md)).
- **No training.** No fine-tuning and no learned weights.
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
uv sync --locked --extra test --extra browser
uv run --locked --extra test --extra browser playwright install chromium
```

## Tests

```bash
uv run --locked --extra test --extra browser pytest -m "not slow and not browser"   # fast (seconds)
uv run --locked --extra test --extra browser pytest -m browser                      # widget and panel in Chromium
uv run --locked --extra test --extra browser pytest                                 # everything; the slow ones download or use real models
```

- A test lives in the folder of the module it tests (`tests/<layer>/`).
- The engine stages are tested with in-memory doubles, without models.
- If a change alters answers on purpose, regenerate the characterization
  and explain why in the commit.
- Run the tests on Python 3.11 or 3.12 before opening the pull request: the
  regression workflow in `.github/workflows/` uses the same uv lockfile.

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
  `docs/es/guia/`) and the `CHANGELOG.md`, in the same commit. See
  [Documentation follows the code](#documentation-follows-the-code).

## Documentation follows the code

Some values live in code and are copied by hand into the READMEs and guides.
When the two disagree, the documentation is corrected, not the code. The
sources of truth are:

- the models of each profile: `ipsis/recursos/perfiles/*.yaml`;
- the configuration version: `CONFIG_VERSION` in `ipsis/configuracion/esquemas.py`;
- the supported formats: `EXTENSIONES_SOPORTADAS` in `ipsis/ingesta/parsear.py`;
- the package version: `pyproject.toml`.

`tests/test_documentacion.py` compares them with the documentation and fails on
the first drift:

- `test_cada_comando_aparece_en_la_guia_de_uso` and
  `test_la_tabla_de_comandos_no_repite_filas`: every command is in both usage
  guides, once;
- `test_los_enlaces_relativos_de_la_documentacion_existen`: no broken link;
- `test_tabla_de_perfiles_nombra_los_modelos_vigentes`: the profile tables name
  the models the profile loads (and not the QA reader, which v2 does not load);
- `test_ejemplos_usan_la_config_version_vigente` and
  `test_la_guia_de_configuracion_describe_la_version_vigente`: examples, the
  stated version and the version table reach `CONFIG_VERSION`;
- `test_formatos_soportados_en_los_readme` and
  `test_la_fila_de_ipsis_load_lista_todos_los_formatos`: every supported format
  is named;
- `test_guias_en_y_es_tienen_las_mismas_secciones`: each guide in `docs/guide/`
  has its Spanish twin with the same `##` sections;
- `test_badge_de_version_coincide_con_pyproject`: the README badges show the
  released version.

A model or format that the tests cannot name yet is added to `ALIAS_DE_MODELOS`
or `NOMBRE_DE_FORMATO` in that file. Figures that describe the past (the removed
`heavy` profile, the v1 engine) stay, with a line that says they are history and
their date.

## Pull requests

1. One branch per change, with small commits and descriptive messages.
2. The fast and browser tests green.
3. Fill in the PR template: what changes, how it was tested and whether it
   affects answers, indexes or the configuration (`config_version`).

By contributing you agree to publish your contribution under the
[AGPL-3.0](LICENSE) license and the [code of conduct](CODE_OF_CONDUCT.md).
