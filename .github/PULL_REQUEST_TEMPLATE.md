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
- [ ] Changes a default, a profile or a supported format: the consistency tests in `tests/test_documentacion.py` pass
      (profile models, `config_version`, formats, EN/ES sections, version badge)
- [ ] English and Spanish documentation changed in the same commit

## Principles

- [ ] No model-generated text in the answers
- [ ] No language text in Python (it goes in the language packs or the message catalog)
