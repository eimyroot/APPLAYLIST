# Bundle 37 — Pipeline Composition Authority Seam

## Status

Implementation candidate. Legacy composition remains the only default authority.

## Goal

Separate pipeline orchestration from the implementation that composes and exports a playlist, while preserving the current API response and observability ordering.

## Contracts

`PipelineCompositionCommand` carries:

- input path,
- requested limit,
- optional BPM range,
- optional mode.

`PipelineCompositionOutcome` carries:

- the authoritative run ID,
- ordered track objects,
- the existing export dictionary.

## Authorities

### LegacyCompositionAuthority

Encapsulates the exact existing flow:

```text
Composer.compose
      │
      ▼
legacy pipeline run ID
      │
      ▼
Exporter.export_m3u
```

The existing `composer`, `exporter` and `run_id_factory` constructor injection remains supported.

### CanonicalCompositionAuthority

Adapts `PipelineCompositionCommand` to the explicit Bundle 36 canonical export service.

It is not selected by configuration or API. It can only be supplied explicitly through dependency injection.

A canonical execution that does not produce a validated artifact fails closed.

## Pipeline ordering

```text
composition authority
        │
        ▼
successful export outcome
        │
        ▼
optional comparison observability
        │
        ▼
existing response payload
```

Authority failures prevent observability. Observability failures remain fail-open and cannot invalidate an already completed export.

## Compatibility

Without `composition_authority`, `OrchestratorPipeline` constructs `LegacyCompositionAuthority` and preserves:

- composer and exporter behavior,
- run-ID validation,
- top-level response keys,
- track ordering,
- comparison hook timing.

Supplying an authority together with legacy composer/exporter/run-ID dependencies is rejected as ambiguous configuration.

## Isolation

Bundle 37 does not:

- add an authority feature flag,
- change the default authority,
- modify API routes or schemas,
- change the database,
- automatically execute canonical composition.

## Rollback

Revert the Bundle 37 squash commit. No data rollback is required.
