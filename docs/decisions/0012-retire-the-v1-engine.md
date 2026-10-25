# ADR 0012: retire the v1 engine

- Status: accepted and implemented.
- Date: 2026-10-23.

## Context

v2 has been the default engine since 2026-10-12: it publishes ranked literal
sources instead of deciding whether a question "has an answer". The v1 engine
(answer cascade, abstention policy, calibration, proactive alternatives and
conversation memory) stayed selectable with `pipeline: v1`, but nothing the
product does by default uses it. Keeping it cost:

- about 9,600 lines of code and tests to read, plus their documentation, with their
  own thresholds, calibration file, admin-panel controls and CLI commands;
- a second set of configuration keys that did nothing in v2 (`posture.*`,
  `profile_overrides.cascade`, `default_thresholds`, the v1 components);
- tests that could only pass with the v1 baseline and failed on a clean
  checkout.

## Decision

Remove the v1 engine and everything that existed only for it:

- `Motor`, the stages, the cascade policy, the intent classifier and the
  answer extractor; the proactive alternatives; `ipsis calibrate`, the
  calibration module and `config/calibration.yaml`; the thresholds editor of
  the admin panel (`PUT /admin/thresholds`) and the calibration check of
  `ipsis doctor`.
- The cascade, stages, lexical and threshold sections of the installation
  profiles: a profile now holds the models, the latency budget, the retrieval
  mode and the per-language rerankers.
- The benchmark experiments (`--experiments`) and the `cascada` section of
  the benchmark report (it now records the retrieval mode; schema version 3).

Moved, because v2 used them from v1 modules: `RetrieverQdrant` to
`consulta/recuperador.py` and `cargar_plantillas` to `consulta/plantillas.py`.

Kept: `consulta/seguimiento.py` and its tests, as the base of the
conversation plan for v2 ([ADR 0006](0006-conversation-memory.md)).

### Compatibility of existing projects

A project keeps starting after updating, with no new `config_version`:

- `pipeline: v1` loads as v2 and prints a notice once per process. The index
  is not rebuilt: a project that had not chosen a preparation keeps `legacy`.
- The v1 components, the `rendering`, `abstention` and `acceptance_criteria`
  sections, the v1 `profile_overrides` and `posture` in `assistant.yaml` are
  ignored when loading.
- A `config/calibration.yaml` is left in place and ignored.

### Guards

Two checks keep v2 independent of v1:

- `tests/test_arquitectura.py` fails if any module outside the v1 list
  imports one of the retired modules, lazy imports included.
- `tests/consulta/test_aislamiento_v2.py` serves v2 in a clean interpreter and
  fails if any v1 module ends up loaded or a heavy dependency is imported
  with an in-memory retriever.

`tests/consulta/test_caracterizacion_v2.py` freezes the public answers of v2
over an in-memory index (no models, no network), so a cleanup like this one
cannot change them unnoticed.

## Consequences

- There is no tool to choose answer thresholds: v2 has none. The `ok`
  status and `exact_answer` stay declared in the API for older clients, but v2
  never produces them.
- Language-pack fields that only the v1 modules read (`pronombres_anaforicos`,
  `abreviaturas_informales`, `bordes_respuesta`, `respaldo_intencion`, the
  modifier lists) are still loaded and unused. Removing them is a separate
  change of the packs.
- The slow tests that needed v1 were converted to v2 and run with the real
  models. The false-`ok` baseline of the universal bank was retired: v2 never
  answers `ok`, so retrieval quality is watched through `tests/datos/banco_general`.
