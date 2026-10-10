## What changes

<!-- One or two sentences. Link the issue if there is one: "Closes #123". -->

## How it was tested

- [ ] `python -m pytest -m "not slow and not browser"`
- [ ] `python herramientas/evaluacion/general.py --download` (all profiles and formatting qualities; reports reviewed)
- [ ] `python -m pytest -m browser` (if it touches the widget or the panel)
- [ ] New or updated tests

## Impact

- [ ] Changes answers (I regenerated the characterization and explain it above)
- [ ] Requires reindexing
- [ ] Changes the configuration (`config_version` and its migration)
- [ ] Updated `docs/guide/` (and `docs/es/guia/`) and `CHANGELOG.md`

## Principles

- [ ] No model-generated text in the answers
- [ ] No language text in Python (it goes in the language packs or the message catalog)
