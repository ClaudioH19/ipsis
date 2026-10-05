# ADR 0002: declarative registry and versioned configuration

## Context

The engine needs to swap parser, chunker, encoder, fusion or extractor
without rewriting the pipeline. YAML files also need to evolve without a new
installation reading unknown options as valid.

## Decision

Small Python contracts in `ipsis.nucleo.contratos`, an explicit
`RegistroComponentes` and strict Pydantic schemas in
`ipsis.configuracion.esquemas`.

The selection is declared under `components` in `engine.yaml`. Factories are
resolved by name and can take options. Format changes go through idempotent
migrations; a future version is rejected.

The effective configuration can be exported to a snapshot with
`ipsis snapshot-config`.

## Consequences

- The core is not coupled to a concrete implementation.
- Name, type or version errors show up at startup.
- Heavy models and external connections are initialized lazily.
- The snapshot makes a run reproducible.
- Qdrant and stateful rerankers are injected by the service.

## Status

Implemented. The cascade stages, the Qdrant retriever, the reranker and the
reader are built by name from the registry; old configurations migrate by
themselves (`config_version` 5, which also moved files, keys and values to
English).
