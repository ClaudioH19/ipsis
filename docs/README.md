# Documentation

| Folder | Contents |
|---|---|
| [architecture.md](architecture.md) | Modules, flows and diagrams |
| [guide/](guide/) | How to install, use, configure, evaluate, customize and deploy the assistant |
| [methodology/](methodology/README.md) | One note per technique: what it does, how, limits and tests |
| [decisions/](decisions/) | Numbered architecture decision records (ADR) |
| [es/](es/README.md) | The guides in Spanish |

## Architecture

[architecture.md](architecture.md): the layers of `ipsis/`, what each module
does, the flow of a query and of ingestion, the service, deployment and where
each decision is audited, with diagrams.

## Repository map

| Folder | Why it exists |
|---|---|
| `ipsis/` | The package: code by layers, plus resources |
| `tests/` | Tests mirroring `ipsis/`, plus `datos/` (synthetic corpora and banks) and `integracion/` |
| `examples/` | Web integrations: HTML, Astro, Svelte, React, Angular, Python and WordPress |
| `herramientas/avatar/` | Reproducible build of the avatar engine and Folio (development only) |
| `docs/` | This documentation |
| `.github/` | Issue forms and the pull request template |

The code's internal identifiers (modules, functions, variables) are in
Spanish; everything a user sees (commands, files, keys, API, messages) is in
English, with Spanish available through `IPSIS_LANG=es`.
